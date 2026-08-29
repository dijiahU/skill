---
name: ethical-redteam-bugbounty
description: Conducts authorized ethical security tests (Red Team / Bug Bounty) covering OSINT reconnaissance, subdomain enumeration, social media username investigation (Sherlock, Blackbird), port/service scanning, vulnerability analysis, and professional OWASP/NIST report generation. Use when the user asks for "penetration testing", "pentest", "vulnerability scan", "OSINT", "bug bounty", "security report", "port scan", "network analysis", "red team", "recon on target", "subdomain enumeration", "username search", or "social media OSINT". Requires written authorization before any active test. Outputs executive and technical reports in Markdown and PDF.
license: MIT
metadata:
  author: prof-ramos
  version: 1.2.0
  compatibility: Requires Python 3.10+, nmap, subfinder, Sherlock, and Blackbird installed. Supports macOS 13+ (Apple Silicon / Intel) and Linux (Ubuntu/Debian, Fedora/RHEL, Arch/Kali). Network access required for active reconnaissance modules. Run scripts/check-deps.sh to validate the environment before first use.
---

# Ethical Red Team & Bug Bounty Skill

> ⚠️ **DISCLAIMER OBRIGATÓRIO**
> Esta skill destina-se **exclusivamente** a testes de segurança autorizados em ambientes controlados.
> Uso não autorizado contra sistemas de terceiros é **ilegal** e viola LGPD, Marco Civil da Internet, CFAA e Computer Misuse Act.
> **SEMPRE** obtenha e documente autorização escrita antes de qualquer teste.

---

## Instructions

### Step 1: Validação de Autorização (OBRIGATÓRIO)

Antes de executar qualquer módulo, pergunte ao usuário:

```
Para prosseguir, confirme:
1. Você possui autorização ESCRITA do proprietário do sistema alvo?
2. O escopo do teste está claramente definido?
3. Existe um Rules of Engagement (RoE) documentado?

Responda SIM para todas para continuar.
```

Se qualquer resposta for NÃO, interrompa e oriente sobre como obter autorização legal.
Consulte `references/ethics-guide.md` para modelos de autorização e orientações legais completas.

---

### Step 2: Verificação de Ambiente (OBRIGATÓRIO)

Antes de qualquer operação de scanning, verifique se as dependências estão instaladas e ativas:

**2a. Verificar Tor (prioridade máxima — afeta todas as operações de rede):**

```bash
# Verificar se Tor está rodando
pgrep -x tor && echo "Tor ativo" || echo "Tor não está rodando"
```

- Se **não instalado**: pergunte ao usuário se deseja instalar (`brew install tor` no macOS, `sudo apt install tor` no Linux)
- Se **instalado mas não rodando**: pergunte se deseja iniciar (`brew services start tor` no macOS, `systemctl start tor` no Linux)
- Se o usuário **recusar** Tor: avise que todas as operações de rede serão realizadas **sem anonimato** e pergunte se deseja prosseguir

**2b. Verificar ferramentas por step:**

| Ferramenta | Verificação | Step impactado | Impacto se ausente |
|-----------|-------------|----------------|-------------------|
| `nmap` | `command -v nmap` | Step 8 (Scanner) | Sem scanning de portas/serviços |
| `subfinder` | `command -v subfinder` | Step 4 (Subdomínios) | Sem enumeração de subdomínios |
| `httpx` | `command -v httpx` | Step 4 (Subdomínios) | Subdomínios não validados como live |
| `sherlock` | `command -v sherlock` | Step 5 (OSINT user) | Sem busca em redes sociais |
| `blackbird` | `ls blackbird/blackbird.py` | Step 6 (OSINT email) | Sem investigação aprofundada |

**2c. Se alguma dependência estiver ausente:**

```
As seguintes dependências estão ausentes:
- [ferramenta] → [impacto]

Deseja prosseguir sem elas? Os elementos acima ficarão fora da análise.
```

