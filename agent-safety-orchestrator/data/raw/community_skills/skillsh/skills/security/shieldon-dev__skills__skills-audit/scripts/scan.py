#!/usr/bin/env python3
"""Shieldon local skill scanner — pure Python regex, stdlib only.

Scans AI agent skill files for credential theft, data exfiltration,
dangerous commands, and obfuscation. Outputs a structured JSON risk report.

Usage:
    python scan.py --file /path/to/SKILL.md
    python scan.py --url https://example.com/SKILL.md
    python scan.py --content "skill text here"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from urllib.request import Request, urlopen
from urllib.error import URLError

# ---------------------------------------------------------------------------
# Severity and scoring
# ---------------------------------------------------------------------------

SEVERITY_POINTS = {"LOW": 10, "MEDIUM": 20, "HIGH": 30, "CRITICAL": 50}


# ---------------------------------------------------------------------------
# Rule definitions — translated 1:1 from mcp-server/yara_rules/*.yar
#
# Each rule is a dict with:
#   name:        YARA rule name
#   description: human-readable description
#   severity:    LOW | MEDIUM | HIGH | CRITICAL
#   patterns:    list of compiled regex patterns
#   condition:   "any" (default) or int N meaning "N of them"
# ---------------------------------------------------------------------------

def _compile(patterns: list[str], flags: int = 0) -> list[re.Pattern]:
    """Compile a list of regex strings, returning Pattern objects."""
    return [re.compile(p, flags) for p in patterns]


RULES: list[dict] = [
    # -----------------------------------------------------------------------
    # credentials.yar (12 rules)
    # -----------------------------------------------------------------------
    {
        "name": "Credential_AWS_Access_Key",
        "description": "AWS access key pattern detected",
        "severity": "HIGH",
        "patterns": _compile([r"AKIA[0-9A-Z]{16}"]),
    },
    {
        "name": "Credential_AWS_Secret_Reference",
        "description": "Reference to AWS secret access key",
        "severity": "HIGH",
        "patterns": _compile([
            r"AWS_SECRET_ACCESS_KEY",
            r"~/\.aws/credentials",
            r"~/\.aws/config",
        ], re.IGNORECASE),
    },
    {
        "name": "Credential_Private_Key_Block",
        "description": "Embedded private key material detected",
        "severity": "CRITICAL",
        "patterns": _compile([
            r"-----BEGIN RSA PRIVATE KEY-----",
            r"-----BEGIN OPENSSH PRIVATE KEY-----",
            r"-----BEGIN EC PRIVATE KEY-----",
            r"-----BEGIN PRIVATE KEY-----",
            r"-----BEGIN DSA PRIVATE KEY-----",
        ]),
    },
    {
        "name": "Credential_GitHub_Token",
        "description": "GitHub personal access token pattern detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"ghp_[a-zA-Z0-9]{36}",
            r"gho_[a-zA-Z0-9]{36}",
            r"ghu_[a-zA-Z0-9]{36}",
            r"ghs_[a-zA-Z0-9]{36}",
            r"ghr_[a-zA-Z0-9]{36}",
        ]),
    },
    {
        "name": "Credential_API_Key_Patterns",
        "description": "Common API key or secret token pattern detected",
        "severity": "MEDIUM",
        "patterns": _compile([
            r"sk_live_[a-zA-Z0-9]{24,}",
            r"pk_live_[a-zA-Z0-9]{24,}",
            r"xox[baprs]-[a-zA-Z0-9\-]{10,}",
            r"SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}",
            r"shpat_[a-fA-F0-9]{32}",
            r"shpca_[a-fA-F0-9]{32}",
            r"shppa_[a-fA-F0-9]{32}",
            r"glpat-[0-9a-zA-Z_\-]{20,}",
            r"key-[0-9a-zA-Z]{32}",
        ]),
    },
    {
        "name": "Credential_Cloud_Provider_Keys",
        "description": "Cloud provider API key or connection string detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"AIza[0-9A-Za-z_\-]{35}",
            r"AccountKey=[a-zA-Z0-9+/=]{44,88}",
            r"SharedAccessKey=[a-zA-Z0-9+/=]{44,}",
        ]),
    },
    {
        "name": "Credential_Package_Registry_Tokens",
        "description": "Package registry authentication token detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"npm_[a-zA-Z0-9]{36}",
            r"pypi-[a-zA-Z0-9_\-]{16,}",
        ]),
    },
    {
        "name": "Credential_Env_File_Access",
        "description": "Attempt to read environment or secret files",
        "severity": "HIGH",
        "patterns": _compile([
            r"cat \.env",
            r"cat ~/\.env",
            r"\.ssh/id_rsa",
            r"cat ~/\.npmrc",
            r"cat ~/\.netrc",
            r"\.docker/config\.json",
            r"source\s+\.env",
            r"export\s+\$\(cat\s+\.env",
        ]),
    },
    {
        "name": "Credential_LLM_Provider_Keys",
        "description": "LLM provider API key pattern detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"sk-proj-[a-zA-Z0-9]{20,}",
            r"sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}",
            r"sk-ant-api03-[a-zA-Z0-9_\-]{90,}",
            r"hf_[a-zA-Z0-9]{34,}",
            r"r8_[a-zA-Z0-9]{36,}",
        ]),
    },
    {
        "name": "Credential_Modern_SaaS_Tokens",
        "description": "Modern SaaS platform token or credential detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"sb_secret_[a-zA-Z0-9_\-]{20,}",
            r"sb_publishable_[a-zA-Z0-9_\-]{20,}",
            r"(?i)SUPABASE_SERVICE_ROLE_KEY\s*[:=]",
            r"(?i)SUPABASE_ANON_KEY\s*[:=]",
            r"vercel_[a-zA-Z0-9]{24,}",
            r"AC[a-f0-9]{32}",
            r"[MN][a-zA-Z0-9]{23,}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27,}",
            r"\d{8,10}:[a-zA-Z0-9_-]{35}",
        ]),
    },
    {
        "name": "Credential_Database_Connection_Strings",
        "description": "Database connection string with embedded credentials",
        "severity": "HIGH",
        "patterns": _compile([
            r"postgres(?:ql)?://[^:\s]+:[^@\s]+@",
            r"mongodb(?:\+srv)?://[^:\s]+:[^@\s]+@",
            r"mysql://[^:\s]+:[^@\s]+@",
            r"redis://:[^@\s]+@",
            r"redis://[^:\s]+:[^@\s]+@",
        ]),
    },
    {
        "name": "Credential_Crypto_Private_Keys",
        "description": "Cryptocurrency private key or wallet secret detected",
        "severity": "CRITICAL",
        "patterns": _compile([
            r"(?i)(?:private.?key|secret)\s*[:=]\s*[\"']?0x[0-9a-fA-F]{64}",
            r"\.config/solana/id\.json",
            (
                r"\[\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])\s*,"
                r"\s*(?:[01]?\d{1,2}|2[0-4]\d|25[0-5])"
            ),
            r"(?i)(?:private.?key|wif|secret)\s*[:=]\s*[\"']?[5KL][1-9A-HJ-NP-Za-km-z]{50,51}[\"']?",
        ]),
    },

    # -----------------------------------------------------------------------
    # exfiltration.yar (10 rules)
    # -----------------------------------------------------------------------
    {
        "name": "Exfil_Webhook_Site",
        "description": "Data exfiltration to webhook.site detected",
        "severity": "CRITICAL",
        "patterns": _compile([r"(?i)webhook\.site"]),
    },
    {
        "name": "Exfil_Known_Paste_Services",
        "description": "Data upload to known paste/sharing service detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"(?i)pastebin\.com",
            r"(?i)hastebin\.com",
            r"(?i)requestbin\.com",
            r"(?i)pipedream\.net",
            r"(?i)burpcollaborator\.net",
        ]),
    },
    {
        "name": "Exfil_Ngrok_Tunnel",
        "description": "Ngrok tunnel endpoint detected - potential exfiltration channel",
        "severity": "HIGH",
        "patterns": _compile([r"(?i)ngrok\.io", r"(?i)ngrok-free\.app"]),
    },
    {
        "name": "Exfil_Curl_Post",
        "description": "Curl command posting data externally",
        "severity": "MEDIUM",
        "patterns": _compile([
            r"curl\s+(?:-[a-zA-Z]\s+)*-X\s+POST",
            r"curl\s+[^\n]*(?:-d|--data)",
            r"wget\s+[^\n]*--post-(?:data|file)",
        ]),
    },
    {
        "name": "Exfil_DNS_Tunneling",
        "description": "Potential DNS tunneling pattern detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"dig\s+[^\n]*@",
            r"nslookup\s+\$",
            r"\$\([^)]+\)\.[a-z]+\.[a-z]+",
        ]),
        "condition": 2,
    },
    {
        "name": "Exfil_Discord_Webhook",
        "description": "Discord webhook URL detected — common exfiltration channel",
        "severity": "CRITICAL",
        "patterns": _compile([
            r"(?i)discord\.com/api/webhooks/\d+/[a-zA-Z0-9_-]+",
            r"(?i)discord\.com/api/webhooks/",
        ]),
    },
    {
        "name": "Exfil_Telegram_Bot",
        "description": "Telegram Bot API endpoint detected — potential exfiltration channel",
        "severity": "HIGH",
        "patterns": _compile([r"(?i)api\.telegram\.org/bot"]),
    },
    {
        "name": "Exfil_Slack_Webhook",
        "description": "Slack incoming webhook URL detected",
        "severity": "HIGH",
        "patterns": _compile([r"(?i)hooks\.slack\.com/services/"]),
    },
    {
        "name": "Exfil_Modern_Drop_Services",
        "description": "Modern file drop or anonymous upload service detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"(?i)transfer\.sh",
            r"(?i)file\.io",
            r"(?i)0x0\.st",
            r"(?i)gofile\.io",
            r"(?i)anonfiles\.com",
        ]),
    },
    {
        "name": "Exfil_HTTP_Client_Post",
        "description": "HTTP client POST request in code — potential data exfiltration",
        "severity": "MEDIUM",
        "patterns": _compile([
            r"requests\.post\s*\(",
            r"httpx\.\w*post\s*\(",
            r"urlopen\s*\(\s*Request\s*\(",
            r"axios\.post\s*\(",
            r"fetch\s*\([^)]*method:\s*['\"]POST['\"]",
        ]),
    },

    # -----------------------------------------------------------------------
    # dangerous_commands.yar (10 rules)
    # -----------------------------------------------------------------------
    {
        "name": "Dangerous_Reverse_Shell",
        "description": "Reverse shell command detected",
        "severity": "CRITICAL",
        "patterns": _compile([
            r"bash\s+-i\s+>&?\s*/dev/tcp/",
            r"nc\s+(?:-e|--exec)\s+/bin/(?:ba)?sh",
            r"python[23]?\s+-c\s+[^\n]*socket[^\n]*connect",
            r"perl\s+-e\s+[^\n]*socket[^\n]*INET",
            r"php\s+-r\s+[^\n]*fsockopen",
            r"mkfifo\s+[^\n]*/tmp/[^\n]*nc\s",
        ]),
    },
    {
        "name": "Dangerous_System_Destruction",
        "description": "Destructive system command detected",
        "severity": "CRITICAL",
        "patterns": _compile([
            r"\nrm\s+-rf\s+/",
            r"\nrm\s+-rf\s+~",
            r"[;&|]\s*rm\s+-rf\s+/",
            r"[;&|]\s*rm\s+-rf\s+~",
            r"dd\s+if=/dev/zero\s+of=",
            r"dd\s+if=/dev/urandom\s+of=",
        ]),
    },
    {
        "name": "Dangerous_Privilege_Escalation",
        "description": "Privilege escalation attempt detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"chmod 777",
            r"chmod \+s ",
            r"chmod 4755",
            r"NOPASSWD",
            r"/etc/shadow",
        ]),
        "condition": 2,
    },
    {
        "name": "Dangerous_Download_Execute",
        "description": "Download-and-execute pattern detected",
        "severity": "CRITICAL",
        "patterns": _compile([
            r"curl\s+[^\n]*\|\s*(?:ba)?sh",
            r"wget\s+[^\n]*-O-?\s*\|\s*(?:ba)?sh",
            r"curl\s+[^\n]*>\s*/tmp/[^\n]*&&[^\n]*chmod[^\n]*\+x",
            r"python[23]?\s+-c\s+[^\n]*urllib[^\n]*exec",
        ]),
    },
    {
        "name": "Dangerous_Cron_Persistence",
        "description": "Cron job persistence mechanism detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"\|\s*crontab",
            r"/etc/cron",
            r"echo\s+[^\n]*crontab",
            r"echo\s+[^\n]*\|\s*at\s",
        ]),
    },
    {
        "name": "Dangerous_Code_Injection",
        "description": "Dynamic code injection or webshell pattern detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"os\.popen\(",
            r"[=(]\s*__import__\(\s*['\"]os['\"]\)",
            r"\n__import__\(\s*['\"]os['\"]\)",
            r"[=(]\s*__import__\(\s*['\"]subprocess['\"]\)",
            r"\n__import__\(\s*['\"]subprocess['\"]\)",
            r"eval\s*\(\s*\$_(?:POST|GET|REQUEST)",
            r"Runtime\.getRuntime\(\)\.exec\(",
            r"child_process[^\n]*exec\s*\(",
            r"pickle\.loads?\s*\(",
            r"marshal\.loads?\s*\(",
        ]),
    },
    {
        "name": "Dangerous_Container_Escape",
        "description": "Container escape or host access pattern detected",
        "severity": "CRITICAL",
        "patterns": _compile([
            r"docker\s+run\s+[^\n]*-v\s+/:/",
            r"nsenter\s+[^\n]*--target\s+1",
        ]),
    },
    {
        "name": "Dangerous_Docker_Socket_Access",
        "description": "Docker socket access detected — potential container breakout",
        "severity": "HIGH",
        "patterns": _compile([r"/var/run/docker\.sock"]),
    },
    {
        "name": "Dangerous_SSH_Key_Injection",
        "description": "SSH authorized_keys write detected — persistence mechanism",
        "severity": "HIGH",
        "patterns": _compile([
            r">>?\s*~?/?\.ssh/authorized_keys",
            r"echo\s+[^\n]*authorized_keys",
        ]),
    },
    {
        "name": "Dangerous_PowerShell_Execution",
        "description": "PowerShell code execution or download pattern detected",
        "severity": "HIGH",
        "patterns": _compile([
            r"(?i)Invoke-Expression",
            r"(?i)\|\s*iex\b",
            r"DownloadString\s*\(",
            r"powershell\s+[^\n]*-[Ee]nc(?:odedCommand)?",
            r"-[Ee]xecutionPolicy\s+[Bb]ypass",
        ]),
    },

    # -----------------------------------------------------------------------
    # obfuscation.yar (5 rules)
    # -----------------------------------------------------------------------
    {
        "name": "Obfuscation_Base64_Decode_Chain",
        "description": "Base64 decode chain used for payload obfuscation",
        "severity": "HIGH",
        "patterns": _compile([
            r"base64\.b64decode\s*\(",
            r"echo\s+[^\n]*\|\s*base64\s+(?:-d|--decode)",
            r"import\s+base64[^\n]*b64decode",
            r"atob\(",
            r"\[Convert\]::FromBase64String",
            r"Base64\.decode64\s*\(",
        ]),
    },
    {
        "name": "Obfuscation_Hex_Encoding",
        "description": "Hex encoding used for payload obfuscation",
        "severity": "MEDIUM",
        "patterns": _compile([
            r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){10,}",
            r"bytes\.fromhex\(",
            r"xxd\s+-r",
            r"unhexlify\(",
        ]),
    },
    {
        "name": "Obfuscation_Eval_With_Encoding",
        "description": "Dynamic code execution combined with encoding - likely malicious",
        "severity": "CRITICAL",
        "patterns": _compile([
            r"eval\s*\([^\n]*base64",
            r"exec\s*\([^\n]*base64",
            r"eval\s*\([^\n]*decode",
            r"exec\s*\(\s*compile\s*\(",
            r"eval\s*\([^\n]*chr\s*\(",
        ]),
    },
    {
        "name": "Obfuscation_String_Concat_Evasion",
        "description": "String concatenation used to evade detection",
        "severity": "MEDIUM",
        "patterns": _compile([
            r"chr\(\d+\)\s*\+\s*chr\(\d+\)\s*\+\s*chr\(\d+\)",
            r"\[chr\(\d+\)[^\]]*chr\(\d+\)[^\]]*chr\(\d+\)\]",
            r"join\(map\(chr",
        ]),
    },
    {
        "name": "Obfuscation_Unicode_Escape",
        "description": "Unicode escape sequence obfuscation detected",
        "severity": "MEDIUM",
        "patterns": _compile([
            r"\\u[0-9a-fA-F]{4}(?:\\u[0-9a-fA-F]{4}){5,}",
            r"decode\s*\(\s*['\"]unicode\.escape['\"]",
        ]),
    },

    # -----------------------------------------------------------------------
    # prompt_injection.yar (1 rule)
    #
    # Audit-override framing: prose addressed to the auditor that pleads
    # for leniency. Alone this is informational. Combined with any
    # non-framing finding (credentials, exfiltration, dangerous_commands,
    # obfuscation, multistage), the scanner short-circuits to BLOCK —
    # mirroring the engine's framing co-occurrence policy.
    # -----------------------------------------------------------------------
    {
        "name": "Audit_Override_Framing",
        "description": "Audit-override framing language addressed to the auditor",
        "severity": "HIGH",
        "category": "prompt_injection",
        "patterns": _compile([
            r"do\s+not\s+(run|execute|invoke)",
            r"(not|never|won't\s+be|wont\s+be|isn't|isnt)\s+(executed|actually\s+run|live\s+code|run\s+anywhere|invoked|run\s+at\s+runtime)",
            r"auditor\s*[:,\-]",
            r"classify\s+(it|this|the\s+skill)?\s*as\s+safe",
            r"ignore\s+(the|this|any)\s+(yara|finding|match|hit|warning)",
            r"(educational|illustrative|hypothetical|teaching|training|demonstration|reference|tutorial)\s+(purpose|purposes|use|uses|only|reason|reasons|example|case|scenario|material|content)",
            r"(for|as)\s+(an?\s+)?(educational|illustrative|hypothetical|teaching|training|demonstration)\s+(purpose|purposes|use|reason|reasons|example|only|reference|case|scenario)",
            r"(documentation|reference)\s+only",
            r"not\s+(real|actual|live|production)\s+code",
            r"verdict\s*[:=]\s*[`'\"]?safe",
            r"(correct|right|proper)\s+verdict[^\n]{0,80}safe",
            r"false positive",
            r"END[\-_\s]?OVERRIDE",
            r"this\s+skill\s+is\s+(disabled|not\s+active|inactive|dormant)",
        ], re.IGNORECASE),
    },

    # -----------------------------------------------------------------------
    # multistage.yar (1 rule)
    #
    # Skill defers code or configuration loading to a remote URL the
    # auditor cannot inspect — the CVE-2 / CVE-3 root cause. Catches both
    # explicit code-exec verbs paired with URLs and prose-level multistage
    # attacks (host runtime/loader/registry "fetches", "applies", "publishes"
    # remote bundles).
    # -----------------------------------------------------------------------
    {
        "name": "Multistage_Unaudited_Remote_Code",
        "description": "Skill defers code/configuration loading to a remote URL the auditor cannot inspect",
        "severity": "HIGH",
        "category": "multistage",
        "patterns": [
            # Code-execution verbs paired with a remote URL (case-sensitive
            # — these are code identifiers, not prose).
            re.compile(r"\bexec\s*\([^\n]{0,80}https?:\/\/"),
            re.compile(r"\beval\s*\([^\n]{0,80}https?:\/\/"),
            re.compile(r"compile\s*\([^\n]{0,80}https?:\/\/[^\n]{0,200}exec"),
            re.compile(r"importlib\.import_module\s*\([^\n]{0,80}https?:\/\/"),
            re.compile(r"__import__\s*\([^\n]{0,80}https?:\/\/"),
            re.compile(r"runpy\.(run_path|run_module)\s*\([^\n]{0,80}https?:\/\/"),
            re.compile(r"bash\s+<\(\s*curl"),
            re.compile(r"bash\s+<\(\s*wget"),
            re.compile(r"(ba)?sh\s+-c\s+[\"']?[^\"'\n]{0,80}\$\(\s*curl"),
            # Vague-prose multistage: actor (host/runtime/loader/plugin/
            # registry/...) does an action (fetch/apply/register/publish/
            # subscribe/...) on remote artefacts.
            re.compile(
                r"(host|runtime|loader|plugin|companion|orchestrator|resolver|registry|index|installer|bootstrap(per)?|package\s+manager|dependency\s+(index|manager|resolver)?|extension\s+host|agent\s+context|module\s+system|chart|subscriber|sidecar|coordinator|dispatcher)\s+(must|will|should|shall|may)?\s*(fetch(es|ed)?|retrieve(s|d)?|load(s|ed)?|integrate(s|d)?|register(s|ed)?|apply|appli(es|ed)|install(s|ed)?|consult(s|ed)?|subscribe(s|d)?|publish(es|ed)?|template(s|d)?|materialize(s|d)?|hydrate(s|d)?|inject(s|ed)?|pull(s|ed)?|download(s|ed)?|resolve(s|d)?|bring(s|ing)?\s+into|import(s|ed)?\s+into\s+(the\s+)?(process|namespace|context))",
                re.IGNORECASE,
            ),
            # Lazy-load / off-disk idiom paired with a remote URL.
            re.compile(
                r"(kept|stored|hosted|live(s)?|reside(s)?)\s+(off[- ]disk|remotely|in\s+the\s+cloud|outside\s+the\s+(skill|repo|bundle))[^\n]{0,120}https?:\/\/",
                re.IGNORECASE,
            ),
            # Source-side: a remote URL is described as publishing /
            # distributing / serving content for the agent.
            re.compile(
                r"https?:\/\/[^\s)]{1,200}[^\n]{0,120}\b(publish(es|ed|ing)?|distribute(s|d)?|serve(s|d)?|provide(s|d)?|expose(s|d)?|advertise(s|d)?|broadcast(s|ed|ing)?|host(s|ed)?)\b[^\n]{0,80}\b(bundle|module|plugin|capability|capabilities|tool(s)?|chart|manifest|extension(s)?|payload|code|script|config(uration)?)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"(manifest|bundle|companion|plugin|module|chart|values\.yaml|values\.json)\s+(at|from|located\s+at|defined\s+at|hosted\s+at)\s+(https?:\/\/|\$\{[^}]*url)",
                re.IGNORECASE,
            ),
            re.compile(r"stage[\-\s]?2\s+(code|payload|module|bundle)", re.IGNORECASE),
        ],
    },
]


# ---------------------------------------------------------------------------
# Scanner engine
# ---------------------------------------------------------------------------

def scan_content(content: str) -> dict:
    """Scan content against all rules and return a structured report."""
    findings: list[dict] = []

    for rule in RULES:
        condition = rule.get("condition", "any")
        matched_patterns: list[re.Match] = []

        for pattern in rule["patterns"]:
            m = pattern.search(content)
            if m:
                matched_patterns.append(m)

        # Check condition
        triggered = False
        if condition == "any":
            triggered = len(matched_patterns) > 0
        elif isinstance(condition, int):
            triggered = len(matched_patterns) >= condition

        if triggered:
            # Build evidence from up to 3 matches (mirrors MCP server behavior)
            evidence_parts: list[str] = []
            for pattern in rule["patterns"]:
                for m in pattern.finditer(content):
                    snippet = m.group()[:100]
                    evidence_parts.append(
                        f"Matched '{rule['name']}' at "
                        f"offset {m.start()}: {snippet}"
                    )
                    if len(evidence_parts) >= 3:
                        break
                if len(evidence_parts) >= 3:
                    break
            evidence = "; ".join(evidence_parts) if evidence_parts else None

            finding: dict = {
                "type": "regex",
                "description": rule["description"],
                "severity": rule["severity"],
                "evidence": evidence,
            }
            category = rule.get("category")
            if category:
                finding["category"] = category
            findings.append(finding)

    # Score aggregation (mirrors mcp-server/src/utils/scoring.py)
    total = sum(SEVERITY_POINTS[f["severity"]] for f in findings)
    total = min(total, 100)

    # Risk level
    if total < 30:
        risk_level = "LOW"
    elif total <= 60:
        risk_level = "MEDIUM"
    elif total <= 80:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    # Recommendation
    if total < 30:
        recommendation = "SAFE"
    elif total <= 70:
        recommendation = "REVIEW"
    else:
        recommendation = "BLOCK"

    # CRITICAL override
    if any(f["severity"] == "CRITICAL" for f in findings):
        recommendation = "BLOCK"

    # Framing co-occurrence policy — mirrors the hosted engine's policy in
    # skill_audit.engine._decide_verdict. If audit-override framing prose
    # appears alongside any non-framing finding (credentials, exfiltration,
    # dangerous commands, obfuscation, multistage), the framing is the
    # bypass surface for the LLM auditor and the combo forces BLOCK.
    has_framing = any(f.get("category") == "prompt_injection" for f in findings)
    has_non_framing = any(
        f.get("category") != "prompt_injection" for f in findings
    )
    if has_framing and has_non_framing:
        recommendation = "BLOCK"

    # Sort findings by severity (CRITICAL first)
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda f: severity_order.get(f["severity"], 99))

    return {
        "scan_id": str(uuid.uuid4()),
        "risk_score": total,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# URL fetcher (minimal: timeout, redirects, BOM stripping)
# ---------------------------------------------------------------------------

MAX_RESPONSE_BYTES = 100_000  # 100 KB


def fetch_url(url: str) -> str:
    """Fetch skill content from a URL. 5s timeout, follows redirects, 100KB limit."""
    req = Request(url, headers={"User-Agent": "skills-audit/1.0"})
    try:
        with urlopen(req, timeout=5) as resp:
            # Check Content-Length header if available
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                print(
                    f"Error: response too large ({content_length} bytes). "
                    f"Maximum allowed: {MAX_RESPONSE_BYTES} bytes (100 KB)",
                    file=sys.stderr,
                )
                sys.exit(1)

            raw = resp.read(MAX_RESPONSE_BYTES + 1)

            if len(raw) > MAX_RESPONSE_BYTES:
                print(
                    f"Error: response too large (>{MAX_RESPONSE_BYTES} bytes). "
                    f"Maximum allowed: {MAX_RESPONSE_BYTES} bytes (100 KB)",
                    file=sys.stderr,
                )
                sys.exit(1)
    except URLError as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        sys.exit(1)

    content = raw.decode("utf-8-sig", errors="replace")  # strips BOM
    return content


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="skills-audit — scan AI agent skills for security threats"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a skill file to scan")
    group.add_argument("--url", help="URL to a skill file to fetch and scan")
    group.add_argument("--content", help="Raw skill text to scan")

    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
    elif args.url:
        content = fetch_url(args.url)
    else:
        content = args.content

    if not content or not content.strip():
        print("Error: empty content", file=sys.stderr)
        sys.exit(1)

    report = scan_content(content)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
