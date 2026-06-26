#!/usr/bin/env bash
# Captura tráfego DENTRO do container cliente (rede Docker 172.29.0.0/24).
# Uso: ./scripts/capture_docker.sh [cenario] [modo]
# Exemplo: ./scripts/capture_docker.sh A tcp
# Deixe rodando e execute o cliente em outro terminal (ver README).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCENARIO="${1:-A}"
MODE="${2:-tcp}"
CONTAINER="${CAPTURE_CONTAINER:-redes2-t02-client}"
BASE="cenario_${SCENARIO}_${MODE}"
OUT="${ROOT}/captures/${BASE}_$(date +%Y%m%d_%H%M%S).pcap"
mkdir -p "${ROOT}/captures"

echo "=== Captura Docker ==="
echo "Container: ${CONTAINER}"
echo "Interface: eth0"
echo "Saída: ${OUT}"
echo ""
echo "Em OUTRO terminal, execute:"
echo "  docker exec ${CONTAINER} bash /app/scripts/setup_tc.sh ${SCENARIO} eth0"
echo "  docker exec -e PYTHONPATH=/app ${CONTAINER} python3 src/web_client.py /index.html \\"
echo "    --dns-host 172.29.0.5 --mode ${MODE} --scenario ${SCENARIO} --run-id 1"
echo "  docker exec ${CONTAINER} bash /app/scripts/setup_tc.sh clear eth0"
echo ""
echo "Pressione Ctrl+C para parar a captura."
echo ""

docker exec "${CONTAINER}" bash -c "
  mkdir -p /app/captures
  tcpdump -i eth0 -w /app/captures/$(basename "${OUT}") \
    'host 172.29.0.5 or host 172.29.0.10'
"
