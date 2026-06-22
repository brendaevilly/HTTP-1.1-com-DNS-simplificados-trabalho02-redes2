#!/usr/bin/env python3
"""Servidor DNS minimalista — consultas tipo A via arquivo de zona local."""

from __future__ import annotations

import path_setup  # noqa: F401

import argparse
import socket
import sys
from pathlib import Path

from src.config import DNS_PORT, HOSTS_FILE
from src.dns_protocol import pack_response, unpack_query


class DnsServer:
    def __init__(self, host: str, port: int, zone_file: Path) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.zone = self._load_zone(zone_file)

    @staticmethod
    def _load_zone(zone_file: Path) -> dict[str, str]:
        zone: dict[str, str] = {}
        if not zone_file.exists():
            return zone
        for line in zone_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                zone[parts[0].lower()] = parts[1]
        return zone

    def reload_zone(self, zone_file: Path) -> None:
        self.zone = self._load_zone(zone_file)

    def handle_query(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            query = unpack_query(data)
        except ValueError as exc:
            print(f"[DNS] Consulta inválida de {addr}: {exc}", file=sys.stderr)
            return

        ip = self.zone.get(query.name.lower(), "0.0.0.0")
        response = pack_response(query.query_id, query.name, ip)
        self.sock.sendto(response, addr)
        status = ip if ip != "0.0.0.0" else "NXDOMAIN"
        print(f"[DNS] {query.name} -> {status} (id={query.query_id}, de {addr})")

    def run(self) -> None:
        print(f"[DNS] Zona com {len(self.zone)} registros. Escutando em {self.sock.getsockname()}")
        while True:
            data, addr = self.sock.recvfrom(4096)
            self.handle_query(data, addr)

    def close(self) -> None:
        self.sock.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor DNS simplificado")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DNS_PORT)
    parser.add_argument("--zone", type=Path, default=HOSTS_FILE)
    args = parser.parse_args()

    server = DnsServer(args.host, args.port, args.zone)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n[DNS] Encerrando.")
    finally:
        server.close()


if __name__ == "__main__":
    main()
