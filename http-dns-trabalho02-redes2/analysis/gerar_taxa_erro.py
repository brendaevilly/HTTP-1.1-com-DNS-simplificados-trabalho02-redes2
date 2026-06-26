#!/usr/bin/env python3
"""
Gera gráfico de taxa de erro a partir do log do terminal do benchmark.

Conta sucessos ([TCP]/[RUDP] com bytes) e falhas ([TCP]/[RUDP] ERRO:)
seguindo a ordem de execução de scripts/run_benchmark.sh.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

OUTPUT = ROOT / "analysis" / "output"

FILES = [
    "index.html",
    "arquivo_100kb.bin",
    "arquivo_1mb.bin",
    "arquivo_10mb.bin",
]
MODES = ["tcp", "rudp"]
SCENARIOS = ["A", "B", "C"]
EXPECTED_RUNS = 10

SUCCESS_RE = re.compile(
    r"^\[(TCP|RUDP)\] (?P<file>\S+): (?P<bytes>\d+) bytes",
    re.IGNORECASE,
)
ERROR_RE = re.compile(r"^\[(TCP|RUDP)\] ERRO:", re.IGNORECASE)
SCENARIO_RE = re.compile(r"cen[aá]rio\s+([ABC])\b", re.IGNORECASE)
BENCHMARK_RE = re.compile(r"Benchmark HTTP:.*cen[aá]rio\s+([ABC])\b", re.IGNORECASE)


def iter_benchmark_jobs(scenario: str):
    """Ordem idêntica a scripts/run_benchmark.sh."""
    for mode in MODES:
        for file_name in FILES:
            for run_id in range(1, EXPECTED_RUNS + 1):
                yield scenario, mode, file_name, run_id


def parse_terminal_log(text: str) -> dict[tuple[str, str, str], dict[str, int]]:
    """Retorna contagem de sucessos/falhas por (cenário, modo, arquivo)."""
    counts: dict[tuple[str, str, str], dict[str, int]] = {}
    current_scenario: str | None = None
    job_iter = None

    def ensure_key(key: tuple[str, str, str]) -> None:
        if key not in counts:
            counts[key] = {"sucessos": 0, "falhas": 0}

    for raw_line in text.splitlines():
        line = raw_line.strip()

        m = BENCHMARK_RE.search(line)
        if m:
            current_scenario = m.group(1).upper()
            job_iter = iter(iter_benchmark_jobs(current_scenario))
            continue

        m = SCENARIO_RE.search(line)
        if m and "Aplicando" in line:
            current_scenario = m.group(1).upper()
            continue

        if job_iter is None:
            continue

        if SUCCESS_RE.match(line):
            try:
                _, mode, file_name, _ = next(job_iter)
            except StopIteration:
                continue
            key = (current_scenario or "?", mode, file_name)
            ensure_key(key)
            counts[key]["sucessos"] += 1
            continue

        if ERROR_RE.match(line):
            try:
                _, mode, file_name, _ = next(job_iter)
            except StopIteration:
                continue
            key = (current_scenario or "?", mode, file_name)
            ensure_key(key)
            counts[key]["falhas"] += 1

    return counts


def build_dataframe(counts: dict[tuple[str, str, str], dict[str, int]]) -> pd.DataFrame:
    rows: list[dict] = []
    for scenario in SCENARIOS:
        for mode in MODES:
            for file_name in FILES:
                key = (scenario, mode, file_name)
                c = counts.get(key, {"sucessos": 0, "falhas": 0})
                sucessos = c["sucessos"]
                falhas = c["falhas"]
                total = sucessos + falhas
                if total == 0:
                    # Grupo não executado ou log incompleto — assume 10 tentativas falhas
                    sucessos = 0
                    falhas = EXPECTED_RUNS
                    total = EXPECTED_RUNS
                taxa_erro = falhas / total if total else 0.0
                rows.append(
                    {
                        "cenario": scenario,
                        "modo": mode,
                        "arquivo": file_name,
                        "sucessos": sucessos,
                        "falhas": falhas,
                        "total": total,
                        "taxa_erro": taxa_erro,
                        "taxa_erro_pct": taxa_erro * 100,
                    }
                )
    return pd.DataFrame(rows)


def plot_error_rate(df: pd.DataFrame, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 6))
    labels = df["cenario"] + " / " + df["modo"] + " / " + df["arquivo"]
    colors = ["tomato" if pct > 0 else "seagreen" for pct in df["taxa_erro_pct"]]
    bars = ax.bar(range(len(df)), df["taxa_erro_pct"], color=colors)
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Taxa de erro (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Taxa de erro por cenário, modo e arquivo (log do terminal)")
    ax.grid(axis="y", alpha=0.3)

    for bar, row in zip(bars, df.itertuples()):
        if row.falhas > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{row.falhas}/{row.total}",
                ha="center",
                va="bottom",
                fontsize=7,
            )

    fig.tight_layout()
    out_path = out_dir / "taxa_erro.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera gráfico de taxa de erro do log do terminal")
    parser.add_argument(
        "log",
        type=Path,
        nargs="?",
        help="Arquivo de log do terminal (stdout do run_docker_tests.sh)",
    )
    args = parser.parse_args()

    if args.log and args.log.exists():
        text = args.log.read_text(encoding="utf-8", errors="replace")
    else:
        text = sys.stdin.read()

    if not text.strip():
        raise SystemExit("Nenhum conteúdo de log fornecido.")

    counts = parse_terminal_log(text)
    df = build_dataframe(counts)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT / "taxa_erro_terminal.csv"
    df.to_csv(csv_path, index=False)
    png_path = plot_error_rate(df, OUTPUT)

    print(df.to_string(index=False))
    print(f"\nCSV: {csv_path}")
    print(f"Gráfico: {png_path}")


if __name__ == "__main__":
    main()
