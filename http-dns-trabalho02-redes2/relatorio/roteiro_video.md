# Roteiro do vídeo — Trabalho 2, Redes de Computadores II

**Título sugerido:** Miniservidor HTTP/1.1 com DNS local sobre TCP e R-UDP  
**Autora:** Brenda Evilly Oliveira de Moura — UFPI/CSHNB  
**Duração alvo:** 8 a 12 minutos  
**Requisito do enunciado:** demonstração com **perda de pacotes ativa** (cenário **B** ou **C**)

---

## Antes de gravar (checklist)

- [ ] Docker Compose rodando: `docker compose up -d`
- [ ] Arquivos em `www/` gerados
- [ ] Wireshark instalado (ou captura `.pcap` já pronta em `captures/`)
- [ ] Terminal com fonte legível (zoom 120%+)
- [ ] Gravar tela + áudio; testar microfone
- [ ] Fechar notificações do sistema
- [ ] Ter aberto: terminal, Wireshark (opcional), um gráfico de `analysis/output/` (opcional)

---

## Cena 1 — Abertura (≈ 45 s)

**Tela:** slide simples ou título no README / capa do relatório.

**Fala:**

> Olá. Meu nome é Brenda Evilly Oliveira de Moura, sou aluna do Bacharelado em Sistemas de Informação da UFPI, campus CSHNB Picos.
>
> Este vídeo apresenta o Trabalho 2 de Redes de Computadores II: um miniservidor HTTP/1.1 com resolução DNS local, evoluindo o trabalho anterior de transferência de arquivos sobre TCP e R-UDP.
>
> O foco da demonstração é o fluxo completo **DNS → HTTP**, com comparação entre **TCP nativo** e **R-UDP Stop-and-Wait**, em ambiente Docker com **perda de pacotes simulada** pelo `tc netem`.

---

## Cena 2 — Arquitetura (≈ 1 min 30 s)

**Tela:** diagrama do README ou `docker compose ps` + `docker network inspect`.

**Fala:**

> A arquitetura usa três contêineres na rede `172.29.0.0/24`.
>
> O **cliente**, em `172.29.0.20`, não recebe o IP do servidor diretamente. Ele resolve o nome `www.redes.local` no **servidor DNS**, em `172.29.0.5`, porta UDP 53.
>
> O DNS consulta a zona estática em `dns/hosts.txt` e devolve o IP `172.29.0.10`, que é o **servidor web**.
>
> Só depois disso o cliente faz o GET HTTP/1.1 — por **TCP na porta 8080** ou por **R-UDP na porta 8081**.
>
> O servidor entrega `index.html` e arquivos binários de 100 kB, 1 MB e 10 MB, gerados pelo script `generate_www_files.py`.
>
> A degradação de rede é aplicada no **egress do cliente**, com `NET_ADMIN`, usando `tc qdisc netem` na interface `eth0`. Assim, tanto o tráfego DNS quanto o HTTP passam pelo mesmo canal degradado.

**Ação na tela (opcional):**

```bash
docker compose ps
docker exec redes2-t02-client cat /app/dns/hosts.txt
```

---

## Cena 3 — Protocolo DNS simplificado (≈ 1 min)

**Tela:** `src/dns_protocol.py` ou trecho de `dns/hosts.txt`.

**Fala:**

> O DNS implementado não segue o RFC 1035 por completo. É uma consulta tipo A simplificada.
>
> A consulta UDP leva: ID de 2 bytes, tamanho do nome de 2 bytes e o nome em UTF-8.
>
> A resposta repete ID e nome e acrescenta 4 bytes de IPv4. Se o endereço for `0.0.0.0`, a resolução falhou.
>
> O cliente usa timeout de aplicação — 1 segundo base — com até três retransmissões. Nos cenários degradados, o timeout efetivo sobe para 0,5 s no A, 1 s no B e 2 s no C.
>
> Por isso, quando há perda, algumas consultas DNS demoram cerca de 1 ou 2 segundos antes de concluir.

---

## Cena 4 — Subir o ambiente (≈ 45 s)

**Tela:** terminal na pasta do projeto.

**Fala:**

> Vou subir o ambiente com Docker Compose. Três serviços sobem: DNS, servidor web e cliente.

**Comandos:**

```bash
cd http-dns-trabalho02-redes2
docker compose up -d --build
docker compose ps
```

> O servidor web já gera os arquivos estáticos e inicia os dois modos: HTTP/TCP e HTTP/R-UDP.

---

## Cena 5 — Cenário sem perda (A), referência rápida (≈ 1 min)

**Tela:** terminal dentro do cliente.

**Fala:**

> Antes de ativar a perda, faço uma execução de referência no cenário A — só atraso de 10 ms, sem perda — para mostrar o fluxo normal.

**Comandos:**

```bash
docker exec -it redes2-t02-client bash
./scripts/setup_tc.sh A eth0
python3 src/web_client.py /index.html --mode tcp --scenario A
```

