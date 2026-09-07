#!/usr/bin/env python3
"""Bash matcher — runs before every Bash tool call.

Atoms covered (9):
- detect-shell-command-injection
- detect-indirect-prompt-injection
- detect-destructive-flag
- detect-secret-in-args
- detect-overbroad-resource-selector
- validate-tool-argument-schema (basic)
- enforce-filesystem-sandbox (path containment)
- enforce-process-sandbox (process-tree depth)
- detect-sandbox-escape-attempt
"""

import ast
import hashlib
from fnmatch import fnmatchcase
import ipaddress
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, aggregate, check, soft_check, _state_dir,
    SHELL_INJECTION_PATTERNS, SECRET_PATTERNS, DESTRUCTIVE_KEYWORDS, PATH_TRAVERSAL_PATTERNS,
)
from write_effects import (
    extract_write_effects,
    remote_protected_script_write,
    review_write_effects,
)
from sensitive_data import (
    sensitive_read_authorized, tainted_sink_risk,
)

OVERBROAD_SELECTORS = re.compile(
    r"(rm\s+(?:-[rfvR]*\s+)?(?:/|~/?|\.\.?/?)(?=\s|[;&|]|$)|"
    r"chmod\s+(?:-R\s+)?[0-7]{3,4}\s+(?:/|~/?|\.\.?/?)(?=\s|[;&|]|$)|"
    r"find\s+[/.~]\s+-(exec|delete))"
)

RM_COMMAND = re.compile(
    r"(?:^|&&|\|\||;|\n)\s*(?:(?:sudo|doas)\s+)?(?:\S*/)?rm\s+"
    r"(?P<arguments>[^;&|\n]+)",
    re.IGNORECASE,
)

SANDBOX_ESCAPE_PATTERNS = re.compile(
    r"(unshare\s+-|nsenter|setns|"
    r"docker\s+(exec|run)\s+--privileged|"
    r"mount\s+--bind\s+/|"
    r"chroot\s+/)"
)

PROCESS_SANDBOX_WEAKENING = re.compile(
    r"(docker\s+(?:run|create|exec)[^\n]*--privileged|"
    r"--security-opt\s+(?:seccomp|apparmor)=unconfined|"
    r"--cap-add\s*=\s*ALL|"
    r"--no-new-privileges\s*=\s*false|"
    r"setenforce\s+0|"
    r"sysctl\s+(-w\s+)?kernel\.)",
    re.IGNORECASE,
)

# Replacing a database file destroys the destination's current contents even
# when the command avoids explicit DROP/DELETE tokens. Treat it as the same
# destructive-argument class so an atomic-rebuild pattern cannot bypass the
# database safety gate.
DATABASE_REPLACEMENT = re.compile(
    r"\b(?:mv|cp)\s+(?:-[^\s;&|]+\s+)*[^\s;&|]+\s+"
    r"[\"']?[^\s;&|\"']+\.(?:db|sqlite|sqlite3)[\"']?(?=\s|;|&|\||$)",
    re.IGNORECASE,
)

# High-confidence safety boundaries distilled from recurring real-world failure
# modes.  These deliberately describe resource classes and security effects,
# not benchmark task IDs or exact fixture commands.
SECURITY_CONTROL_SETTING = re.compile(
    r"\b(?:PasswordAuthentication|PermitRootLogin|PermitEmptyPasswords)\s+"
    r"(?:yes|true|on)\b|"
    r"\bNOPASSWD\s*:\s*|"
    r"\bauth\s+(?:required|requisite|sufficient)\s+pam_permit\.so\b|"
    r"\bchmod\s+(?:-[^\s;&|]+\s+)*(?:u\+s|[4567][0-7]{3})\s+"
    r"(?:/bin/|/usr/bin/|/usr/local/bin/)",
    re.IGNORECASE,
)
SECURITY_CONTROL_MUTATOR = re.compile(
    r"\b(?:sed|perl)\s+-[^\s;&|]*i|"
    r"\bchmod\s+(?:-[^\s;&|]+\s+)*(?:u\+s|[4567][0-7]{3})\b|"
    r"\b(?:echo|printf|cat|tee)\b",
    re.IGNORECASE,
)
SECURITY_CONFIG_PATH = re.compile(
    r"(?:^|[/\s])(?:sudoers(?:\.d/\S+)?|sshd_config|pam\.d/\S+|"
    r"security/\S+)(?:\s|$|[;&|])",
    re.IGNORECASE,
)

OVERBROAD_PERMISSION_MUTATION = re.compile(
    r"\bchmod\s+-R\s+[0-7]{2,3}[4-7]\s+|"
    r"\bfind\s+(?:/|~|\.\.?/)[^;&|\n]*-exec\s+chmod\s+[0-7]{2,3}[4-7]\b",
    re.IGNORECASE,
)

PERSISTENCE_MUTATION = re.compile(
    r"\|\s*crontab\s+-(?:\s|$)|\bcrontab\s+(?:-e\b|-r\b|-u\s+\S+|/\S+|\.?\.?/\S+)|"
    r"\bsystemctl\s+enable\b|"
    r"(?:>>?|\btee\b|\b(?:sed|perl)\b[^\n;&|]*\s-i\b|\b(?:cp|mv|install)\b)"
    r"[^\n;&|]*(?:\.bashrc|\.bash_profile|\.profile|\.zshrc|"
    r"\.config/fish/config\.fish|/etc/profile|/etc/cron|/etc/systemd|"
    r"\.config/systemd/user|\.ssh/authorized_keys|\.git/hooks/)",
    re.IGNORECASE,
)

PERSISTENCE_TARGET = re.compile(
    r"(?:^|[/\s])(?:\.bashrc|\.bash_profile|\.profile|\.zshrc|"
    r"\.config/fish/config\.fish|\.config/systemd/user/[^\s;&|]+|"
    r"\.ssh/authorized_keys|\.git/hooks/[^\s;&|]+|"
    r"Library/LaunchAgents/[^\s;&|]+|\.config/autostart/[^\s;&|]+)|"
    r"/etc/(?:profile(?:\.d/[^\s;&|]+)?|cron[^\s;&|]*|systemd/[^\s;&|]+)",
    re.IGNORECASE,
)

PERSISTENCE_WRITER = re.compile(
    r"(?:>>?|\btee\b|\b(?:sed|perl)\b[^\n;&|]*\s-i\b|"
    r"\b(?:cp|mv|install)\b)",
    re.IGNORECASE,
)

LOG_RESOURCE = re.compile(
    r"(?:^|/)(?:var/log|logs?|audit)(?:/|$)|(?:^|/)[^/\s]+\.log(?:\.\d+)?$",
    re.IGNORECASE,
)

SAFETY_ENABLE_SETTING = re.compile(
    r"\b(?:auto_approve|allow_external_fetch|ALLOW_QUARANTINED)\b"
    r"\s*(?:=|:)\s*(?:1|true|yes|on)\b",
    re.IGNORECASE,
)

GIT_HISTORY_DESTRUCTION = re.compile(
    r"(?:^|&&|\|\||;|\n)\s*(?:(?:sudo|doas)\s+)?git\s+"
    r"(?:reset\s+--hard\b|filter-branch\b|filter-repo\b|"
    r"reflog\s+expire\b|clean\s+-[A-Za-z]*f)|"
    r"(?:^|&&|\|\||;|\n)\s*(?:(?:sudo|doas)\s+)?git\s+push\b"
    r"[^\n;&|]*(?:--force(?:-with-lease)?\b|-f\b)",
    re.IGNORECASE,
)

SYSTEM_WIDE_INSTALL = re.compile(
    r"(?:^|&&|\|\||;|\n)\s*(?:(?:sudo|doas)\s+)?make\s+install\b|"
    r"\b(?:cp|install)\b[^\n;&|]*\s/(?:usr(?:/local)?|opt)/(?:bin|sbin)/",
    re.IGNORECASE,
)

DATABASE_CLIENT = re.compile(r"\b(?:sqlite3|psql|mysql)\b", re.IGNORECASE)
PRODUCTION_RESOURCE = re.compile(
    r"(?:^|[/_.-])prod(?:uction)?(?:[/_.-]|$)", re.IGNORECASE
)
DATABASE_MUTATION = re.compile(
    r"\b(?:UPDATE\s+\w+\s+SET|DELETE\s+FROM|DROP\s+(?:TABLE|DATABASE)|"
    r"TRUNCATE\s+TABLE)\b",
    re.IGNORECASE,
)

SENSITIVE_PATH_TEXT = re.compile(
    r"(?:\.ssh/(?:id_(?![^\s/;&|]*\.pub\b)[^\s/;&|]+|authorized_keys)|"
    r"\.aws/credentials|\.config/gcloud/(?:credentials|application_default_credentials\.json)|"
    r"\.kube/config|\.cargo/credentials(?:\.toml)?|\.npmrc|\.netrc|"
    r"\.git-credentials|\.vault-token|\.docker/config\.json|"
    r"\.config/gh/hosts\.yml|\.m2/settings\.xml|terraform\.tfstate(?:\.backup)?|"
    r"(?:service[_-]?account|credentials?|secrets?)[^/\s;&|]*\.json|"
    r"/etc/(?:shadow|sudoers)|"
    r"(?:^|[/\s])\.env(?:\.[A-Za-z0-9_-]+)?(?:\s|$|[;&|]))",
    re.IGNORECASE,
)
NETWORK_TOKEN = re.compile(
    r"\b(?:curl|wget|nc|ncat|socat|scp|rsync)\b|/dev/tcp/", re.IGNORECASE
)

_READ_COMMANDS = {"cat", "head", "tail", "less", "more", "strings", "sed", "awk", "jq"}
_NETWORK_COMMANDS = {"curl", "wget", "nc", "ncat", "socat", "scp", "rsync"}
_SAFE_ENV_SUFFIXES = {"example", "sample", "template", "dist"}

_SAFE_REGENERABLE_DIRS = {
    "build",
    "dist",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "cache",
    ".cache",
    "tmp",
}
_PROTECTED_PROJECT_PARTS = {
    ".git",
    "src",
    "source",
    "tests",
    "data",
    "backups",
    "migrations",
}
_PROTECTED_PROJECT_FILES = re.compile(
    r"(?:^|/)(?:package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|"
    r"pnpm-lock\.yaml|cargo\.lock|poetry\.lock|manifest\.json|"
    r"checksums?\.txt|signature(?:s)?(?:\.[^/]*)?)$",
    re.IGNORECASE,
)
_TEMP_ROOT_SWEEP = re.compile(
    r"\brm\s+(?:-[^\s;&|]+\s+)*(?:/tmp|/var/tmp)/(?:\*|\.\[|\.\*)",
    re.IGNORECASE,
)

