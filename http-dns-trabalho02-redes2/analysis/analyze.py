#!/usr/bin/env python3
"""
Análise estatística: taxa de transferência, DNS, erros e overhead HTTP.
Gera gráficos comparando TCP vs R-UDP por cenário e tamanho de arquivo.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from src.metrics import MetricsLogger

OUTPUT = ROOT / "analysis" / "output"


def load_dataframe() -> pd.DataFrame:
    rows = MetricsLogger.load_all()
    if not rows:
        raise SystemExit("Nenhum dado em logs/transfers.jsonl. Execute os testes primeiro.")
    df = pd.DataFrame(rows)
    if "throughput_mbps" not in df.columns:
        df["throughput_mbps"] = df["throughput_bps"] / 1_000_000
    if "success" not in df.columns:
        df["success"] = True
    return df


def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    agg = (
        df.groupby(["scenario", "mode", "file_name"])
        .agg(
            vazao_min_mbps=("throughput_mbps", "min"),
            vazao_media_mbps=("throughput_mbps", "mean"),
            vazao_max_mbps=("throughput_mbps", "max"),
            desvio_padrao_mbps=("throughput_mbps", "std"),
            dns_media_s=("dns_duration_s", "mean"),
            http_media_s=("http_duration_s", "mean"),
            total_media_s=("total_duration_s", "mean"),
            taxa_erro=("success", lambda s: 1 - s.mean()),
            retransmissoes_media=("retransmissions", "mean"),
            amostras=("throughput_mbps", "count"),
        )
        .reset_index()
    )
    agg.columns = [
        "cenario",
        "modo",
        "arquivo",
        "vazao_min_mbps",
        "vazao_media_mbps",
        "vazao_max_mbps",
        "desvio_padrao_mbps",
        "dns_media_s",
        "http_media_s",
        "total_media_s",
        "taxa_erro",
        "retransmissoes_media",
        "amostras",
    ]
    return agg


def plot_throughput_by_file(df: pd.DataFrame, out_dir: Path) -> None:
    summary = summary_table(df)
    files = sorted(df["file_name"].unique())
    scenarios = sorted(df["scenario"].unique())

    for file_name in files:
        subset = summary[summary["arquivo"] == file_name]
        if subset.empty:
            continue
        fig, ax = plt.subplots(figsize=(10, 6))
        x = range(len(scenarios))
        width = 0.35
        for i, mode in enumerate(["tcp", "rudp"]):
            means, stds = [], []
            for sc in scenarios:
                row = subset[(subset["cenario"] == sc) & (subset["modo"] == mode)]
                means.append(row["vazao_media_mbps"].iloc[0] if len(row) else 0)
                stds.append(row["desvio_padrao_mbps"].iloc[0] if len(row) else 0)
            offset = [xi + (i - 0.5) * width for xi in x]
            ax.bar(offset, means, width, yerr=stds, capsize=4, label=mode.upper())
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"Cenário {s}" for s in scenarios])
        ax.set_ylabel("Throughput médio (Mbps)")
        ax.set_title(f"TCP vs R-UDP — {file_name}")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        safe_name = file_name.replace(".", "_")
        fig.savefig(out_dir / f"throughput_{safe_name}.png", dpi=150)
        plt.close(fig)


def plot_dns_vs_http(df: pd.DataFrame, out_dir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, col, title in zip(
        axes,
        ["dns_duration_s", "http_duration_s"],
        ["Tempo médio DNS (s)", "Tempo médio HTTP (s)"],
    ):
        pivot = df.groupby(["scenario", "mode"])[col].mean().unstack()
        pivot.plot(kind="bar", ax=ax, rot=0)
        ax.set_title(title)
        ax.set_xlabel("Cenário")
        ax.legend(title="Modo")
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "dns_vs_http_tempo.png", dpi=150)
    plt.close(fig)


def plot_error_rate(df: pd.DataFrame, out_dir: Path) -> None:
    summary = summary_table(df)
    fig, ax = plt.subplots(figsize=(10, 6))
    labels = summary["cenario"] + " / " + summary["modo"] + " / " + summary["arquivo"]
    ax.bar(range(len(summary)), summary["taxa_erro"] * 100, color="tomato")
    ax.set_xticks(range(len(summary)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Taxa de erro (%)")
    ax.set_title("Taxa de erro por cenário, modo e arquivo")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "taxa_erro.png", dpi=150)
    plt.close(fig)


def plot_total_duration_box(df: pd.DataFrame, out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    df_plot = df.copy()
    df_plot["label"] = (
        df_plot["mode"].str.upper()
        + " / "
        + df_plot["scenario"]
        + " / "
        + df_plot["file_name"]
    )
    df_plot.boxplot(column="total_duration_s", by="label", ax=ax, rot=45)
    ax.set_title("Tempo total de carregamento (DNS + HTTP)")
    ax.set_ylabel("Duração (s)")
    fig.suptitle("")
    fig.tight_layout()
    fig.savefig(out_dir / "duracao_total_boxplot.png", dpi=150)
    plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    df = load_dataframe()
    summary = summary_table(df)
    summary.to_csv(OUTPUT / "summary_statistics.csv", index=False)
    print(summary.to_string(index=False))

    plot_throughput_by_file(df, OUTPUT)
    plot_dns_vs_http(df, OUTPUT)
    plot_error_rate(df, OUTPUT)
    plot_total_duration_box(df, OUTPUT)
    print(f"\nGráficos e CSV em {OUTPUT}")


if __name__ == "__main__":
    main()