- Se o usuário **aceitar**: continue apenas com os steps cujas dependências estão presentes
- Se o usuário **recusar**: oriente a instalar via `./scripts/install.sh` e interrompa

---

### Step 3: Reconhecimento (OSINT/DNS/IP)

Execute reconhecimento passivo ou ativo conforme o escopo autorizado:

```bash
python scripts/recon.py --target ALVO --mode [passive|active|full] --output recon_output/
```

**Modos disponíveis:**
- `passive` — Apenas OSINT (sem contato direto com o alvo)
- `active` — DNS enumeration + IP range mapping
- `full` — Passive + Active combinados

Saída esperada: `recon_output/ALVO_recon_TIMESTAMP.json`

Se `theHarvester` der timeout: use `--mode passive --timeout 30`.

---

### Step 4: Enumeração de Subdomínios (subfinder)

Expande a superfície de ataque identificando subdomínios ativos do alvo:

```bash
subfinder -d DOMINIO -o recon_output/ALVO_subdomains.txt -silent
```

**Opções úteis:**
- `-all` — Usa todas as fontes disponíveis (mais lento, mais completo)
- `-recursive` — Enumeração recursiva de subdomínios
- `-t 50` — Controla o número de threads (padrão: 10)
- `-nW` — Remove wildcards dos resultados

Após enumerar, resolva e filtre ativos:

```bash
subfinder -d DOMINIO -all -o recon_output/ALVO_subdomains.txt
cat recon_output/ALVO_subdomains.txt | httpx -silent -o recon_output/ALVO_subdomains_live.txt
```

Saída esperada: `recon_output/ALVO_subdomains.txt` + `ALVO_subdomains_live.txt`

> **Instalação:** `go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest`
> Alternativa sem Go: `pip install sublist3r` → `sublist3r -d DOMINIO -o saida.txt`

---

### Step 5: OSINT de Usuário — Sherlock

Busca username em centenas de redes sociais e plataformas para mapeamento de pegada digital:

```bash
sherlock USERNAME --output recon_output/ALVO_sherlock.txt --timeout 10
```

**Opções:**
- `--site SITE` — Limita a busca a um site específico
- `--timeout 10` — Timeout por requisição (padrão: 60s)
- `--print-found` — Imprime apenas resultados encontrados
- `--csv` — Exporta em CSV: `sherlock USERNAME --csv`
- `--tor` — Roteia via rede Tor (recomendado para testes sensíveis)

Busca de múltiplos usernames:

```bash
sherlock USERNAME1 USERNAME2 USERNAME3 --output recon_output/
```

Saída esperada: `USERNAME.txt` com URLs encontradas por plataforma

> **Instalação:** `pip install sherlock-project`
> Documentação: https://github.com/sherlock-project/sherlock

---

### Step 6: OSINT de Usuário/Email — Blackbird

Investigação aprofundada de username ou e-mail em mais de 600 sites, com metadados e exportação JSON:

```bash
# Por username
python blackbird.py -u USERNAME --json

# Por e-mail
python blackbird.py -e EMAIL --json

# Redirecionar saída
python blackbird.py -u USERNAME --json -o recon_output/ALVO_blackbird.json
```

**Opções:**
- `--json` — Exporta resultados em JSON estruturado
- `--pdf` — Gera relatório PDF dos achados
- `-p` — Habilita modo de permissive matching
- `--timeout 10` — Timeout por site

> **Instalação:**
> ```bash
> git clone https://github.com/p1ngul1n0/blackbird.git
> cd blackbird
> pip install -r requirements.txt
> ```
> Documentação: https://github.com/p1ngul1n0/blackbird

> ⚠️ Blackbird não inclui proxy por padrão. Para testes sensíveis, configure `--proxy http://127.0.0.1:9050` com Tor ativo.

---

### Step 7: Web Application Scanning — Burp Suite MCP (Community)

