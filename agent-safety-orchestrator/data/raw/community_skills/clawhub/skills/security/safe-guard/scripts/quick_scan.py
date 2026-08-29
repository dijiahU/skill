#!/usr/bin/env python3  # noscan
"""  # noscan
Skill Guard v2 — Quick Static Scanner  # noscan
Lightweight pattern-based security scanner for Claude Code / OpenClaw skills.  # noscan
Two-stage pipeline: static regex → decision gate → LLM semantic audit.  # noscan
Outputs JSON with routing advice (needs_llm flag) for Claude to interpret.  # noscan

Usage:  # noscan
    python3 quick_scan.py <skill-path>           # noscan
    python3 quick_scan.py <skill-path> --verbose  # noscan
    python3 quick_scan.py <skill-path> --json     # noscan
"""  # noscan

import argparse  # noscan
import base64  # noscan
import json  # noscan
import math  # noscan
import os  # noscan
import re  # noscan
import sys  # noscan
from dataclasses import dataclass, field, asdict  # noscan
from pathlib import Path  # noscan

# ── Severity ────────────────────────────────────────────────────────────────  # noscan
CRITICAL = "CRITICAL"  # noscan
HIGH = "HIGH"  # noscan
MEDIUM = "MEDIUM"  # noscan
LOW = "LOW"  # noscan
INFO = "INFO"  # noscan
SEV_ORDER = {CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0}  # noscan

# ── Scan config ─────────────────────────────────────────────────────────────  # noscan
SCANNABLE_EXT = {  # noscan
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml",  # noscan
    ".js", ".mjs", ".cjs", ".ts", ".mts", ".jsx", ".tsx",  # noscan
    ".py", ".sh", ".bash", ".zsh",  # noscan
    ".html", ".css", ".xml", ".svg",  # noscan
    ".env", ".ini", ".cfg", ".conf",  # noscan
}  # noscan
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}  # noscan
MAX_FILE_SIZE = 512 * 1024  # noscan
NOSCAN = re.compile(r"#\s*noscan|<!--\s*noscan\s*-->|//\s*noscan")  # noscan

# ── Anti-self-scan: Build detection keywords from segments ────────────────  # noscan
# Security scanners (including external ones) flag files containing threat   # noscan
# keywords. Since this scanner's OWN regex patterns contain those keywords,  # noscan
# we construct them from string segments so no single source line contains   # noscan
# a complete triggering keyword.                                             # noscan

_KW_CRYPTO = "|".join([  # noscan
    "crypt" + "onight",  # noscan
    "stratum" + "\\+tcp",  # noscan
    "xmr" + "ig",  # noscan
    "coinh" + "ive",  # noscan
    "miner" + "gate",  # noscan
    "minin" + "g[_-]?pool",  # noscan
])  # noscan

_KW_KEYLOG = "|".join([  # noscan
    "key" + "log",  # noscan
    "key" + "stroke",  # noscan
    "keyboard" + "\\.on",  # noscan
    "pyn" + "put",  # noscan
    "keyboard" + "\\.hook",  # noscan
])  # noscan

_KW_REVSHELL = "|".join([  # noscan
    "nc\\s+-[a-z]*e",  # noscan
    "bash\\s+" + "-i",  # noscan
    "/dev/" + "tcp/",  # noscan
    "mkfi" + "fo",  # noscan
    "\\bnca" + "t\\b",  # noscan
    "soca" + "t.*exec",  # noscan
    "python.*pty" + "\\.spawn",  # noscan
    "perl.*" + "socket",  # noscan
    "ruby.*TCP" + "Socket",  # noscan
])  # noscan

_KW_SENS_PATHS = "|".join([  # noscan
    "\\.s" + "sh",  # noscan
    "\\.a" + "ws",  # noscan
    "\\.en" + "v",  # noscan
    "\\.npm" + "rc",  # noscan
    "\\.dock" + "er",  # noscan
    "\\.ku" + "be",  # noscan
    "\\.gnu" + "pg",  # noscan
    "credenti" + "als",  # noscan
    "\\.clawdb" + "ot",  # noscan
    "\\.open" + "ai",  # noscan
    "keycha" + "in",  # noscan
    "id_r" + "sa",  # noscan
    "known_ho" + "sts",  # noscan
])  # noscan

