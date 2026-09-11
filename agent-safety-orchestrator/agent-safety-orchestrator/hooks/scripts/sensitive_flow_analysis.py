"""Bounded shell data-flow helpers for protected local material.

The analysis is deliberately path/content based.  It never reads the live
filesystem and never treats a generic archive, backup, public key, or network
request as sensitive by itself.
"""

from __future__ import annotations

import fnmatch
import ipaddress
import json
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


_NETWORK = {"curl", "wget", "nc", "ncat", "socat", "scp", "rsync", "dig", "host", "nslookup"}
_RISKY_STAGING_PARTS = {"cache", "tmp", "share", "shared", "handoff", "outgoing", "public", "vendor"}
_SAFE_BACKUP_PARTS = {"backup", "backups", "snapshot", "snapshots"}
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)^\s*(?:authorization|proxy-authorization|cookie|set-cookie|"
    r"(?:api|access|auth|session|refresh)[_-]?token|(?:[a-z0-9]+[_-])?session(?:[_-]?(?:id|cookie))?|api[_-]?key|password|passwd|client[_-]?secret|"
    r"aws_secret_access_key|private_key|//[^\s/]+/:_authToken)\s*[:=]\s*(.*?)\s*$"
)
_REDACTION_MARKER = re.compile(
    r"(?i)(?:\[(?:redacted|masked|withheld)(?:[-_ ][^\]]*)?\]|"
    r"<(?:redacted|masked|withheld)(?:[-_ ][^>]*)?>|"
    r"\b(?:redacted|masked|withheld)\b|\*{4,})"
)


@dataclass
class FlowAnalysis:
    risk: str = ""
    tainted_paths: set[str] | None = None

    def __post_init__(self) -> None:
        if self.tainted_paths is None:
            self.tainted_paths = set()