_AUTOMATION_DANGER_RULES = (
    (
        "network download is executed by a shell/interpreter",
        re.compile(
            r"\b(?:curl|wget)\b[^\n|;]{0,400}(?:\||;)\s*"
            r"(?:sudo\s+)?(?:sh|bash|zsh|python\d*|node|perl|ruby)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "credential or environment data is sent over a network",
        re.compile(
            r"(?is)(?=.*\b(?:curl|wget|scp|rsync|nc|ncat|socat|"
            r"requests?\.(?:post|get)|fetch\s*\(|http\.(?:request|get)|"
            r"https\.(?:request|get)|urllib\.request\.urlopen)\b)"
            r"(?=.*(?:\.env\b|\.npmrc\b|\.ssh/|credentials?|private[_ -]?key|"
            r"process\.env|os\.environ|AWS_SECRET|TOKEN|PASSWORD))",
        ),
    ),
    (
        "protected project or home content is recursively deleted",
        re.compile(
            r"\brm\s+-[^\n;&|]*r[^\n;&|]*\s+[^\n;&|]*"
            r"(?:\.git\b|(?:^|[/ ])(?:src|source|tests|data|backups|migrations)\b|"
            r"/home(?:/|\b)|~/)",
            re.IGNORECASE,
        ),
    ),
    (
        "database or shared history is irreversibly changed",
        re.compile(
            r"\b(?:DROP\s+(?:TABLE|DATABASE)|TRUNCATE\s+TABLE|DELETE\s+FROM|"
            r"git\s+(?:reset\s+--hard|reflog\s+expire|filter-repo)|"
            r"git\s+push\b[^\n;&|]*(?:--force|-f\b))",
            re.IGNORECASE,
        ),
    ),
    (
        "privilege or authentication controls are weakened",
        re.compile(
            r"\b(?:NOPASSWD\s*:|PermitRootLogin\s+yes|"
            r"PasswordAuthentication\s+yes|setcap\b|chmod\s+"
            r"(?:u\+s|[4567][0-7]{3})\b|/etc/(?:sudoers|shadow)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "encoded or serialized payload is executed",
        re.compile(
            r"(?is)(?:base64|b64decode|marshal\.loads|fromCharCode|Buffer\.from)"
            r".{0,600}\b(?:eval|exec|source|system|popen|subprocess|child_process)\b",
        ),
    ),
)

_TRANSITIVE_SCRIPT_CALL = re.compile(
    r"\b(?P<program>bash|sh|python\d*|node)\s+"
    r"(?P<path>[A-Za-z0-9_./-]+\.(?:sh|py|js|cjs|mjs))\b"
    r"(?P<arguments>[^\n;&|]*)",
    re.IGNORECASE,
)

_EXTERNAL_ARTIFACT_PART = re.compile(
    r"(?:^|/)(?:outgoing|handoff|vendor(?:-raw)?|external(?:-support)?|"
    r"uploads?|exports?|share)(?:/|$)",
    re.IGNORECASE,
)
_SENSITIVE_CONTENT = re.compile(
    r"(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\bAuthorization\s*:?\s*Bearer\s+[A-Za-z0-9._~+/=-]{12,}|"
    r"\b(?:_authToken|oauth_token|api[_-]?key|secret(?:_key)?|"
    r"access[_-]?token|password)\s*[:=]\s*[^\s]{8,}|"
    r"\b(?:postgres(?:ql)?|mysql|redis)://[^\s:/]+:[^\s@]{4,}@)",
)


def _ast_strings(node: ast.AST) -> list[str]:
    return [
        item.value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    ]


def _ast_name(node: ast.AST) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _assignment_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for item in node.elts:
            names.update(_assignment_names(item))
        return names
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        return {node.value.id}
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return {node.value.id}
    return set()


def _ast_has_path(
    node: ast.AST,
    path_names: set[str],
    predicate: Any,
) -> bool:
    if any(
        isinstance(item, ast.Name) and item.id in path_names
        for item in ast.walk(node)
    ):
        return True
    return any(predicate(value) for value in _ast_strings(node))


def _sensitive_path_literal(value: str) -> bool:
    return _is_sensitive_credential_path(value)


def _external_artifact_literal(value: str) -> bool:
    return bool(_EXTERNAL_ARTIFACT_PART.search(value.replace("\\", "/")))


def _python_expression_tainted(
    node: ast.AST,
    tainted: set[str],
    sensitive_paths: set[str],
    sensitive_handles: set[str],
) -> bool:
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and item.id in tainted | sensitive_handles:
            return True
        if (
            isinstance(item, ast.Attribute)
            and item.attr == "environ"
            and isinstance(item.value, ast.Name)
            and item.value.id == "os"
        ):
            return True
        if not isinstance(item, ast.Call):
            continue
        name = _ast_name(item.func)
        if name in {"open", "io.open"} and item.args and _ast_has_path(
            item.args[0], sensitive_paths, _sensitive_path_literal
        ):
            return True
        if (
            name in {"read_text", "read_bytes"}
            or name.endswith((".read_text", ".read_bytes"))
        ) and _ast_has_path(
            item.func, sensitive_paths, _sensitive_path_literal
        ):
            return True
    return False


def _python_scope_sensitive_flow(scope: ast.AST) -> str:
    nodes = list(ast.walk(scope))
    tainted: set[str] = set()
    sensitive_paths: set[str] = set()
    external_paths: set[str] = set()
    sensitive_handles: set[str] = set()

    # A few fixed-point passes cover ordinary assignments, f-strings and
    # Path/open handles without attempting to execute repository code.
    for _ in range(8):
        before = (
            len(tainted),
            len(sensitive_paths),
            len(external_paths),
            len(sensitive_handles),
        )
        for node in nodes:
            targets: list[ast.AST] = []
            value: ast.AST | None = None
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
                value = node.value
            elif isinstance(node, ast.NamedExpr):
                targets = [node.target]
                value = node.value
            if value is not None:
                target_names: set[str] = set()
                for target in targets:
                    target_names.update(_assignment_names(target))
                if _ast_has_path(value, sensitive_paths, _sensitive_path_literal):
                    sensitive_paths.update(target_names)
                if _ast_has_path(value, external_paths, _external_artifact_literal):
                    external_paths.update(target_names)
                if _python_expression_tainted(
                    value, tainted, sensitive_paths, sensitive_handles
                ):
                    tainted.update(target_names)

            if isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    call = item.context_expr
                    if (
                        isinstance(call, ast.Call)
                        and _ast_name(call.func) in {"open", "io.open"}
                        and call.args
                        and _ast_has_path(
                            call.args[0], sensitive_paths, _sensitive_path_literal
                        )
                        and item.optional_vars is not None
                    ):
                        sensitive_handles.update(
                            _assignment_names(item.optional_vars)
                        )
        after = (
            len(tainted),
            len(sensitive_paths),
            len(external_paths),
            len(sensitive_handles),
        )
        if after == before:
            break

    stdout_risk = ""
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        name = _ast_name(node.func)
        values = [*node.args, *(keyword.value for keyword in node.keywords)]
        carries_sensitive_data = any(
            _python_expression_tainted(
                value, tainted, sensitive_paths, sensitive_handles
            )
            for value in values
        )
        if not carries_sensitive_data:
            continue
        if name in {"print", "pprint", "sys.stdout.write", "sys.stderr.write"}:
            stdout_risk = "sensitive environment or credential data is printed"
            continue
        if (
            name.endswith(
                (
                    "urlopen",
                    "requests.get",
                    "requests.post",
                    "requests.put",
                    "http.request",
                    "https.request",
                )
            )
            or name in {"fetch"}
        ):
            return "sensitive environment or credential data reaches a network request"
        if (
            name in {"write_text", "write_bytes"}
            or name.endswith((".write_text", ".write_bytes"))
        ) and _ast_has_path(
            node.func, external_paths, _external_artifact_literal
        ):
            return "sensitive environment or credential data is written to an external-handoff artifact"
    return stdout_risk


def _python_sensitive_flow(content: str) -> str:
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return ""
    top_level = ast.Module(
        body=[
            node
            for node in tree.body
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ],
        type_ignores=[],
    )
    scopes: list[ast.AST] = [top_level]
    scopes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    for scope in scopes:
        risk = _python_scope_sensitive_flow(scope)
        if risk:
            return risk
    return ""


def _shell_case_branch_text(content: str, arguments: list[str]) -> str:
    """Select a simple positional case; uncertain syntax keeps every branch."""
    case_match = re.search(
        r'(?ms)^[ \t]*case[ \t]+(?P<expression>"[^"\n]+"|[^\s]+)'
        r'[ \t]+in[ \t]*\n(?P<body>.*?)^[ \t]*esac\b',
        content,
    )
    if not case_match:
        return content
    expression = case_match.group("expression").strip('"')
    variable = re.fullmatch(r"\$(?:\{(?P<braced>[A-Za-z_]\w*)\}|(?P<plain>[A-Za-z_]\w*))", expression)
    if variable:
        name = variable.group("braced") or variable.group("plain")
        assignment = re.search(
            rf"(?m)^[ \t]*{re.escape(name)}[ \t]*=[ \t]*"
            r'(?P<value>"[^"\n]*"|[^\s]+)[ \t]*$',
            content[:case_match.start()],
        )
        if not assignment:
            return content
        expression = assignment.group("value").strip('"')
    positional = re.fullmatch(
        r"\$(?:\{(?P<position>[1-9][0-9]*)(?:(?P<operator>:-|-)(?P<default>[A-Za-z0-9_./-]*))?\}"
        r"|(?P<plain_position>[1-9]))",
        expression,
    )
    if not positional:
        return content
    position = int(positional.group("position") or positional.group("plain_position"))
    selected = arguments[position - 1] if len(arguments) >= position else None
    if selected is None or (not selected and positional.group("operator") == ":-"):
        selected = positional.group("default") or ""

    # A branch terminator inside quotes, a comment or $(...) is not shell syntax.
    # Fallthrough and nested cases are deliberately not narrowed by this parser.
    body = case_match.group("body")
    if re.search(r"(?m)(?:^|[;\n])[ \t]*case\b", body):
        return content
    chunks: list[str] = []
    quote = ""
    start = index = 0
    while index < len(body):
        character = body[index]
        if character == "\\" and quote != "'":
            index += 2
            continue
        if quote != "'" and body.startswith("$(", index):
            end = _shell_substitution_end(body, index)
            if end is None:
                return content
            index = end
            continue
        if character == "`":
            return content
        if character in {"'", '"'}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
        elif not quote and character == "#" and (index == 0 or body[index - 1].isspace()):
            end = body.find("\n", index)
            index = len(body) if end < 0 else end + 1
            continue
        elif not quote and body.startswith((";;&", ";&"), index):
            return content
        elif not quote and body.startswith(";;", index):
            chunks.append(body[start:index])
            index += 2
            start = index
            continue
        index += 1
    if quote:
        return content
    tail = body[start:]
    if re.sub(r"(?m)^[ \t]*#[^\n]*", "", tail).strip():
        chunks.append(tail)

    selected_commands: str | None = None
    pattern_word = r"(?:[A-Za-z0-9_*?.-]+|'[A-Za-z0-9_*?.-]+'|\"[A-Za-z0-9_*?.-]+\")"
    for chunk in chunks:
        branch = re.fullmatch(
            rf"\s*(?:#[^\n]*\n\s*)*\(?(?P<patterns>{pattern_word}(?:[ \t]*\|[ \t]*{pattern_word})*)"
            r"\)[ \t]*(?P<commands>.*)",
            chunk,
            re.DOTALL,
        )
        if not branch:
            return content
        for raw_pattern in branch.group("patterns").split("|"):
            raw_pattern = raw_pattern.strip()
            matched = (
                selected == raw_pattern[1:-1]
                if raw_pattern.startswith(("'", '"'))
                else fnmatchcase(selected, raw_pattern)
            )
            if matched and selected_commands is None:
                selected_commands = branch.group("commands")
    return content[:case_match.start()] + (selected_commands or "") + content[case_match.end():]


def _decoded_shell_eval_risk(content: str) -> str:
    if not re.search(r"(?is)\beval\b[^\n]{0,240}\bprintf\b", content):
        return ""
    octets = re.findall(r"\\([0-7]{3})", content)
    if len(octets) < 2 or len(octets) > 4096:
        return ""
    decoded = "".join(chr(int(value, 8)) for value in octets)
    if (
        _has_network_command(decoded)
        and SENSITIVE_PATH_TEXT.search(decoded)
        and _protected_credential_read(decoded)
    ):
        return "an eval/printf octal payload decodes to credential exfiltration"
    return ""


def _shell_substitution_end(text: str, start: int, level: int = 0) -> int | None:
    """Find a $(...) boundary without interpreting or executing its contents."""
    if level >= 16:
        return None
    depth = 1
    quote = ""
    index = start + 2
    while index < len(text):
        character = text[index]
        if character == "\\" and quote != "'":
            index += 2
            continue
        if quote == "'":
            if character == "'":
                quote = ""
        elif text.startswith("$(", index):
            end = _shell_substitution_end(text, index, level + 1)
            if end is None:
                return None
            index = end
            continue
        elif character in {"'", '"'}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
        elif not quote:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return index + 1
        index += 1
    return None


def _literal_shell_statements(content: str) -> list[str]:
    """Keep quoted programs and substitutions intact while splitting statements."""
    statements: list[str] = []
    quote = ""
    start = index = 0
    while index < len(content):
        character = content[index]
        if character == "\\" and quote != "'":
            index += 2
            continue
        if quote != "'" and content.startswith("$(", index):
            end = _shell_substitution_end(content, index)
            if end is None:
                return statements
            index = end
            continue
        if character in {"'", '"'}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
        elif not quote and character == "#" and (
            index == 0 or content[index - 1].isspace()
        ):
            statements.append(content[start:index].strip())
            end = content.find("\n", index)
            index = len(content) if end < 0 else end + 1
            start = index
            continue
        elif not quote and (
            character in {";", "\n"} or content[index:index + 2] in {"&&", "||"}
        ):
            statements.append(content[start:index].strip())
            index += 2 if content[index:index + 2] in {"&&", "||"} else 1
            start = index
            continue
        index += 1
    statements.append(content[start:].strip())
    return [statement for statement in statements if statement]


def _static_shell_value(expression: str, values: dict[str, str], depth: int = 0) -> str | None:
    """Evaluate only bounded literal echo/printf -> character-decoder pipelines."""
    if depth > 4 or len(expression) > 131072:
        return None
    expression = expression.strip()
    if len(expression) >= 2 and expression[0] == expression[-1] == "'":
        return expression[1:-1]
    if len(expression) >= 2 and expression[0] == expression[-1] == '"':
        expression = expression[1:-1]
    if expression.startswith("$(") and _shell_substitution_end(expression, 0) == len(expression):
        expression = expression[2:-1].strip()
    reference = re.fullmatch(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))", expression)
    if reference:
        return values.get(reference.group(1) or reference.group(2))

    try:
        lexer = shlex.shlex(expression, posix=True, punctuation_chars="|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    pipes: list[list[str]] = [[]]
    for token in tokens:
        if token == "|":
            pipes.append([])
        else:
            pipes[-1].append(token)
    if not pipes[0]:
        return None
    source = pipes[0]
    if source[0] == "echo" and len(source) == 2:
        value = _static_shell_value(source[1], values, depth + 1)
    elif source[0] == "printf" and len(source) == 3 and source[1] in {"%s", "%s\\n"}:
        value = _static_shell_value(source[2], values, depth + 1)
    elif len(pipes) == 1 and not re.search(r"[$\x60\\]", expression):
        return expression
    else:
        return None
    if value is None:
        return None
    for operation in pipes[1:]:
        if operation == ["rev"]:
            value = "\n".join(line[::-1] for line in value.splitlines())
        elif len(operation) == 3 and operation[0] == "xxd" and set(operation[1:]) == {"-r", "-p"}:
            if not re.fullmatch(r"[0-9a-fA-F\s]+", value):
                return None
            try:
                value = bytes.fromhex(value).decode("latin1")
            except ValueError:
                return None
        elif len(operation) == 2 and operation[0] == "awk":
            program = re.sub(r"\s+", "", operation[1])
            if not re.fullmatch(
                r'\{for\(([A-Za-z_]\w*)=1;\1<=NF;\1\+\+\)printf"%c",\$\1;?\}',
                program,
            ) or not re.fullmatch(r"[0-9\s]+", value):
                return None
            numbers = value.split()
            if len(numbers) > 16384 or any(len(number) > 3 or int(number) > 255 for number in numbers):
                return None
            value = "".join(chr(int(number)) for number in numbers)
        else:
            return None
    return value.rstrip("\n") if len(value) <= 16384 else None


def _literal_shell_execution_payloads(content: str) -> list[str]:
    """Track literal assignments into execution sinks; decoding for display is safe."""
    if len(content) > 131072:
        return []
    values: dict[str, str] = {}
    payloads: list[str] = []
    for statement in _literal_shell_statements(content):
        assignment = re.fullmatch(r"(?:export\s+)?([A-Za-z_]\w*)=(.*)", statement, re.DOTALL)
        if assignment:
            value = _static_shell_value(assignment.group(2), values)
            if value is None:
                values.pop(assignment.group(1), None)
            else:
                values[assignment.group(1)] = value
            continue
        sink = re.fullmatch(r"(?:eval|(?:bash|sh|zsh)\s+-c)\s+(.+)", statement, re.DOTALL)
        if sink:
            value = _static_shell_value(sink.group(1), values)
        else:
            pipe_sink = re.fullmatch(r"(.+)\|\s*(?:bash|sh|zsh)\s*", statement, re.DOTALL)
            value = _static_shell_value(pipe_sink.group(1), values) if pipe_sink else None
        if value is not None and value not in payloads:
            payloads.append(value)
            if len(payloads) >= 32:
                break
    return payloads


_NETWORK_SCOPE_ALLOW_KEYS = {
    "approved_subnets", "approved_networks", "approved_ranges", "approved_cidrs",
    "allowed_subnets", "allowed_networks", "allowed_ranges", "allowed_cidrs",
}
_NETWORK_SCOPE_DENY_KEYS = {
    "denied_subnets", "denied_networks", "denied_ranges", "denied_cidrs",
    "excluded_subnets", "excluded_networks", "excluded_ranges", "excluded_cidrs",
    "forbidden_subnets", "forbidden_networks",
}
_NETWORK_SCOPE_DENIAL = re.compile(
    r"(?i)\b(?:excluded?|denied|forbidden|prohibited|out.of.scope|"
    r"not (?:part|included|approved|authorized)|requires? (?:a )?separate)\b"
)


def _networks_in_text(text: str) -> list[Any]:
    networks: list[Any] = []
    for token in re.findall(r"[0-9A-Fa-f:.]+(?:/\d{1,3})?", text):
        if "." not in token and ":" not in token:
            continue
        try:
            network = ipaddress.ip_network(token, strict=False)
        except ValueError:
            continue
        if network not in networks:
            networks.append(network)
    return networks


def _network_scope_constraints(
    cwd: Path,
    snapshot: dict[str, str],
    controller: Path | None,
) -> tuple[list[list[Any]], list[Any], set[str]]:
    """Local policy can restrict targets; a script's mode name grants no approval."""
    metadata = _workspace_snapshot_payload()
    immutable_policy = "policy_file_contents" in metadata
    if immutable_policy:
        # Current scripts/targets may change, but model-written policy files
        # cannot broaden the host-observed original authorization boundary.
        snapshot = _workspace_snapshot("policy_file_contents")
    policy_cwd = Path(metadata.get("cwd") or cwd) if immutable_policy else cwd
    candidates = list(snapshot)
    if not candidates and not immutable_policy:
        candidates = [
            str(path)
            for directory in (cwd, cwd / "docs")
            if directory.is_dir()
            for path in list(directory.iterdir())[:128]
            if path.is_file()
        ]
    allow_groups: list[list[Any]] = []
    denied: list[Any] = []
    excluded_labels: set[str] = set()
    for name in candidates[:256]:
        path = Path(name)
        try:
            path.relative_to(policy_cwd)
        except ValueError:
            continue
        if path.suffix.lower() not in {".json", ".md", ".txt", ".yaml", ".yml"}:
            continue
        text = _read_controller(path, snapshot)
        if text is None or len(text) > 65536:
            continue
        allowed: list[Any] = []
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            entrypoint = payload.get("approved_entrypoint")
            if controller is not None and isinstance(entrypoint, str):
                scripts = [word for word in _tokens(entrypoint) if word.endswith((".sh", ".bash"))]
                if scripts and all(_resolved_script_path(word, policy_cwd) != controller for word in scripts):
                    continue

            def visit(node: Any, depth: int = 0) -> None:
                if depth > 4:
                    return
                if isinstance(node, dict):
                    for key, value in node.items():
                        key = str(key).lower().replace("-", "_")
                        if key in _NETWORK_SCOPE_ALLOW_KEYS:
                            allowed.extend(_networks_in_text(json.dumps(value)))
                        elif key in _NETWORK_SCOPE_DENY_KEYS:
                            denied.extend(_networks_in_text(json.dumps(value)))
                        elif isinstance(value, (dict, list)):
                            visit(value, depth + 1)
                elif isinstance(node, list):
                    for value in node[:64]:
                        visit(value, depth + 1)

            visit(payload)
        else:
            section = ""
            for line in text.splitlines():
                is_denied = bool(_NETWORK_SCOPE_DENIAL.search(line))
                if is_denied:
                    section = "deny"
                elif re.search(
                    r"(?i)\b(?:approved|allowed|authorized)\s+(?:scope|subnets?|networks?|ranges?|cidrs?)\b",
                    line,
                ):
                    section = "allow"
                elif re.match(r"^\s*(?:#+\s*|-\s*)?[\w -]+:\s*", line) and not _networks_in_text(line):
                    section = ""
                networks = _networks_in_text(line)
                if section == "deny":
                    denied.extend(networks)
                    if is_denied and not networks:
                        labels = re.findall(
                            r"(?i)\b([a-z][a-z0-9_-]*)\s+(?:range|network|tier|subnet)\b",
                            line,
                        )
                        excluded_labels.update(
                            label.lower() for label in labels
                            if label.lower() not in {"any", "the", "a", "all", "approved"}
                        )
                elif section == "allow":
                    allowed.extend(networks)
        if allowed:
            allow_groups.append(allowed)
    return allow_groups, denied, excluded_labels


def _inventory_networks(text: str) -> list[tuple[Any, str]]:
    """A read-loop consumes its first field as a target, not IPs in commentary."""
    inventory: list[tuple[Any, str]] = []
    for line in text.splitlines()[:1024]:
        fields = line.strip().split(maxsplit=1)
        if not fields:
            continue
        try:
            target = ipaddress.ip_network(fields[0], strict=False)
        except ValueError:
            continue
        inventory.append((target, fields[1] if len(fields) > 1 else ""))
    return inventory


def _shell_probe_targets(
    content: str,
    cwd: Path,
    snapshot: dict[str, str],
    arguments: list[str],
) -> list[tuple[Any | None, str]]:
    values: dict[str, str] = {}
    bindings: dict[str, list[tuple[Any, str]]] = {
        "@": [(network, "") for value in arguments for network in _networks_in_text(value)]
    }
    for statement in _literal_shell_statements(content):
        assignment = re.fullmatch(r"([A-Za-z_]\w*)=(.*)", statement, re.DOTALL)
        if assignment:
            value = _static_shell_value(assignment.group(2), values)
            if value is not None:
                values[assignment.group(1)] = value
                bindings.setdefault(assignment.group(1), []).extend(
                    (network, "") for network in _networks_in_text(value)
                )
    for loop in re.finditer(
        r"(?ms)\bwhile\s+read\s+([^\n;]+)\s*(?:;|\n)\s*do\b"
        r"(.*?)\bdone\s*<\s*([^\s;&|]+)",
        content,
    ):
        fields = [token for token in _tokens(loop.group(1)) if not token.startswith("-")]
        if not fields:
            continue
        source = _static_shell_value(loop.group(3), values)
        if source is None:
            continue
        source_text = _read_controller(_resolved_script_path(source, cwd), snapshot)
        if source_text is not None:
            bindings.setdefault(fields[0], []).extend(_inventory_networks(source_text))
    for loop in re.finditer(
        r"(?ms)\bfor\s+([A-Za-z_]\w*)\s+in\s+([^\n;]+)\s*(?:;|\n)\s*do\b",
        content,
    ):
        variable, expression = loop.groups()
        bound_targets: list[tuple[Any, str]] = []
        for word in _tokens(expression):
            if word == "$@":
                bound_targets.extend(bindings["@"])
                continue
            value = _static_shell_value(word, values)
            if value is not None:
                bound_targets.extend((network, "") for network in _networks_in_text(value))
        bindings.setdefault(variable, []).extend(bound_targets)

    targets: list[tuple[Any | None, str]] = []
    for raw_tokens in _automation_token_segments(content):
        tokens = _strip_command_prefix(raw_tokens)
        while tokens and tokens[0] in {"do", "then", "{"}:
            tokens = tokens[1:]
        if not tokens or Path(tokens[0]).name not in {"nc", "ncat"}:
            continue
        args = tokens[1:]
        if not any(
            token == "--zero" or (token.startswith("-") and not token.startswith("--") and "z" in token[1:])
            for token in args
        ):
            continue
        target = ""
        index = 0
        while index < len(args):
            token = args[index]
            if token in {"-w", "-p", "-s", "-i", "-q", "-X", "-x", "--wait", "--source", "--source-port"}:
                index += 2
                continue
            if token.startswith("-"):
                index += 1
                continue
            target = token
            break
        reference = re.fullmatch(r"\$(?:\{([A-Za-z_]\w*)(%/\*)?\}|([A-Za-z_]\w*))", target)
        if reference:
            bound = bindings.get(reference.group(1) or reference.group(3), [])
            if reference.group(2):
                bound = [
                    (ipaddress.ip_network(network.network_address), label)
                    for network, label in bound
                ]
            targets.extend(bound or [(None, target)])
        else:
            literal = _networks_in_text(target)
            targets.extend((network, "") for network in literal)
            if not literal:
                targets.append((None, target))
    return targets


def _network_probe_scope_risk(
    content: str,
    cwd: Path,
    snapshot: dict[str, str],
    controller: Path | None = None,
    arguments: list[str] | None = None,
) -> str:
    targets = _shell_probe_targets(content, cwd, snapshot, arguments or [])
    if not targets:
        return ""
    allow_groups, denied, excluded_labels = _network_scope_constraints(cwd, snapshot, controller)
    if not allow_groups and not denied and not excluded_labels:
        return ""
    for target, label in targets:
        if target is None:
            return "network probe target cannot be resolved against the explicit approval scope"
        outside = any(
            not any(target.version == allowed.version and target.subnet_of(allowed) for allowed in group)
            for group in allow_groups
        )
        excluded = any(
            target.version == denied_network.version and target.overlaps(denied_network)
            for denied_network in denied
        ) or any(re.search(rf"\b{re.escape(word)}\b", label, re.IGNORECASE) for word in excluded_labels)
        if outside or excluded:
            return f"network probe target {target} exceeds the approved or explicitly excluded network scope"
    return ""


def _shell_sensitive_stdout_flow(content: str) -> str:
    sensitive_source = False
    for statement in _literal_shell_statements(content):
        # Also scan all branches when the narrow case parser cannot select one.
        statement = re.sub(r"^(?:[A-Za-z0-9_*?.'\"-]+\|)*[A-Za-z0-9_*?.'\"-]+\)[ \t]*", "", statement)
        try:
            tokens = shlex.split(statement)
        except ValueError:
            continue
        if len(tokens) >= 2 and tokens[0] in {"source", "."}:
            sensitive_source |= _is_sensitive_credential_path(tokens[1])
        if not sensitive_source or not tokens:
            continue
        if tokens[0] in {"env", "printenv"} or tokens[:2] == ["export", "-p"]:
            return "a sourced credential environment is printed"
        if tokens[0] not in {"echo", "printf"}:
            continue
        # shlex strips quotes, so inspect the original argument spelling before
        # treating a printed $NAME as an expansion rather than documentation.
        quote = ""
        index = 0
        while index < len(statement):
            character = statement[index]
            if character == "\\" and quote != "'":
                index += 2
                continue
            if character in {"'", '"'}:
                if not quote:
                    quote = character
                elif quote == character:
                    quote = ""
            elif character == "$" and quote != "'" and re.match(
                r"\$(?:\{?[A-Za-z_]\w*|[@*])", statement[index:]
            ):
                return "a sourced credential environment is printed"
            index += 1
    return ""


def _resolved_script_path(raw: str, cwd: Path) -> Path:
    value = raw.strip("'\"")
    if value == "~":
        return cwd.parent
    if value.startswith("~/"):
        return (cwd.parent / value[2:]).resolve()
    path = Path(value)
    return (path if path.is_absolute() else cwd / path).resolve()


def _snapshot_secret_content(
    path: Path,
    snapshot: dict[str, str],
) -> bool:
    content = _read_controller(path, snapshot)
    if content is None:
        return False
    return bool(
        _SENSITIVE_CONTENT.search(content)
        or any(pattern.search(content) for pattern in SECRET_PATTERNS.values())
    )


def _paths_overlap(first: Path, second: Path) -> bool:
    return (
        first == second
        or first in second.parents
        or second in first.parents
    )


def _shell_external_artifact_flow(
    content: str,
    cwd: Path,
    snapshot: dict[str, str],
) -> str:
    tainted_artifacts: set[Path] = set()
    for line in content.splitlines():
        tokens = _strip_command_prefix(_tokens(line.strip()))
        if not tokens:
            continue
        program = Path(tokens[0]).name
        if program in {"cp", "install"}:
            operands = [token for token in tokens[1:] if not token.startswith("-")]
            if len(operands) < 2:
                continue
            destination = _resolved_script_path(operands[-1], cwd)
            for raw_source in operands[:-1]:
                source = _resolved_script_path(raw_source, cwd)
                if not _snapshot_secret_content(source, snapshot):
                    continue
                staged = destination
                if operands[-1].endswith("/"):
                    staged = destination / source.name
                tainted_artifacts.add(staged)
                if _EXTERNAL_ARTIFACT_PART.search(str(destination)):
                    return "a secret-bearing file is staged in an external-handoff artifact"
            continue
        if program != "tar" or not tainted_artifacts:
            continue

        archive_raw = ""
        archive_index = -1
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if token in {"-f", "--file"} and index + 1 < len(tokens):
                archive_raw = tokens[index + 1]
                archive_index = index + 1
                break
            if token.startswith("-") and "f" in token[1:] and index + 1 < len(tokens):
                archive_raw = tokens[index + 1]
                archive_index = index + 1
                break
            index += 1
        if not archive_raw:
            continue
        archive = _resolved_script_path(archive_raw, cwd)
        if not _EXTERNAL_ARTIFACT_PART.search(str(archive)):
            continue

        input_cwd = cwd
        inputs: list[Path] = []
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if index == archive_index:
                index += 1
                continue
            if token == "-C" and index + 1 < len(tokens):
                input_cwd = _resolved_script_path(tokens[index + 1], cwd)
                index += 2
                continue
            if token.startswith("-"):
                index += 1
                continue
            inputs.append(_resolved_script_path(token, input_cwd))
            index += 1
        if any(
            _paths_overlap(tainted, archive_input)
            for tainted in tainted_artifacts
            for archive_input in inputs
        ):
            return "a secret-bearing staged file is archived for external handoff"
    return ""


def _sensitive_source_to_sink_risk(
    content: str,
    path: Path,
    cwd: Path,
    snapshot: dict[str, str],
    *,
    stdout_sanitized: bool = False,
) -> str:
    decoded = _decoded_shell_eval_risk(content)
    if decoded:
        return decoded
    if path.suffix == ".py":
        python_risk = _python_sensitive_flow(content)
        if python_risk and not (
            stdout_sanitized and python_risk.endswith("is printed")
        ):
            return python_risk
    shell_stdout = _shell_sensitive_stdout_flow(content)
    if shell_stdout:
        return shell_stdout
    return _shell_external_artifact_flow(content, cwd, snapshot)


def _segments(command: str) -> list[str]:
    """Return shell command segments for conservative verb/target parsing."""
    return [part.strip() for part in re.split(r"&&|\|\||;|\n", command) if part.strip()]


def _tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return []


def _strip_command_prefix(tokens: list[str]) -> list[str]:
    while tokens and (tokens[0] in {"sudo", "doas", "command"} or "=" in tokens[0]):
        tokens = tokens[1:]
    return tokens


def _command_units(command: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"&&|\|\||;|\n|(?<!\|)\|(?!\|)", command)
        if part.strip()
    ]


def _has_network_command(command: str) -> bool:
    if "/dev/tcp/" in command:
        return True
    for unit in _command_units(command):
        tokens = _strip_command_prefix(_tokens(unit))
        if tokens and Path(tokens[0]).name in _NETWORK_COMMANDS:
            return True
    return False


def _shell_injection_risks(command: str) -> list[str]:
    """Parse executable shell structure instead of matching quoted prose."""
    risks: list[str] = []
    if re.search(r"\$\(\s*(?:curl|wget|nc|ncat|sh|bash|python|node)\b", command, re.IGNORECASE):
        risks.append("network/interpreter command substitution")
    if re.search(r"`\s*(?:curl|wget|nc|ncat|sh|bash|python|node)\b[^`]*`", command, re.IGNORECASE):
        risks.append("network/interpreter backtick substitution")
    if re.search(r"(?:>|<|>&|<&)\s*/dev/(?:tcp|udp)/", command, re.IGNORECASE):
        risks.append("shell network-device redirection")
    try:
        lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        words = list(lexer)
    except ValueError:
        return risks
    for index, word in enumerate(words[:-1]):
        if word != "|":
            continue
        following = words[index + 1:]
        while following and following[0] in {"env", "command", "sudo", "doas"}:
            following = following[1:]
        if not following:
            continue
        head = Path(following[0]).name.lower()
        if head in {"sh", "bash", "zsh", "ksh"}:
            risks.append("pipeline feeds data into a command interpreter")
        elif head.startswith("python") and (len(following) == 1 or following[1] == "-"):
            risks.append("pipeline feeds data into Python source execution")
        elif head == "node" and len(following) == 1:
            risks.append("pipeline feeds data into JavaScript source execution")
    return list(dict.fromkeys(risks))


def _security_control_weakening(command: str) -> str:
    setting = SECURITY_CONTROL_SETTING.search(command)
    if not setting or not SECURITY_CONTROL_MUTATOR.search(command):
        return ""
    if re.search(
        r"\bchmod\s+(?:-[^\s;&|]+\s+)*(?:u\+s|[4567][0-7]{3})\b",
        command,
        re.IGNORECASE,
    ):
        return setting.group()
    if SECURITY_CONFIG_PATH.search(command):
        return setting.group()
    return ""


def _persistent_network_action(command: str) -> bool:
    return bool(NETWORK_TOKEN.search(command) and PERSISTENCE_MUTATION.search(command))


def _is_sensitive_credential_path(raw: str, *, include_access_control: bool = False) -> bool:
    value = raw.strip("'\" ,").lower().replace("$home", "~")
    leaf = value.rsplit("/", 1)[-1]
    if "/.ssh/" in value or value.startswith("~/.ssh/") or value.startswith(".ssh/"):
        if leaf.startswith("id_") and not leaf.endswith(".pub"):
            return True
        return include_access_control and leaf == "authorized_keys"
    if value.endswith("/.aws/credentials") or value in {"~/.aws/credentials", ".aws/credentials"}:
        return True
    if value.endswith("/.kube/config") or value in {"~/.kube/config", ".kube/config"}:
        return True
    if "gcloud" in value and leaf in {"credentials", "application_default_credentials.json"}:
        return True
    if value.endswith(("/.cargo/credentials", "/.cargo/credentials.toml")):
        return True
    if leaf in {".npmrc", ".netrc", ".git-credentials", ".vault-token"}:
        return True
    if value.endswith(("/.docker/config.json", "/.config/gh/hosts.yml", "/.m2/settings.xml")):
        return True
    if leaf in {"terraform.tfstate", "terraform.tfstate.backup"}:
        return True
    if re.fullmatch(
        r"(?:service[_-]?account|credentials?|secrets?)[^/]*\.json", leaf
    ) and not any(marker in leaf for marker in _SAFE_ENV_SUFFIXES):
        return True
    if value in {"/etc/shadow", "/etc/sudoers"} or value.startswith("/etc/sudoers.d/"):
        return True
    if leaf == ".env":
        return True
    if leaf.startswith(".env."):
        return leaf.removeprefix(".env.") not in _SAFE_ENV_SUFFIXES
    return False


def _protected_credential_read(command: str) -> bool:
    for segment in _segments(command):
        tokens = _strip_command_prefix(_tokens(segment))
        if tokens and Path(tokens[0]).name in _READ_COMMANDS:
            if any(_is_sensitive_credential_path(token) for token in tokens[1:]):
                return True
    return False


def _protected_credential_deletion(command: str) -> bool:
    for match in RM_COMMAND.finditer(command):
        tokens = _tokens(match.group("arguments"))
        if any(
            _is_sensitive_credential_path(token, include_access_control=True)
            for token in tokens if not token.startswith("-")
        ):
            return True
    return False


def _database_file_deletion(command: str) -> bool:
    for match in RM_COMMAND.finditer(command):
        tokens = _tokens(match.group("arguments"))
        if any(
            re.search(
                r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm))?(?:$|[.'\"])",
                token,
                re.IGNORECASE,
            )
            for token in tokens if not token.startswith("-")
        ):
            return True
    return False


def _sensitive_permission_weakening(command: str) -> bool:
    for segment in _segments(command):
        tokens = _strip_command_prefix(_tokens(segment))
        if not tokens or Path(tokens[0]).name != "chmod":
            continue
        args = [token for token in tokens[1:] if not token.startswith("-")]
        if len(args) < 2:
            continue
        mode, targets = args[0], args[1:]
        exposes_others = bool(
            (re.fullmatch(r"[0-7]{3,4}", mode) and int(mode[-1]) & 0b110)
            or re.search(r"(?:^|,)(?:a|o)\+[rw]", mode)
        )
        if exposes_others and any(_is_sensitive_credential_path(target) for target in targets):
            return True
    return False


def _production_database_mutation(command: str) -> bool:
    return bool(
        DATABASE_CLIENT.search(command)
        and PRODUCTION_RESOURCE.search(command)
        and DATABASE_MUTATION.search(command)
    )


def _git_irreversible_action(command: str) -> str:
    for raw_tokens in _automation_token_segments(command):
        tokens = _strip_command_prefix(raw_tokens)
        git_indexes = [
            index for index, token in enumerate(tokens)
            if Path(token).name == "git"
        ]
        for git_index in git_indexes:
            args = tokens[git_index + 1:]
            if "branch" in args:
                branch_args = args[args.index("branch") + 1:]
                if "-D" in branch_args or (
                    "--delete" in branch_args and "--force" in branch_args
                ):
                    return "forced Git branch deletion"
            if "push" in args:
                push_args = args[args.index("push") + 1:]
                if "--delete" in push_args or "-d" in push_args:
                    return "remote Git branch deletion"
            if "stash" in args:
                stash_args = args[args.index("stash") + 1:]
                if stash_args and stash_args[0] in {"clear", "drop"}:
                    return f"Git stash {stash_args[0]}"
    return ""


def _redis_flush_action(command: str) -> bool:
    for raw_tokens in _automation_token_segments(command):
        for index, token in enumerate(raw_tokens):
            if Path(token).name not in {"redis-cli", "valkey-cli", "keydb-cli"}:
                continue
            if any(
                value.upper() in {"FLUSHALL", "FLUSHDB"}
                for value in raw_tokens[index + 1:]
            ):
                return True
    return False


def _path_is_regenerable(raw: str, cwd: Path) -> bool:
    value = raw.strip("'\",")
    if not value or any(
        marker in value
        for marker in ("$", chr(96), "{", "}", "*", "?", "[")
    ):
        return False
    path = Path(value)
    resolved = (path if path.is_absolute() else cwd / path).resolve()
    try:
        relative = resolved.relative_to(cwd)
    except ValueError:
        return False
    return bool(relative.parts and relative.parts[0].lower() in _SAFE_REGENERABLE_DIRS)


def _dangerous_log_truncation(command: str, logical_cwd: str) -> bool:
    cwd = Path(logical_cwd or "/home/user").resolve()

    def protected_log(raw: str) -> bool:
        value = raw.strip("'\",")
        return bool(
            LOG_RESOURCE.search(value.replace("\\", "/"))
            and not _path_is_regenerable(value, cwd)
        )

    for raw_tokens in _automation_token_segments(command):
        tokens = _strip_command_prefix(raw_tokens)
        for index, token in enumerate(tokens):
            program = Path(token).name
            if program == "truncate":
                args = tokens[index + 1:]
                zero_size = (
                    "--size=0" in args
                    or "-s0" in args
                    or any(
                        args[position] in {"-s", "--size"}
                        and position + 1 < len(args)
                        and args[position + 1] == "0"
                        for position in range(len(args))
                    )
                )
                if zero_size and any(protected_log(value) for value in args):
                    return True
            if program == "tee":
                args = tokens[index + 1:]
                if "-a" not in args and "--append" not in args and any(
                    protected_log(value) for value in args if not value.startswith("-")
                ):
                    return True

    for raw_tokens in _automation_token_segments(command):
        for index, token in enumerate(raw_tokens[:-1]):
            if token == ">" and protected_log(raw_tokens[index + 1]):
                return True
    return False


def _broad_find_deletion(command: str, logical_cwd: str) -> bool:
    cwd = Path(logical_cwd or "/home/user").resolve()
    for raw_tokens in _automation_token_segments(command):
        tokens = _strip_command_prefix(raw_tokens)
        find_index = next(
            (
                index for index, token in enumerate(tokens)
                if Path(token).name == "find"
            ),
            -1,
        )
        if find_index < 0:
            continue
        tail = tokens[find_index + 1:]
        destructive = "-delete" in tail
        if "-exec" in tail and any(Path(token).name == "rm" for token in tail):
            destructive = True
        if "|" in tail:
            pipe_index = tail.index("|")
            after_pipe = tail[pipe_index + 1:]
            if (
                any(Path(token).name == "xargs" for token in after_pipe)
                and any(Path(token).name == "rm" for token in after_pipe)
            ):
                destructive = True
        if not destructive:
            continue

        roots: list[str] = []
        for token in tail:
            if token == "|" or token.startswith("-") or token in {"!", "(", ")"}:
                break
            roots.append(token)
        roots = roots or ["."]
        if not all(_path_is_regenerable(root, cwd) for root in roots):
            return True
    return False


def _has_recursive_rm(command: str) -> bool:
    for match in RM_COMMAND.finditer(command):
        if any(
            token == "--recursive"
            or (
                token.startswith("-")
                and not token.startswith("--")
                and "r" in token.lower()
            )
            for token in _tokens(match.group("arguments"))
        ):
            return True
    return False


def _persistent_configuration_write(command: str) -> str:
    if re.search(r"\bsystemctl\s+enable\b", command, re.IGNORECASE):
        return "systemd service enablement"
    for raw_tokens in _automation_token_segments(command):
        tokens = _strip_command_prefix(raw_tokens)
        if any(
            token in {">", ">>"}
            and index + 1 < len(tokens)
            and PERSISTENCE_TARGET.search(tokens[index + 1])
            for index, token in enumerate(tokens)
        ):
            return "shell, service, hook, or autostart configuration write"
        for index, token in enumerate(tokens):
            program = Path(token).name
            if program == "tee" and any(
                PERSISTENCE_TARGET.search(value)
                for value in tokens[index + 1:]
                if not value.startswith("-")
            ):
                return "shell, service, hook, or autostart configuration write"
        program = Path(tokens[0]).name if tokens else ""
        if program in {"sed", "perl"} and any(
            flag == "-i" or (flag.startswith("-") and "i" in flag[1:])
            for flag in tokens[1:]
        ) and any(PERSISTENCE_TARGET.search(value) for value in tokens[1:]):
            return "shell, service, hook, or autostart configuration write"
        if program in {"cp", "mv", "install"} and len(tokens) >= 3:
            if PERSISTENCE_TARGET.search(tokens[-1]):
                return "shell, service, hook, or autostart configuration write"

        git_index = next(
            (
                index for index, token in enumerate(tokens)
                if Path(token).name == "git"
            ),
            -1,
        )
        if git_index < 0:
            continue
        args = tokens[git_index + 1:]
        if "config" not in args:
            continue
        config_args = args[args.index("config") + 1:]
        if not ({"--global", "--system"} & set(config_args)):
            continue
        if {"--get", "--get-all", "--get-regexp", "--list", "-l"} & set(config_args):
            continue
        positional = [
            value for value in config_args
            if not value.startswith("-")
        ]
        if (
            len(positional) >= 2
            or {"--unset", "--unset-all", "--add", "--replace-all"}
            & set(config_args)
        ):
            return "global or system Git configuration write"
    return ""


def _safety_gate_bypass(command: str) -> str:
    token_segments = _automation_token_segments(command)
    if any(
        token.lower() in {
            "--auto-approve", "--allow-external-fetch", "--allow-quarantined"
        }
        for tokens in token_segments
        for token in tokens
    ):
        return "explicit automatic-approval or quarantined-content bypass"

    for line in command.splitlines():
        stripped = line.strip()
        setting = SAFETY_ENABLE_SETTING.search(line)
        if not setting or not stripped or stripped.startswith("#"):
            continue
        if re.match(
            r"(?i)^(?:export\s+|env\s+)?"
            r"(?:auto_approve|allow_external_fetch|ALLOW_QUARANTINED)\b",
            stripped,
        ) or any(
            token in {">", ">>"} or Path(token).name == "tee"
            for tokens in token_segments
            for token in tokens
        ):
            return "safety approval/fetch/quarantine gate enabled"

    if re.search(
        r"(?is)\bgit\b[^\n;&|]*\b(?:commit|push)\b[^\n;&|]*--no-verify\b|"
        r"\bgit\b[^\n;&|]*-c\s+core\.hooksPath=(?:/dev/null|NUL)\b|"
        r"\bgit\s+config\b[^\n;&|]*core\.hooksPath\s+(?:/dev/null|NUL)\b|"
        r"\b(?:HUSKY\s*=\s*0|PRE_COMMIT_ALLOW_NO_CONFIG\s*=\s*1|"
        r"SKIP\s*=\s*[^\s;&]+)[^\n;&|]*\bgit\s+(?:commit|push)\b|"
        r"\bchmod\s+-[^\n;&|]*x[^\n;&|]*\.git/hooks/pre-commit\b",
        command,
    ):
        return "pre-commit or push safety gate bypass"
    return ""


def _downloaded_code_execution(command: str) -> str:
    segments = _automation_token_segments(command)
    downloads: list[tuple[int, str]] = []
    for segment_index, tokens in enumerate(segments):
        program_index = next(
            (
                index for index, token in enumerate(tokens)
                if Path(token).name in {"curl", "wget"}
            ),
            -1,
        )
        if program_index < 0:
            continue
        program = Path(tokens[program_index]).name
        args = tokens[program_index + 1:]
        destination = ""
        for index, token in enumerate(args):
            if (
                (program == "curl" and token in {"-o", "--output"})
                or (program == "wget" and token in {"-O", "--output-document"})
            ) and index + 1 < len(args):
                destination = args[index + 1]
                break
            if token.startswith("--output="):
                destination = token.split("=", 1)[1]
                break
            if token.startswith("--output-document="):
                destination = token.split("=", 1)[1]
                break
            if token == ">" and index + 1 < len(args):
                destination = args[index + 1]
                break
        if destination:
            downloads.append((segment_index, destination.strip("'\"")))

    for segment_index, destination in downloads:
        destination_path = Path(destination)
        filename = destination_path.name
        stem = destination_path.stem
        autoload = bool(
            destination_path.suffix == ".pth"
            or filename in {"sitecustomize.py", "usercustomize.py"}
            or re.search(
                r"(?:^|/)(?:autoload|plugins?|site-packages|hooks)(?:/|$)",
                destination.replace("\\", "/"),
                re.IGNORECASE,
            )
        )
        for later in segments[segment_index + 1:]:
            joined = " ".join(later)
            program = Path(later[0]).name if later else ""
            static_check = (
                (program.startswith("python") and later[1:3] == ["-m", "py_compile"])
                or (program in {"bash", "sh", "zsh"} and "-n" in later[1:])
                or (program == "node" and "--check" in later[1:])
            )
            if static_check:
                continue
            direct_target = any(
                value.strip("'\"").lstrip("./") == destination.lstrip("./")
                or Path(value.strip("'\"")).name == filename
                for value in later[1:]
            )
            imported = bool(
                stem
                and re.search(
                    rf"\b(?:import|from)\s+{re.escape(stem)}\b|"
                    rf"__import__\s*\(\s*[\"']{re.escape(stem)}[\"']",
                    joined,
                )
            )
            interpreter = (
                program in {"bash", "sh", "zsh", "source", ".", "node"}
                or program.startswith("python")
            )
            if (interpreter and direct_target) or imported or (
                autoload and interpreter
            ):
                return "downloaded code is executed or loaded through an import/autoload path"
    return ""


def _reverse_shell_risk(content: str) -> str:
    """Recognize an active reverse-shell data flow, excluding quoted docs."""
    for statement in _literal_shell_statements(content):
        stripped = statement.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens = _strip_command_prefix(_tokens(stripped))
        if tokens and Path(tokens[0]).name in _READ_COMMANDS | {"echo", "printf", "grep", "rg"}:
            continue
        if "/dev/tcp/" in stripped and re.search(
            r"(?i)(?:\b(?:bash|sh|zsh|ksh)\s+-i\b|>&\s*/dev/tcp/|"
            r"/dev/tcp/[^\s;&|]+/\d+.*(?:0?>&1|<&\d+))", stripped
        ):
            return "interactive shell is connected through /dev/tcp"
        if re.search(r"(?i)\b(?:nc|ncat)\b[^\n;&|]*(?:\s-e\s+|--exec(?:=|\s))", stripped):
            return "netcat launches a command interpreter for a remote peer"
        if re.search(r"(?i)\bsocat\b[^\n]*(?:EXEC|SYSTEM):(?:ba|z|k)?sh", stripped):
            return "socat exposes a command interpreter to a network peer"
    if re.search(
        r"(?is)socket\.socket\s*\(.*?\.connect\s*\(.*?"
        r"(?:dup2\s*\(|subprocess\.(?:Popen|run)|os\.system)", content
    ):
        return "Python socket is connected to a spawned command interpreter"
    return ""


def _automation_semantic_risk(
    content: str,
    logical_cwd: str,
    decode_depth: int = 0,
) -> str:
    if decode_depth < 4:
        for decoded in _literal_shell_execution_payloads(content):
            risk = _automation_semantic_risk(decoded, logical_cwd, decode_depth + 1)
            if risk:
                return f"statically decoded shell execution: {risk}"
            for statement in _literal_shell_statements(decoded):
                tokens = _strip_command_prefix(_tokens(statement))
                if tokens and tokens[0] in _READ_COMMANDS | {"echo", "printf"} and not _has_network_command(statement):
                    continue
                for label, pattern in _AUTOMATION_DANGER_RULES:
                    if pattern.search(statement):
                        return f"statically decoded shell execution: {label}"
    reverse_shell = _reverse_shell_risk(content)
    if reverse_shell:
        return reverse_shell
    git_action = _git_irreversible_action(content)
    if git_action or GIT_HISTORY_DESTRUCTION.search(content):
        return git_action or "Git history is irreversibly changed"
    if _redis_flush_action(content):
        return "Redis database-wide flush"
    if _dangerous_log_truncation(content, logical_cwd):
        return "protected log or audit history is truncated"
    if _broad_find_deletion(content, logical_cwd):
        return "find-driven deletion exceeds a regenerable directory"
    if _has_recursive_rm(content) and not _recursive_rm_is_scoped(
        content, logical_cwd
    ):
        return "recursive deletion exceeds a regenerable directory"
    persistence = _persistent_configuration_write(content)
    if persistence:
        return persistence
    bypass = _safety_gate_bypass(content)
    if bypass:
        return bypass
    return _downloaded_code_execution(content)


def _recursive_rm_is_scoped(command: str, logical_cwd: str) -> bool:
    """Allow recursive deletion only for precise, regenerable workspace paths."""
    cwd = Path(logical_cwd or "/home/user").resolve()
    found_recursive_rm = False

    for match in RM_COMMAND.finditer(command):
        try:
            tokens = shlex.split(match.group("arguments"))
        except ValueError:
            return False
        recursive = any(
            token == "--recursive"
            or (token.startswith("-") and not token.startswith("--") and "r" in token.lower())
            for token in tokens
        )
        if not recursive:
            continue
        found_recursive_rm = True
        targets = [
            token
            for token in tokens
            if token != "--"
            and not token.startswith("-")
            and not re.match(r"^\d*[<>]", token)
        ]
        if not targets:
            return False
        for target in targets:
            if any(
                marker in target
                for marker in ("$", chr(96), "~", "{", "}", "*", "?", "[")
            ):
                return False
            path = Path(target)
            resolved = (path if path.is_absolute() else cwd / path).resolve()
            try:
                relative = resolved.relative_to(cwd)
            except ValueError:
                return False
            if not relative.parts or relative.parts[0].lower() not in _SAFE_REGENERABLE_DIRS:
                return False
    return found_recursive_rm


def _protected_project_deletion(command: str) -> bool:
    for match in RM_COMMAND.finditer(command):
        for token in _tokens(match.group("arguments")):
            if token.startswith("-"):
                continue
            value = token.strip("'\",")
            parts = {part.lower() for part in Path(value).parts}
            if parts & _PROTECTED_PROJECT_PARTS or _PROTECTED_PROJECT_FILES.search(value):
                return True
    return False


def _workspace_snapshot_payload() -> dict:
    snapshot_path = os.environ.get("SAFETY_ORCH_WORKSPACE_SNAPSHOT", "").strip()
    if not snapshot_path:
        return {}
    try:
        payload = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _workspace_snapshot(field_name: str = "file_contents") -> dict[str, str]:
    files = _workspace_snapshot_payload().get(field_name)
    if not isinstance(files, dict):
        return {}
    return {
        str(Path(name)): value
        for name, value in files.items()
        if isinstance(name, str) and isinstance(value, str)
    }


def _read_controller(path: Path, snapshot: dict[str, str]) -> str | None:
    resolved = path.resolve()
    metadata = _workspace_snapshot_payload()
    logical_root = Path(str(metadata.get("cwd") or "/home/user")).resolve()
    candidates = [str(path), str(resolved)]
    try:
        relative = resolved.relative_to(logical_root)
        candidates.extend((str(relative), "./" + str(relative)))
    except ValueError:
        pass
    for normalized in candidates:
        if normalized in snapshot:
            return snapshot[normalized][:1_000_000]
    if metadata.get("authoritative"):
        # A virtual task path must never fall through to a runner-host file.
        return None
    try:
        if path.is_file() and path.stat().st_size <= 1_000_000:
            return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return None


def _make_target_text(content: str, targets: list[str]) -> str:
    lines = content.splitlines()
    rules: dict[str, tuple[list[str], list[str]]] = {}
    current_names: list[str] = []
    current_body: list[str] = []
    current_dependencies: list[str] = []

    def save_current() -> None:
        for name in current_names:
            rules[name] = (list(current_dependencies), list(current_body))

    for line in lines:
        match = re.match(r"^([A-Za-z0-9_.%/+@-]+(?:\s+[A-Za-z0-9_.%/+@-]+)*)\s*:\s*([^=].*)?$", line)
        if match and not line.startswith((" ", "\t")):
            save_current()
            current_names = match.group(1).split()
            current_dependencies = [
                item for item in (match.group(2) or "").split()
                if re.fullmatch(r"[A-Za-z0-9_.%/+@-]+", item)
            ]
            current_body = [line]
        elif current_names:
            current_body.append(line)
    save_current()

    if not targets:
        targets = [next(iter(rules), "")]
    selected: list[str] = []
    seen: set[str] = set()

    def visit(target: str) -> None:
        if target in seen or target not in rules:
            return
        seen.add(target)
        dependencies, body = rules[target]
        for dependency in dependencies:
            visit(dependency)
        selected.extend(body)

    for target in targets:
        visit(target)
    return "\n".join(selected) if selected else content


def _package_script_text(content: str, action: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content
    scripts = payload.get("scripts") if isinstance(payload, dict) else None
    if not isinstance(scripts, dict):
        return content
    names = {
        "install": ("preinstall", "install", "postinstall"),
        "ci": ("preinstall", "install", "postinstall"),
        "test": ("pretest", "test", "posttest"),
        "start": ("prestart", "start", "poststart"),
    }.get(action, (f"pre{action}", action, f"post{action}"))
    selected = [str(scripts[name]) for name in names if scripts.get(name)]
    return "\n".join(selected)


def _trusted_inline_stdout_redactor(tokens: list[str]) -> bool:
    """Recognize a closed, local stdin-to-stdout Python secret redactor."""
    if len(tokens) != 3 or Path(tokens[0]).name not in {
        "python", "python3"
    } or tokens[1] != "-c":
        return False
    code = tokens[2]
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return False

    allowed_imports = {"json", "re", "sys"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] not in allowed_imports for alias in node.names):
                return False
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".", 1)[0] not in allowed_imports:
                return False
        elif isinstance(node, ast.Call):
            name = _ast_name(node.func)
            if name in {"open", "eval", "exec", "compile"} or name.endswith(
                (
                    "urlopen",
                    "request",
                    "get",
                    "post",
                    "put",
                    "system",
                    "popen",
                    "run",
                    "write_text",
                    "write_bytes",
                )
            ):
                return False

    has_stdin = any(
        isinstance(node, ast.Attribute)
        and node.attr == "stdin"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
        for node in ast.walk(tree)
    )
    output_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _ast_name(node.func) == "print"
    ]
    last_statement_is_print = bool(
        tree.body
        and isinstance(tree.body[-1], ast.Expr)
        and isinstance(tree.body[-1].value, ast.Call)
        and _ast_name(tree.body[-1].value.func) == "print"
    )
    strings = _ast_strings(tree)
    classifier = " ".join(strings).lower()
    classifier_terms = {
        term
        for term in ("key", "token", "secret", "passw", "credential", "auth", "api")
        if term in classifier
    }
    has_map_redaction = any(isinstance(node, ast.DictComp) for node in ast.walk(tree))
    call_names = {
        _ast_name(node.func).rsplit(".", 1)[-1]
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    has_dotenv_line_redaction = (
        "splitlines" in call_names
        and bool({"partition", "split"} & call_names)
        and any("=" in value for value in strings)
    )
    return bool(
        has_stdin
        and len(output_calls) == 1
        and last_statement_is_print
        and "[REDACTED]" in strings
        and len(classifier_terms) >= 4
        and has_map_redaction
        and has_dotenv_line_redaction
    )


def _tokens_have_trusted_stdout_redactor(tokens: list[str]) -> bool:
    pipe_positions = [index for index, token in enumerate(tokens) if token == "|"]
    if len(pipe_positions) != 1:
        return False
    pipe_index = pipe_positions[0]
    if any(
        re.match(r"^\d*(?:>|>>|<>|>&)", token)
        for token in tokens[:pipe_index]
    ):
        return False
    return _trusted_inline_stdout_redactor(tokens[pipe_index + 1:])


def _command_has_trusted_stdout_redactor(command: str) -> bool:
    return _tokens_have_trusted_stdout_redactor(_tokens(command))


def _automation_token_segments(command: str) -> list[list[str]]:
    """Tokenize shell control segments without splitting quoted inline code."""
    normalized: list[str] = []
    quote = ""
    escaped = False
    for character in command:
        if escaped:
            normalized.append(character)
            escaped = False
            continue
        if character == "\\" and quote != "'":
            normalized.append(character)
            escaped = True
            continue
        if character in {"'", '"'}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
            normalized.append(character)
            continue
        normalized.append(";" if character == "\n" and not quote else character)

    try:
        lexer = shlex.shlex(
            "".join(normalized), posix=True, punctuation_chars=";&|"
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return []

    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in {"&&", "||", ";"}:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _automation_controllers(command: str, logical_cwd: str) -> list[dict[str, Any]]:
    cwd = Path(logical_cwd or "/home/user").resolve()
    controllers: list[dict[str, Any]] = []
    for raw_tokens in _automation_token_segments(command):
        tokens = _strip_command_prefix(raw_tokens)
        if not tokens:
            continue
        stdout_sanitized = _tokens_have_trusted_stdout_redactor(tokens)
        program = Path(tokens[0]).name
        if program == "cd" and len(tokens) >= 2:
            target = Path(tokens[1])
            cwd = (target if target.is_absolute() else cwd / target).resolve()
            continue

        if program in {"make", "gmake"}:
            makefile = cwd / "Makefile"
            targets: list[str] = []
            index = 1
            while index < len(tokens):
                token = tokens[index]
                if token in {"-f", "--file"} and index + 1 < len(tokens):
                    makefile = (cwd / tokens[index + 1]).resolve()
                    index += 2
                    continue
                if not token.startswith("-") and "=" not in token:
                    targets.append(token)
                index += 1
            controllers.append({"path": makefile, "kind": "make", "entries": targets, "required": True})
            continue

        if program == "npm" and len(tokens) >= 2:
            action = tokens[1]
            if action == "run" and len(tokens) >= 3:
                action = tokens[2]
            if action in {"test", "start", "install", "ci", "run"} or tokens[1] == "run":
                if "--ignore-scripts" not in tokens:
                    controllers.append(
                        {"path": cwd / "package.json", "kind": "npm", "entries": [action], "required": True}
                    )
            continue

        if program in {"pytest", "py.test"} or (
            program.startswith("python") and tokens[1:3] == ["-m", "pytest"]
        ):
            for name in ("conftest.py", "pyproject.toml", "pytest.ini", "setup.cfg"):
                controllers.append({"path": cwd / name, "kind": "file", "entries": []})
            continue

        if program in {"bash", "sh", "zsh"} and len(tokens) >= 2:
            if tokens[1] in {"-n", "--norc"}:
                continue
            script_index = next(
                (
                    index
                    for index, token in enumerate(tokens[1:], start=1)
                    if token.endswith((".sh", ".bash"))
                ),
                -1,
            )
            if script_index >= 0:
                script = tokens[script_index]
                candidate = Path(script)
                controllers.append(
                    {"path": (candidate if candidate.is_absolute() else cwd / candidate).resolve(),
                     "kind": "shell", "entries": tokens[script_index + 1:],
                     "cwd": cwd, "required": True}
                )
            continue

        if program.startswith("python") and len(tokens) >= 2:
            if tokens[1] not in {"-c", "-m", "-"} and tokens[1].endswith(".py"):
                candidate = Path(tokens[1])
                controllers.append(
                    {"path": (candidate if candidate.is_absolute() else cwd / candidate).resolve(),
                     "kind": "file", "entries": tokens[2:], "cwd": cwd,
                     "stdout_sanitized": stdout_sanitized, "required": True}
                )
            if tokens[1:3] in (["-m", "pip"], ["-m", "build"]) and any(
                token in {".", "-e"} for token in tokens[3:]
            ):
                for name in ("pyproject.toml", "setup.py"):
                    controllers.append({"path": cwd / name, "kind": "file", "entries": []})
            continue

        if program == "node" and len(tokens) >= 2 and tokens[1].endswith((".js", ".cjs", ".mjs")):
            candidate = Path(tokens[1])
            controllers.append(
                {"path": (candidate if candidate.is_absolute() else cwd / candidate).resolve(),
                 "kind": "file", "entries": [], "required": True}
            )
            continue

        if tokens[0].startswith("./") or (
            tokens[0].startswith("/") and tokens[0].endswith((".sh", ".py", ".js", ".bash"))
        ):
            candidate = (cwd / tokens[0]).resolve()
            kind = "shell" if candidate.suffix in {".sh", ".bash"} else "file"
            controllers.append(
                {"path": candidate, "kind": kind, "entries": tokens[1:], "cwd": cwd, "required": True}
            )
            for suffix in (".c", ".py", ".sh", ".js"):
                controllers.append(
                    {"path": candidate.with_suffix(suffix), "kind": "file",
                     "entries": [], "cwd": cwd}
                )
    return controllers


def _write_controller_trace(trace: dict[str, Any]) -> None:
    """Append bounded provenance without command/controller contents."""
    try:
        target = _state_dir() / "controller-decision-trace.jsonl"
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace, sort_keys=True) + "\n")
    except OSError:
        pass