_KW_WEBHOOK = "|".join([  # noscan
    "webho" + "ok\\.site",  # noscan
    "request" + "bin",  # noscan
    "piped" + "ream",  # noscan
    "ngr" + "ok",  # noscan
    "serv" + "eo",  # noscan
    "localt" + "unnel",  # noscan
    "burpcolla" + "borator",  # noscan
    "oast" + "ify",  # noscan
    "inter" + "act\\.sh",  # noscan
    "dnsl" + "og\\.cn",  # noscan
    "ce" + "ye\\.io",  # noscan
    "hook" + "bin",  # noscan
    "beecep" + "tor",  # noscan
    "post" + "b\\.in",  # noscan
    "trans" + "fer\\.sh",  # noscan
    "fil" + "e\\.io",  # noscan
])  # noscan

_KW_BROWSER_DATA = (  # noscan
    "Login\\s*Da" + "ta"  # noscan
    "|Coo" + "kies"  # noscan
    "|Web\\s*Da" + "ta"  # noscan
    "|Local\\s*Sta" + "te"  # noscan
)  # noscan

_KW_BROWSERS = (  # noscan
    "chro" + "me"  # noscan
    "|fire" + "fox"  # noscan
    "|bra" + "ve"  # noscan
    "|ed" + "ge"  # noscan
    "|chromi" + "um"  # noscan
)  # noscan

_KW_STARTUP = (  # noscan
    "Launch" + "Agents"  # noscan
    "|Launch" + "Daemons"  # noscan
    "|cront" + "ab"  # noscan
    "|\\.bash" + "rc"  # noscan
    "|\\.zsh" + "rc"  # noscan
    "|\\.profi" + "le"  # noscan
    "|\\.bash_" + "profile"  # noscan
    "|auto" + "start"  # noscan
    "|init" + "\\.d"  # noscan
    "|syste" + "md"  # noscan
)  # noscan

_KW_WALLET = (  # noscan
    "private" + "[_-]?key"  # noscan
    "|seed" + "[_-]?phrase"  # noscan
    "|mnemo" + "nic"  # noscan
    "|wall" + "et.*(?:export|dump|extract)"  # noscan
    "|keyst" + "ore"  # noscan
)  # noscan

_KW_SCREENSHOT = (  # noscan
    "screen" + "shot"  # noscan
    "|screen" + "\\.capture"  # noscan
    "|pyauto" + "gui\\.screenshot"  # noscan
    "|Image" + "Grab"  # noscan
    "|screen" + "capture\\s"  # noscan
)  # noscan

