#!/usr/bin/env python3
"""Gera arquivos estáticos de teste para benchmark HTTP."""

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WWW_FILES = ROOT / "www" / "files"

SIZES = {
    "arquivo_100kb.bin": 100 * 1024,
    "arquivo_1mb.bin": 1024 * 1024,
    "arquivo_10mb.bin": 10 * 1024 * 1024,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Gera todos os tamanhos padrão")
    parser.add_argument("--size", type=int, help="Tamanho customizado em bytes")
    parser.add_argument("--name", default="custom.bin")
    args = parser.parse_args()

    WWW_FILES.mkdir(parents=True, exist_ok=True)

    if args.all:
        targets = SIZES.items()
    elif args.size:
        targets = [(args.name, args.size)]
    else:
        targets = SIZES.items()

    for name, size in targets:
        path = WWW_FILES / name
        path.write_bytes(bytes([i % 256 for i in range(size)]))
        print(f"Gerado: {path} ({size} bytes)")


if __name__ == "__main__":
    main()
