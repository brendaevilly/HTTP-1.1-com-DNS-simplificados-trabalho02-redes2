#!/usr/bin/env python3
"""
Cliente Web integrado: resolução DNS obrigatória + HTTP GET via TCP ou R-UDP.
"""

from __future__ import annotations

import path_setup  # noqa: F401

import argparse
import socket
import sys
import time
from pathlib import Path

from src.config import (
    DNS_PORT,
    DNS_SERVER,
    HTTP_RUDP_PORT,
    HTTP_TCP_PORT,
    RECEIVED_DIR,
    RUDP_MAX_RETRIES,
    RUDP_TIMEOUT,
    WEB_DOMAIN,
)
from src.dns_client import DnsClient
from src.http_utils import build_get_request, parse_response
from src.metrics import MetricsLogger, WebTransferMetrics
from src.rudp_protocol import MsgType, max_payload_size, pack_packet, unpack_packet


class HttpTcpFetcher:
    def fetch(self, host: str, port: int, domain: str, path: str) -> tuple[bytes, int]:
        request = build_get_request(domain, path)
        sock = socket.create_connection((host, port), timeout=30)
        try:
            sock.sendall(request)
            response = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                response += chunk
        finally:
            sock.close()
        parsed = parse_response(response)
        return response, parsed.status_code


class HttpRudpFetcher:
    def __init__(self, timeout: float = RUDP_TIMEOUT) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._base_timeout = timeout
        self.retransmissions = 0

    def set_scenario_timeout(self, scenario: str) -> None:
        timeouts = {"A": 0.2, "B": 0.5, "C": 1.0, "local": self._base_timeout}
        self.sock.settimeout(timeouts.get(scenario, self._base_timeout))

    def send_wait_ack(self, host: str, port: int, pkt: bytes, expected_ack: int) -> None:
        for _ in range(RUDP_MAX_RETRIES):
            self.sock.sendto(pkt, (host, port))
            try:
                data, _ = self.sock.recvfrom(65535)
                mtype, _, ack, _, _ = unpack_packet(data)
                if mtype == MsgType.ACK and ack == expected_ack:
                    return
                self.retransmissions += 1
            except socket.timeout:
                self.retransmissions += 1
            except ValueError:
                self.retransmissions += 1
        raise TimeoutError(f"Sem ACK esperado={expected_ack}")

    def send_bytes(self, host: str, port: int, data: bytes) -> None:
        chunk = max_payload_size()
        seq = 0
        offset = 0
        while offset < len(data):
            piece = data[offset : offset + chunk]
            if offset == 0:
                pkt = pack_packet(MsgType.SYN, seq=seq, ack=0, payload=piece)
            else:
                pkt = pack_packet(MsgType.DATA, seq=seq, ack=0, payload=piece)
            next_ack = (seq + 1) % (2**32)
            self.send_wait_ack(host, port, pkt, next_ack)
            offset += len(piece)
            seq = next_ack

        fin_pkt = pack_packet(MsgType.FIN, seq=seq, ack=0, payload=b"")
        self.send_wait_ack(host, port, fin_pkt, seq)

    def recv_bytes(self, host: str, port: int) -> bytes:
        buffer = bytearray()
        expected_seq = 0
        while True:
            data, _ = self.sock.recvfrom(65535)
            mtype, seq, _, payload, _ = unpack_packet(data)
            if mtype == MsgType.SYN:
                buffer.extend(payload)
                expected_seq = 1
                ack_pkt = pack_packet(MsgType.ACK, seq=0, ack=expected_seq)
                self.sock.sendto(ack_pkt, (host, port))
                continue
            if mtype == MsgType.DATA:
                if seq == expected_seq:
                    buffer.extend(payload)
                    expected_seq = (expected_seq + 1) % (2**32)
                ack_pkt = pack_packet(MsgType.ACK, seq=0, ack=expected_seq)
                self.sock.sendto(ack_pkt, (host, port))
                continue
            if mtype == MsgType.FIN:
                ack_pkt = pack_packet(MsgType.ACK, seq=0, ack=expected_seq)
                self.sock.sendto(ack_pkt, (host, port))
                break
        return bytes(buffer)

    def fetch(
        self,
        host: str,
        port: int,
        domain: str,
        path: str,
        scenario: str,
    ) -> tuple[bytes, int]:
        self.set_scenario_timeout(scenario)
        request = build_get_request(domain, path)
        self.send_bytes(host, port, request)
        response = self.recv_bytes(host, port)
        parsed = parse_response(response)
        return response, parsed.status_code

    def close(self) -> None:
        self.sock.close()


