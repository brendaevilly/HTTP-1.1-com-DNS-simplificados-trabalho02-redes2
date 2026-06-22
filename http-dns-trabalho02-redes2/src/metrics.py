"""Registro de métricas de transferência web (DNS + HTTP)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.config import LOGS_DIR


@dataclass
class WebTransferMetrics:
    mode: str  # tcp | rudp
    scenario: str  # A | B | C | local
    run_id: int
    file_name: str
    bytes_received: int
    dns_duration_s: float
    http_duration_s: float
    total_duration_s: float
    throughput_bps: float = 0.0
    retransmissions: int = 0
    dns_retries: int = 0
    dns_errors: int = 0
    http_status: int = 0
    host: str = ""
    domain: str = ""
    timestamp: float = 0.0
    success: bool = True
    error_message: str = ""

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.total_duration_s > 0 and self.bytes_received > 0:
            self.throughput_bps = self.bytes_received * 8 / self.total_duration_s
        else:
            self.throughput_bps = 0.0

    def throughput_mbps(self) -> float:
        return self.throughput_bps / 1_000_000


class MetricsLogger:
    def __init__(self, log_file: Path | None = None) -> None:
        self.log_file = log_file or (LOGS_DIR / "transfers.jsonl")

    def log(self, metrics: WebTransferMetrics) -> None:
        record = asdict(metrics)
        record["throughput_mbps"] = metrics.throughput_mbps()
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def load_all(path: Path | None = None) -> list[dict[str, Any]]:
        log_path = path or (LOGS_DIR / "transfers.jsonl")
        if not log_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows
