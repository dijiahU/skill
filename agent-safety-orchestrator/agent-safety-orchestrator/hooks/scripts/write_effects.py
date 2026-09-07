"""Static extraction and shared review of proposed file-write effects.

The module never executes shell or generated Python.  It converts supported
Write/Edit and Bash forms into the same bounded representation, then reviews
content and before/after security-control changes before the host commits them.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ported_atom_checks import (
    ci_workflow_findings,
    install_hook_findings,
    malicious_install_findings,
)

_MAX_CONTENT = 1_000_000


@dataclass(frozen=True)
class WriteEffect:
    path: str
    content: str | None
    previous: str | None
    method: str
    complete: bool = True
    removed_text: str = ""


@dataclass(frozen=True)
class WriteFinding:
    atom_id: str
    severity: str
    reason: str
    path: str
    method: str


_SECURITY_CONTROL_PATTERNS = (
    ("artifact signature verification", re.compile(
        r"(?im)^.*(?:verify(?:ing)?\s+(?:artifact\s+)?signature|"
        r"cosign\s+verify|gpg\s+--verify|minisign\s+-V|"
        r"verify[_ -]?signature|signature[_ -]?check).*$"
    )),
    ("checksum verification", re.compile(
        r"(?im)^.*(?:sha(?:256|512)sum\s+--?check|checksum[_ -]?verify|"
        r"verify[_ -]?checksum).*$"
    )),
    ("TLS certificate verification", re.compile(
        r"(?im)^.*(?:verify[_ -]?tls|check[_ -]?hostname|CERT_REQUIRED|"
        r"ssl[_ -]?verify\s*[:=]\s*(?:true|1)).*$"
    )),
    ("authentication or authorization gate", re.compile(
        r"(?im)^.*(?:require[_ -]?auth|authorization[_ -]?check|"
        r"enforce[_ -]?(?:auth|rbac)|validate[_ -]?(?:token|permission)).*$"
    )),
)

_SAFETY_BYPASS_CONTENT = re.compile(
    r"(?is)(?:\"?(?:autoApprove|allowAllDomains|auto_approve|"
    r"allow_external_fetch|allow_quarantined)\"?\s*[:=]\s*(?:true|1|yes|on))|"
    r"(?:NODE_OPTIONS\s*\"?\s*[:=]\s*\"?[^\n]*--require\s+"
    r"(?:/tmp|/var/tmp|\.\.?/)[^\s\"']+)|"
    r"(?:core\.hooksPath\s*[:=]?\s*(?:/dev/null|NUL))"
)

_REMOTE_EXECUTION = re.compile(
    r"(?is)(?:fetch\s*\(|https?\.(?:get|request)\s*\(|"
    r"requests?\.(?:get|post)\s*\(|urllib\.request\.urlopen\s*\(|"
    r"\b(?:curl|wget)\b).{0,1000}(?:\beval\b|\bexec\s*\(|"
    r"child_process|subprocess\.(?:run|Popen|call)|\|\s*(?:ba|z|k)?sh\b)"
)

_AUTOMATIC_EXECUTION_CONTEXT = re.compile(
    r"(?i)(?:package\.json|pyproject\.toml|setup\.py|"
    r"\.github/workflows/|\.git/hooks/|\.vscode/settings\.json|"
    r"systemd|cron|autostart|profile|bashrc|zshrc)"
)

_SECURITY_SENSITIVE_TARGET = re.compile(
    r"(?i)(?:^|/)(?:\.github/workflows/|\.git/hooks/|\.vscode/settings\.json$|"
    r"package\.json$|pyproject\.toml$|setup\.py$|(?:etc/)?(?:systemd|cron)(?:/|$)|"
    r"(?:bashrc|zshrc|profile)$)"
)


_SSH_OPTIONS_WITH_ARGUMENT = {
    "-B", "-b", "-c", "-D", "-E", "-e", "-F", "-I", "-i", "-J",
    "-L", "-l", "-m", "-O", "-o", "-P", "-p", "-Q", "-R", "-S", "-W", "-w",
}


def _protected_remote_path(value: str) -> bool:
    value = value.rstrip("/")
    return bool(re.fullmatch(
        r"/etc/(?:hosts|sudoers|ssh/sshd_config|crontab|(?:sudoers|cron)\.d/[^/\s]+)",
        value,
        re.IGNORECASE,
    ))


def _script_command_segments(command: str) -> list[list[str]]:
    segments: list[list[str]] = []
    # Parse each physical line so shell comments end at the actual newline.
    # This is intentionally bounded and does not claim full shell grammar.
    for line in command.splitlines():
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|<>")
            lexer.whitespace_split = True
            lexer.commenters = "#"
            words = list(lexer)
        except ValueError:
            continue
        current: list[str] = []
        for word in words:
            if word in {";", "&&", "||", "|", "&"}:
                if current:
                    segments.append(current)
                    current = []
            else:
                current.append(word)
        if current:
            segments.append(current)
    return segments


def _script_raw_segments(command: str) -> list[list[str]]:
    """Tokenize one shell layer while preserving each token's outer quotes."""
    segments: list[list[str]] = []
    for line in command.splitlines():
        try:
            lexer = shlex.shlex(line, posix=False, punctuation_chars=";&|<>")
            lexer.whitespace_split = True
            lexer.commenters = "#"
            words = list(lexer)
        except ValueError:
            continue
        current: list[str] = []
        for word in words:
            if word in {";", "&&", "||", "|", "&"}:
                if current:
                    segments.append(current)
                    current = []
            else:
                current.append(word)
        if current:
            segments.append(current)
    return segments


def _shell_token_value(raw: str) -> str | None:
    try:
        values = shlex.split(raw, comments=False, posix=True)
    except ValueError:
        return None
    return values[0] if len(values) == 1 else None


def _command_substitutions(script: str) -> list[str]:
    """Extract bounded active $(...) bodies; single-quoted examples stay inert."""
    bodies: list[str] = []
    stack: list[tuple[int, int]] = []
    quote = ""
    escaped = False
    index = 0
    while index < len(script):
        character = script[index]
        if not quote and character == "#":
            newline = script.find("\n", index)
            index = len(script) if newline < 0 else newline + 1
            continue
        if escaped:
            escaped = False
        elif character == "\\" and quote != "'":
            escaped = True
        elif character in {"'", '"'}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
        elif quote != "'" and script.startswith("$(", index):
            stack.append((index + 2, 1))
            index += 1
        elif quote != "'" and character == ")" and stack:
            start, depth = stack[-1]
            if depth == 1:
                bodies.append(script[start:index])
                stack.pop()
            else:
                stack[-1] = (start, depth - 1)
        elif quote != "'" and character == "(" and stack:
            start, depth = stack[-1]
            stack[-1] = (start, depth + 1)
        index += 1
    return bodies[:32]


def _ssh_remote_command(raw_words: list[str]) -> str | None:
    values = [_shell_token_value(word) for word in raw_words]
    if not raw_words or any(value is None for value in values):
        return None
    start = 1 if values[0] in {"if", "elif", "while", "until", "!"} else 0
    if start >= len(values) or Path(values[start]).name != "ssh":
        return None
    index = start + 1
    while index < len(values):
        word = values[index]
        if word == "--":
            index += 1
            break
        option = word.split("=", 1)[0]
        if option in _SSH_OPTIONS_WITH_ARGUMENT:
            index += 1 if "=" in word else 2
            continue
        if word.startswith("-"):
            index += 1
            continue
        index += 1
        break
    if index >= len(values):
        return None
    raw_remote = raw_words[index]
    if len(raw_remote) >= 2 and raw_remote[0] in {"'", '"'} and raw_remote[-1] == raw_remote[0]:
        return values[index]
    # Unquoted outer redirections belong to the local shell, not the host.
    end = next((position for position in range(index, len(raw_words))
                if raw_words[position] in {">", ">>", "<", "<<"}), len(raw_words))
    return " ".join(raw_words[index:end]) or None


def _remote_command_writes_protected(command: str) -> bool:
    for segment in _script_command_segments(command):
        if not segment:
            continue
        program = Path(segment[0]).name.lower()
        if program in {"mv", "cp", "install"}:
            operands = [word for word in segment[1:] if not word.startswith("-")]
            if operands and _protected_remote_path(operands[-1]):
                return True
        elif program == "tee":
            if any(_protected_remote_path(word) for word in segment[1:] if not word.startswith("-")):
                return True
        elif program == "sed":
            in_place = any(
                word == "--in-place" or word.startswith("--in-place=")
                or (word.startswith("-") and "i" in word[1:])
                for word in segment[1:]
            )
            if in_place and any(_protected_remote_path(word) for word in segment[1:]):
                return True
        for index, word in enumerate(segment[:-1]):
            if word in {">", ">>"} and _protected_remote_path(segment[index + 1]):
                return True
    return False


def _python_static_value(node: ast.AST, values: dict[str, Any]) -> Any:
    """Resolve only literal Python values, preserving dynamic parts as unknown."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id, "__SAFETY_DYNAMIC_VALUE__")
    if isinstance(node, (ast.List, ast.Tuple)):
        items = [_python_static_value(item, values) for item in node.elts]
        return items if all(isinstance(item, str) for item in items) else None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for item in node.values:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                parts.append(item.value)
            elif isinstance(item, ast.FormattedValue):
                parts.append("__SAFETY_DYNAMIC_VALUE__")
            else:
                return None
        return "".join(parts)
    return None


def _python_remote_protected_write(content: str) -> bool:
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return False

    class ProcessCallVisitor(ast.NodeVisitor):
        def __init__(self, values: dict[str, Any] | None = None, subprocess_bound: bool = False):
            self.values = dict(values or {})
            self.subprocess_bound = subprocess_bound
            self.found = False

        def _invalidate_name(self, name: str) -> None:
            previous = self.values.get(name)
            for bound_name, bound_value in list(self.values.items()):
                if bound_name == name or (previous is not None and bound_value is previous):
                    self.values.pop(bound_name, None)

        def _bind(self, target: ast.AST, value: Any) -> None:
            if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
                self._invalidate_name(target.value.id)
                return
            if not isinstance(target, ast.Name):
                return
            if value is None:
                self._invalidate_name(target.id)
            else:
                self.values[target.id] = value
            if target.id == "subprocess":
                self.subprocess_bound = False

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                if bound_name == "subprocess":
                    self.subprocess_bound = alias.name == "subprocess"
                    self.values.pop("subprocess", None)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            # `from subprocess import ...` has no `subprocess.run` module binding.
            for alias in node.names:
                bound_name = alias.asname or alias.name
                if bound_name == "subprocess":
                    self.subprocess_bound = False
                    self.values.pop("subprocess", None)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            child = ProcessCallVisitor(self.values, self.subprocess_bound)
            parameters = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            if node.args.vararg:
                parameters.append(node.args.vararg)
            if node.args.kwarg:
                parameters.append(node.args.kwarg)
            for parameter in parameters:
                child.values.pop(parameter.arg, None)
                if parameter.arg == "subprocess":
                    child.subprocess_bound = False
            for statement in node.body:
                child.visit(statement)
                if child.found:
                    self.found = True
                    return

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Assign(self, node: ast.Assign) -> None:
            self.visit(node.value)
            value = _python_static_value(node.value, self.values)
            for target in node.targets:
                self._bind(target, value)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value:
                self.visit(node.value)
            value = _python_static_value(node.value, self.values) if node.value else None
            self._bind(node.target, value)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            self.visit(node.value)
            self._bind(node.target, None)

        def visit_Call(self, node: ast.Call) -> None:
            function = node.func
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id in self.values
                and function.attr in {"append", "extend", "insert", "clear", "pop", "remove", "reverse", "sort"}
            ):
                self._invalidate_name(function.value.id)
            shell_keywords = [keyword for keyword in node.keywords if keyword.arg == "shell"]
            default_executor = not any(
                keyword.arg is None or keyword.arg == "executable"
                for keyword in node.keywords
            )
            default_executor = default_executor and all(
                isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                for keyword in shell_keywords
            )
            is_subprocess_run = (
                default_executor and self.subprocess_bound
                and isinstance(function, ast.Attribute) and function.attr == "run"
                and isinstance(function.value, ast.Name) and function.value.id == "subprocess"
            )
            argv = _python_static_value(node.args[0], self.values) if is_subprocess_run and node.args else None
            if isinstance(argv, list) and argv and Path(argv[0]).name == "ssh":
                index = 1
                while index < len(argv):
                    word = argv[index]
                    if word == "--":
                        index += 1
                        break
                    option = word.split("=", 1)[0]
                    if option in _SSH_OPTIONS_WITH_ARGUMENT:
                        index += 1 if "=" in word else 2
                        continue
                    if word.startswith("-"):
                        index += 1
                        continue
                    index += 1  # destination
                    break
                # OpenSSH concatenates the remaining argv into the remote shell
                # command. Preserve unknown values as markers; inspect only the
                # statically present operators and paths in that executed tail.
                remote = " ".join(argv[index:])
                if remote and _remote_command_writes_protected(remote):
                    self.found = True
                    return
            self.generic_visit(node)

    visitor = ProcessCallVisitor()
    for statement in tree.body:
        visitor.visit(statement)
        if visitor.found:
            return True
    return False


def remote_protected_script_write(path: str, content: str) -> bool:
    """Detect a bounded set of active SSH writes to protected remote configuration."""
    suffix = Path(path).suffix.lower()
    if suffix == ".py" or re.match(r"^#![^\n]*python(?:3(?:\.\d+)?)?\b", content):
        return _python_remote_protected_write(content)
    if not (
        suffix in {".sh", ".bash", ".zsh"}
        or re.match(r"^#![^\n]*(?:ba|z|k)?sh\b", content)
    ):
        return False
    candidates = [content, *_command_substitutions(content)]
    for candidate in candidates:
        for raw_words in _script_raw_segments(candidate):
            remote = _ssh_remote_command(raw_words)
            if remote and _remote_command_writes_protected(remote):
                return True
    return False

def _snapshot_payload() -> dict[str, Any]:
    raw = os.environ.get("SAFETY_ORCH_WORKSPACE_SNAPSHOT", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(Path(raw).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _snapshot_files() -> dict[str, str]:
    files = _snapshot_payload().get("file_contents")
    if not isinstance(files, dict):
        return {}
    return {
        str(Path(name)): content[:_MAX_CONTENT]
        for name, content in files.items()
        if isinstance(name, str) and isinstance(content, str)
    }


def _resolve(raw: str, cwd: Path) -> Path:
    value = raw.strip("'\"")
    if value.startswith("~/"):
        return (Path("/home/user") / value[2:]).resolve()
    path = Path(value)
    return (path if path.is_absolute() else cwd / path).resolve()


def _snapshot_read(path: Path, files: dict[str, str]) -> str | None:
    absolute = str(path.resolve())
    if absolute in files:
        return files[absolute]
    payload = _snapshot_payload()
    root = Path(str(payload.get("cwd") or "/home/user")).resolve()
    candidates = [str(path), str(path.resolve())]
    try:
        relative = path.resolve().relative_to(root)
        candidates.extend((str(relative), "./" + str(relative)))
    except ValueError:
        pass
    for candidate in candidates:
        if candidate in files:
            return files[candidate]
    return None


def _literal(node: ast.AST, constants: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        return node.value.decode(errors="replace") if isinstance(node.value, bytes) else node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            parts.append(value.value)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _literal(node.left, constants), _literal(node.right, constants)
        return left + right if isinstance(left, str) and isinstance(right, str) else None
    return None


def _call_name(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _python_write_effects(code: str, cwd: Path, files: dict[str, str], method: str) -> list[WriteEffect]:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return []
    constants: dict[str, Any] = {}
    handles: dict[str, tuple[str, bool]] = {}
    effects: list[WriteEffect] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = _literal(node.value, constants)
            if value is not None:
                constants[node.targets[0].id] = value
            if isinstance(node.value, ast.Call) and _call_name(node.value.func) in {"open", "io.open"} and node.value.args:
                raw_path = _literal(node.value.args[0], constants)
                mode_value = _literal(node.value.args[1], constants) if len(node.value.args) > 1 else "r"
                if isinstance(raw_path, str) and isinstance(mode_value, str) and any(flag in mode_value for flag in "wax+"):
                    handles[node.targets[0].id] = (raw_path, "a" in mode_value)
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                call = item.context_expr
                target = item.optional_vars
                if not isinstance(call, ast.Call) or _call_name(call.func) not in {"open", "io.open"} or not isinstance(target, ast.Name) or not call.args:
                    continue
                raw_path = _literal(call.args[0], constants)
                mode_value = _literal(call.args[1], constants) if len(call.args) > 1 else "r"
                if isinstance(raw_path, str) and isinstance(mode_value, str) and any(flag in mode_value for flag in "wax+"):
                    handles[target.id] = (raw_path, "a" in mode_value)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        raw_path = content = None
        append = False
        if (name in {"write_text", "write_bytes"} or name.endswith((".write_text", ".write_bytes"))) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if isinstance(receiver, ast.Call) and _call_name(receiver.func) in {"Path", "pathlib.Path"} and receiver.args:
                raw_path = _literal(receiver.args[0], constants)
            if node.args:
                content = _literal(node.args[0], constants)
        elif (name == "write" or name.endswith(".write")) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if isinstance(receiver, ast.Name):
                handle = handles.get(receiver.id)
                if handle:
                    raw_path, append = handle
            elif isinstance(receiver, ast.Call) and _call_name(receiver.func) in {"open", "io.open"} and receiver.args:
                raw_path = _literal(receiver.args[0], constants)
                mode_value = _literal(receiver.args[1], constants) if len(receiver.args) > 1 else "r"
                append = isinstance(mode_value, str) and "a" in mode_value
            if node.args:
                content = _literal(node.args[0], constants)
        if not isinstance(raw_path, str):
            continue
        path = _resolve(raw_path, cwd)
        previous = _snapshot_read(path, files)
        if not isinstance(content, str):
            effects.append(WriteEffect(str(path), None, previous, method, False))
            continue
        final = ((previous or "") + content) if append else content
        effects.append(WriteEffect(str(path), final[:_MAX_CONTENT], previous, method, True))
    return effects[:32]


def _extract_heredocs(command: str, cwd: Path, files: dict[str, str]) -> tuple[list[WriteEffect], list[str]]:
    lines = command.splitlines()
    effects: list[WriteEffect] = []
    python_bodies: list[str] = []
    index = 0
    while index < len(lines):
        header = lines[index]
        marker = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", header)
        if not marker:
            index += 1
            continue
        delimiter = marker.group(2)
        end = index + 1
        while end < len(lines) and lines[end].strip() != delimiter:
            end += 1
        if end >= len(lines):
            break
        body = "\n".join(lines[index + 1:end]) + "\n"
        prefix = header[:marker.start()]
        if re.search(r"\bpython(?:\d+(?:\.\d+)*)?\s+-\b", prefix):
            python_bodies.append(body)
        target = None
        append = False
        redirect = re.search(r"(?<!\d)(>>|>)\s*([^\s;&|]+)", header)
        if redirect:
            append = redirect.group(1) == ">>"
            target = redirect.group(2)
        else:
            # The heredoc may feed tee on either side of the marker, e.g.
            # ``tee file <<EOF`` or ``cat <<EOF | tee file``.
            shell_header = header[:marker.start()] + header[marker.end():]
            try:
                lexer = shlex.shlex(shell_header, posix=True, punctuation_chars=";&|")
                lexer.whitespace_split = True
                lexer.commenters = ""
                words = list(lexer)
            except ValueError:
                words = []
            tee_index = next(
                (position for position, word in enumerate(words) if Path(word).name == "tee"),
                None,
            )
            if tee_index is not None:
                tee_words = words[tee_index + 1:]
                append = "-a" in tee_words or "--append" in tee_words
                targets = [word for word in tee_words if not word.startswith("-") and word not in {"|", ";", "&&", "||"}]
                target = targets[0] if targets else None
        if target:
            path = _resolve(target, cwd)
            previous = _snapshot_read(path, files)
            final = ((previous or "") + body) if append else body
            effects.append(WriteEffect(str(path), final[:_MAX_CONTENT], previous, "bash-heredoc", True))
        index = end + 1
    return effects[:32], python_bodies[:8]


def _shell_segments(command: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        words = list(lexer)
    except ValueError:
        return []
    segments, current = [], []
    for word in words:
        if word in {";", "&&", "||", "|"}:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(word)
    if current:
        segments.append(current)
    return segments


def _sed_apply(previous: str, expression: str) -> tuple[str | None, str]:
    # Bounded support for the common mutation forms. Unknown expressions remain
    # incomplete and are reviewed through the matched removed text instead.
    deletion = re.fullmatch(r"/([^/]+)/,\+(\d+)d", expression)
    if deletion:
        try:
            pattern = re.compile(deletion.group(1))
        except re.error:
            return None, ""
        count = int(deletion.group(2)) + 1
        lines = previous.splitlines(keepends=True)
        removed, kept, remaining = [], [], 0
        for line in lines:
            if remaining or pattern.search(line):
                removed.append(line)
                remaining = count - 1 if not remaining else remaining - 1
            else:
                kept.append(line)
        return "".join(kept), "".join(removed)
    block_delete = re.fullmatch(r"/([^/]+)/\{N;d\}", expression)
    if block_delete:
        try:
            pattern = re.compile(block_delete.group(1))
        except re.error:
            return None, ""
        lines = previous.splitlines(keepends=True)
        removed, kept = [], []
        index = 0
        while index < len(lines):
            if pattern.search(lines[index]):
                removed.append(lines[index])
                index += 1
                if index < len(lines):
                    removed.append(lines[index])
                    index += 1
                continue
            kept.append(lines[index])
            index += 1
        return "".join(kept), "".join(removed)
    substitution = re.fullmatch(r"s(.)(.*?)\1(.*?)\1([gIim]*)", expression)
    if substitution:
        _, old, new, flags = substitution.groups()
        try:
            pattern = re.compile(old, re.IGNORECASE if "I" in flags or "i" in flags else 0)
        except re.error:
            return None, ""
        removed = "\n".join(match.group() for match in pattern.finditer(previous))
        return pattern.sub(new, previous, count=0 if "g" in flags else 1), removed
    return None, ""


def _sed_effects(command: str, initial_cwd: Path, files: dict[str, str]) -> list[WriteEffect]:
    cwd = initial_cwd
    effects: list[WriteEffect] = []
    for words in _shell_segments(command):
        if not words:
            continue
        program = Path(words[0]).name
        if program == "cd" and len(words) == 2:
            cwd = _resolve(words[1], cwd)
            continue
        if program != "sed" or not any(word == "-i" or (word.startswith("-") and "i" in word[1:]) for word in words[1:]):
            continue
        expressions: list[str] = []
        targets: list[str] = []
        index = 1
        while index < len(words):
            word = words[index]
            if word in {"-e", "--expression"} and index + 1 < len(words):
                expressions.append(words[index + 1]); index += 2; continue
            if word == "-i" or word.startswith("-i"):
                index += 1; continue
            if word.startswith("-"):
                index += 1; continue
            if not expressions:
                expressions.append(word)
            else:
                targets.append(word)
            index += 1
        for raw_path in targets[:16]:
            path = _resolve(raw_path, cwd)
            previous = _snapshot_read(path, files)
            if previous is None:
                effects.append(WriteEffect(str(path), None, None, "bash-sed-in-place", False))
                continue
            candidate = previous
            removed_parts = []
            complete = True
            for expression in expressions:
                candidate, removed = _sed_apply(candidate, expression)
                removed_parts.append(removed)
                if candidate is None:
                    complete = False
                    break
            effects.append(WriteEffect(
                str(path), candidate[:_MAX_CONTENT] if candidate is not None else None,
                previous, "bash-sed-in-place", complete, "".join(removed_parts)[:_MAX_CONTENT],
            ))
    return effects


def _patch_effects(patch: str, cwd: Path, files: dict[str, str]) -> list[WriteEffect]:
    """Extract bounded per-file effects from the apply_patch envelope.

    Reconstructing arbitrary fuzzy patches belongs to the host. The safety
    review needs proposed additions and explicit removals, so retain those even
    when a complete candidate cannot be reconstructed statically.
    """
    effects: list[WriteEffect] = []
    current_path = ""
    method = "apply-patch"
    additions: list[str] = []
    removals: list[str] = []

    def flush() -> None:
        nonlocal current_path, method, additions, removals
        if not current_path:
            return
        path = _resolve(current_path, cwd)
        previous = _snapshot_read(path, files)
        added = "\n".join(additions) + ("\n" if additions else "")
        removed = "\n".join(removals) + ("\n" if removals else "")
        # Added files are complete. Updates remain intentionally incomplete:
        # additions and removals are still passed to every applicable policy.
        complete = method == "apply-patch-add"
        effects.append(WriteEffect(
            str(path), added[:_MAX_CONTENT], previous, method, complete,
            removed[:_MAX_CONTENT],
        ))
        current_path, method, additions, removals = "", "apply-patch", [], []

    for line in patch.splitlines():
        header = re.match(r"\*\*\* (Update|Add|Delete) File:\s*(.+?)\s*$", line)
        if header:
            flush()
            operation, current_path = header.group(1).lower(), header.group(2)
            method = f"apply-patch-{operation}"
            continue
        if not current_path or line.startswith(("@@", "*** End Patch")):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            additions.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removals.append(line[1:])
    flush()
    return effects[:32]


def extract_write_effects(event: dict[str, Any]) -> list[WriteEffect]:
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return []
    cwd = Path(str(event.get("cwd") or "/home/user")).resolve()
    files = _snapshot_files()
    tool_name = str(event.get("tool_name") or "")
    if tool_name in {"Write", "Edit", "MultiEdit", "apply_patch"}:
        patch = tool_input.get("patch") or tool_input.get("input")
        if isinstance(patch, str) and "*** Begin Patch" in patch:
            return _patch_effects(patch, cwd, files)
        raw_path = str(tool_input.get("file_path") or tool_input.get("path") or "")
        if not raw_path:
            return []
        path = _resolve(raw_path, cwd)
        previous = _snapshot_read(path, files)
        if "content" in tool_input:
            content = tool_input.get("content")
        elif "new_string" in tool_input:
            new = tool_input.get("new_string")
            old = tool_input.get("old_string")
            content = previous.replace(old, new, 1) if isinstance(previous, str) and isinstance(old, str) and isinstance(new, str) else new
        else:
            content = None
        return [WriteEffect(str(path), content[:_MAX_CONTENT] if isinstance(content, str) else None, previous, "write-edit", isinstance(content, str))]

    command = tool_input.get("command") or event.get("command") or ""
    if tool_name not in {"Bash", "bash"} or not isinstance(command, str):
        return []
    effects, python_bodies = _extract_heredocs(command, cwd, files)
    effects.extend(_sed_effects(command, cwd, files))
    for body in python_bodies:
        effects.extend(_python_write_effects(body, cwd, files, "bash-python-heredoc"))
    for words in _shell_segments(command):
        if len(words) >= 3 and Path(words[0]).name.startswith("python") and words[1] == "-c":
            effects.extend(_python_write_effects(words[2], cwd, files, "bash-python-inline"))
    unique: dict[tuple[str, str], WriteEffect] = {}
    for effect in effects:
        unique[(effect.path, effect.method)] = effect
    return list(unique.values())[:32]


def review_write_effect(effect: WriteEffect) -> list[WriteFinding]:
    findings: list[WriteFinding] = []
    content = effect.content or ""
    path = effect.path
    for finding in ci_workflow_findings(path, content):
        if finding.get("severity") in {"critical", "high"}:
            findings.append(WriteFinding("audit-ci-workflow-security", "block", str(finding.get("reason")), path, effect.method))
    for finding in install_hook_findings(path, content):
        findings.append(WriteFinding("audit-install-hook", "warn", str(finding.get("reason")), path, effect.method))
    for finding in malicious_install_findings(path, content):
        findings.append(WriteFinding("detect-malicious-postinstall-script", "block", str(finding.get("reason")), path, effect.method))
    if content and _SAFETY_BYPASS_CONTENT.search(content):
        findings.append(WriteFinding(
            "detect-malicious-postinstall-script", "block",
            "write enables automatic approval, unrestricted domains, disabled hooks, or terminal autoload from an untrusted path",
            path, effect.method,
        ))
    if content and _AUTOMATIC_EXECUTION_CONTEXT.search(path) and _REMOTE_EXECUTION.search(content):
        findings.append(WriteFinding(
            "detect-malicious-postinstall-script", "block",
            "automatic execution context downloads and executes remote content",
            path, effect.method,
        ))
    if content and remote_protected_script_write(path, content):
        findings.append(WriteFinding(
            "detect-indirect-prompt-injection", "block",
            "written script performs a remote mutation of protected host configuration",
            path, effect.method,
        ))
    previous = effect.previous or ""
    candidate = effect.content
    removal_source = effect.removed_text
    if candidate is None and _SECURITY_SENSITIVE_TARGET.search(path):
        findings.append(WriteFinding(
            "audit-ci-workflow-security", "block",
            "write effect on an automatic or security-sensitive file cannot be resolved before execution",
            path, effect.method,
        ))
    for label, pattern in _SECURITY_CONTROL_PATTERNS:
        before = bool(pattern.search(previous))
        after = bool(pattern.search(candidate)) if candidate is not None else False
        removed = bool(pattern.search(removal_source))
        if (before and not after and effect.complete) or removed:
            findings.append(WriteFinding(
                "audit-ci-workflow-security", "block",
                f"write removes {label} from an existing security-sensitive file",
                path, effect.method,
            ))
    return findings


def review_write_effects(effects: list[WriteEffect]) -> list[WriteFinding]:
    findings: list[WriteFinding] = []
    for effect in effects[:32]:
        findings.extend(review_write_effect(effect))
    unique: dict[tuple[str, str, str], WriteFinding] = {}
    for finding in findings:
        unique[(finding.atom_id, finding.path, finding.reason)] = finding
    return list(unique.values())
