# Detection Coverage

Full list of 39 detection patterns across 6 threat categories.

## Credentials (12 rules)

| Rule | Severity | What it detects |
|------|----------|----------------|
| `Credential_AWS_Access_Key` | HIGH | AWS access key IDs (`AKIA` prefix) |
| `Credential_AWS_Secret_Reference` | HIGH | `AWS_SECRET_ACCESS_KEY`, `~/.aws/credentials` |
| `Credential_Private_Key_Block` | CRITICAL | PEM-encoded private keys (RSA, OpenSSH, EC, DSA) |
| `Credential_GitHub_Token` | HIGH | GitHub token prefixes: `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` |
| `Credential_API_Key_Patterns` | MEDIUM | Stripe, Slack, SendGrid, Shopify, GitLab PAT, Mailgun |
| `Credential_Cloud_Provider_Keys` | HIGH | Google/GCP API keys, Azure Storage/SAS keys |
| `Credential_Package_Registry_Tokens` | HIGH | npm tokens, PyPI tokens |
| `Credential_Env_File_Access` | HIGH | `cat .env`, `.ssh/id_rsa`, `source .env`, `.npmrc`, `.netrc` |
| `Credential_LLM_Provider_Keys` | HIGH | OpenAI `sk-proj-`, Anthropic `sk-ant-api03-`, Hugging Face `hf_`, Replicate `r8_` |
| `Credential_Modern_SaaS_Tokens` | HIGH | Supabase, Vercel, Twilio, Discord bot, Telegram bot tokens |
| `Credential_Database_Connection_Strings` | HIGH | PostgreSQL, MongoDB, MySQL, Redis with embedded credentials |
| `Credential_Crypto_Private_Keys` | CRITICAL | EVM private keys, Solana keypair files/JSON, Bitcoin WIF keys |

## Exfiltration (10 rules)

| Rule | Severity | What it detects |
|------|----------|----------------|
| `Exfil_Webhook_Site` | CRITICAL | `webhook.site` references |
| `Exfil_Known_Paste_Services` | HIGH | Pastebin, hastebin, requestbin, pipedream, burpcollaborator |
| `Exfil_Ngrok_Tunnel` | HIGH | Ngrok tunnel endpoints |
| `Exfil_Curl_Post` | MEDIUM | `curl -X POST`, `wget --post-data` |
| `Exfil_DNS_Tunneling` | HIGH | DNS query patterns indicating tunneling (requires 2+ indicators) |
| `Exfil_Discord_Webhook` | CRITICAL | Discord webhook URLs |
| `Exfil_Telegram_Bot` | HIGH | Telegram Bot API endpoints |
| `Exfil_Slack_Webhook` | HIGH | Slack incoming webhook URLs |
| `Exfil_Modern_Drop_Services` | HIGH | transfer.sh, file.io, 0x0.st, gofile.io, anonfiles.com |
| `Exfil_HTTP_Client_Post` | MEDIUM | `requests.post()`, `axios.post()`, `fetch(...POST)`, `httpx.post()` |

## Dangerous Commands (10 rules)

| Rule | Severity | What it detects |
|------|----------|----------------|
| `Dangerous_Reverse_Shell` | CRITICAL | Bash, netcat, Python/Perl/PHP reverse shells |
| `Dangerous_System_Destruction` | CRITICAL | `rm -rf /`, `dd if=/dev/zero` |
| `Dangerous_Privilege_Escalation` | HIGH | `chmod 777`, SUID, NOPASSWD, `/etc/shadow` (requires 2+ indicators) |
| `Dangerous_Download_Execute` | CRITICAL | `curl \| bash`, `wget \| sh`, download-chmod-execute |
| `Dangerous_Cron_Persistence` | HIGH | Piped crontab writes, `/etc/cron` |
| `Dangerous_Code_Injection` | HIGH | `os.popen()`, `__import__('os')`, PHP webshells, `pickle.loads()`, `marshal.loads()` |
| `Dangerous_Container_Escape` | CRITICAL | Docker host root mount, nsenter into host PID namespace |
| `Dangerous_Docker_Socket_Access` | HIGH | `/var/run/docker.sock` access |
| `Dangerous_SSH_Key_Injection` | HIGH | Writes to `~/.ssh/authorized_keys` |
| `Dangerous_PowerShell_Execution` | HIGH | `Invoke-Expression`, `\| iex`, `DownloadString()`, encoded commands, execution policy bypass |

## Obfuscation (5 rules)

| Rule | Severity | What it detects |
|------|----------|----------------|
| `Obfuscation_Base64_Decode_Chain` | HIGH | `b64decode()`, `base64 -d`, `atob()`, `[Convert]::FromBase64String`, `Base64.decode64()` |
| `Obfuscation_Hex_Encoding` | MEDIUM | Long `\x` sequences, `bytes.fromhex()` |
| `Obfuscation_Eval_With_Encoding` | CRITICAL | `eval()`/`exec()` + base64/decode/compile |
| `Obfuscation_String_Concat_Evasion` | MEDIUM | `chr()` concatenation, `join(map(chr, ...))` |
| `Obfuscation_Unicode_Escape` | MEDIUM | 6+ consecutive `\uXXXX` escapes, `decode('unicode_escape')` |

## Prompt Injection (1 rule)

| Rule | Severity | What it detects |
|------|----------|----------------|
| `Audit_Override_Framing` | HIGH | Prose addressed to the auditor pleading for leniency: "do not run", "not (real\|actual\|live\|production) code", "classify as safe", "(educational\|illustrative\|hypothetical\|teaching\|training\|demonstration) (purpose\|only)", "(documentation\|reference) only", "verdict: safe", "false positive", "ignore the (YARA\|finding\|match)", `END-OVERRIDE` markers, "this skill is disabled". Tagged with `category: prompt_injection`. |

## Multistage (1 rule)

| Rule | Severity | What it detects |
|------|----------|----------------|
| `Multistage_Unaudited_Remote_Code` | HIGH | Code or configuration that loads from a remote URL the auditor cannot inspect: `exec(...http(s)://...)`, `eval(...http(s)://...)`, `compile(...http(s)://...) ... exec`, `importlib.import_module(...http://...)`, `__import__(...http://...)`, `runpy.run_path/run_module(...http(s)://...)`, `bash <(curl ...)`, `bash -c "$(curl ...)"`, plus prose directives that instruct a host runtime / loader / plugin / registry to fetch, apply, register, or publish a remote manifest, bundle, or stage-2 module. Tagged with `category: multistage`. |

## Scoring

| Severity | Points |
|----------|--------|
| LOW | 10 |
| MEDIUM | 20 |
| HIGH | 30 |
| CRITICAL | 50 |

Total score is capped at 100. Any CRITICAL finding forces the recommendation to BLOCK.

## Framing Co-occurrence Policy

If a `prompt_injection` finding (audit-override framing prose) appears alongside any non-framing finding (credentials, exfiltration, dangerous commands, obfuscation, multistage), the scanner short-circuits to `BLOCK` regardless of the score. The framing prose is the bypass surface attackers use to launder real malicious indicators past an LLM auditor — when the two co-occur the framing is treated as additional evidence the malicious indicator is real. This mirrors the hosted Shieldon engine's policy in `engine._decide_verdict`.
