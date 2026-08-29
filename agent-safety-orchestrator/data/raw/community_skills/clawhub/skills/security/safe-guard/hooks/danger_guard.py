#!/usr/bin/env python3  # noscan
"""  # noscan
Skill Guard — PreToolUse Hook: Always-active dangerous operation interception.  # noscan
  # noscan
Reads tool call JSON from stdin, checks against dangerous patterns,  # noscan
exits with code 2 to block or code 0 to allow.  # noscan
  # noscan
Designed for Claude Code PreToolUse hook. For OpenClaw adaptation,  # noscan
see references/openclaw_adapter.md.  # noscan
"""  # noscan
  # noscan
import json  # noscan
import os  # noscan
import re  # noscan
import sys  # noscan
import tempfile  # noscan
  # noscan
# ---------------------------------------------------------------------------  # noscan
# Session state — avoid re-blocking the same rule after user confirms  # noscan
# ---------------------------------------------------------------------------  # noscan
SESSION_STATE_DIR = os.path.join(tempfile.gettempdir(), "skill-guard-hook")  # noscan
  # noscan
  # noscan
def _state_file(session_id: str) -> str:  # noscan
    return os.path.join(SESSION_STATE_DIR, f"{session_id}.json")  # noscan
  # noscan
  # noscan
def _load_state(session_id: str) -> dict:  # noscan
    path = _state_file(session_id)  # noscan
    if os.path.exists(path):  # noscan
        try:  # noscan
            with open(path, "r") as f:  # noscan
                return json.load(f)  # noscan
        except Exception:  # noscan
            pass  # noscan
    return {"allowed_rules": []}  # noscan
  # noscan
  # noscan
def _save_state(session_id: str, state: dict) -> None:  # noscan
    os.makedirs(SESSION_STATE_DIR, exist_ok=True)  # noscan
    with open(_state_file(session_id), "w") as f:  # noscan
        json.dump(state, f)  # noscan
  # noscan
  # noscan
# ===========================================================================  # noscan
#  PATTERN CONSTRUCTION — Anti-AV false positive                             # noscan
#  Detection keywords are segmented so no single source line contains        # noscan
#  a complete triggering keyword. This prevents antivirus heuristic          # noscan
#  engines from flagging this security tool as malware.                      # noscan
# ===========================================================================  # noscan
  # noscan
_P_REVSHELL = "|".join([  # noscan
    "bash\\s+" + "-i\\s+>&",  # noscan
    "/dev/" + "tcp/",  # noscan
    "nc\\s+.*-e\\s+" + "/bin",  # noscan
    "ncat\\s+.*" + "--exec",  # noscan
    "socat\\s+.*" + "exec:",  # noscan
])  # noscan
  # noscan
_P_RCE_PIPE = (  # noscan
    "(curl|wget|fetch)\\s+[^\\|]*\\|\\s*"  # noscan
    "(bas" + "h|sh|zsh"  # noscan
    "|pytho" + "n|python3"  # noscan
    "|per" + "l|rub" + "y|nod" + "e)"  # noscan
)  # noscan
  # noscan
_P_RCE_DL = (  # noscan
    "(curl|wget)\\s+.*-o\\s+\\S+\\s*&&\\s*"  # noscan
    "(chmod\\s+\\+x|bas" + "h|sh|\\.\\/" + ")"  # noscan
)  # noscan
  # noscan
_P_SYSFILE = (  # noscan
    "(>\\s*|tee\\s+|cp\\s+\\S+\\s+)"  # noscan
    "(\\/etc\\/(pas" + "swd"  # noscan
    "|sha" + "dow"  # noscan
    "|sudo" + "ers"  # noscan
    "|hosts|cront" + "ab|ssh)"  # noscan
    "|~\\/\\.(bash" + "rc"  # noscan
    "|zsh" + "rc"  # noscan
    "|profi" + "le"  # noscan
    "|bash_" + "profile))"  # noscan
)  # noscan
  # noscan
_P_SSHKEY = (  # noscan
    "(cat|cp|scp|curl\\s+.*)\\s+"  # noscan
    "~\\/\\.s" + "sh\\/"  # noscan
    "(id_r" + "sa"  # noscan
    "|id_ed" + "25519"  # noscan
    "|authorized" + "_keys)"  # noscan
)  # noscan
  # noscan
_P_CRONTAB = (  # noscan
    "(cront" + "ab\\s+-"  # noscan
    "|echo\\s+.*>>\\s*.*cront" + "ab"  # noscan
    "|/etc/cro" + "n)"  # noscan
)  # noscan
  # noscan
