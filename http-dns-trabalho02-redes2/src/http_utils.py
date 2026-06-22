"""Utilitários para construção e análise de mensagens HTTP/1.1."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path

from src.config import WWW_DIR, custom_auth_hash


@dataclass
class HttpRequest:
    method: str
    path: str
    host: str
    headers: dict[str, str]


@dataclass
class HttpResponse:
    status_code: int
    reason: str
    headers: dict[str, str]
    body: bytes

    @property
    def header_block(self) -> bytes:
        lines = [f"HTTP/1.1 {self.status_code} {self.reason}"]
        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")
        lines.append("")
        lines.append("")
        return "\r\n".join(lines).encode("utf-8")

    def to_bytes(self) -> bytes:
        return self.header_block + self.body


def build_get_request(domain: str, path: str) -> bytes:
    if not path.startswith("/"):
        path = "/" + path
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {domain}\r\n"
        f"X-Custom-Auth: {custom_auth_hash()}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return request.encode("utf-8")


def parse_request(data: bytes) -> HttpRequest:
    header_end = data.find(b"\r\n\r\n")
    if header_end == -1:
        raise ValueError("Requisição HTTP incompleta")
    header_text = data[:header_end].decode("utf-8", errors="replace")
    lines = header_text.split("\r\n")
    if not lines:
        raise ValueError("Requisição HTTP vazia")
    method, path, _ = lines[0].split(" ", 2)
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
    host = headers.get("Host", "localhost")
    return HttpRequest(method=method, path=path, host=host, headers=headers)


def guess_content_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def serve_file(path: str) -> HttpResponse:
    safe_path = path.lstrip("/")
    file_path = (WWW_DIR / safe_path).resolve()
    if not str(file_path).startswith(str(WWW_DIR.resolve())):
        return HttpResponse(
            status_code=403,
            reason="Forbidden",
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Content-Length": "0",
                "X-Custom-Auth": custom_auth_hash(),
            },
            body=b"",
        )
    if not file_path.is_file():
        body = b"Arquivo nao encontrado"
        return HttpResponse(
            status_code=404,
            reason="Not Found",
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Content-Length": str(len(body)),
                "X-Custom-Auth": custom_auth_hash(),
            },
            body=body,
        )
    body = file_path.read_bytes()
    return HttpResponse(
        status_code=200,
        reason="OK",
        headers={
            "Content-Type": guess_content_type(file_path),
            "Content-Length": str(len(body)),
            "X-Custom-Auth": custom_auth_hash(),
        },
        body=body,
    )


def parse_response(data: bytes) -> HttpResponse:
    header_end = data.find(b"\r\n\r\n")
    if header_end == -1:
        raise ValueError("Resposta HTTP incompleta")
    header_text = data[:header_end].decode("utf-8", errors="replace")
    body = data[header_end + 4 :]
    lines = header_text.split("\r\n")
    status_line = lines[0]
    _, status_s, reason = status_line.split(" ", 2)
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
    return HttpResponse(
        status_code=int(status_s),
        reason=reason,
        headers=headers,
        body=body,
    )
