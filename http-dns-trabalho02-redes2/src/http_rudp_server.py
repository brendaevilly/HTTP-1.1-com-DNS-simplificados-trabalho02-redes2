#!/usr/bin/env python3
"""Miniservidor HTTP/1.1 sobre camada R-UDP (Stop-and-Wait)."""

from __future__ import annotations

import path_setup  # noqa: F401

import argparse
import socket
import sys

from src.config import HTTP_RUDP_PORT, RUDP_MAX_RETRIES, custom_auth_hash
from src.http_utils import parse_request, serve_file
from src.rudp_protocol import MsgType, max_payload_size, pack_packet, unpack_packet


class HttpRudpServer:
    def __init__(self, host: str, port: int) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.client_addr: tuple[str, int] | None = None

    def send_ack(self, ack: int) -> None:
        if self.client_addr is None:
            return
        pkt = pack_packet(MsgType.ACK, seq=0, ack=ack)
        self.sock.sendto(pkt, self.client_addr)

    def recv_packet(self) -> tuple[MsgType, int, int, bytes]:
        while True:
            data, addr = self.sock.recvfrom(65535)
            try:
                mtype, seq, ack, payload, _ = unpack_packet(data)
                self.client_addr = addr
                return mtype, seq, ack, payload
            except ValueError as exc:
                print(f"[HTTP-RUDP] Pacote inválido de {addr}: {exc}", file=sys.stderr)

    def recv_bytes(self) -> bytes:
        """Recebe requisição HTTP completa via Stop-and-Wait."""
        buffer = bytearray()
        expected_seq = 0

        while True:
            mtype, seq, _, payload = self.recv_packet()
            if mtype == MsgType.SYN:
                buffer.extend(payload)
                expected_seq = 1
                self.send_ack(expected_seq)
                continue
            if mtype == MsgType.DATA:
                if seq == expected_seq:
                    buffer.extend(payload)
                    expected_seq = (expected_seq + 1) % (2**32)
                self.send_ack(expected_seq)
                continue
            if mtype == MsgType.FIN:
                self.send_ack(expected_seq)
                break
        return bytes(buffer)

    def send_wait_ack(self, pkt: bytes, expected_ack: int) -> None:
        for _ in range(RUDP_MAX_RETRIES):
            self.sock.settimeout(2.0)
            self.sock.sendto(pkt, self.client_addr)
            try:
                data, _ = self.sock.recvfrom(65535)
                mtype, _, ack, _, _ = unpack_packet(data)
                if mtype == MsgType.ACK and ack == expected_ack:
                    self.sock.settimeout(None)
                    return
            except socket.timeout:
                continue
            except ValueError:
                continue
        self.sock.settimeout(None)
        raise TimeoutError(f"Sem ACK para ack={expected_ack}")

    def send_bytes(self, data: bytes) -> None:
        """Envia resposta HTTP completa via Stop-and-Wait."""
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
            self.send_wait_ack(pkt, next_ack)
            offset += len(piece)
            seq = next_ack

        fin_pkt = pack_packet(MsgType.FIN, seq=seq, ack=0, payload=b"")
        self.send_wait_ack(fin_pkt, seq)

    def handle_session(self) -> None:
        raw_request = self.recv_bytes()
        request = parse_request(raw_request)
        auth = request.headers.get("X-Custom-Auth", "")
        if auth != custom_auth_hash():
            body = b"Unauthorized"
            response = (
                b"HTTP/1.1 401 Unauthorized\r\n"
                + f"X-Custom-Auth: {custom_auth_hash()}\r\n".encode()
                + b"Content-Length: 12\r\n\r\n"
                + body
            )
            self.send_bytes(response)
            return

        http_response = serve_file(request.path)
        self.send_bytes(http_response.to_bytes())
        print(
            f"[HTTP-RUDP] GET {request.path} -> "
            f"{http_response.status_code} ({len(http_response.body)} bytes)"
        )

    def run(self) -> None:
        while True:
            try:
                self.handle_session()
            except Exception as exc:
                print(f"[HTTP-RUDP] Erro na sessão: {exc}", file=sys.stderr)

    def close(self) -> None:
        self.sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor HTTP/1.1 sobre R-UDP")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=HTTP_RUDP_PORT)
    args = parser.parse_args()

    server = HttpRudpServer(args.host, args.port)
    print(f"[HTTP-RUDP] Escutando em {args.host}:{args.port}")
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n[HTTP-RUDP] Encerrando.")
    finally:
        server.close()


if __name__ == "__main__":
    main()
