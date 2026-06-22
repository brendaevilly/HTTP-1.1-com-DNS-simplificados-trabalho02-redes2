#!/usr/bin/env bash
# Captura tráfego DNS + HTTP durante os testes
# Uso: ./scripts/capture_traffic.sh [interface] [nome_base]

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IFACE="${1:-any}"
BASE="${2:-capture}"
OUT="${ROOT}/captures/${BASE}_$(date +%Y%m%d_%H%M%S).pcap"
mkdir -p "${ROOT}/captures"

echo "Capturando em ${IFACE} -> ${OUT}"
echo "Filtro: udp port 53 or tcp port 8080 or udp port 8081"
echo "Pressione Ctrl+C para parar."
sudo tcpdump -i "${IFACE}" -w "${OUT}" \
  'udp port 53 or tcp port 8080 or udp port 8081'