> Reparem: o cliente resolve `www.redes.local`, obtém `172.29.0.10` e só então abre a conexão HTTP. O log mostra `dns_duration_s`, `http_duration_s` e se a transferência teve sucesso.

**Mostrar:** última linha de saída ou entrada em `logs/transfers.jsonl`.

---

## Cena 6 — Ativar perda de pacotes — cenário B (≈ 2 min) ⭐ OBRIGATÓRIO

**Tela:** terminal no cliente + saída do `setup_tc.sh`.

**Fala:**

> Agora entro no **cenário B**, exigido pela demonstração: **5% de perda** e **50 ms de atraso**, configurados com `netem`.
>
> Esse perfil simula um link instável. O UDP do DNS não retransmite sozinho — quem retransmite é a nossa aplicação. Já o TCP do kernel absorve perdas de forma transparente.

**Comandos:**

```bash
./scripts/setup_tc.sh B eth0
tc qdisc show dev eth0
```

> Confirmo que a regra está ativa: delay 50 ms e loss 5%.

**Demonstração TCP (deve funcionar):**

```bash
python3 src/web_client.py /files/arquivo_1mb.bin --mode tcp --scenario B
```

**Fala enquanto roda:**

> No modo TCP, mesmo com 5% de perda, a transferência tende a completar. A vazão cai em relação ao cenário A, mas a taxa de erro permanece zero nos nossos testes.

**Demonstração R-UDP (pode falhar — isso é esperado):**

```bash
python3 src/web_client.py /files/arquivo_1mb.bin --mode rudp --scenario B
```

**Fala:**

> No R-UDP Stop-and-Wait, cada pacote de até 4 kB espera um ACK antes do próximo. Com perda, surgem retransmissões e timeouts. Para arquivos acima de 100 kB, no benchmark registramos taxas de erro de 90% a 100% no cenário B.
>
> Se a execução falhar aqui, isso ilustra exatamente a limitação do protocolo sob perda — não é bug da demo, é o resultado experimental.

**Alternativa mais dramática (cenário C):**

```bash
./scripts/setup_tc.sh C eth0   # 10% perda, 100 ms delay
python3 src/web_client.py /files/arquivo_100kb.bin --mode rudp --scenario C
```

---

## Cena 7 — Wireshark: ordem DNS → HTTP (≈ 2 min)

**Tela:** Wireshark com `.pcap` de `captures/` **ou** captura ao vivo.

**Fala:**

> Agora valido o fluxo na rede com Wireshark.
>
> Abro uma captura do cenário B. Filtro pelo cliente: `ip.addr == 172.29.0.20`.
>
> A sequência esperada é:
>
> 1. Consulta UDP do cliente para o DNS na porta 53;
> 2. Resposta DNS com o IP do servidor web;
> 3. Em seguida, **SYN TCP** para `172.29.0.10:8080` — ou tráfego UDP na porta 8081, no modo R-UDP;
> 4. Requisição GET e resposta HTTP 200.
>
> O Wireshark pode rotular nossas consultas DNS como "Malformed Packet", porque o formato é customizado e não é RFC 1035. Mesmo assim, a **ordem temporal** confirma o comportamento: DNS completo antes do HTTP.
>
> Aqui, entre a resposta DNS e o SYN TCP, o intervalo fica na ordem de milissegundos — mostrando que a resolução precede a sessão HTTP, como previsto pela arquitetura em camadas.

**Captura ao vivo (opcional, em outro terminal antes dos testes):**

```bash
# no host, se preferir capturar dentro do container:
docker exec redes2-t02-client bash -c \
  'tcpdump -i eth0 -w /app/captures/demo_B.pcap "udp port 53 or tcp port 8080 or udp port 8081"'
```

**Mostrar prints já usados no relatório:**

- fluxo geral DNS → TCP
- transição DNS → SYN
- tráfego R-UDP na porta 8081 com retransmissões (cenário B)

---

## Cena 8 — Resultados e gráficos (≈ 1 min 30 s)

**Tela:** gráficos em `analysis/output/`.

**Fala:**

> Resumindo os resultados do benchmark — 240 execuções planejadas, três cenários, dois modos, quatro tamanhos de arquivo:
>
> - No cenário A, TCP atingiu cerca de **126 Mbps** no arquivo de 10 MB; R-UDP ficou em torno de **3 Mbps**, limitado pelo Stop-and-Wait.
> - Com perda, TCP manteve **100% de sucesso** nos cenários B e C; R-UDP falhou massivamente em arquivos grandes — até **100% de erro** a partir de 100 kB no cenário B.
> - O tempo de DNS ficou em ~10 ms na maioria dos casos, mas picos de **1 s ou 2 s** apareceram quando consultas UDP foram perdidas e o cliente retransmitiu.
> - Em páginas pequenas como `index.html`, DNS e cabeçalhos HTTP dominam o tempo total — chegam a ~86% do tempo no cenário A.

**Mostrar rapidamente:**

- `throughput_arquivo_10mb_bin.png`
- `taxa_erro.png`
- `dns_vs_http_tempo.png`

