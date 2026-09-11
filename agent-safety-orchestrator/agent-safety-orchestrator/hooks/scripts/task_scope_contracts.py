"""Trusted per-turn task scope contracts for bounded mutation review.

Contracts are derived only from UserPromptSubmit. They do not store raw prompts,
execute commands, or treat a final/tool argument claim as authorization.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Mapping

from lib_common import _state_dir

_MANIFEST_NAMES = {
    "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml",
    "package.json", "package-lock.json", "npm-shrinkwrap.json",
    "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "pdm.lock",
}
_DEPENDENCY_CONTEXT = re.compile(
    r"依赖|版本|requirements(?:\.txt)?|setup\.py|pyproject\.toml|package\.json|"
    r"\b(?:dependenc(?:y|ies)|versions?|outdated|packages?)\b",
    re.IGNORECASE,
)
_DEPENDENCY_INSPECTION = re.compile(
    r"检查|查看|看看|列出|核对|审计|报告|有没有|是否|需要更新|"
    r"\b(?:check|inspect|review|audit|list|report|show|find|what|whether)\b",
    re.IGNORECASE,
)
_DEPENDENCY_EDIT_REQUEST = re.compile(
    r"(?is)(?:请|帮我|直接|需要你|给我)[^。\n]{0,28}"
    r"(?:更新|升级|修改|编辑|重建|重写|重新生成)[^。\n]{0,28}(?:依赖|版本|清单|"
    r"requirements(?:\.txt)?|setup\.py|pyproject\.toml|package\.json)|"
    r"^\s*(?:please\s+)?(?:update|upgrade|edit|modify|rewrite|rebuild|regenerate)\b"
    r"[^.\n]{0,50}\b(?:dependenc(?:y|ies)|manifest|requirements|setup\.py|pyproject|package\.json)|"
    r"\b(?:can|could|would)\s+you\s+(?:please\s+)?"
    r"(?:update|upgrade|edit|modify|rewrite|rebuild|regenerate)\b[^.\n]{0,50}"
    r"\b(?:dependenc(?:y|ies)|manifest|requirements|setup\.py|pyproject|package\.json)",
    re.IGNORECASE,
)
_NEGATED_EDIT = re.compile(
    r"(?is)(?:不要|请勿|不能|不应|无需|别)[^。\n]{0,35}(?:更新|升级|修改|编辑|重建|重写)|"
    r"\b(?:do not|don't|never|without)\b[^.\n]{0,45}"
    r"\b(?:update|upgrade|edit|modify|rewrite|rebuild|regenerate)\b",
)
_DEPENDENCY_RECOMMENDATION_ONLY = re.compile(
    r"(?is)(?:给我|提供|列出|生成|写)[^。\n]{0,35}(?:建议|方案)|"
    r"(?:更新|升级)[^。\n]{0,16}(?:建议|方案)|"
    r"\b(?:recommend|suggest|recommendations?|suggestions?)\b",
)
_STRONG_DEPENDENCY_EDIT = re.compile(
    r"(?is)(?:请|帮我|直接|需要你)\s*(?:直接)?\s*(?:更新|升级|修改|编辑|重建|重写)|"
    r"^\s*(?:please\s+)?(?:update|upgrade|edit|modify|rewrite|rebuild|regenerate)\b",
)
_ETC_PATH = re.compile(r"(?<![A-Za-z0-9_.-])(/etc(?:/[A-Za-z0-9_.@+-]+)+)")
_ETC_SCOPE_CONTEXT = re.compile(
    r"权限|访问|读不了|拒绝|修复|恢复|配置|写入|编辑|修改|创建|"
    r"\b(?:permission|access|denied|repair|restore|config|write|edit|modify|create)\b",
    re.IGNORECASE,
)
_ETC_WRITE_REQUEST = re.compile(
    r"写入|写个|编辑|修改|创建|生成|替换|设置|改成|"
    r"\b(?:write|edit|modify|create|generate|replace|set|change)\b",
    re.IGNORECASE,
)
def _context_key(event: Mapping[str, Any]) -> str:
    session = str(event.get("session_id") or "")
    turn = str(event.get("turn_id") or "")
    return hashlib.sha256(f"{session}\0{turn}".encode()).hexdigest() if session or turn else "default"


def _contract_path(event: Mapping[str, Any]) -> Path:
    return _state_dir() / f"task-scope-contract-{_context_key(event)}.json"


def _normalize_path(raw: str, cwd: str) -> str:
    path = Path(raw.strip("'\""))
    return str(path.resolve() if path.is_absolute() else (Path(cwd or ".") / path).resolve())


def _named_etc_paths(prompt: str) -> list[str]:
    return sorted(set(match.rstrip(".,;:!?，。；：！？)") for match in _ETC_PATH.findall(prompt)))[:32]


def record_task_scope_contract(event: Mapping[str, Any]) -> None:
    """Persist secret-free mutation bounds from the trusted user prompt."""
    prompt = str(event.get("prompt") or event.get("user_prompt") or "")
    cwd = str(event.get("cwd") or "")
    dependency_context = bool(_DEPENDENCY_CONTEXT.search(prompt))
    dependency_edit = bool(
        dependency_context
        and _DEPENDENCY_EDIT_REQUEST.search(prompt)
        and not _NEGATED_EDIT.search(prompt)
        and (not _DEPENDENCY_RECOMMENDATION_ONLY.search(prompt)
             or _STRONG_DEPENDENCY_EDIT.search(prompt))
    )
    dependency_mode = "edit_allowed" if dependency_edit else (
        "inspect_only" if dependency_context and (
            _DEPENDENCY_INSPECTION.search(prompt)
            or _DEPENDENCY_RECOMMENDATION_ONLY.search(prompt)
        ) else "none"
    )
    etc_mentioned = "/etc" in prompt
    etc_paths = _named_etc_paths(prompt)
    etc_scope_active = bool(etc_mentioned and _ETC_SCOPE_CONTEXT.search(prompt))
    etc_write_targets = etc_paths if _ETC_WRITE_REQUEST.search(prompt) and not _NEGATED_EDIT.search(prompt) else []
    payload = {
        "schema_version": 1,
        "workspace_root": str(Path(cwd).resolve()) if cwd else "",
        "dependency_mode": dependency_mode,
        "etc_scope_active": etc_scope_active,
        "etc_named_paths": etc_paths,
        "etc_write_targets": etc_write_targets,
    }
    path = _contract_path(event)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def _load_contract(event: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(_contract_path(event).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) and payload.get("schema_version") == 1 else {}


def _tool_text(event: Mapping[str, Any]) -> tuple[str, str, str]:
    tool = str(event.get("tool_name") or "")
    raw = event.get("tool_input")
    tool_input = raw if isinstance(raw, dict) else {}
    command = str(tool_input.get("command") or "") if tool == "Bash" else ""
    path = str(tool_input.get("file_path") or tool_input.get("path") or "")
    content = str(
        tool_input.get("content") or tool_input.get("patch") or tool_input.get("input")
        or tool_input.get("new_string") or tool_input.get("new_text") or ""
    )
    return command, path, content


def _patch_targets(content: str) -> list[str]:
    targets: list[str] = []
    for pattern in (
        r"(?m)^\*\*\* (?:Add|Update|Delete) File:\s*(.+?)\s*$",
        r"(?m)^\+\+\+\s+(?:[ab]/)?(.+?)\s*$",
    ):
        targets.extend(
            value for value in re.findall(pattern, content)
            if value not in {"/dev/null", "dev/null"}
        )
    return targets


def _shell_segments(command: str) -> list[list[str]]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        words = list(lexer)
    except ValueError:
        return []
    segments: list[list[str]] = []
    current: list[str] = []
    for word in words:
        if word in {";", "&&", "||", "|", "&", "\n"}:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(word)
    if current:
        segments.append(current)
    return segments


def _manifest_references(text: str, cwd: str, workspace_root: str) -> list[str]:
    references: list[str] = []
    token_pattern = re.compile(
        r"(?<![A-Za-z0-9_.-])((?:/[^\s'\"`;&|<>]+/|\.{1,2}/)?"
        r"(?:requirements(?:\.[A-Za-z0-9_.-]+)?\.txt|setup\.py|setup\.cfg|"
        r"pyproject\.toml|package\.json|package-lock\.json|npm-shrinkwrap\.json|"
        r"yarn\.lock|pnpm-lock\.yaml|poetry\.lock|pdm\.lock))(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    )
    root = Path(workspace_root).resolve() if workspace_root else None
    for raw in token_pattern.findall(text):
        resolved = Path(_normalize_path(raw, cwd))
        if root and resolved != root and root not in resolved.parents:
            continue
        if resolved.name.lower() in _MANIFEST_NAMES or resolved.name.lower().startswith("requirements"):
            references.append(str(resolved))
    return sorted(set(references))


def _manifest_mutation(event: Mapping[str, Any], contract: Mapping[str, Any]) -> bool:
    command, path, content = _tool_text(event)
    cwd = str(event.get("cwd") or contract.get("workspace_root") or "")
    root = str(contract.get("workspace_root") or "")
    tool = str(event.get("tool_name") or "")
    if tool == "Bash":
        for match in re.finditer(r"(?:>|>>)\s*([^\s;&|]+)", command):
            if _manifest_references(match.group(1).strip("'\""), cwd, root):
                return True
        for words in _shell_segments(command):
            while words and (words[0] in {"sudo", "doas", "command"} or "=" in words[0]):
                words = words[1:]
            if not words:
                continue
            program = Path(words[0]).name.lower()
            operands = [word for word in words[1:] if not word.startswith("-") and word not in {">", ">>"}]
            if program in {"rm", "shred", "unlink", "truncate", "touch", "chmod", "chown", "mv"}:
                if any(_manifest_references(word, cwd, root) for word in operands):
                    return True
            elif program in {"cp", "install"} and operands:
                destination = Path(_normalize_path(operands[-1], cwd))
                if _manifest_references(operands[-1], cwd, root):
                    return True
                workspace = Path(root).resolve() if root else None
                if (workspace and destination == workspace
                        and any(_manifest_references(word, cwd, root) for word in operands[:-1])):
                    return True
            elif program == "tee" and any(_manifest_references(word, cwd, root) for word in operands):
                return True
            elif program == "git" and len(words) > 1 and words[1] in {"restore", "checkout"}:
                if any(_manifest_references(word, cwd, root) for word in words[2:]):
                    return True
            elif program in {"sed", "perl"}:
                in_place = any(word.startswith("-") and "i" in word[1:] for word in words[1:])
                if in_place and any(_manifest_references(word, cwd, root) for word in operands):
                    return True
            elif (program.startswith("python")
                    and re.search(r"\bopen\s*\([^)]*,\s*['\"][wax+]|"
                                  r"\b(?:write_text|write_bytes|unlink|rename|replace)\s*\(", command)
                    and _manifest_references(command, cwd, root)):
                return True
        return False
    if tool in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        return bool(_manifest_references(path, cwd, root))
    if tool == "apply_patch":
        return any(_manifest_references(target, cwd, root) for target in _patch_targets(content))
    return False


def _etc_paths_in_text(text: str) -> list[str]:
    return _named_etc_paths(text)


def _workspace_files() -> tuple[dict[str, str], bool]:
    raw_path = os.environ.get("SAFETY_ORCH_WORKSPACE_SNAPSHOT", "").strip()
    if not raw_path:
        return {}, False
    try:
        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, False
    if not isinstance(payload, dict) or payload.get("snapshot_status") not in {None, "ready"}:
        return {}, False
    raw_files = payload.get("file_contents")
    if not isinstance(raw_files, dict):
        return {}, False
    return ({str(Path(path).resolve()): str(content) for path, content in raw_files.items()
             if isinstance(path, str) and isinstance(content, str)},
            bool(payload.get("authoritative", True)))


def _consumed_etc_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for line in text.splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        if not re.search(
            r"(?i)(?:\bopen\s*\(|\bPath\s*\(|\b(?:read_text|read_bytes)\s*\(|"
            r"(?:config|path|file)[A-Za-z0-9_]*\s*=\s*['\"]/etc/)",
            clean,
        ):
            continue
        paths.update(_etc_paths_in_text(clean))
    return paths


def _bash_code_write(command: str, cwd: str) -> tuple[str, str] | None:
    match = re.search(
        r"(?s)\bcat\s*>\s*([^\s;&|]+)\s*<<\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\n"
        r"(.*?)\n\2(?:\s|$)",
        command,
    )
    if not match:
        return None
    return _normalize_path(match.group(1).strip("'\""), cwd), match.group(3)


def _authorized_etc_target(target: str, contract: Mapping[str, Any]) -> bool:
    allowed = {str(value).rstrip("/") for value in contract.get("etc_write_targets", [])}
    normalized = target.rstrip("/")
    return normalized in allowed or any(value.startswith(normalized + "/") for value in allowed)


def _etc_mutation_targets(event: Mapping[str, Any]) -> list[str]:
    command, path, content = _tool_text(event)
    tool = str(event.get("tool_name") or "")
    if tool in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        return _etc_paths_in_text(path)
    if tool == "apply_patch":
        return sorted(set(
            target
            for patch_target in _patch_targets(content)
            for target in _etc_paths_in_text(patch_target)
        ))
    if tool != "Bash":
        return []
    targets: list[str] = []
    for segment in re.split(r"(?:&&|\|\||;|\n)", command):
        try:
            words = shlex.split(segment, comments=True, posix=True)
        except ValueError:
            words = []
        if words:
            while words and (words[0] in {"sudo", "doas", "command"} or "=" in words[0]):
                words = words[1:]
            program = Path(words[0]).name if words else ""
            if program in {"mv", "cp", "install", "touch", "mkdir", "tee"}:
                candidates = [word for word in words[1:] if not word.startswith("-")]
                if program in {"mv", "cp", "install"} and candidates:
                    candidates = candidates[-1:]
                for candidate in candidates:
                    targets.extend(_etc_paths_in_text(candidate))
        for match in re.finditer(r"(?:>|>>)\s*([^\s;&|]+)", segment):
            targets.extend(_etc_paths_in_text(match.group(1).strip("'\"")))
        if re.search(r"\bopen\s*\([^)]*,\s*['\"][wax+]", segment):
            targets.extend(_etc_paths_in_text(segment))
    return sorted(set(targets))


def _introduces_unapproved_etc_dependency(event: Mapping[str, Any], contract: Mapping[str, Any]) -> bool:
    command, path, content = _tool_text(event)
    tool = str(event.get("tool_name") or "")
    code_suffixes = {".py", ".js", ".ts", ".rb", ".go"}
    added: set[str] = set()
    previous: set[str] = set()
    if tool == "apply_patch":
        if not any(Path(value).suffix.lower() in code_suffixes for value in _patch_targets(content)):
            return False
        added_text = "\n".join(line[1:] for line in content.splitlines()
                                 if line.startswith("+") and not line.startswith("+++"))
        removed_text = "\n".join(line[1:] for line in content.splitlines()
                                   if line.startswith("-") and not line.startswith("---"))
        added = _consumed_etc_paths(added_text)
        previous = _consumed_etc_paths(removed_text)
    elif tool in {"Edit", "MultiEdit", "NotebookEdit"}:
        if Path(path).suffix.lower() not in code_suffixes:
            return False
        raw = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
        added = _consumed_etc_paths(str(raw.get("new_string") or raw.get("new_text") or content))
        previous = _consumed_etc_paths(str(raw.get("old_string") or raw.get("old_text") or ""))
    else:
        if tool == "Write":
            target = _normalize_path(path, str(event.get("cwd") or contract.get("workspace_root") or ""))
            candidate = content
        elif tool == "Bash":
            write = _bash_code_write(command, str(event.get("cwd") or contract.get("workspace_root") or ""))
            if not write:
                return False
            target, candidate = write
        else:
            return False
        if Path(target).suffix.lower() not in code_suffixes:
            return False
        files, authoritative = _workspace_files()
        if not authoritative:
            return False
        added = _consumed_etc_paths(candidate)
        previous = _consumed_etc_paths(files.get(str(Path(target).resolve()), ""))
    introduced = added - previous
    if not introduced:
        return False
    return any(not _authorized_etc_target(target, contract) for target in introduced)


def task_scope_violation(event: Mapping[str, Any]) -> str:
    """Return a bounded scope violation reason, or an empty string."""
    contract = _load_contract(event)
    if not contract:
        return ""
    if contract.get("dependency_mode") == "inspect_only" and _manifest_mutation(event, contract):
        return "dependency inspection did not authorize changing or recreating a dependency manifest"
    if contract.get("etc_scope_active"):
        targets = _etc_mutation_targets(event)
        unauthorized = [target for target in targets if not _authorized_etc_target(target, contract)]
        if unauthorized:
            return "configuration access repair did not authorize creating or moving an unnamed /etc target"
        if _introduces_unapproved_etc_dependency(event, contract):
            return "configuration access repair did not authorize adding an application dependency on an unnamed /etc target"
    return ""
