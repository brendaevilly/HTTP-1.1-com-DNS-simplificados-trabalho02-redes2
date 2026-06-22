#!/usr/bin/env bash
# Configura cenários de rede com tc qdisc (netem)
# Uso: sudo ./scripts/setup_tc.sh [A|B|C|clear] [interface]

set -euo pipefail

SCENARIO="${1:-A}"
IFACE="${2:-eth0}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute com sudo."
  exit 1
fi

tc qdisc del dev "${IFACE}" root 2>/dev/null || true

case "${SCENARIO}" in
  A)
    tc qdisc add dev "${IFACE}" root netem delay 10ms
    echo "Cenário A: delay 10ms, 0% perda"
    ;;
  B)
    tc qdisc add dev "${IFACE}" root netem delay 50ms loss 5%
    echo "Cenário B: delay 50ms, 5% perda"
    ;;
  C)
    tc qdisc add dev "${IFACE}" root netem delay 100ms loss 10%
    echo "Cenário C: delay 100ms, 10% perda"
    ;;
  clear)
    echo "Regras tc removidas em ${IFACE}"
    ;;
  *)
    echo "Cenário inválido. Use A, B, C ou clear."
    exit 1
    ;;
esac

tc qdisc show dev "${IFACE}"