Analisa aplicações web interceptando tráfego via Burp Suite + MCP, sem necessidade de Burp Pro:

```bash
# Pré-requisito: Burp Suite com extensão MCP carregada e browser usando proxy 127.0.0.1:8080

# 1. Verificar se Burp MCP está ativo
python scripts/burp_mcp.py --check

# 2. Análise passiva do histórico de proxy (navegue no alvo antes)
python scripts/burp_mcp.py --mode history --output scan_output/

# 3. Probing ativo + histórico combinados
python scripts/burp_mcp.py --mode full --target https://alvo.com --output scan_output/
```

**O que detecta (Community — sem Burp Pro):**
- Headers de segurança ausentes (HSTS, CSP, X-Frame-Options, etc.)
- Cookies sem HttpOnly/Secure/SameSite
- Dados sensíveis expostos em URLs (tokens, senhas, session IDs)
- Versão do servidor exposta (Server: header)
- HTTP sem criptografia (sem redirect para HTTPS)
- CORS wildcard (`Access-Control-Allow-Origin: *`)
- Caminhos sensíveis: `/.git/HEAD`, `/.env`, `/admin`, `/phpinfo.php`, etc.
- Métodos HTTP perigosos (PUT, DELETE, TRACE)

**Configuração da extensão MCP:**
```bash
git clone https://github.com/portswigger/mcp-server
cd mcp-server && ./gradlew embedProxyJar
# Burp Suite → Extensions → Add → Java → build/libs/mcp-server-all.jar
# Aba MCP → Enable Server (porta padrão: 9876)
```

Saída: `scan_output/ALVO_burp_mcp_TIMESTAMP.json` — compatível com `analyzer.py`

> **Burp Pro:** Adiciona `GetScannerIssues` para SQLi, XSS, IDOR e 100+ vulnerabilidades automáticas.
> A versão Community cobre os 20% de esforço que detectam 80% dos problemas mais comuns.

---

### Step 8: Scanning (Portas / Serviços / Vulnerabilidades)

```bash
python scripts/scanner.py --target ALVO --profile [quick|standard|deep] --output scan_output/
```

**Perfis:**
- `quick` — Top 100 portas + detecção de SO
- `standard` — Top 1000 portas + banner grabbing *(recomendado)*
- `deep` — Todas as portas + detecção de CVEs conhecidos

> Limite de recursos: máx. 4 GB RAM configurado para M3. Em redes grandes com `deep`, use `--profile standard`.

Saída esperada: `scan_output/ALVO_scan_TIMESTAMP.json`

---

### Step 9: Análise de Vulnerabilidades

```bash
python scripts/analyzer.py \
  --recon recon_output/ARQUIVO.json \
  --scan scan_output/ARQUIVO.json \
  --output analysis/
```

Gera análise consolidada com classificação de severidade **CVSS v3.1**.
Consulte `references/owasp-checklist.md` para cobertura metodológica OWASP WSTG completa.

Saída esperada: `analysis/ALVO_analysis_TIMESTAMP.json`

---

### Step 10: Geração de Relatório

```bash
python scripts/reporter.py \
  --analysis analysis/ARQUIVO.json \
  --target "Nome do Alvo" \
  --tester "Seu Nome" \
  --output reports/
```

Gera automaticamente três artefatos:
- `ALVO_executive_report.md` — Sumário executivo para gestores
- `ALVO_technical_report.md` — Detalhamento técnico completo
- `ALVO_full_report.pdf` — Relatório unificado em PDF

Consulte `references/report-template.md` para o template e `references/sample-report.md` para exemplo de saída esperada.

---

## Examples

### Example 1: Bug Bounty — Recon Completo com OSINT Social

Usuário diz: "Preciso fazer recon completo em alvo.com com mapeamento de presença social"