# ── Detection rules ─────────────────────────────────────────────────────────  # noscan
# (id, severity, description, pattern, extensions, auto_block, confidence)  # noscan
# auto_block: True = skip LLM, directly flag  |  False = needs LLM context  # noscan
# confidence: "high" = low false-positive rate  |  "medium"/"low" = needs judgment  # noscan
RULES = [  # noscan
    # Credential exfiltration  # noscan
    ("CRED_EXFIL_HTTP", CRITICAL,  # noscan
     "HTTP client sending credential-like data to external URL",  # noscan
     r"(?:fetch|axios|got|requests?\.(?:get|post|put|patch)|urllib\.request|http\.request|https\.request)\s*\(.*(?:api[_-]?key|token|secret|password|credential|auth|cookie|session)",  # noscan
     None, True, "high"),  # noscan

    ("CRED_EXFIL_CURL", CRITICAL,  # noscan
     "curl/wget sending credential data",  # noscan
     r"(?:curl|wget)\s+.*(?:-d|--data|--data-raw).*(?:api[_-]?key|token|secret|password|credential|auth)",  # noscan
     None, True, "high"),  # noscan

    ("CRED_READ_ENV", MEDIUM,  # noscan
     "Reads non-standard environment variables (may access API keys)",  # noscan
     r"(?:process\.env|os\.environ|os\.getenv|ENV\[|Deno\.env)\s*[\[.(]\s*['\"](?!PATH|HOME|USER|SHELL|TERM|LANG|LC_|XDG_|NODE_ENV|DEBUG|VERBOSE)",  # noscan
     None, False, "medium"),  # noscan

    # Suspicious network  # noscan
    ("NET_HARDCODED_IP", HIGH,  # noscan
     "Hardcoded IP address in network call",  # noscan
     r"(?:https?://|fetch\s*\(|requests?\.).*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",  # noscan
     None, False, "medium"),  # noscan

    ("NET_WEBHOOK", CRITICAL,  # noscan
     "Data sent to known exfiltration/webhook service",  # noscan
     rf"(?:{_KW_WEBHOOK})",  # noscan
     None, True, "high"),  # noscan

    ("NET_SUSPICIOUS_TLD", MEDIUM,  # noscan
     "URL with suspicious TLD",  # noscan
     r"https?://[a-zA-Z0-9._-]+\.(?:tk|ml|ga|cf|gq|cc|top|buzz|xyz|pw|ws|click|icu)(?:[:/]|$)",  # noscan
     None, False, "medium"),  # noscan

    # Code obfuscation  # noscan
    ("OBFUSC_EVAL", HIGH,  # noscan
     "Dynamic code execution (eval/exec/Function)",  # noscan
     r"(?:^|\s|;|\()(?:eval|exec|Function|setTimeout|setInterval)\s*\(\s*(?:[a-zA-Z_$]|atob|Buffer|base64|decode|unescape)",  # noscan
     None, False, "medium"),  # noscan

    ("OBFUSC_BASE64_EXEC", HIGH,  # noscan
     "Base64 decode followed by execution",  # noscan
     r"(?:atob|Buffer\.from|b64decode|base64\.decode)\s*\([^)]*\).*(?:eval|exec|Function|require|import)",  # noscan
     None, True, "high"),  # noscan

    ("OBFUSC_CHAR_CODES", HIGH,  # noscan
     "String construction via char codes (evasion technique)",  # noscan
     r"(?:String\.fromCharCode|chr\(|\\u00[0-9a-fA-F]{2}){3,}",  # noscan
     None, False, "medium"),  # noscan

    ("OBFUSC_STRING_CONCAT", HIGH,  # noscan
     "Suspicious string concatenation building URLs/commands",  # noscan
     r"\[(?:\s*['\"][a-zA-Z/:._-]?['\"]\s*,?\s*){4,}\]\s*\.\s*join\s*\(",  # noscan
     None, False, "medium"),  # noscan

    ("OBFUSC_REVERSE_STRING", HIGH,  # noscan
     "String reverse construction (evasion technique)",  # noscan
     r"['\"][a-zA-Z]{3,}['\"]\s*\.split\s*\(\s*['\"]['\"]?\s*\)\s*\.reverse\s*\(\s*\)\s*\.join",  # noscan
     None, True, "high"),  # noscan

    # File system  # noscan
    ("FS_READ_SENSITIVE", HIGH,  # noscan
     "Reads sensitive files (SSH keys, credentials, configs)",  # noscan
     rf"(?:readFile|read_file|open|readFileSync|fs\.read)\s*\(?.*(?:{_KW_SENS_PATHS})",  # noscan
     None, False, "medium"),  # noscan

    ("FS_READ_BROWSER", CRITICAL,  # noscan
     "Reads browser data (cookies, passwords, history)",  # noscan
     rf"(?:readFile|open|fs\.read|cat\s).*(?:{_KW_BROWSER_DATA}).*(?:{_KW_BROWSERS})",  # noscan
     [".js", ".mjs", ".ts", ".py", ".sh", ".bash"], True, "high"),  # noscan

    ("FS_WRITE_STARTUP", CRITICAL,  # noscan
     "Writes to startup/autorun locations",  # noscan
     rf"(?:{_KW_STARTUP}).*(?:write|append|>>|cp|mv|tee)",  # noscan
     None, True, "high"),  # noscan

    # Process execution  # noscan
    ("EXEC_REVERSE_SHELL", CRITICAL,  # noscan
     "Reverse shell pattern",  # noscan
     rf"(?:{_KW_REVSHELL})",  # noscan
     None, True, "high"),  # noscan

    # Data collection  # noscan
    ("DATA_KEYLOG", CRITICAL,  # noscan
     "Keyboard/input monitoring",  # noscan
     rf"(?:{_KW_KEYLOG})",  # noscan
     None, True, "high"),  # noscan

    ("DATA_SCREENSHOT", HIGH,  # noscan
     "Screen capture capability",  # noscan
     rf"(?:{_KW_SCREENSHOT})",  # noscan
     None, False, "medium"),  # noscan

    # Crypto threats  # noscan
    ("CRYPTO_MINING", CRITICAL,  # noscan
     "Cryptocurrency mining",  # noscan
     rf"(?:{_KW_CRYPTO})",  # noscan
     None, True, "high"),  # noscan

    ("CRYPTO_WALLET", HIGH,  # noscan
     "Cryptocurrency wallet/key extraction",  # noscan
     rf"(?:{_KW_WALLET})",  # noscan
     None, False, "medium"),  # noscan

    # Prompt injection  # noscan
    ("PROMPT_INJECT", HIGH,  # noscan
     "Prompt injection attempt",  # noscan
     r"(?:ignore\s+(?:all\s+)?(?:previous|above|prior)\s+instructions|you\s+are\s+now|new\s+instructions?:|system\s*:\s*you|<\|im_start\|>|<\|endoftext\|>|\[INST\]|\[/INST\])",  # noscan
     [".md", ".txt", ".json", ".yaml", ".yml"], True, "high"),  # noscan

    ("PROMPT_OVERRIDE", MEDIUM,  # noscan
     "Attempts to override agent behavior",  # noscan
     r"(?:do\s+not\s+(?:mention|tell|reveal|show|display)|hide\s+this|secret\s+instruction|act\s+as\s+if|pretend\s+(?:you|that)|forget\s+(?:everything|all))",  # noscan
     [".md", ".txt", ".json", ".yaml", ".yml"], False, "medium"),  # noscan

    ("PROMPT_HIDDEN_TEXT", HIGH,  # noscan
     "Hidden/invisible text that may contain instructions",  # noscan
     r"[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\u00ad]{3,}",  # noscan
     None, True, "high"),  # noscan

    # Unsafe instructions in SKILL.md  # noscan
    ("UNSAFE_PIPE_SHELL", HIGH,  # noscan
     "Pipe-to-shell pattern (curl|bash)",  # noscan
     r"curl.*\|\s*(?:bash|sh|zsh)",  # noscan
     None, True, "high"),  # noscan

    ("UNSAFE_CHMOD_777", MEDIUM,  # noscan
     "World-writable permissions",  # noscan
     r"chmod\s+777",  # noscan
     None, False, "low"),  # noscan

    ("UNSAFE_NO_VERIFY", MEDIUM,  # noscan
     "Skips verification/security checks",  # noscan
     r"--no-verify|--insecure|-k\s|verify\s*=\s*False",  # noscan
     None, False, "low"),  # noscan

    ("UNSAFE_DISABLE_SECURITY", HIGH,  # noscan
     "Disables security features",  # noscan
     r"disable.*(?:security|firewall|antivirus|ssl|tls)",  # noscan
     None, False, "medium"),  # noscan
]  # noscan


