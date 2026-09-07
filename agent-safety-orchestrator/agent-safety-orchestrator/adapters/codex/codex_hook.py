#!/usr/bin/env python3
"""Codex adapter — deterministic safety hook bridge.

Translates an OpenAI Codex hook event (stdin JSON) into the Claude-Code-shaped
event the vendored Safety Orchestrator matchers expect, runs the relevant
matcher(s) as the reusable "core", and translates their verdict back into
Codex's hook output protocol.

This is the thin per-host ADAPTER in the "one safety core, many adapters"
design: the atom-evaluation logic in the shared hooks/scripts/matcher_*.py is
reused VERBATIM (each matcher is run as an event-in / verdict-out black box) —
the SAME code the Claude Code plugin ships, not a vendored copy. Only the I/O
shapes are host-specific. Wire it via hooks.json for PreToolUse / PostToolUse /
UserPromptSubmit / Stop / SubagentStart.

Codex hook protocol (verified against codex-cli 0.144.1 +
developers.openai.com/codex/hooks):
  - stdin:  {hook_event_name, tool_name, tool_input{command|...}, cwd,
             permission_mode, turn_id, session_id, ...}
  - block (PreToolUse / PermissionRequest):
      {"hookSpecificOutput":{"hookEventName":<e>,"permissionDecision":"deny",
       "permissionDecisionReason":<why>}}   (+ exit 2 + stderr, belt-and-braces)
  - block (other events): legacy {"decision":"block","reason":<why>}
  - allow is exit 0 with no decision.
  - COVERAGE GAP (by Codex design): hosted tools such as WebSearch do not use
    the local function-tool hook path, and specialized tools may opt out. Back
    filesystem / network-egress atoms with sandbox_mode + approval_policy
    (see config.toml template) — this bridge cannot close that gap alone.

Fails OPEN on internal error (never bricks Codex on an adapter bug); the error
is logged to stderr. Flip FAIL_CLOSED=1 in the env for high-stakes deployments.
"""
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