---

## Cena 9 — Respostas às 3 perguntas obrigatórias (≈ 2 min)

**Tela:** slide com as três perguntas ou seção do relatório.

### Pergunta 1 — Como a perda simulada afeta o DNS e o download HTTP?

**Fala:**

> A perda afeta o DNS de forma pontual. Consultas bem-sucedidas seguem o atraso configurado — cerca de 50 ms no B e 100 ms no C. Quando um pacote UDP se perde, o cliente espera o timeout e reenvia, podendo levar 1 ou 2 segundos.
>
> No HTTP/TCP, o kernel retransmite automaticamente — mantivemos 100% de sucesso. No HTTP/R-UDP, a confiabilidade depende da nossa camada Stop-and-Wait; com 5% ou 10% de perda, transferências grandes praticamente não completam dentro do limite de tentativas.

### Pergunta 2 — Qual o impacto dos cabeçalhos HTTP?

**Fala:**

> Comparando com o protocolo textual do Trabalho 1, o HTTP/1.1 adiciona linha de requisição, cabeçalhos como `Host`, `Content-Type`, `Content-Length` e o cabeçalho customizado `X-Custom-Auth`.
>
> Para `index.html` de 624 bytes, quase todo o tempo vai para DNS e negociação HTTP — o payload é pequeno demais para compensar. Para o arquivo de 10 MB, esse overhead fixo cai para cerca de 5% do tempo total.

### Pergunta 3 — A ordem do fluxo corresponde à arquitetura em camadas?

**Fala:**

> Sim. As capturas Wireshark mostram consulta DNS em UDP/53, resposta imediata, e só então início da sessão HTTP — SYN/TCP:8080 ou primeiro pacote R-UDP:8081.
>
> Isso confirma a sequência da pilha: camada de aplicação DNS antes da camada HTTP, sobre transporte TCP ou UDP confiável implementado na aplicação.

---

## Cena 10 — Encerramento (≈ 30 s)

**Tela:** repositório / README / link do GitHub (se houver).

**Fala:**

> Concluindo: integramos DNS local simplificado, miniservidor HTTP/1.1 e transporte alternável TCP/R-UDP em Docker, com emulação de rede por `tc netem` e validação por Wireshark.
>
> O TCP nativo mostrou-se confiável e rápido; o R-UDP funcionou apenas sem perda significativa. O código, os `.pcap`, os gráficos e o relatório SBC estão no repositório do trabalho.
>
> Obrigada por assistir.

---

## Roteiro resumido (cola de 1 página)


| #   | Tempo | O que mostrar        | O que dizer                                   |
| --- | ----- | -------------------- | --------------------------------------------- |
| 1   | 0:45  | Capa                 | Apresentação + objetivo do trabalho           |
| 2   | 1:30  | Diagrama Docker      | 3 contêineres, DNS obrigatório, tc no cliente |
| 3   | 1:00  | Código DNS           | Formato simplificado, timeout, retransmissão  |
| 4   | 0:45  | `docker compose up`  | Subir ambiente                                |
| 5   | 1:00  | Cenário A + TCP      | Fluxo normal DNS → HTTP                       |
| 6   | 2:00  | **Cenário B/C + tc** | **Perda ativa**, TCP ok, R-UDP falha          |
| 7   | 2:00  | Wireshark            | Ordem DNS → HTTP, Malformed OK                |
| 8   | 1:30  | Gráficos             | Throughput, erro, DNS vs HTTP                 |
| 9   | 2:00  | 3 perguntas          | Respostas do relatório                        |
| 10  | 0:30  | Encerramento         | Conclusão + agradecimento                     |


---

## Comandos úteis durante a gravação

```bash
# Status dos containers
docker compose ps

# Shell no cliente (onde roda tc e web_client)
docker exec -it redes2-t02-client bash

# Cenários de rede
./scripts/setup_tc.sh A eth0   # 0% perda, 10 ms
./scripts/setup_tc.sh B eth0   # 5% perda, 50 ms  ← demo principal
./scripts/setup_tc.sh C eth0   # 10% perda, 100 ms
./scripts/setup_tc.sh clear eth0

# Testes manuais
python3 src/web_client.py /index.html --mode tcp --scenario B
python3 src/web_client.py /files/arquivo_1mb.bin --mode tcp --scenario B
python3 src/web_client.py /files/arquivo_1mb.bin --mode rudp --scenario B

# Ver último log
tail -1 logs/transfers.jsonl | python3 -m json.tool

# Ver regra tc ativa
tc qdisc show dev eth0
```

---

## Dicas finais

1. **Grave a cena 6 com calma** — é a exigência central do enunciado (perda ativa).
2. Se o R-UDP falhar ao vivo, **explique por quê**; isso reforça a análise.
3. No Wireshark, **aproxime o zoom** nos frames 1–6 (DNS → SYN).
4. Evite ler o relatório palavra por palavra; use este roteiro como guia natural.
5. Coloque o link do vídeo no README ou na entrega conforme orientação do professor.