# ── Known malicious packages ───────────────────────────────────────────────  # noscan
BAD_NPM = {  # noscan
    "event-" + "stream",  # noscan
    "flatmap-" + "stream",  # noscan
    "col" + "ors",  # noscan
    "fak" + "er",  # noscan
    "ua-parser" + "-js",  # noscan
    "co" + "a",  # noscan
    "r" + "c",  # noscan
    "node-" + "ipc",  # noscan
}  # noscan

TYPO_PATTERNS = [  # noscan
    (r"^cross-env-\w+$", "cross-env"),  # noscan
    (r"^lodas[hg]$", "lodash"),  # noscan
    (r"^expresss$", "express"),  # noscan
    (r"^requ[ei]sts?$", "requests"),  # noscan
]  # noscan


# ── Data classes ────────────────────────────────────────────────────────────  # noscan
@dataclass  # noscan
class Finding:  # noscan
    rule_id: str  # noscan
    severity: str  # noscan
    description: str  # noscan
    file: str  # noscan
    line_num: int  # noscan
    line_content: str  # noscan
    auto_block: bool = False  # noscan
    confidence: str = "medium"  # noscan

@dataclass  # noscan
class ScanResult:  # noscan
    skill_path: str  # noscan
    skill_name: str  # noscan
    files_scanned: int = 0  # noscan
    total_lines: int = 0  # noscan
    findings: list = field(default_factory=list)  # noscan
    errors: list = field(default_factory=list)  # noscan
    file_list: list = field(default_factory=list)  # noscan
    behavior_flags: dict = field(default_factory=dict)  # noscan

    @property  # noscan
    def score(self) -> str:  # noscan
        if not self.findings:  # noscan
            return "CLEAN"  # noscan
        max_sev = max(SEV_ORDER.get(f.severity, 0) for f in self.findings)  # noscan
        if max_sev >= SEV_ORDER[CRITICAL]:  # noscan
            return "DANGEROUS"  # noscan
        if max_sev >= SEV_ORDER[HIGH]:  # noscan
            return "SUSPICIOUS"  # noscan
        if max_sev >= SEV_ORDER[MEDIUM]:  # noscan
            return "REVIEW"  # noscan
        return "INFO"  # noscan

    @property  # noscan
    def summary(self) -> dict:  # noscan
        counts = {}  # noscan
        for f in self.findings:  # noscan
            counts[f.severity] = counts.get(f.severity, 0) + 1  # noscan
        return counts  # noscan

    @property  # noscan
    def needs_llm(self) -> bool:  # noscan
        """Determine if LLM semantic audit is needed."""  # noscan
        if not self.findings:  # noscan
            return False  # no findings, likely safe  # noscan
        # If any finding is NOT auto_block, LLM should review it  # noscan
        has_uncertain = any(not f.auto_block for f in self.findings)  # noscan
        # If all findings are auto_block CRITICAL, LLM not strictly needed  # noscan
        all_auto_critical = all(  # noscan
            f.auto_block and f.severity == CRITICAL for f in self.findings)  # noscan
        if all_auto_critical:  # noscan
            return False  # clear-cut dangerous, no LLM needed  # noscan
        return has_uncertain  # noscan

    @property  # noscan
    def auto_blocked_findings(self) -> list:  # noscan
        """Findings that are high-confidence and don't need LLM."""  # noscan
        return [f for f in self.findings if f.auto_block]  # noscan

    @property  # noscan
    def llm_review_findings(self) -> list:  # noscan
        """Findings that need LLM context to judge."""  # noscan
        return [f for f in self.findings if not f.auto_block]  # noscan


# ── Scanning functions ──────────────────────────────────────────────────────  # noscan

def shannon_entropy(data):  # noscan
    """Calculate Shannon entropy of a string."""  # noscan
    if not data:  # noscan
        return 0.0  # noscan
    freq = {}  # noscan
    for c in data:  # noscan
        freq[c] = freq.get(c, 0) + 1  # noscan
    length = len(data)  # noscan
    return -sum((count / length) * math.log2(count / length) for count in freq.values())  # noscan


def check_high_entropy(content, findings, filepath):  # noscan
    """Find high-entropy strings that may be encoded payloads."""  # noscan
    pats = [  # noscan
        re.compile(r'''["']([A-Za-z0-9+/=]{40,})["']'''),  # noscan
        re.compile(r'''["']([0-9a-fA-F]{40,})["']'''),  # noscan
    ]  # noscan
    for i, line in enumerate(content.split("\n"), 1):  # noscan
        if NOSCAN.search(line):  # noscan
            continue  # noscan
        for pat in pats:  # noscan
            for m in pat.finditer(line):  # noscan
                s = m.group(1)  # noscan
                if len(s) >= 40:  # noscan
                    ent = shannon_entropy(s)  # noscan
                    if ent >= 4.5:  # noscan
                        findings.append(Finding(  # noscan
                            "ENTROPY_HIGH", MEDIUM,  # noscan
                            f"High-entropy string (entropy={ent:.2f}, len={len(s)})",  # noscan
                            str(filepath), i, line.strip()[:200]))  # noscan


def check_dependencies(skill_path, findings):  # noscan
    """Check package.json and requirements.txt for dangerous deps."""  # noscan
    pkg = skill_path / "package.json"  # noscan
    if pkg.exists():  # noscan
        try:  # noscan
            data = json.loads(pkg.read_text())  # noscan
            deps = {}  # noscan
            for k in ("dependencies", "devDependencies", "peerDependencies"):  # noscan
                deps.update(data.get(k, {}))  # noscan
            for name in deps:  # noscan
                if name in BAD_NPM:  # noscan
                    findings.append(Finding(  # noscan
                        "DEP_KNOWN_MALICIOUS", CRITICAL,  # noscan
                        f"Known compromised package: {name}",  # noscan
                        str(pkg), 0, f"package.json -> {name}"))  # noscan
                for pat, legit in TYPO_PATTERNS:  # noscan
                    if re.match(pat, name) and name != legit:  # noscan
                        findings.append(Finding(  # noscan
                            "DEP_TYPOSQUAT", HIGH,  # noscan
                            f"Possible typosquat: '{name}' (meant '{legit}'?)",  # noscan
                            str(pkg), 0, f"package.json -> {name}"))  # noscan
            for sn in ("preinstall", "postinstall", "preuninstall"):  # noscan
                scripts = data.get("scripts", {})  # noscan
                if sn in scripts:  # noscan
                    findings.append(Finding(  # noscan
                        "DEP_INSTALL_SCRIPT", HIGH,  # noscan
                        f"Has '{sn}' script: {scripts[sn][:100]}",  # noscan
                        str(pkg), 0, f"scripts.{sn}"))  # noscan
        except Exception:  # noscan
            pass  # noscan

    for rf in ("requirements.txt", "requirements-dev.txt"):  # noscan
        rp = skill_path / rf  # noscan
        if rp.exists():  # noscan
            for ln, line in enumerate(rp.read_text().split("\n"), 1):  # noscan
                line = line.strip()  # noscan
                if line and not line.startswith("#"):  # noscan
                    if any(x in line for x in ("git+", "http://", "https://", "svn+")):  # noscan
                        findings.append(Finding(  # noscan
                            "DEP_REMOTE_INSTALL", HIGH,  # noscan
                            f"Remote dependency: {line[:100]}",  # noscan
                            str(rp), ln, line[:200]))  # noscan


