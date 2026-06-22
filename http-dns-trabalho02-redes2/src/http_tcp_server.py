#!/usr/bin/env python3
"""Miniservidor HTTP/1.1 sobre TCP nativo."""

from __future__ import annotations

import path_setup  # noqa: F401

import argparse
import socket
import sys

from src.config import HTTP_TCP_PORT, custom_auth_hash
from src.http_utils import parse_request, serve_file


def recv_http_request(conn: socket.socket) -> bytes:
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    try:
        raw = recv_http_request(conn)
        if not raw:
            return
        request = parse_request(raw)
        auth = request.headers.get("X-Custom-Auth", "")
        if auth != custom_auth_hash():
            response = (
                "HTTP/1.1 401 Unauthorized\r\n"
                f"X-Custom-Auth: {custom_auth_hash()}\r\n"
                "Content-Length: 0\r\n"
                "\r\n"
            )
            conn.sendall(response.encode("utf-8"))
            print(f"[HTTP-TCP] Auth inválido de {addr}", file=sys.stderr)
            return

        if request.method != "GET":
            response = (
                "HTTP/1.1 405 Method Not Allowed\r\n"
                f"X-Custom-Auth: {custom_auth_hash()}\r\n"
                "Content-Length: 0\r\n"
                "\r\n"
            )
            conn.sendall(response.encode("utf-8"))
            return

        http_response = serve_file(request.path)
        conn.sendall(http_response.to_bytes())
        print(
            f"[HTTP-TCP] {addr} GET {request.path} -> "
            f"{http_response.status_code} ({len(http_response.body)} bytes)"
        )
    except Exception as exc:
        print(f"[HTTP-TCP] Erro com {addr}: {exc}", file=sys.stderr)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor HTTP/1.1 sobre TCP")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=HTTP_TCP_PORT)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    sock.listen(16)
    print(f"[HTTP-TCP] Escutando em {args.host}:{args.port}")
    try:
        while True:
            conn, addr = sock.accept()
            handle_client(conn, addr)
    except KeyboardInterrupt:
        print("\n[HTTP-TCP] Encerrando.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