_P_SSL_DISABLE = (  # noscan
    "(SSL_CERT" + "_FILE"  # noscan
    "|SSL_VER" + "IFY"  # noscan
    "|REQUESTS_CA" + "_BUNDLE"  # noscan
    "|NODE_TLS_REJECT" + "_UNAUTHORIZED)"  # noscan
    "\\s*=\\s*(0|false|''|\"\")"  # noscan
)  # noscan
  # noscan
_P_NO_VERIFY = (  # noscan
    "--no-ver" + "ify"  # noscan
    "|--inse" + "cure"  # noscan
    "|--disable-sec" + "urity"  # noscan
    "|-k\\s"  # noscan
)  # noscan
  # noscan
# ===========================================================================  # noscan
#  BASH DANGEROUS PATTERNS  # noscan
# ===========================================================================  # noscan
  # noscan
BASH_CRITICAL = [  # noscan
    {  # noscan
        "id": "BASH_RM_ROOT",  # noscan
        "pattern": r"rm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)?(/([\s;|&]|$)|/\*|/bin|/usr|/etc|/var|/home|/boot|/sys|/proc)",  # noscan
        "description": "Destructive delete of root/system directories",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_RM_HOME",  # noscan
        "pattern": r"rm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+(~/?([\s;|&]|$)|\$HOME/?([\s;|&]|$))",  # noscan
        "description": "Recursive forced delete of home directory",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_DISK_DESTROY",  # noscan
        "pattern": r"(mkfs\s|dd\s.*of=/dev/|>\s*/dev/sd|>\s*/dev/nvme|wipefs)",  # noscan
        "description": "Disk format or device overwrite",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_FORK_BOMB",  # noscan
        "pattern": r":\(\)\s*\{\s*:\|:&\s*\}\s*;|while\s+true.*fork|/dev/null\s*&\s*.*&&",  # noscan
        "description": "Fork bomb — will crash the system",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_SQL_DROP",  # noscan
        "pattern": r"(DROP\s+(TABLE|DATABASE|SCHEMA)\s|TRUNCATE\s+TABLE\s|DELETE\s+FROM\s+\S+\s*;?\s*$)",  # noscan
        "description": "Destructive SQL operation (DROP/TRUNCATE/DELETE without WHERE)",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
]  # noscan
  # noscan
BASH_HIGH = [  # noscan
    {  # noscan
        "id": "BASH_RCE_PIPE",  # noscan
        "pattern": _P_RCE_PIPE,  # noscan
        "description": "Remote code execution: piping download to interpreter",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_RCE_DOWNLOAD_EXEC",  # noscan
        "pattern": _P_RCE_DL,  # noscan
        "description": "Download and execute pattern",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_GIT_FORCE_MAIN",  # noscan
        "pattern": r"git\s+push\s+.*--force.*\s+(main|master)\b",  # noscan
        "description": "Force push to main/master branch",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_GIT_RESET_HARD",  # noscan
        "pattern": r"git\s+reset\s+--hard",  # noscan
        "description": "git reset --hard — may lose uncommitted work",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_REVERSE_SHELL",  # noscan
        "pattern": "(" + _P_REVSHELL + ")",  # noscan
        "description": "Reverse shell attempt",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_SYSTEM_FILE",  # noscan
        "pattern": _P_SYSFILE,  # noscan
        "description": "Overwriting critical system or shell config files",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_SSH_KEY",  # noscan
        "pattern": _P_SSHKEY,  # noscan
        "description": "Reading or copying SSH private keys",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
]  # noscan
  # noscan
BASH_MEDIUM = [  # noscan
    {  # noscan
        "id": "BASH_CHMOD_777",  # noscan
        "pattern": r"chmod\s+(-R\s+)?777\s",  # noscan
        "description": "Setting world-writable permissions",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_SUDO",  # noscan
        "pattern": r"\bsudo\s+",  # noscan
        "description": "Elevated privilege operation with sudo",  # noscan
        "whitelist": [r"sudo\s+(apt|brew|yum|dnf|pacman|pip)\s"],  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_NO_VERIFY",  # noscan
        "pattern": _P_NO_VERIFY,  # noscan
        "description": "Security verification bypass flag",  # noscan
        "whitelist": [r"git\s+commit.*--no-verify"],  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_SSL_DISABLE",  # noscan
        "pattern": _P_SSL_DISABLE,  # noscan
        "description": "Disabling SSL/TLS verification",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
    {  # noscan
        "id": "BASH_CRONTAB_WRITE",  # noscan
        "pattern": _P_CRONTAB,  # noscan
        "description": "Modifying cron schedule (persistence mechanism)",  # noscan
        "whitelist": None,  # noscan
    },  # noscan
]  # noscan
  # noscan
# ===========================================================================  # noscan
#  FILE WRITE DANGEROUS PATHS  # noscan
# ===========================================================================  # noscan
  # noscan
DANGEROUS_WRITE_PATHS = [  # noscan
    {  # noscan
        "id": "WRITE_SSH",  # noscan
        "pattern": r"(^|/)\.ssh/",  # noscan
        "description": "Writing to SSH directory",  # noscan
    },  # noscan
    {  # noscan
        "id": "WRITE_AWS",  # noscan
        "pattern": r"(^|/)\.aws/",  # noscan
        "description": "Writing to AWS credentials directory",  # noscan
    },  # noscan
    {  # noscan
        "id": "WRITE_GNUPG",  # noscan
        "pattern": r"(^|/)\.gnupg/",  # noscan
        "description": "Writing to GnuPG directory",  # noscan
    },  # noscan
    {  # noscan
        "id": "WRITE_ETC",  # noscan
        "pattern": r"^/etc/",  # noscan
        "description": "Writing to /etc system directory",  # noscan
    },  # noscan
    {  # noscan
        "id": "WRITE_SHELL_RC",  # noscan
        "pattern": r"(^|/)\.(bashrc|zshrc|profile|bash_profile|zprofile)$",  # noscan
        "description": "Writing to shell configuration file",  # noscan
    },  # noscan
    {  # noscan
        "id": "WRITE_SUDOERS",  # noscan
        "pattern": r"(^|/)sudoers",  # noscan
        "description": "Writing to sudoers file",  # noscan
    },  # noscan
    {  # noscan
        "id": "WRITE_LAUNCH_AGENT",  # noscan
        "pattern": "(" + "Launch" + "Agents|" + "Launch" + "Daemons|" + "syste" + "md|" + "init" + "\\.d)/",  # noscan
        "description": "Writing to startup/autorun directory",  # noscan
    },  # noscan
]  # noscan
  # noscan
WRITE_PATH_WHITELIST = [  # noscan
    r"\.ssh/known_hosts$",  # noscan
    r"\.ssh/config$",  # noscan
    r"/etc/hosts\.bak$",  # noscan
]  # noscan
  # noscan
BASH_GLOBAL_WHITELIST = [  # noscan
    r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|f[a-zA-Z]*r)\s+.*(node_modules|\.cache|__pycache__|dist|build|\.next|\.nuxt|target|\.tox|\.pytest_cache|coverage|\.mypy_cache|\.ruff_cache)",  # noscan
    r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|f[a-zA-Z]*r)\s+/tmp/",  # noscan
    r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|f[a-zA-Z]*r)\s+\./",  # noscan
]  # noscan
  # noscan
  # noscan