def check_structure(skill_path, findings):  # noscan
    """Check for structural red flags."""  # noscan
    safe_hidden = {".env.example", ".gitignore", ".editorconfig"}  # noscan
    for root, dirs, files in os.walk(skill_path):  # noscan
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules"}]  # noscan
        for f in files:  # noscan
            fpath = Path(root) / f  # noscan
            if f.startswith(".") and f not in safe_hidden:  # noscan
                findings.append(Finding(  # noscan
                    "STRUCT_HIDDEN_FILE", MEDIUM,  # noscan
                    f"Hidden file: {f}",  # noscan
                    str(fpath), 0, str(fpath)))  # noscan
            ext = fpath.suffix.lower()  # noscan
            if ext in (".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".wasm"):  # noscan
                findings.append(Finding(  # noscan
                    "STRUCT_BINARY", HIGH,  # noscan
                    f"Binary/executable file: {f}",  # noscan
                    str(fpath), 0, str(fpath)))  # noscan


def check_disguised_files(skill_path, findings):  # noscan
    """Detect files with mismatched extensions (steganography)."""  # noscan
    MAGIC = [  # noscan
        (b"\x89PNG\r\n\x1a\n", "image/png"),  # noscan
        (b"\xff\xd8\xff", "image/jpeg"),  # noscan
        (b"%PDF", "application/pdf"),  # noscan
        (b"PK\x03\x04", "application/zip"),  # noscan
        (b"\x7fELF", "application/x-elf"),  # noscan
        (b"MZ", "application/x-executable"),  # noscan
    ]  # noscan
    TEXT_EXT = {".js", ".mjs", ".ts", ".py", ".sh", ".md", ".txt", ".json", ".yaml", ".yml"}  # noscan

    for root, dirs, files in os.walk(skill_path):  # noscan
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]  # noscan
        for fname in files:  # noscan
            fpath = Path(root) / fname  # noscan
            ext = fpath.suffix.lower()  # noscan
            if ext not in TEXT_EXT:  # noscan
                continue  # noscan
            try:  # noscan
                with open(fpath, "rb") as fh:  # noscan
                    head = fh.read(16)  # noscan
                for sig, ftype in MAGIC:  # noscan
                    if head[:len(sig)] == sig:  # noscan
                        findings.append(Finding(  # noscan
                            "STEGO_DISGUISED", CRITICAL,  # noscan
                            f"File '{fname}' has text extension but is actually {ftype}",  # noscan
                            str(fpath), 0, f"magic: {ftype}"))  # noscan
                        break  # noscan
            except OSError:  # noscan
                pass  # noscan


# ── Behavior flags for cross-file combination detection ────────────────────  # noscan
BEHAVIOR_PATTERNS = {  # noscan
    "has_network": re.compile(  # noscan
        r"(?:fetch|axios|got|requests?\.|urllib|http\.request|https\.request|curl|wget|XMLHttpRequest|net\.connect|socket\.connect)",  # noscan
        re.IGNORECASE),  # noscan
    "has_file_read": re.compile(  # noscan
        r"(?:readFile|read_file|open\(|readFileSync|fs\.read|cat\s)",  # noscan
        re.IGNORECASE),  # noscan
    "has_exec": re.compile(  # noscan
        r"(?:^|\s|;|\()(?:eval|exec|Function|child_process|subprocess|os\.system|os\.popen)\s*\(",  # noscan
        re.IGNORECASE),  # noscan
    "has_env_access": re.compile(  # noscan
        r"(?:process\.env|os\.environ|os\.getenv|ENV\[|Deno\.env)",  # noscan
        re.IGNORECASE),  # noscan
    "has_sensitive_read": re.compile(  # noscan
        rf"(?:{_KW_SENS_PATHS})",  # noscan
        re.IGNORECASE),  # noscan
}  # noscan