Ações:
1. Confirmar autorização (Step 1) e verificar ambiente (Step 2)
2. `python scripts/recon.py --target alvo.com --mode passive --output ./saida/`
3. `subfinder -d alvo.com -all -o ./saida/subdomains.txt`
4. `sherlock admin_username --output ./saida/ --timeout 10`
5. `python blackbird.py -u admin_username --json -o ./saida/blackbird.json`
6. `python scripts/reporter.py --analysis ./saida/analysis_*.json --target "Alvo" --tester "Pentester"`

Resultado: Mapa completo de subdomínios + pegada digital social + relatório técnico

---

### Example 2: Red Team Interno — Varredura de Rede

Usuário diz: "Red team na rede interna 192.168.1.0/24, tenho autorização documentada"

Ações:
1. Confirmar RoE e escopo (Step 1) e verificar ambiente (Step 2)
2. `python scripts/scanner.py --target 192.168.1.0/24 --profile standard --output ./saida/`
3. `python scripts/analyzer.py --scan ./saida/scan_*.json --output ./saida/`
4. `python scripts/reporter.py --analysis ./saida/analysis_*.json --target "Rede Interna Lab" --tester "Pentester A" --output ./reports/`

Resultado: Relatório executivo + técnico + PDF em `reports/`

---

### Example 3: OSINT de Pessoa — Investigação de Username

Usuário diz: "Preciso mapear a pegada digital de um username suspeito para um case de threat intel"

Ações:
1. Confirmar autorização e escopo legal (Step 1) e verificar ambiente (Step 2)
2. `sherlock USERNAME --csv --timeout 10 --output ./saida/`
3. `python blackbird.py -u USERNAME --json --pdf -o ./saida/blackbird.json`

Resultado: Lista de perfis encontrados em +600 plataformas + relatório PDF Blackbird

---

## Troubleshooting

**Erro: `subfinder: command not found`**
Causa: subfinder não instalado ou não está no PATH.
Solução: `go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest` e adicione `$GOPATH/bin` ao PATH

**Erro: `sherlock: command not found`**
Causa: Sherlock não instalado.
Solução: `pip install sherlock-project`

**Erro: `python blackbird.py: No module named 'requests'`**
Causa: Dependências do Blackbird não instaladas.
Solução: `cd blackbird && pip install -r requirements.txt`

**Erro: `nmap not found`**
Causa: nmap não instalado.
Solução: `brew install nmap` (macOS) ou `sudo apt install nmap` (Linux)

**Erro: `Permission denied` no install.sh**
Causa: Arquivo sem permissão de execução.
Solução: `chmod +x scripts/install.sh && ./scripts/install.sh`

**Erro: memória excedida no scan `deep`**
Causa: Range de rede muito grande.
Solução: Reduza o range ou use `--profile standard`

**Erro: `theHarvester` timeout**
Causa: APIs externas lentas ou indisponíveis.
Solução: `--mode passive --timeout 30`

**Sherlock com muitos falsos positivos**
Causa: Sites com detecção inconsistente.
Solução: Valide manualmente as URLs retornadas; use `--print-found` para filtrar

**Blackbird sem resultados**
Causa: Username inexistente ou rate limiting.
Solução: Tente com variações do username; aguarde e reexecute com `--timeout 20`

---

## Hooks de Ciclo de Vida

A skill suporta hooks de ciclo de vida para inicializar e encerrar serviços temporários.

### on_start.sh
Inicializa serviços e valida dependências:
- Inicia Tor para anonimato (se disponível) e exporta `TOR_PID`
- Verifica dependências críticas (nmap, subfinder, httpx)
- Configura variáveis de ambiente (`TOR_PROXY`)

### on_end.sh
Encerra serviços e limpa recursos:
- Encerra Tor apenas se foi iniciado pela skill (usa `TOR_PID`)
- Remove arquivos temporários de diretório controlado
- Limpa variáveis de ambiente (`TOR_PID`, `TOR_PROXY`)

### Uso
```bash
# Executar hooks manualmente (para testes)
source hooks/on_start.sh && on_start
source hooks/on_end.sh && on_end
```
