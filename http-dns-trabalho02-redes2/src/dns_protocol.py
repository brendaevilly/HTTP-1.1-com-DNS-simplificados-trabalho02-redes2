"""
Protocolo DNS simplificado (consulta tipo A).

Formato de consulta (UDP):
  ID (2 bytes) + tamanho_nome (2 bytes) + nome (UTF-8)

Formato de resposta (UDP):
  ID (2 bytes) + tamanho_nome (2 bytes) + nome (UTF-8) + IP (4 bytes IPv4)
  IP 0.0.0.0 indica registro não encontrado (NXDOMAIN simplificado).
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass


QUERY_FMT = "!HH"
RESPONSE_FMT = "!HH4s"
HEADER_SIZE = struct.calcsize("!HH")


@dataclass
class DnsQuery:
    query_id: int
    name: str


@dataclass
class DnsResponse:
    query_id: int
    name: str
    ip: str
    found: bool


def pack_query(query_id: int, name: str) -> bytes:
    name_bytes = name.encode("utf-8")
    return struct.pack(QUERY_FMT, query_id & 0xFFFF, len(name_bytes)) + name_bytes


def unpack_query(data: bytes) -> DnsQuery:
    if len(data) < HEADER_SIZE:
        raise ValueError("Consulta DNS muito curta")
    query_id, name_len = struct.unpack(QUERY_FMT, data[:HEADER_SIZE])
    if len(data) < HEADER_SIZE + name_len:
        raise ValueError("Nome DNS incompleto")
    name = data[HEADER_SIZE : HEADER_SIZE + name_len].decode("utf-8")
    return DnsQuery(query_id=query_id, name=name)


def pack_response(query_id: int, name: str, ip: str) -> bytes:
    name_bytes = name.encode("utf-8")
    ip_bytes = socket.inet_aton(ip) if ip else socket.inet_aton("0.0.0.0")
    return (
        struct.pack(QUERY_FMT, query_id & 0xFFFF, len(name_bytes))
        + name_bytes
        + ip_bytes
    )


def unpack_response(data: bytes) -> DnsResponse:
    if len(data) < HEADER_SIZE + 4:
        raise ValueError("Resposta DNS muito curta")
    query_id, name_len = struct.unpack(QUERY_FMT, data[:HEADER_SIZE])
    offset = HEADER_SIZE
    if len(data) < offset + name_len + 4:
        raise ValueError("Resposta DNS incompleta")
    name = data[offset : offset + name_len].decode("utf-8")
    offset += name_len
    ip_bytes = data[offset : offset + 4]
    ip = socket.inet_ntoa(ip_bytes)
    found = ip != "0.0.0.0"
    return DnsResponse(query_id=query_id, name=name, ip=ip, found=found)