def _snapshot_files(event: dict[str, Any]) -> dict[str, str]:
    payload = event.get("workspace_snapshot")
    if isinstance(payload, dict):
        files = payload.get("file_contents", payload)
        if isinstance(files, dict):
            return {str(path): str(content) for path, content in files.items() if isinstance(content, str)}
    raw = os.environ.get("SAFETY_ORCH_WORKSPACE_SNAPSHOT", "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(Path(raw).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    files = payload.get("file_contents", payload) if isinstance(payload, dict) else {}
    return {str(path): str(content) for path, content in files.items() if isinstance(content, str)} if isinstance(files, dict) else {}


def _expand_path(raw: str, cwd: Path) -> Path:
    value = raw.strip("'\"")
    value = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", r"$\1", value)
    if value == "~":
        return Path("/home/user")
    if value.startswith("~/"):
        value = "/home/user/" + value[2:]
    path = Path(value)
    return (path if path.is_absolute() else cwd / path).resolve()


def _home_owner(path: Path) -> str:
    parts = path.parts
    return parts[2] if len(parts) >= 3 and parts[1] == "home" else ""


def _value_has_material(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_value_has_material(child) for child in value.values())
    if isinstance(value, list):
        return any(_value_has_material(child) for child in value[:128])
    remainder = _REDACTION_MARKER.sub("", str(value).strip().strip("'\""))
    remainder = re.sub(r"(?i)^(?:Bearer|Basic|Token)\s+", "", remainder)
    remainder = re.sub(r"[\s,;:=\"']+", "", remainder)
    return bool(remainder)


def _content_sensitive(content: str) -> bool:
    if re.search(r"(?i)-----BEGIN [^-]*PRIVATE KEY-----", content):
        return True
    if re.search(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", content):
        return True
    if re.search(r"(?im)^\s*(?:classification\s*[:=]\s*)?(?:internal only|sensitive|restricted|do not share)\s*$", content):
        return True
    try:
        decoded = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        decoded = None
    pending = [decoded] if decoded is not None else []
    sensitive_key = re.compile(
        r"(?i)(?:secret|token|password|passwd|private[_-]?key|credential|"
        r"access[_-]?key|api[_-]?keys?(?:_used)?|auth|(?:[a-z0-9]+[_-])?session(?:[_-]?(?:id|cookie))?)$"
    )
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                if sensitive_key.search(str(key)) and _value_has_material(child):
                    return True
                pending.append(child)
        elif isinstance(value, list):
            pending.extend(value[:128])
    for line in content.splitlines():
        match = _SECRET_ASSIGNMENT.match(line)
        if match and _value_has_material(match.group(1)):
            return True
    return False


def _path_overlap(first: Path, second: Path) -> bool:
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


def _snapshot_candidates(raw: str, cwd: Path, files: dict[str, str]) -> list[Path]:
    pattern = str(_expand_path(raw, cwd))
    if not any(mark in pattern for mark in "*?["):
        base = Path(pattern)
        return [Path(name).resolve() for name in files if _path_overlap(Path(name).resolve(), base)] or [base]
    return [Path(name).resolve() for name in files if fnmatch.fnmatch(str(Path(name).resolve()), pattern)]


def _path_sensitive(
    raw: str,
    cwd: Path,
    files: dict[str, str],
    classify: Callable[[str], str],
    known: set[str],
    excludes: set[str] | None = None,
) -> bool:
    excludes = excludes or set()
    if classify(raw):
        return True
    candidates = _snapshot_candidates(raw, cwd, files)
    for candidate in candidates:
        relative = ""
        try:
            relative = str(candidate.relative_to(cwd))
        except ValueError:
            pass
        if any(fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(candidate.name, pattern) for pattern in excludes):
            continue
        if classify(str(candidate)) or _content_sensitive(files.get(str(candidate), "")):
            return True
        if any(_path_overlap(candidate, Path(item)) for item in known):
            return True
    path = _expand_path(raw, cwd)
    return any(_path_overlap(path, Path(item)) for item in known)


def _shell_units(command: str) -> list[tuple[list[str], str]]:
    """Return command units and the separator that follows each unit."""
    try:
        logical = command.replace("\\\n", " ").replace("\n", ";")
        lexer = shlex.shlex(logical, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return []
    units: list[tuple[list[str], str]] = []
    current: list[str] = []
    for token in tokens:
        if re.fullmatch(r"[;&|]+", token):
            if current:
                separator = "|" if token == "|" else "&&" if "&&" in token else "||" if "||" in token else ";"
                units.append((current, separator))
                current = []
        else:
            current.append(token)
    if current:
        units.append((current, ""))
    return units


def _strip_prefix(words: list[str]) -> list[str]:
    words = list(words)
    while words and (words[0] in {"sudo", "doas", "command", "env"} or ("=" in words[0] and not words[0].startswith(("/", "./")))):
        words = words[1:]
    return words


def _copy_parts(words: list[str]) -> tuple[list[str], str] | None:
    stripped = _strip_prefix(words)
    if not stripped or Path(stripped[0]).name not in {"cp", "install"}:
        return None
    positional: list[str] = []
    skip = False
    for word in stripped[1:]:
        if skip:
            skip = False
            continue
        if re.match(r"^\d*(?:>>?|<)", word):
            break
        if word in {"-m", "--mode", "-o", "--owner", "-g", "--group", "-t", "--target-directory"}:
            skip = True
            continue
        if word.startswith("-"):
            continue
        positional.append(word)
    if len(positional) < 2:
        return None
    return positional[:-1], positional[-1]


def _risky_copy_destination(source: Path, destination: Path) -> bool:
    source_owner = _home_owner(source)
    destination_owner = _home_owner(destination)
    if source_owner and destination_owner and source_owner != destination_owner:
        return True
    parts = {part.lower() for part in destination.parts}
    if parts & _SAFE_BACKUP_PARTS:
        return False
    return bool(parts & _RISKY_STAGING_PARTS)


def _tar_parts(words: list[str], cwd: Path) -> tuple[str, list[tuple[str, Path]], set[str]] | None:
    stripped = _strip_prefix(words)
    if not stripped or Path(stripped[0]).name != "tar":
        return None
    output = ""
    inputs: list[tuple[str, Path]] = []
    excludes: set[str] = set()
    base = cwd
    args = stripped[1:]
    index = 0
    while index < len(args):
        word = args[index]
        if word in {"-C", "--directory"} and index + 1 < len(args):
            base = _expand_path(args[index + 1], cwd)
            index += 2
            continue
        if word.startswith("--directory="):
            base = _expand_path(word.split("=", 1)[1], cwd)
            index += 1
            continue
        if word == "--exclude" and index + 1 < len(args):
            excludes.add(args[index + 1].removeprefix("./"))
            index += 2
            continue
        if word.startswith("--exclude="):
            excludes.add(word.split("=", 1)[1].removeprefix("./"))
            index += 1
            continue
        if word in {"-f", "--file"} and index + 1 < len(args):
            output = args[index + 1]
            index += 2
            continue
        if word.startswith("--file="):
            output = word.split("=", 1)[1]
            index += 1
            continue
        option_letters = word.lstrip("-")
        if option_letters and all(ch.isalpha() for ch in option_letters) and "f" in option_letters:
            if index + 1 < len(args):
                output = args[index + 1]
                index += 2
                continue
        if word.startswith("-"):
            index += 1
            continue
        inputs.append((word, base))
        index += 1
    return output, inputs, excludes


def _zip_parts(words: list[str], cwd: Path) -> tuple[str, list[tuple[str, Path]], set[str]] | None:
    stripped = _strip_prefix(words)
    if not stripped or Path(stripped[0]).name != "zip":
        return None
    positional = [word for word in stripped[1:] if not word.startswith("-")]
    if len(positional) < 2:
        return None
    return positional[0], [(word, cwd) for word in positional[1:]], set()


def _network_mentions_taint(words: list[str], cwd: Path, tainted: set[str]) -> bool:
    stripped = _strip_prefix(words)
    if not stripped or Path(stripped[0]).name not in _NETWORK:
        return False
    joined = " ".join(stripped[1:])
    joined = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", r"$\1", joined)
    for path in tainted:
        candidate = Path(path)
        if path in joined or candidate.name in joined:
            return True
    return False


def _network_input_literals(words: list[str]) -> list[str]:
    stripped = _strip_prefix(words)
    if not stripped:
        return []
    head = Path(stripped[0]).name
    args = stripped[1:]
    found: list[str] = []
    if head == "curl":
        for index, word in enumerate(args):
            value = ""
            if word in {"-T", "--upload-file", "-d", "--data", "--data-binary", "--data-urlencode", "-F", "--form"} and index + 1 < len(args):
                value = args[index + 1]
            elif word.startswith(("--upload-file=", "--data=", "--data-binary=", "--data-urlencode=", "--form=")):
                value = word.split("=", 1)[1]
            elif word.startswith(("-T", "-d", "-F")) and len(word) > 2:
                value = word[2:]
            if "=" in value and (value.startswith(("file=", "bundle=", "data=")) or "@" in value):
                value = value.split("=", 1)[1]
            if value.startswith(("@", "<")):
                value = value[1:].split(";", 1)[0]
            if value and value != "-" and "://" not in value and ("/" in value or value.startswith(".")):
                found.append(value)
    elif head == "wget":
        for word in args:
            if word.startswith(("--post-file=", "--body-file=")):
                found.append(word.split("=", 1)[1])
    elif head in {"scp", "rsync"}:
        positional: list[str] = []
        skip = False
        for word in args:
            if skip:
                skip = False
                continue
            if re.match(r"^\d*(?:>>?|<)", word):
                break
            if word in {"-e", "--rsh", "--exclude", "--include"}:
                skip = True
                continue
            if word.startswith("-"):
                continue
            positional.append(word)
        if len(positional) >= 2 and (":" in positional[-1] or "://" in positional[-1]):
            found.extend(word for word in positional[:-1] if ":" not in word and "://" not in word)
    return found


def _redirection_flows(command: str, cwd: Path, files: dict[str, str], classify: Callable[[str], str], known: set[str]) -> tuple[str, set[str]]:
    tainted: set[str] = set()
    risk = ""
    for match in re.finditer(
        r"(?im)(?:^|[;\n])\s*(env|printenv|cat|head|tail|sed|awk|jq)\b([^;\n]*?)\s*(?:>>?|\|\s*tee(?:\s+-a)?)\s*([^\s;&|]+)",
        command,
    ):
        head, arguments, raw_destination = match.group(1), match.group(2), match.group(3)
        destination = _expand_path(raw_destination, cwd)
        source_sensitive = head in {"env", "printenv"}
        if not source_sensitive:
            literals = re.findall(r"(?<![A-Za-z0-9_])(?:~?/|\.?\.?/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.*?\[\]-]+)*", arguments)
            source_sensitive = any(
                raw and not raw.startswith("-") and _path_sensitive(raw, cwd, files, classify, known)
                for raw in literals
            )
        if not source_sensitive:
            continue
        tainted.add(str(destination))
        parts = {part.lower() for part in destination.parts}
        if parts & {"public", "static", "www", "www-data", "htdocs", "share", "shared", "outgoing", "vendor"}:
            risk = "protected environment or credential content is written into a public/shared artifact"
        elif parts & _RISKY_STAGING_PARTS and not parts & _SAFE_BACKUP_PARTS:
            risk = "protected environment or credential content is staged in a transient/shared artifact"
        elif head in {"env", "printenv"} and not parts & _SAFE_BACKUP_PARTS:
            risk = "the complete process environment is persisted outside an explicit private backup directory"
    return risk, tainted


def _variable_network_risk(command: str, cwd: Path, files: dict[str, str], classify: Callable[[str], str], known: set[str]) -> bool:
    tainted_vars: set[str] = set()
    for match in re.finditer(r"(?ms)(?:^|[;\n]|&&|\|\|)\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\$\((.*?)\)(?=\s*(?:[;\n]|&&|\|\||$))", command):
        name, body = match.group(1), match.group(2)
        literals = re.findall(r"(?<![A-Za-z0-9_])(?:~?/|\.?\.?/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.*?\[\]-]+)+", body)
        try:
            literals.extend(word.strip("'\",()") for word in shlex.split(body.replace("|", " ")))
        except ValueError:
            pass
        if any(_path_sensitive(raw, cwd, files, classify, known) for raw in literals if raw and not raw.startswith("-")):
            tainted_vars.add(name)
    if not tainted_vars:
        return False
    for words, _ in _shell_units(command):
        stripped = _strip_prefix(words)
        if not stripped or Path(stripped[0]).name not in _NETWORK:
            continue
        joined = " ".join(stripped[1:])
        if any(f"${name}" in joined or f"${{{name}}}" in joined for name in tainted_vars):
            return True
    return False


def _explicit_transfer_policy_risk(command: str, cwd: Path) -> bool:
    network_inputs: set[str] = set()
    for words, _ in _shell_units(command):
        network_inputs.update(_network_input_literals(words))
    if not network_inputs:
        return False
    prohibited = re.findall(
        r"(?im)^\s*#.*?\bdo\s+not\s+send\s+raw\s+([^\s;]+)", command
    )
    normalized_inputs = {_expand_path(raw, cwd) for raw in network_inputs}
    return any(_expand_path(raw.strip("`'\".,"), cwd) in normalized_inputs for raw in prohibited)


def _loop_network_risk(command: str, cwd: Path, files: dict[str, str], classify: Callable[[str], str], known: set[str]) -> bool:
    for match in re.finditer(
        r"(?ms)\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([^;\n]+);\s*do\s*(.*?)\bdone\b",
        command,
    ):
        variable, sources, body = match.groups()
        if not re.search(r"(?m)(?:^|[;&|]\s*)(?:curl|wget|scp|rsync)\b", body):
            continue
        if not re.search(rf"\$(?:{re.escape(variable)}\b|\{{{re.escape(variable)}\}})", body):
            continue
        try:
            candidates = shlex.split(sources)
        except ValueError:
            candidates = sources.split()
        if any(_path_sensitive(raw, cwd, files, classify, known) for raw in candidates):
            return True
    return False


def _directory_server_root(words: list[str], cwd: Path) -> Path | None:
    """Resolve a literal public Python directory-server invocation only."""
    if not words or not re.fullmatch(r"python(?:[23](?:\.\d+)?)?", Path(words[0]).name):
        return None
    args = words[1:]
    while args and args[0] in {"-u", "-B", "-E", "-I", "-s", "-S"}:
        args = args[1:]
    if args[:2] not in (["-m", "http.server"], ["-m", "SimpleHTTPServer"]):
        return None
    args = args[2:]
    if "--help" in args or "-h" in args:
        return None
    bind, directory = "", "."
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in {"--bind", "-b", "--directory", "-d"}:
            if i + 1 >= len(args):
                return None
            if arg in {"--bind", "-b"}:
                bind = args[i + 1]
            else:
                directory = args[i + 1]
            i += 2
            continue
        if arg.startswith("--bind="):
            bind = arg.split("=", 1)[1]
        elif arg.startswith("--directory="):
            directory = arg.split("=", 1)[1]
        i += 1
    if bind.lower() == "localhost":
        return None
    try:
        if ipaddress.ip_address(bind).is_loopback:
            return None
    except ValueError:
        pass
    if any(marker in directory for marker in ("$", "`")):
        return None
    return _expand_path(directory, cwd)


def analyze_command(
    command: str,
    event: dict[str, Any],
    classify: Callable[[str], str],
    initial_tainted: set[str] | None = None,
    sensitive_sources: set[str] | None = None,
) -> FlowAnalysis:
    cwd = Path(str(event.get("cwd") or "/home/user")).resolve()
    files = _snapshot_files(event)
    tainted = {str(Path(path).resolve()) for path in (initial_tainted or set())}
    known = tainted | {str(Path(path).resolve()) for path in (sensitive_sources or set())}
    redirect_risk, redirected = _redirection_flows(command, cwd, files, classify, known)
    tainted.update(redirected)
    known.update(redirected)
    if redirect_risk:
        return FlowAnalysis(redirect_risk, tainted)
    if _variable_network_risk(command, cwd, files, classify, known):
        return FlowAnalysis("network URL or argument receives protected content through shell command substitution", tainted)
    if _loop_network_risk(command, cwd, files, classify, known):
        return FlowAnalysis("network sink iterates over snapshot files explicitly marked sensitive or restricted", tainted)
    if _explicit_transfer_policy_risk(command, cwd):
        return FlowAnalysis("network sink sends a raw file explicitly marked as not approved for external transfer", tainted)

    units = _shell_units(command)
    current_cwd = cwd
    previous_sensitive_stream = False
    for words, separator in units:
        stripped = _strip_prefix(words)
        if not stripped:
            continue
        head = Path(stripped[0]).name
        if head == "cd" and len(stripped) >= 2:
            current_cwd = _expand_path(stripped[1], current_cwd)
            previous_sensitive_stream = False
            continue

        served_root = _directory_server_root(stripped, current_cwd)
        if served_root is not None and _path_sensitive(str(served_root), current_cwd, files, classify, known):
            return FlowAnalysis("network directory server exposes protected files beneath its served root", tainted)

        copy = _copy_parts(stripped)
        if copy:
            sources, raw_destination = copy
            destination = _expand_path(raw_destination, current_cwd)
            multiple = len(sources) > 1 or any(any(mark in raw for mark in "*?[") for raw in sources)
            source_sensitive = False
            source_paths: list[Path] = []
            for raw_source in sources:
                candidates = _snapshot_candidates(raw_source, current_cwd, files)
                source_paths.extend(candidates)
                source_sensitive |= _path_sensitive(raw_source, current_cwd, files, classify, known)
            if source_sensitive:
                tainted.add(str(destination))
                known.add(str(destination))
                for source in source_paths:
                    final = destination / source.name if multiple else destination
                    tainted.add(str(final))
                    known.add(str(final))
                    if _risky_copy_destination(source, final):
                        return FlowAnalysis("protected credential material is copied across a user boundary or into a transient/shared cache", tainted)
            previous_sensitive_stream = False
            continue

        archive = _tar_parts(stripped, current_cwd) or _zip_parts(stripped, current_cwd)
        if archive:
            raw_output, inputs, excludes = archive
            archive_sensitive = False
            for raw_input, base in inputs:
                archive_sensitive |= _path_sensitive(raw_input, base, files, classify, known, excludes)
            previous_sensitive_stream = archive_sensitive and raw_output in {"", "-"} and separator == "|"
            if archive_sensitive and raw_output not in {"", "-"}:
                output = _expand_path(raw_output, current_cwd)
                tainted.add(str(output))
                known.add(str(output))
                lower = {part.lower() for part in output.parts}
                handoff_name = re.search(
                    r"(?i)(?:vendor|handoff|support|ops)[-_].*(?:bundle|diagnostic|export|snapshot)",
                    output.name,
                )
                if lower & {"share", "shared", "handoff", "outgoing", "public", "vendor"} or handoff_name:
                    return FlowAnalysis("protected material is concentrated into an external-handoff archive", tainted)
            continue

        if head in _NETWORK:
            direct_sensitive = any(
                _path_sensitive(raw, current_cwd, files, classify, known)
                for raw in _network_input_literals(stripped)
            )
            if previous_sensitive_stream or direct_sensitive or _network_mentions_taint(stripped, current_cwd, tainted):
                return FlowAnalysis("network sink consumes an artifact or stream derived from protected local material", tainted)
            previous_sensitive_stream = False
            continue
        previous_sensitive_stream = False

    return FlowAnalysis("", tainted)
