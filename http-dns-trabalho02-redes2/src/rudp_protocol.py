"""
Protocolo Reliable UDP (Stop-and-Wait) com cabeçalho binário.

Cabeçalho (49 bytes fixos + payload):
  magic(4) + version(1) + msg_type(1) + seq(4) + ack(4) +
  payload_len(2) + auth(32) + checksum(4) + payload(var)
"""

from __future__ import annotations

import struct
import zlib
from enum import IntEnum

from src.config import CHUNK_SIZE, custom_auth_bytes

MAGIC = b"RUDP"
VERSION = 1
HEADER_FMT = "!4sBBIIH32s"
HEADER_SIZE = struct.calcsize(HEADER_FMT) + 4


class MsgType(IntEnum):
    SYN = 1
    DATA = 2
    ACK = 3
    FIN = 4


def payload_checksum(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def pack_packet(
    msg_type: MsgType,
    seq: int,
    ack: int,
    payload: bytes = b"",
) -> bytes:
    auth = custom_auth_bytes()
    plen = len(payload)
    chk = payload_checksum(payload)
    header = struct.pack(
        HEADER_FMT,
        MAGIC,
        VERSION,
        int(msg_type),
        seq & 0xFFFFFFFF,
        ack & 0xFFFFFFFF,
        plen,
        auth,
    )
    return header + struct.pack("!I", chk) + payload


def unpack_packet(data: bytes) -> tuple[MsgType, int, int, bytes, int]:
    if len(data) < HEADER_SIZE:
        raise ValueError("Pacote muito curto")
    header = data[: HEADER_SIZE - 4]
    chk_recv, = struct.unpack("!I", data[HEADER_SIZE - 4 : HEADER_SIZE])
    payload = data[HEADER_SIZE:]
    magic, ver, mtype, seq, ack, plen, auth = struct.unpack(HEADER_FMT, header)
    if magic != MAGIC:
        raise ValueError("Magic inválido")
    if ver != VERSION:
        raise ValueError("Versão não suportada")
    if auth != custom_auth_bytes():
        raise ValueError("X-Custom-Auth inválido")
    if len(payload) != plen:
        raise ValueError("Tamanho de payload inconsistente")
    chk_calc = payload_checksum(payload)
    if chk_calc != chk_recv:
        raise ValueError("Checksum inválido")
    return MsgType(mtype), seq, ack, payload, chk_recv


def max_payload_size() -> int:
    return CHUNK_SIZE