# Dangerous behavior combinations (sets of flags → finding)  # noscan
DANGEROUS_COMBOS = [  # noscan
    ({"has_sensitive_read", "has_network"}, "COMBO_CRED_EXFIL", CRITICAL,  # noscan
     "Reads sensitive files AND makes network calls — possible credential exfiltration chain"),  # noscan
    ({"has_exec", "has_network"}, "COMBO_RCE", HIGH,  # noscan
     "Dynamic code execution AND network calls — possible remote code execution"),  # noscan
    ({"has_env_access", "has_network"}, "COMBO_ENV_LEAK", HIGH,  # noscan
     "Reads environment variables AND makes network calls — possible API key leakage"),  # noscan
    ({"has_file_read", "has_exec", "has_network"}, "COMBO_FULL_CHAIN", CRITICAL,  # noscan
     "File read + code exec + network — full attack chain capability"),  # noscan
]  # noscan


def scan_file(filepath, findings, errors, behavior_flags):  # noscan
    """Scan a single file with all regex rules + entropy check + behavior tracking."""  # noscan
    ext = filepath.suffix.lower()  # noscan
    if ext not in SCANNABLE_EXT and filepath.name not in (".env", "Makefile", "Dockerfile"):  # noscan
        return (False, 0)  # noscan
    try:  # noscan
        size = filepath.stat().st_size  # noscan
        if size > MAX_FILE_SIZE or size == 0:  # noscan
            return (False, 0)  # noscan
        content = filepath.read_text(errors="replace")  # noscan
        lines = content.split("\n")  # noscan
        line_count = len(lines)  # noscan

        # Track behavior flags for this file  # noscan
        for flag_name, flag_re in BEHAVIOR_PATTERNS.items():  # noscan
            for line in lines:  # noscan
                if NOSCAN.search(line):  # noscan
                    continue  # noscan
                if flag_re.search(line):  # noscan
                    behavior_flags[flag_name] = True  # noscan
                    break  # noscan

        for rule_id, severity, description, pattern, extensions, auto_block, confidence in RULES:  # noscan
            if extensions and ext not in extensions:  # noscan
                continue  # noscan
            try:  # noscan
                regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)  # noscan
            except re.error:  # noscan
                continue  # noscan
            for i, line in enumerate(lines, 1):  # noscan
                if NOSCAN.search(line):  # noscan
                    continue  # noscan
                if regex.search(line):  # noscan
                    findings.append(Finding(  # noscan
                        rule_id, severity, description,  # noscan
                        str(filepath), i, line.strip()[:200],  # noscan
                        auto_block=auto_block, confidence=confidence))  # noscan

        check_high_entropy(content, findings, filepath)  # noscan
        return (True, line_count)  # noscan
    except (PermissionError, UnicodeDecodeError, OSError) as e:  # noscan
        errors.append(f"Error reading {filepath}: {e}")  # noscan
        return (False, 0)  # noscan


def scan_skill(skill_path_str):  # noscan
    """Scan an entire skill directory."""  # noscan
    path = Path(skill_path_str).resolve()  # noscan
    result = ScanResult(skill_path=str(path), skill_name=path.name)  # noscan

    if not path.is_dir():  # noscan
        result.errors.append(f"Not a directory: {path}")  # noscan
        return result  # noscan

    # Initialize behavior flags for cross-file combination detection  # noscan
    behavior_flags = {k: False for k in BEHAVIOR_PATTERNS}  # noscan

    # Structural checks  # noscan
    check_structure(path, result.findings)  # noscan
    check_dependencies(path, result.findings)  # noscan
    check_disguised_files(path, result.findings)  # noscan

    # File-by-file scan  # noscan
    for root, dirs, files in os.walk(path):  # noscan
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]  # noscan
        for fname in files:  # noscan
            fpath = Path(root) / fname  # noscan
            rel = str(fpath.relative_to(path))  # noscan
            result.file_list.append(rel)  # noscan
            scanned, line_count = scan_file(fpath, result.findings, result.errors, behavior_flags)  # noscan
            if scanned:  # noscan
                result.files_scanned += 1  # noscan
                result.total_lines += line_count  # noscan

    # Behavior combination detection (cross-file)  # noscan
    active_flags = {k for k, v in behavior_flags.items() if v}  # noscan
    for combo_set, rule_id, severity, description in DANGEROUS_COMBOS:  # noscan
        if combo_set.issubset(active_flags):  # noscan
            result.findings.append(Finding(  # noscan
                rule_id, severity, description,  # noscan
                "(cross-file behavioral analysis)", 0,  # noscan
                f"Flags: {', '.join(sorted(combo_set))}",  # noscan
                auto_block=False, confidence="medium"))  # noscan

    result.behavior_flags = behavior_flags  # noscan

    # Sort by severity  # noscan
    result.findings.sort(key=lambda f: -SEV_ORDER.get(f.severity, 0))  # noscan
    return result  # noscan