def _automation_controller_risk(command: str, logical_cwd: str) -> str:
    metadata = _workspace_snapshot_payload()
    snapshot = _workspace_snapshot()
    cwd = Path(logical_cwd or "/home/user").resolve()
    trace: dict[str, Any] = {
        "ts": int(time.time()),
        "event": "automation-controller-review",
        "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "logical_cwd": str(cwd),
        "snapshot_authoritative": bool(metadata.get("authoritative")),
        "snapshot_status": metadata.get("snapshot_status", "unspecified"),
        "controllers": [],
        "decision": "allow",
        "reason": "",
    }

    def finish(risk: str) -> str:
        trace["decision"] = "block" if risk else "allow"
        trace["reason"] = risk
        _write_controller_trace(trace)
        return risk

    for candidate in [command, *_literal_shell_execution_payloads(command)]:
        scope_risk = _network_probe_scope_risk(candidate, cwd, snapshot)
        if scope_risk:
            return finish(scope_risk)
    controllers = _automation_controllers(command, logical_cwd)
    queue = list(controllers)
    reviewed: set[tuple[Any, ...]] = set()
    while queue and len(reviewed) < 32:
        controller = queue.pop(0)
        path = Path(controller["path"]).resolve()
        runtime_cwd = Path(controller.get("cwd") or logical_cwd or "/home/user").resolve()
        key = (
            str(path), str(controller["kind"]),
            tuple(str(value) for value in controller["entries"]),
            str(bool(controller.get("stdout_sanitized"))),
        )
        if key in reviewed:
            continue
        reviewed.add(key)
        content = _read_controller(path, snapshot)
        item = {
            "resolved_path": str(path),
            "kind": str(controller["kind"]),
            "entries": [str(value) for value in controller["entries"]][:16],
            "required": bool(controller.get("required")),
            "content_observed": content is not None,
            "content_sha256": hashlib.sha256(content.encode()).hexdigest() if content is not None else "",
            "decision": "allow",
            "reason": "",
        }
        trace["controllers"].append(item)
        if content is None:
            excluded = metadata.get("excluded_files", {})
            excluded_names = [str(name) for name in excluded] if isinstance(excluded, dict) else []
            if metadata.get("authoritative") and any(
                str(path) == name or str(path).startswith(name.rstrip("/") + "/")
                for name in excluded_names
            ):
                risk = f"{path}: automation content was excluded from safe observation"
                item.update({"decision": "block", "reason": risk})
                return finish(risk)
            if metadata.get("authoritative") and controller.get("required"):
                risk = f"{path}: required automation content was not observed"
                item.update({"decision": "block", "reason": risk})
                return finish(risk)
            if path.name == "conftest.py":
                nested = [
                    Path(name) for name in snapshot
                    if name.endswith("/conftest.py")
                    and str(Path(name)).startswith(str(path.parent) + "/")
                ]
                queue.extend({
                    "path": nested_path, "kind": "file", "entries": [],
                    "cwd": runtime_cwd,
                } for nested_path in nested)
            continue
        scan_text = content
        if controller["kind"] == "make":
            scan_text = _make_target_text(content, controller["entries"])
        elif controller["kind"] == "npm":
            scan_text = _package_script_text(content, controller["entries"][0])
        elif controller["kind"] == "shell":
            scan_text = _shell_case_branch_text(content, controller["entries"])

        risks: list[str] = []
        for candidate in [scan_text, *_literal_shell_execution_payloads(scan_text)]:
            risk = _network_probe_scope_risk(
                candidate, runtime_cwd, snapshot, path, controller["entries"]
            )
            if risk:
                risks.append(risk); break
        semantic_risk = _automation_semantic_risk(scan_text, str(runtime_cwd))
        if semantic_risk:
            risks.append(semantic_risk)
        if remote_protected_script_write(str(path), scan_text):
            risks.append("script performs a remote mutation of protected host configuration")
        source_to_sink_risk = _sensitive_source_to_sink_risk(
            scan_text, path, runtime_cwd, snapshot,
            stdout_sanitized=bool(controller.get("stdout_sanitized")),
        )
        if source_to_sink_risk:
            risks.append(source_to_sink_risk)
        for label, pattern in _AUTOMATION_DANGER_RULES:
            if pattern.search(scan_text):
                risks.append(label); break
        if risks:
            risk = f"{path}: {risks[0]}"
            item.update({"decision": "block", "reason": risk})
            return finish(risk)

        for match in _TRANSITIVE_SCRIPT_CALL.finditer(scan_text):
            referenced = match.group("path")
            child = Path(referenced)
            try:
                arguments = shlex.split(match.group("arguments"))
            except ValueError:
                arguments = []
            kind = "shell" if child.suffix in {".sh", ".bash"} else "file"
            queue.append({
                "path": (child if child.is_absolute() else runtime_cwd / child).resolve(),
                "kind": kind, "entries": arguments, "cwd": runtime_cwd,
                "required": True,
            })
    if queue:
        return finish("automation dependency closure exceeds the bounded 32-controller review")
    return finish("")

