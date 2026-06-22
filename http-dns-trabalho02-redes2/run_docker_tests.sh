#!/usr/bin/env bash
# Sobe containers, aplica tc no cliente por cenário e roda benchmark HTTP
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT}"

docker compose build
docker compose up -d dns
sleep 2
docker compose up -d server
sleep 3
docker compose up -d client
sleep 2

DNS_HOST="172.29.0.5"
CLIENT_CONTAINER="redes2-t02-client"

docker exec "${CLIENT_CONTAINER}" bash -c "truncate -s 0 /app/logs/transfers.jsonl 2>/dev/null || true"

for SCENARIO in A B C; do
  echo ">>> Aplicando cenário ${SCENARIO} no cliente"
  docker exec "${CLIENT_CONTAINER}" bash /app/scripts/setup_tc.sh "${SCENARIO}" eth0
  docker exec -e PYTHONPATH=/app "${CLIENT_CONTAINER}" \
    bash /app/scripts/run_benchmark.sh "${DNS_HOST}" 10 "${SCENARIO}"
done

docker exec "${CLIENT_CONTAINER}" bash /app/scripts/setup_tc.sh clear eth0
docker exec -e PYTHONPATH=/app "${CLIENT_CONTAINER}" python3 /app/analysis/analyze.py

echo "Gráficos e CSV em analysis/output/"
echo "Testes Docker concluídos. Logs em logs/transfers.jsonl"