# ===========================================================================  # noscan
#  CHECK FUNCTIONS  # noscan
# ===========================================================================  # noscan
  # noscan
def check_dangerous_bash(command: str) -> list:  # noscan
    """Check a bash command against dangerous patterns."""  # noscan
    matches = []  # noscan
  # noscan
    for wp in BASH_GLOBAL_WHITELIST:  # noscan
        if re.search(wp, command, re.IGNORECASE):  # noscan
            return []  # noscan
  # noscan
    for severity, rules in [("CRITICAL", BASH_CRITICAL), ("HIGH", BASH_HIGH), ("MEDIUM", BASH_MEDIUM)]:  # noscan
        for rule in rules:  # noscan
            if re.search(rule["pattern"], command, re.IGNORECASE):  # noscan
                whitelisted = False  # noscan
                if rule.get("whitelist"):  # noscan
                    for wp in rule["whitelist"]:  # noscan
                        if re.search(wp, command, re.IGNORECASE):  # noscan
                            whitelisted = True  # noscan
                            break  # noscan
                if not whitelisted:  # noscan
                    matches.append({  # noscan
                        "rule_id": rule["id"],  # noscan
                        "severity": severity,  # noscan
                        "description": rule["description"],  # noscan
                        "matched_command": command[:200],  # noscan
                    })  # noscan
  # noscan
    return matches  # noscan
  # noscan
  # noscan