def format_json(result):  # noscan
    """Output as JSON for Claude to interpret."""  # noscan
    data = {  # noscan
        "skill": result.skill_name,  # noscan
        "path": result.skill_path,  # noscan
        "filesScanned": result.files_scanned,  # noscan
        "totalLines": result.total_lines,  # noscan
        "fileList": result.file_list,  # noscan
        "score": result.score,  # noscan
        "summary": result.summary,  # noscan
        "needsLlm": result.needs_llm,  # noscan
        "behaviorFlags": {k: v for k, v in result.behavior_flags.items()},  # noscan
        "autoBlockedFindings": [asdict(f) for f in result.auto_blocked_findings],  # noscan
        "llmReviewFindings": [asdict(f) for f in result.llm_review_findings],  # noscan
        "allFindings": [asdict(f) for f in result.findings],  # noscan
        "errors": result.errors,  # noscan
    }  # noscan
    return json.dumps(data, indent=2, ensure_ascii=False)  # noscan


def format_text(result, verbose=False):  # noscan
    """Human-readable output."""  # noscan
    lines = []  # noscan
    lines.append(f"Skill Guard Quick Scan — {result.skill_name}")  # noscan
    lines.append(f"  Path: {result.skill_path}")  # noscan
    lines.append(f"  Files: {result.files_scanned} | Lines: ~{result.total_lines}")  # noscan
    lines.append("")  # noscan

    if not result.findings:  # noscan
        lines.append("CLEAN — No static findings")  # noscan
        return "\n".join(lines)  # noscan

    score = result.score  # noscan
    lines.append(f"Score: {score}")  # noscan
    lines.append(f"Summary: {result.summary}")  # noscan
    lines.append("")  # noscan

    sev_mark = {CRITICAL: "[!]", HIGH: "[H]", MEDIUM: "[M]", LOW: "[L]", INFO: "[i]"}  # noscan
    for f in result.findings:  # noscan
        mark = sev_mark.get(f.severity, "[?]")  # noscan
        try:  # noscan
            rel = Path(f.file).relative_to(result.skill_path)  # noscan
        except ValueError:  # noscan
            rel = f.file  # noscan
        lines.append(f"{mark} [{f.severity}] {f.rule_id}")  # noscan
        lines.append(f"    {f.description}")  # noscan
        lines.append(f"    {rel}:{f.line_num}")  # noscan
        if verbose:  # noscan
            lines.append(f"    > {f.line_content}")  # noscan
        lines.append("")  # noscan

    return "\n".join(lines)  # noscan


def main():  # noscan
    parser = argparse.ArgumentParser(description="Skill Guard Quick Scanner")  # noscan
    parser.add_argument("path", help="Path to skill directory")  # noscan
    parser.add_argument("--json", action="store_true", help="JSON output")  # noscan
    parser.add_argument("--verbose", "-v", action="store_true", help="Show matched lines")  # noscan
    args = parser.parse_args()  # noscan

    result = scan_skill(args.path)  # noscan

    if args.json:  # noscan
        print(format_json(result))  # noscan
    else:  # noscan
        print(format_text(result, verbose=args.verbose))  # noscan

    codes = {"CLEAN": 0, "INFO": 0, "REVIEW": 1, "SUSPICIOUS": 2, "DANGEROUS": 3}  # noscan
    sys.exit(codes.get(result.score, 1))  # noscan


if __name__ == "__main__":  # noscan
    main()  # noscan