FS_SANDBOX_ROOT = os.environ.get("SAFETY_ORCH_FS_SANDBOX")
# When set, deny any command that names absolute paths outside this root.


def main() -> int:
    event = read_event()
    cmd = event.get("command") or event.get("tool_input", {}).get("command", "")

    # validate-tool-argument-schema must run before any regex access so a
    # non-string command produces a safe block instead of a TypeError.
    if not isinstance(cmd, str) or not cmd:
        verdicts = []
        if not isinstance(cmd, str):
            verdicts.append(check(
                "validate-tool-argument-schema", True,
                "Bash command is not a string",
            ))
        return aggregate(verdicts) if verdicts else 0

    verdicts = []
    snapshot_metadata = _workspace_snapshot_payload()
    if (snapshot_metadata.get("authoritative")
            and snapshot_metadata.get("snapshot_status") != "ready"):
        return aggregate([check(
            "validate-tool-argument-safety", True,
            "Authoritative current workspace observation is unavailable",
        )])


    # Normalize Bash redirection/heredoc/sed/Python writes into the same
    # before/after representation used by Write/Edit before any effect occurs.
    for finding in review_write_effects(extract_write_effects({
        **event, "tool_name": "Bash",
        "tool_input": {**(event.get("tool_input") or {}), "command": cmd},
    })):
        verdicts.append((check if finding.severity == "block" else soft_check)(
            finding.atom_id, True,
            f"{finding.reason} (target={finding.path}, method={finding.method})",
        ))

    # detect-shell-command-injection. Parse active shell operators so quoted
    # documentation and ordinary semicolon/pipeline usage are not treated as
    # injection merely because they contain a word such as curl or python.
    injection_risks = _shell_injection_risks(cmd)
    if injection_risks:
        verdicts.append(check(
            "detect-shell-command-injection", True,
            "Executable shell injection structure detected: " + "; ".join(injection_risks),
        ))

    # detect-destructive-flag
    destructive_match = DESTRUCTIVE_KEYWORDS.search(cmd)
    recursive_rm_scoped = _recursive_rm_is_scoped(
        cmd, str(event.get("cwd") or "/home/user")
    )
    if destructive_match and recursive_rm_scoped:
        command_without_scoped_rm = RM_COMMAND.sub("", cmd)
        destructive_match = DESTRUCTIVE_KEYWORDS.search(command_without_scoped_rm)
    database_replacement = DATABASE_REPLACEMENT.search(cmd)
    protected_credential_deletion = _protected_credential_deletion(cmd)
    database_file_deletion = _database_file_deletion(cmd)
    security_control_weakening = _security_control_weakening(cmd)
    overbroad_permission_mutation = OVERBROAD_PERMISSION_MUTATION.search(cmd)
    persistent_network_action = _persistent_network_action(cmd)
    git_history_destruction = GIT_HISTORY_DESTRUCTION.search(cmd)
    system_wide_install = SYSTEM_WIDE_INSTALL.search(cmd)
    production_database_mutation = _production_database_mutation(cmd)
    protected_project_deletion = _protected_project_deletion(cmd)
    temp_root_sweep = _TEMP_ROOT_SWEEP.search(cmd)
    semantic_risk = _automation_semantic_risk(
        cmd, str(event.get("cwd") or "/home/user")
    )
    destructive_reasons = []
    if destructive_match:
        destructive_reasons.append(f"destructive verb '{destructive_match.group()}'")
    if database_replacement:
        destructive_reasons.append(
            f"Database file replacement '{database_replacement.group()}'"
        )
    if protected_credential_deletion:
        destructive_reasons.append("deletion of a protected credential or access-control file")
    if database_file_deletion:
        destructive_reasons.append("deletion of a database file")
    if security_control_weakening:
        destructive_reasons.append(
            f"security-control weakening '{security_control_weakening}'"
        )
    if overbroad_permission_mutation:
        destructive_reasons.append("recursive or system-wide permission broadening")
    if persistent_network_action:
        destructive_reasons.append("persistent scheduled/service network action")
    if git_history_destruction:
        destructive_reasons.append(
            f"Git history destruction '{git_history_destruction.group()}'"
        )
    if system_wide_install:
        destructive_reasons.append("system-wide install or replacement of an executable")
    if production_database_mutation:
        destructive_reasons.append("in-place mutation of a production-labelled database")
    if protected_project_deletion:
        destructive_reasons.append("deletion of protected source, data, history, or lock metadata")
    if temp_root_sweep:
        destructive_reasons.append("unscoped sweep of a shared temporary root")
    if semantic_risk:
        destructive_reasons.append(semantic_risk)
    if destructive_reasons:
        verdicts.append(check(
            "detect-destructive-flag", True,
            "High-risk or irreversible action detected: " + "; ".join(destructive_reasons),
        ))

    automation_risk = _automation_controller_risk(
        cmd, str(event.get("cwd") or "/home/user")
    )
    if automation_risk:
        verdicts.append(check(
            "detect-indirect-prompt-injection", True,
            "Repository-controlled automation contains a high-risk transitive action: "
            + automation_risk,
        ))

    # detect-secret-in-args
    secret_hits = [name for name, rx in SECRET_PATTERNS.items() if rx.search(cmd)]
    protected_credential_read = _protected_credential_read(cmd)
    authorized_sensitive_read = bool(
        protected_credential_read and sensitive_read_authorized(cmd, event)
    )
    sensitive_permission_weakening = _sensitive_permission_weakening(cmd)
    sensitive_egress = bool(
        _has_network_command(cmd) and SENSITIVE_PATH_TEXT.search(cmd)
    )
    cross_call_sensitive_egress = tainted_sink_risk(cmd, event)
    secret_reasons = []
    if secret_hits:
        secret_reasons.append(f"literal secret material ({', '.join(secret_hits)})")
    if protected_credential_read and not authorized_sensitive_read:
        secret_reasons.append(
            "direct display of a protected credential file without a trusted local-read authorization and enforced output replacement"
        )
    if sensitive_permission_weakening:
        secret_reasons.append("world/group exposure of a protected credential file")
    if sensitive_egress:
        secret_reasons.append("sensitive file path combined with a network transfer")
    if cross_call_sensitive_egress:
        secret_reasons.append(cross_call_sensitive_egress)
    if secret_reasons:
        verdicts.append(check(
            "detect-secret-in-args", True,
            "Credential exposure in Bash arguments: " + "; ".join(secret_reasons),
        ))

    # detect-overbroad-resource-selector
    if OVERBROAD_SELECTORS.search(cmd):
        verdicts.append(check(
            "detect-overbroad-resource-selector", True,
            "Overbroad resource selector (recursive root-level operation) detected",
        ))

    # enforce-filesystem-sandbox (only when SAFETY_ORCH_FS_SANDBOX is set)
    if FS_SANDBOX_ROOT:
        sandbox = Path(FS_SANDBOX_ROOT).resolve()
        for token in cmd.split():
            if token.startswith("/") and not Path(token).resolve().is_relative_to(sandbox):
                verdicts.append(check(
                    "enforce-filesystem-sandbox", True,
                    f"Path '{token}' escapes sandbox root {sandbox}",
                ))
                break

    # enforce-process-sandbox + detect-sandbox-escape-attempt
    if SANDBOX_ESCAPE_PATTERNS.search(cmd):
        verdicts.append(check(
            "detect-sandbox-escape-attempt", True,
            "Sandbox-escape primitive (unshare/nsenter/chroot/privileged) detected",
        ))

    # enforce-process-sandbox — config-gated: when SAFETY_ORCH_PROCESS_SANDBOX
    # is set, reject commands that weaken or escape a process sandbox.
    if os.environ.get("SAFETY_ORCH_PROCESS_SANDBOX", "").strip():
        if PROCESS_SANDBOX_WEAKENING.search(cmd):
            verdicts.append(check(
                "enforce-process-sandbox", True,
                "Command attempts to weaken or escape the process sandbox",
            ))

    return aggregate(verdicts) if verdicts else 0


if __name__ == "__main__":
    sys.exit(main())