def download_page(
    domain: str,
    path: str,
    mode: str,
    dns_host: str,
    scenario: str,
    run_id: int,
    save: bool = True,
) -> WebTransferMetrics:
    total_start = time.perf_counter()
    dns_client = DnsClient(dns_host, DNS_PORT)
    dns_retries = 0
    dns_errors = 0
    retransmissions = 0

    try:
        dns_result = dns_client.resolve(domain, scenario=scenario)
        dns_duration = dns_result.duration_s
        dns_retries = dns_result.retries
        dns_errors = dns_result.errors
    except (TimeoutError, LookupError) as exc:
        duration = time.perf_counter() - total_start
        return WebTransferMetrics(
            mode=mode,
            scenario=scenario,
            run_id=run_id,
            file_name=Path(path).name,
            bytes_received=0,
            dns_duration_s=duration,
            http_duration_s=0.0,
            total_duration_s=duration,
            dns_retries=dns_retries,
            dns_errors=dns_errors + 1,
            host=dns_host,
            domain=domain,
            success=False,
            error_message=str(exc),
        )
    finally:
        dns_client.close()

    http_start = time.perf_counter()
    try:
        if mode == "tcp":
            fetcher = HttpTcpFetcher()
            response, status = fetcher.fetch(
                dns_result.ip, HTTP_TCP_PORT, domain, path
            )
        else:
            rudp_fetcher = HttpRudpFetcher()
            try:
                response, status = rudp_fetcher.fetch(
                    dns_result.ip, HTTP_RUDP_PORT, domain, path, scenario
                )
                retransmissions = rudp_fetcher.retransmissions
            finally:
                rudp_fetcher.close()

        http_duration = time.perf_counter() - http_start
        parsed = parse_response(response)
        body = parsed.body

        if save and status == 200:
            dest = RECEIVED_DIR / f"{mode}_{Path(path).name}"
            dest.write_bytes(body)

        total_duration = time.perf_counter() - total_start
        return WebTransferMetrics(
            mode=mode,
            scenario=scenario,
            run_id=run_id,
            file_name=Path(path).name,
            bytes_received=len(body),
            dns_duration_s=dns_duration,
            http_duration_s=http_duration,
            total_duration_s=total_duration,
            retransmissions=retransmissions,
            dns_retries=dns_retries,
            dns_errors=dns_errors,
            http_status=status,
            host=dns_result.ip,
            domain=domain,
            success=status == 200,
        )
    except Exception as exc:
        http_duration = time.perf_counter() - http_start
        total_duration = time.perf_counter() - total_start
        return WebTransferMetrics(
            mode=mode,
            scenario=scenario,
            run_id=run_id,
            file_name=Path(path).name,
            bytes_received=0,
            dns_duration_s=dns_duration,
            http_duration_s=http_duration,
            total_duration_s=total_duration,
            retransmissions=retransmissions,
            dns_retries=dns_retries,
            dns_errors=dns_errors,
            host=dns_result.ip,
            domain=domain,
            success=False,
            error_message=str(exc),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente Web (DNS + HTTP)")
    parser.add_argument("path", help="Caminho HTTP, ex: /index.html ou /files/arquivo_1mb.bin")
    parser.add_argument("--domain", default=WEB_DOMAIN)
    parser.add_argument("--dns-host", default=DNS_SERVER)
    parser.add_argument("--mode", choices=["tcp", "rudp"], default="tcp")
    parser.add_argument("--scenario", default="local", choices=["A", "B", "C", "local"])
    parser.add_argument("--run-id", type=int, default=1)
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    metrics = download_page(
        domain=args.domain,
        path=args.path,
        mode=args.mode,
        dns_host=args.dns_host,
        scenario=args.scenario,
        run_id=args.run_id,
        save=not args.no_save,
    )

    if metrics.success:
        print(
            f"[{args.mode.upper()}] {metrics.file_name}: "
            f"{metrics.bytes_received} bytes | "
            f"DNS={metrics.dns_duration_s:.4f}s | "
            f"HTTP={metrics.http_duration_s:.4f}s | "
            f"Total={metrics.total_duration_s:.4f}s | "
            f"{metrics.throughput_mbps():.2f} Mbps"
        )
    else:
        print(f"[{args.mode.upper()}] ERRO: {metrics.error_message}", file=sys.stderr)

    if not args.no_log:
        MetricsLogger().log(metrics)

    if not metrics.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