def _resolve_core_scripts() -> Path:
    """Locate the shared matcher core (hooks/scripts) — one copy, two layouts.

    The atom-evaluation core is NOT vendored into this adapter; it is the same
    code the Claude Code plugin ships. We resolve it in priority order so the
    bridge works both when run from the repo and when installed into a Codex home:
      1. $SAFETY_ORCH_CORE         — explicit override (installer may set it)
      2. <here>/core/hooks/scripts — INSTALLED layout (install.sh assembles core/)
      3. <repo>/hooks/scripts      — IN-REPO layout (adapters/codex/ -> repo root)
    """
    here = Path(__file__).resolve().parent
    candidates = [
        os.environ.get("SAFETY_ORCH_CORE"),
        here / "core" / "hooks" / "scripts",
        here.parent.parent / "hooks" / "scripts",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return Path(c)
    return here / "core" / "hooks" / "scripts"  # default; matchers no-op if absent


CORE_SCRIPTS = _resolve_core_scripts()
FAIL_CLOSED = os.environ.get("SAFETY_ORCH_FAIL_CLOSED", "0") == "1"
MANUAL_BRIDGE = os.environ.get("SAFETY_ORCH_MANUAL_BRIDGE", "0") == "1"
BLOCK_LATCH_PREFIX = "codex-blocked-turn-"
USAGE_FIELD = "safetyOrchestratorUsage"
MAX_RECOVERY_ACTIONS = int(os.environ.get("SAFETY_ORCH_MAX_RECOVERY_ACTIONS", "4"))


def _atom_ids(reasons: list[str]) -> list[str]:
    """Extract atom IDs from the shared matchers' ``[atom-id]`` reasons."""
    found: list[str] = []
    for reason in reasons:
        for atom_id in re.findall(r"\[([a-z][a-z0-9-]+)\]", reason):
            if atom_id not in found:
                found.append(atom_id)
    return found


def _emit(payload: dict, usage: dict) -> None:
    """Emit normal hook output plus audit-only usage for the manual bridge."""
    if MANUAL_BRIDGE:
        payload[USAGE_FIELD] = usage
    if payload:
        print(json.dumps(payload))


def _bash_tool_aliases() -> set[str]:
    """Return Codex function-tool names that should receive Bash checks.

    App-server clients commonly expose a remote shell as a dynamic function
    instead of Codex's built-in shell.  Let those clients opt the function into
    the exact same matcher path without weakening the default tool mapping.
    """
    configured = os.environ.get("SAFETY_ORCH_BASH_TOOL_NAMES", "")
    return {"Bash", *(name.strip() for name in configured.split(",") if name.strip())}


def _status_dir() -> Path:
    """Return the shared runtime state directory used by the safety core."""
    raw = os.environ.get("SAFETY_ORCH_STATUS_DIR")
    return Path(raw) if raw else Path.home() / ".safety-orch"


def _turn_latch_path(codex_event: dict):
    """Return a privacy-preserving per-turn latch path, if Codex supplied a turn."""
    turn_id = str(codex_event.get("turn_id") or "").strip()
    if not turn_id:
        return None
    session_id = str(codex_event.get("session_id") or "").strip()
    digest = hashlib.sha256(f"{session_id}\0{turn_id}".encode()).hexdigest()
    return _status_dir() / f"{BLOCK_LATCH_PREFIX}{digest}.json"


def _read_turn_latch(codex_event: dict) -> dict:
    """Return structured per-turn risk state; corrupt state remains fail-closed."""
    path = _turn_latch_path(codex_event)
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception as e:
        sys.stderr.write(f"[codex_hook] cannot read turn latch {path}: {e}\n")
        return {
            "schema_version": 2,
            "reason": "A previous action in this turn was blocked.",
            "risk_class": "generic",
            "total_high_risk_blocks": 1,
            "successful_recovery_actions": 0,
        }


def _action_identity(codex_event: dict) -> str:
    tool = str(codex_event.get("tool_name") or "")
    tool_input = codex_event.get("tool_input") or {}
    try:
        serialized = json.dumps(tool_input, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        serialized = str(tool_input)
    # Persist only the hash; the original action remains in the compatible
    # top-level command field for Stop-side handoff review.
    return hashlib.sha256(f"{tool}\0{serialized}".encode()).hexdigest()


def _risk_class(atom_ids: list[str]) -> str:
    joined = " ".join(atom_ids)
    for risk, markers in (
        ("credential", ("secret", "credential", "private-key")),
        ("egress", ("exfil", "unsafe-url", "beacon", "dns")),
        ("destructive", ("destructive", "resource-selector")),
        ("permission", ("namespace-scope", "human-confirmation")),
        ("persistence", ("install-hook", "postinstall")),
        ("supply-chain", ("ci-workflow", "package-cve", "hallucinated-package")),
        ("injection", ("injection", "jailbreak")),
    ):
        if any(marker in joined for marker in markers):
            return risk
    return "generic"


def _write_turn_latch(codex_event: dict, reason: str, atom_ids: list[str]) -> dict:
    """Record action-scoped retries plus a cross-signature high-risk budget."""
    path = _turn_latch_path(codex_event)
    if path is None:
        return {}
    previous = _read_turn_latch(codex_event)
    identity = _action_identity(codex_event)
    same = int(previous.get("same_action_retries") or 0) + 1 if previous.get("action_identity") == identity else 1
    total = int(previous.get("total_high_risk_blocks") or 0) + 1
    payload = {
        "schema_version": 2,
        "reason": reason,
        "tool_name": codex_event.get("tool_name", ""),
        "command": str((codex_event.get("tool_input") or {}).get("command") or "")[:8192],
        "atom_ids": atom_ids,
        "risk_class": _risk_class(atom_ids),
        "action_identity": identity,
        "same_action_retries": same,
        "total_high_risk_blocks": total,
        "successful_recovery_actions": int(previous.get("successful_recovery_actions") or 0),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] cannot write turn latch {path}: {e}\n")
    return payload


def _record_recovery(codex_event: dict, state: dict) -> dict:
    path = _turn_latch_path(codex_event)
    if path is None:
        return state
    updated = dict(state)
    updated["successful_recovery_actions"] = int(state.get("successful_recovery_actions") or 0) + 1
    try:
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(updated, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] cannot record recovery {path}: {e}\n")
    return updated


def _bash_recovery_profile(command: str, cwd: str) -> tuple[bool, str]:
    """Allow bounded observation or narrowly scoped normal permission repair."""
    try:
        lexer = shlex.shlex(command.replace("\n", ";"), posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        words = list(lexer)
    except ValueError:
        return False, "unparseable-shell"
    # FD-to-FD duplication only changes where already-produced diagnostics are
    # observed (for example ``2>&1``); it does not create a file. Strip only
    # the bounded standard-descriptor form before rejecting other redirects.
    normalized_words = []
    index = 0
    while index < len(words):
        if (index + 2 < len(words) and words[index] == "2"
                and words[index + 1] == ">&" and words[index + 2] == "1"):
            index += 3
            continue
        normalized_words.append(words[index])
        index += 1
    words = normalized_words
    if any(set(word) & {"<", ">"} for word in words):
        return False, "shell-redirection"
    if re.search(r"\$\(|`", command):
        return False, "command-substitution"
    segments, current = [], []
    for word in words:
        if word in {";", "&&", "||", "|"}:
            if current:
                segments.append(current); current = []
        else:
            current.append(word)
    if current:
        segments.append(current)
    root = Path(cwd or "/home/user").resolve()
    readers = {
        "pwd", "ls", "stat", "file", "cat", "head", "tail", "grep", "rg",
        "wc", "cut", "jq", "find", "du", "sort", "echo", "printf",
    }
    for segment in segments:
        while segment and (segment[0] in {"sudo", "doas", "command"} or "=" in segment[0]):
            segment = segment[1:]
        if not segment:
            continue
        head = Path(segment[0]).name
        if head == "cd" and len(segment) == 2:
            target = Path(segment[1])
            resolved = (target if target.is_absolute() else root / target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                return False, "directory-outside-cwd"
            continue
        if head == "git" and len(segment) >= 2 and segment[1] in {"status", "diff", "log", "show"}:
            continue
        if head in readers:
            if head == "find" and any(word in {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprintf", "-fprint", "-fls"} for word in segment[1:]):
                return False, "mutating-find"
            if head == "rg" and any(word == "--pre" or word.startswith("--pre=") for word in segment[1:]):
                return False, "executing-reader-option"
            option_words = segment[1:]
            if "--" in option_words:
                option_words = option_words[:option_words.index("--")]
            if head == "sort":
                for word in option_words:
                    if word.startswith("-") and not re.fullmatch(r"-[hnr]+", word):
                        return False, "unrecognized-sort-option"
            if head == "printf" and any(word.startswith("-") for word in option_words):
                return False, "unrecognized-printf-option"
            continue
        if head == "chmod" and "-R" not in segment and "--recursive" not in segment:
            positional = [word for word in segment[1:] if not word.startswith("-")]
            if len(positional) >= 2 and positional[0] in {"600", "640", "644", "700", "750", "755"}:
                for raw in positional[1:]:
                    if any(marker in raw for marker in ("*", "?", "[", "$", "~")):
                        return False, "broad-permission-target"
                    target = Path(raw)
                    resolved = (target if target.is_absolute() else root / target).resolve()
                    try:
                        resolved.relative_to(root)
                    except ValueError:
                        return False, "permission-target-outside-cwd"
                continue
        return False, "effectful-or-unrecognized"
    return bool(segments), "bounded-observation-or-scope-reduction"


def _low_risk_recovery(codex_event: dict) -> tuple[bool, str]:
    tool = str(codex_event.get("tool_name") or "")
    if tool in {"Read", "Grep", "Glob", "List", "saber_skill_read", "saber_skill_health"}:
        return True, "read-only-tool"
    if tool in _bash_tool_aliases():
        command = str((codex_event.get("tool_input") or {}).get("command") or "")
        return _bash_recovery_profile(command, str(codex_event.get("cwd") or "/home/user"))
    return False, "tool-not-in-recovery-allowlist"

def _clear_turn_latch(codex_event: dict) -> None:
    """Release terminal state once Codex signals that the turn has stopped."""
    path = _turn_latch_path(codex_event)
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] cannot clear turn latch {path}: {e}\n")


def _deny_tool_event(ev: str, reason: str, usage=None) -> int:
    payload = {"hookSpecificOutput": {
        "hookEventName": ev, "permissionDecision": "deny",
        "permissionDecisionReason": reason}}
    _emit(payload, usage or {})
    sys.stderr.write(reason + "\n")
    return 2


def _read_event() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _shared_context(codex_event: dict) -> dict:
    return {
        "turn_id": codex_event.get("turn_id"),
        "session_id": codex_event.get("session_id"),
        "cwd": codex_event.get("cwd", ""),
    }


def _jobs_for(codex_event: dict):
    """Map a Codex hook event -> [(matcher_filename, claude_code_event), ...].

    Empty list => nothing applies => allow.
    """
    ev = codex_event.get("hook_event_name", "")
    tool = codex_event.get("tool_name", "")
    normalized_tool = "Bash" if tool in _bash_tool_aliases() else tool
    ti = codex_event.get("tool_input", {}) or {}

    if ev == "UserPromptSubmit":
        prompt = (codex_event.get("prompt") or codex_event.get("user_prompt")
                  or codex_event.get("message") or ti.get("prompt") or "")
        return [("matcher_user_prompt.py", {**_shared_context(codex_event), "prompt": prompt})]

    if ev == "PreToolUse":
        jobs = []
        if normalized_tool == "Bash":
            jobs.append(("matcher_bash.py", {
                "tool_name": "Bash",
                "tool_input": ti,
                **_shared_context(codex_event),
            }))
        elif normalized_tool in ("apply_patch", "Edit", "Write", "MultiEdit"):
            # Codex apply_patch tool_input is a patch blob, not {file_path,content}.
            # Best-effort: scan the raw patch text as `content` so secret /
            # injection / SAST checks still fire; pass any path through too.
            patch_text = ti.get("patch") or ti.get("input") or json.dumps(ti)
            fp = ti.get("file_path") or ti.get("path") or ""
            write_input = dict(ti)
            write_input.setdefault("file_path", fp)
            write_input.setdefault("content", patch_text)
            jobs.append(("matcher_write_edit.py",
                         {**_shared_context(codex_event), "tool_name": normalized_tool,
                          "tool_input": write_input}))
        if tool in ("WebFetch", "WebSearch", "webfetch", "web_search"):
            url = ti.get("url") or ti.get("urls") or ti.get("target_url") or ""
            jobs.append(("matcher_webfetch.py", {
                **_shared_context(codex_event),
                "url": url,
                "tool_input": ti,
            }))
        # generic checks (rate / trust / supply-chain / MCP) run for EVERY tool,
        # mirroring Claude Code's PreToolUse `*` matcher.
        jobs.append(("matcher_pretool_generic.py", {
            **_shared_context(codex_event),
            "tool_name": normalized_tool,
            "tool_input": ti,
            "cwd": codex_event.get("cwd", ""),
        }))
        return jobs

    if ev == "PostToolUse":
        out = (codex_event.get("tool_response") or codex_event.get("tool_output")
               or codex_event.get("output") or "")
        metadata = (codex_event.get("response_metadata")
                    or codex_event.get("tool_response_metadata") or {})
        return [("matcher_posttool.py",
                 {**_shared_context(codex_event), "tool_name": normalized_tool, "tool_input": ti, "tool_response": out,
                  "response_metadata": metadata})]

    if ev == "SubagentStart":
        return [("matcher_task.py", {**_shared_context(codex_event), "tool_name": "Task", "tool_input": ti})]

    if ev == "Stop":
        blocked_action = {}
        latch_path = _turn_latch_path(codex_event)
        if latch_path is not None and latch_path.is_file():
            try:
                blocked_action = json.loads(latch_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                blocked_action = {"reason": "A previous action was blocked."}
        return [("matcher_stop.py",
                 {**_shared_context(codex_event),
                  "blocked_action": blocked_action,
                  "final_message": (codex_event.get("last_assistant_message")
                                    or codex_event.get("final_message", "")),
                  "human_decision": codex_event.get("human_decision"),
                  "decision_context": codex_event.get("decision_context", {})})]

    return []


def _run_matcher(fname: str, cc_event: dict):
    """Run a vendored matcher as a subprocess.

    Returns (blocked, warned, reasons, modified_output, output_view).
    ``output_view`` carries provenance for a sanitized PostTool result.
    """
    script = CORE_SCRIPTS / fname
    if not script.exists():
        return (False, False, [], "", {})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        p = subprocess.run([sys.executable, str(script)], input=json.dumps(cc_event),
                           capture_output=True, text=True, env=env, timeout=25)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] matcher {fname} error: {e}\n")
        return (False, False, [], "", {})
    if p.returncode not in {0, 2}:
        detail = (p.stderr or p.stdout or f"exit {p.returncode}").strip()[:1000]
        reason = f"Safety matcher {fname} failed: {detail}"
        sys.stderr.write(f"[codex_hook] {reason}\n")
        return (FAIL_CLOSED, not FAIL_CLOSED, [reason], "", {})
    reasons, warned, modified_output, output_view = [], False, "", {}
    for line in (p.stdout + "\n" + p.stderr).splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                v = json.loads(line)
                if v.get("reason"):
                    reasons.append(v["reason"])
                if v.get("verdict") == "warn":
                    warned = True
                if isinstance(v.get("modified_output"), str):
                    modified_output = v["modified_output"]
                if isinstance(v.get("output_view"), dict):
                    output_view = v["output_view"]
            except Exception:
                pass
    return (p.returncode == 2, warned, reasons, modified_output, output_view)


def main() -> int:
    codex_event = _read_event()
    ev = codex_event.get("hook_event_name", "")
    tool = codex_event.get("tool_name", "")

    latch_state = _read_turn_latch(codex_event) if ev in ("PreToolUse", "PermissionRequest", "Stop") else {}

    matcher_usage = []
    try:
        any_block = any_warn = False
        all_reasons = []
        modified_outputs = []
        output_views = []
        for fname, cc_event in _jobs_for(codex_event):
            blocked, warned, reasons, modified_output, output_view = _run_matcher(fname, cc_event)
            matcher_usage.append({
                "matcher": fname.removeprefix("matcher_").removesuffix(".py"),
                "blocked": blocked,
                "warned": warned,
                "modified_output": bool(modified_output),
                "triggered_atoms": _atom_ids(reasons),
            })
            any_block |= blocked
            any_warn |= warned
            all_reasons.extend(reasons)
            if modified_output:
                modified_outputs.append(modified_output)
            if output_view:
                output_views.append(output_view)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] {'fail-closed' if FAIL_CLOSED else 'fail-open'} on error: {e}\n")
        if FAIL_CLOSED and ev in ("PreToolUse", "PermissionRequest"):
            return _deny_tool_event(ev, "Safety adapter error (fail-closed).", {
                "hook_event": ev,
                "tool_name": tool,
                "error": str(e),
                "matchers": matcher_usage,
                "triggered_atoms": [],
            })
        return 0

    reason = "; ".join(dict.fromkeys(all_reasons)) or "Blocked by Safety Orchestrator policy."
    atom_ids = _atom_ids(all_reasons)
    usage = {
        "hook_event": ev,
        "tool_name": tool,
        "latched": bool(latch_state),
        "matchers": matcher_usage,
        "triggered_atoms": atom_ids,
        "decision_kind": "pass",
        "risk_class": "",
        "action_identity": _action_identity(codex_event) if ev in ("PreToolUse", "PermissionRequest") else "",
        "same_action_retries": int(latch_state.get("same_action_retries") or 0),
        "total_high_risk_blocks": int(latch_state.get("total_high_risk_blocks") or 0),
        "successful_recovery_actions": int(latch_state.get("successful_recovery_actions") or 0),
        "recovery_eligible": False,
        "recovery_allowed": False,
    }
    if output_views:
        usage["output_view"] = output_views[-1]

    if ev == "Stop" and not any_block:
        # A denied final answer may be regenerated in the same turn. Preserve
        # its trusted action identity until a safe final answer is accepted.
        _clear_turn_latch(codex_event)
        try:
            sys.path.insert(0, str(CORE_SCRIPTS))
            from sensitive_data import clear_sensitive_state
            clear_sensitive_state(codex_event)
        except Exception as exc:
            sys.stderr.write(f"[codex_hook] cannot clear sensitive state: {exc}\n")

    if any_block:
        if ev in ("PreToolUse", "PermissionRequest"):
            state = _write_turn_latch(codex_event, reason, atom_ids)
            usage.update({
                "decision_kind": "high_risk_block",
                "risk_class": state.get("risk_class", _risk_class(atom_ids)),
                "same_action_retries": state.get("same_action_retries", 1),
                "total_high_risk_blocks": state.get("total_high_risk_blocks", 1),
                "successful_recovery_actions": state.get("successful_recovery_actions", 0),
            })
            return _deny_tool_event(ev, reason, usage)
        usage["decision_kind"] = "high_risk_block"
        usage["risk_class"] = _risk_class(atom_ids)
        _emit({"decision": "block", "reason": reason}, usage)
        return 0

    if ev in ("PreToolUse", "PermissionRequest") and latch_state:
        eligible, recovery_reason = _low_risk_recovery(codex_event)
        allowed = eligible and int(latch_state.get("successful_recovery_actions") or 0) < MAX_RECOVERY_ACTIONS
        usage["recovery_eligible"] = eligible
        usage["recovery_allowed"] = allowed
        usage["recovery_reason"] = recovery_reason
        if not allowed:
            usage["decision_kind"] = "high_risk_block"
            usage["risk_class"] = "recovery-scope"
            deny_reason = (
                "A prior high-risk action was denied. This different action passed its matcher "
                "but is outside the bounded read-only or narrowly scoped recovery channel."
            )
            return _deny_tool_event(ev, deny_reason, usage)
        latch_state = _record_recovery(codex_event, latch_state)
        usage.update({
            "decision_kind": "low_risk_recovery_allow",
            "successful_recovery_actions": latch_state.get("successful_recovery_actions", 0),
        })

    if ev in ("PreToolUse", "PermissionRequest") and tool in _bash_tool_aliases():
        try:
            sys.path.insert(0, str(CORE_SCRIPTS))
            from sensitive_data import record_allowed_bash_flow
            record_allowed_bash_flow(codex_event)
        except Exception as exc:
            sys.stderr.write(f"[codex_hook] cannot record sensitive flow: {exc}\n")

    if ev == "PostToolUse" and modified_outputs and output_views:
        usage["decision_kind"] = "posttool_isolation"
    elif any_warn:
        usage["decision_kind"] = "warning"
    if any_warn or modified_outputs:
        context = f"[safety-warn] {reason}" if any_warn else ""
        if modified_outputs:
            if MANUAL_BRIDGE:
                context += " [safety-redact] sanitized tool output applied by the client bridge"
            else:
                context += " [safety-redact] sanitized tool output was produced by the matcher; " \
                           "Codex PostToolUse hooks cannot replace the original output in this version"
        hook_output = {
            "hookEventName": ev or "PreToolUse",
            "additionalContext": context.strip(),
        }
        if MANUAL_BRIDGE and modified_outputs:
            hook_output["modifiedOutput"] = modified_outputs[-1]
        _emit({"hookSpecificOutput": hook_output}, usage)
        return 0
    if MANUAL_BRIDGE:
        _emit({}, usage)
    return 0  # allow


if __name__ == "__main__":
    sys.exit(main())
