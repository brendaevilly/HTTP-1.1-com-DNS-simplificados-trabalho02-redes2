#!/usr/bin/env python3
"""Exporta campos DNS e HTTP de arquivos pcap via tshark."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "captures"
OUTPUT = ROOT / "analysis" / "output"

FIELDS = [
    "frame.number",
    "frame.time_relative",
    "ip.src",
    "ip.dst",
    "udp.srcport",
    "udp.dstport",
    "tcp.srcport",
    "tcp.dstport",
    "dns.qry.name",
    "dns.a",
    "http.request.method",
    "http.request.uri",
    "http.response.code",
    "frame.len",
]


def export_pcap(pcap: Path, out_csv: Path) -> None:
    cmd = [
        "tshark",
        "-r",
        str(pcap),
        "-T",
        "fields",
        "-E",
        "header=y",
        "-E",
        "separator=,",
        "-E",
        "quote=d",
    ]
    for field in FIELDS:
        cmd.extend(["-e", field])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"tshark falhou para {pcap}")
    out_csv.write_text(result.stdout, encoding="utf-8")
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    summary = out_csv.with_suffix(".txt")
    summary.write_text(
        f"Pacotes exportados: {max(0, len(lines) - 1)}\nArquivo: {pcap.name}\n",
        encoding="utf-8",
    )
    print(f"Exportado: {out_csv} ({max(0, len(lines) - 1)} linhas)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pcap", type=Path, nargs="?", help="Arquivo .pcap")
    args = parser.parse_args()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    if args.pcap:
        pcaps = [args.pcap]
    else:
        pcaps = sorted(CAPTURES.glob("*.pcap"))
    if not pcaps:
        raise SystemExit("Nenhum arquivo .pcap em captures/")
    for pcap in pcaps:
        out = OUTPUT / f"{pcap.stem}.csv"
        export_pcap(pcap, out)


if __name__ == "__main__":
    main()
