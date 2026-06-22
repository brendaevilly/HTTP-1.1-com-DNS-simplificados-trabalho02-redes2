#!/usr/bin/env bash
# Executa N rodadas HTTP (TCP e R-UDP) para UM cenário e grava métricas.
# Uso: ./scripts/run_benchmark.sh [dns_host] [runs] [scenario]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"
export PYTHONPATH="${ROOT}"

DNS_HOST="${1:-172.29.0.5}"
RUNS="${2:-10}"
SCENARIO="${3:-A}"

python3 scripts/generate_www_files.py --all

FILES=(
  "/index.html"
  "/files/arquivo_100kb.bin"
  "/files/arquivo_1mb.bin"
  "/files/arquivo_10mb.bin"
)

echo "=== Benchmark HTTP: ${RUNS} execuções por modo/arquivo/cenário ${SCENARIO} ==="

for MODE in tcp rudp; do
  for FILE in "${FILES[@]}"; do
    for ((i=1; i<=RUNS; i++)); do
      python3 src/web_client.py "${FILE}" \
        --dns-host "${DNS_HOST}" \
        --mode "${MODE}" \
        --scenario "${SCENARIO}" \
        --run-id "${i}" || true
      sleep 0.05
    done
  done
done

echo "Logs em logs/transfers.jsonl"
