# Miniservidor HTTP/1.1 com DNS local — Redes de Computadores II

Evolução do trabalho anterior: cliente web com resolução DNS obrigatória, miniservidor HTTP/1.1 sobre TCP nativo e R-UDP, e ambiente Docker multi-container.

## Arquitetura

```
Cliente (172.29.0.20)
    │ 1. Consulta DNS (UDP:53)
    ▼
Servidor DNS (172.29.0.5) ── hosts.txt ──► www.redes.local → 172.29.0.10
    │ 2. HTTP GET (TCP:8080 ou R-UDP:8081)
    ▼
Servidor Web (172.29.0.10) ── www/ ──► index.html, arquivos estáticos
```

## Módulos

| Módulo | Arquivo | Descrição |
|--------|---------|-----------|
| DNS | `src/dns_server.py`, `src/dns_client.py` | Consultas tipo A simplificadas (ID, Name, IP) |
| HTTP/TCP | `src/http_tcp_server.py` | Servidor HTTP/1.1 com cabeçalhos padrão |
| HTTP/R-UDP | `src/http_rudp_server.py` | HTTP sobre camada R-UDP Stop-and-Wait |
| Cliente | `src/web_client.py` | DNS + GET via `--mode tcp\|rudp` |

## Uso local (sem Docker)

Terminal 1 — DNS:
```bash
python3 src/dns_server.py
```

Terminal 2 — Servidor web:
```bash
python3 scripts/generate_www_files.py --all
python3 src/http_tcp_server.py &
python3 src/http_rudp_server.py &
```

Terminal 3 — Cliente:
```bash
python3 src/web_client.py /index.html --dns-host 127.0.0.1 --mode tcp
python3 src/web_client.py /files/arquivo_1mb.bin --dns-host 127.0.0.1 --mode rudp --scenario B
```

## Testes Docker (cenários A, B, C)

```bash
chmod +x run_docker_tests.sh scripts/*.sh
./run_docker_tests.sh
```

Cenários de rede (`tc netem` no cliente):
- **A:** 0% perda, 10 ms delay
- **B:** 5% perda, 50 ms delay
- **C:** 10% perda, 100 ms delay

## Captura Wireshark

```bash
./scripts/capture_traffic.sh any cenario_A
# Em outro terminal, execute o benchmark ou cliente manual
```

Exportar pcap para CSV:
```bash
python3 analysis/pcap_to_csv.py captures/cenario_A_*.pcap
```