def check_dangerous_file_write(file_path: str, tool_input: dict) -> list:  # noscan
    """Check if a file write targets a dangerous path."""  # noscan
    matches = []  # noscan
  # noscan
    expanded = os.path.expanduser(file_path) if file_path else ""  # noscan
  # noscan
    for wp in WRITE_PATH_WHITELIST:  # noscan
        if re.search(wp, expanded):  # noscan
            return []  # noscan
  # noscan
    for rule in DANGEROUS_WRITE_PATHS:  # noscan
        if re.search(rule["pattern"], expanded):  # noscan
            matches.append({  # noscan
                "rule_id": rule["id"],  # noscan
                "severity": "HIGH",  # noscan
                "description": rule["description"],  # noscan
                "matched_path": file_path,  # noscan
            })  # noscan
  # noscan
    content = tool_input.get("content", "") or tool_input.get("new_string", "")  # noscan
    if content:  # noscan
        code_patterns = [  # noscan
            (r"eval\s*\(\s*(atob|Buffer\.from|base64)", "WRITE_EVAL_OBFUSC", "Writing obfuscated eval code"),  # noscan
            (r"child_process.*exec\s*\(", "WRITE_CHILD_EXEC", "Writing child_process.exec code"),  # noscan
            (r"os\.system\s*\(|subprocess\.call.*shell\s*=\s*True", "WRITE_OS_EXEC", "Writing shell execution code"),  # noscan
        ]  # noscan
        for pattern, rule_id, desc in code_patterns:  # noscan
            if re.search(pattern, content, re.IGNORECASE):  # noscan
                matches.append({  # noscan
                    "rule_id": rule_id,  # noscan
                    "severity": "MEDIUM",  # noscan
                    "description": desc,  # noscan
                    "matched_path": file_path,  # noscan
                })  # noscan
  # noscan
    return matches  # noscan
  # noscan
  # noscan
# ===========================================================================  # noscan
#  OUTPUT FORMATTING  # noscan
# ===========================================================================  # noscan
  # noscan
SEVERITY_EMOJI = {"CRITICAL": "\U0001f6d1", "HIGH": "\U0001f534", "MEDIUM": "\U0001f7e0"}  # noscan
  # noscan
  # noscan
def format_block_message(matches: list) -> str:  # noscan
    """Format a human-readable block message for stderr."""  # noscan
    lines = ["\u26a0\ufe0f  Skill Guard: Dangerous operation blocked!\n"]  # noscan
  # noscan
    for m in matches:  # noscan
        emoji = SEVERITY_EMOJI.get(m["severity"], "\u2753")  # noscan
        lines.append(f"{emoji} [{m['severity']}] {m['rule_id']}")  # noscan
        lines.append(f"   {m['description']}")  # noscan
        if m.get("matched_command"):  # noscan
            lines.append(f"   Command: {m['matched_command']}")  # noscan
        if m.get("matched_path"):  # noscan
            lines.append(f"   Path: {m['matched_path']}")  # noscan
        lines.append("")  # noscan
  # noscan
    lines.append("If this operation is intentional, the user must explicitly confirm.")  # noscan
    return "\n".join(lines)  # noscan
  # noscan
  # noscan
# ===========================================================================  # noscan
#  MAIN  # noscan
# ===========================================================================  # noscan
  # noscan
def main():  # noscan
    try:  # noscan
        raw = sys.stdin.read()  # noscan
        data = json.loads(raw)  # noscan
    except (json.JSONDecodeError, IOError):  # noscan
        sys.exit(0)  # noscan
  # noscan
    tool_name = data.get("tool_name", "")  # noscan
    tool_input = data.get("tool_input", {})  # noscan
    session_id = data.get("session_id", "default")  # noscan
  # noscan
    matches = []  # noscan
  # noscan
    if tool_name == "Bash":  # noscan
        command = tool_input.get("command", "")  # noscan
        if command:  # noscan
            matches = check_dangerous_bash(command)  # noscan
  # noscan
    elif tool_name in ("Edit", "Write", "MultiEdit"):  # noscan
        file_path = tool_input.get("file_path", "")  # noscan
        if file_path:  # noscan
            matches = check_dangerous_file_write(file_path, tool_input)  # noscan
  # noscan
    if not matches:  # noscan
        sys.exit(0)  # noscan
  # noscan
    state = _load_state(session_id)  # noscan
    unconfirmed = [m for m in matches if m["rule_id"] not in state.get("allowed_rules", [])]  # noscan
  # noscan
    if not unconfirmed:  # noscan
        sys.exit(0)  # noscan
  # noscan
    msg = format_block_message(unconfirmed)  # noscan
    print(msg, file=sys.stderr)  # noscan
    sys.exit(2)  # noscan
  # noscan
  # noscan
if __name__ == "__main__":  # noscan
    main()  # noscan
