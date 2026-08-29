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


def _read_turn_latch(codex_event: dict):
    """Return the original block reason for this turn, or None."""
    path = _turn_latch_path(codex_event)
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("reason") or "Blocked by Safety Orchestrator policy."
    except Exception as e:
        sys.stderr.write(f"[codex_hook] cannot read turn latch {path}: {e}\n")
        return "A previous action in this turn was blocked."


def _write_turn_latch(codex_event: dict, reason: str) -> None:
    """Persist a terminal block so a model cannot retry around it this turn."""
    path = _turn_latch_path(codex_event)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps({"reason": reason}) + "\n", encoding="utf-8")
        temporary.replace(path)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] cannot write turn latch {path}: {e}\n")


def _clear_turn_latch(codex_event: dict) -> None:
    """Release terminal state once Codex signals that the turn has stopped."""
    path = _turn_latch_path(codex_event)
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] cannot clear turn latch {path}: {e}\n")


def _deny_tool_event(ev: str, reason: str) -> int:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": ev, "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))
    sys.stderr.write(reason + "\n")
    return 2


def _read_event() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


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
        return [("matcher_user_prompt.py", {"prompt": prompt})]

    if ev == "PreToolUse":
        jobs = []
        if normalized_tool == "Bash":
            jobs.append(("matcher_bash.py", {"tool_name": "Bash", "tool_input": ti}))
        elif normalized_tool in ("apply_patch", "Edit", "Write", "MultiEdit"):
            # Codex apply_patch tool_input is a patch blob, not {file_path,content}.
            # Best-effort: scan the raw patch text as `content` so secret /
            # injection / SAST checks still fire; pass any path through too.
            patch_text = ti.get("patch") or ti.get("input") or json.dumps(ti)
            fp = ti.get("file_path") or ti.get("path") or ""
            jobs.append(("matcher_write_edit.py",
                         {"tool_name": "Write",
                          "tool_input": {"file_path": fp, "content": patch_text}}))
        if tool in ("WebFetch", "WebSearch", "webfetch", "web_search"):
            url = ti.get("url") or ti.get("urls") or ti.get("target_url") or ""
            jobs.append(("matcher_webfetch.py", {
                "url": url,
                "tool_input": ti,
            }))
        # generic checks (rate / trust / supply-chain / MCP) run for EVERY tool,
        # mirroring Claude Code's PreToolUse `*` matcher.
        jobs.append(("matcher_pretool_generic.py", {
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
                 {"tool_name": normalized_tool, "tool_input": ti, "tool_response": out,
                  "response_metadata": metadata})]

    if ev == "SubagentStart":
        return [("matcher_task.py", {"tool_name": "Task", "tool_input": ti})]

    if ev == "Stop":
        return [("matcher_stop.py",
                 {"turn_id": codex_event.get("turn_id"),
                  "final_message": (codex_event.get("last_assistant_message")
                                    or codex_event.get("final_message", "")),
                  "human_decision": codex_event.get("human_decision"),
                  "decision_context": codex_event.get("decision_context", {})})]

    return []


def _run_matcher(fname: str, cc_event: dict):
    """Run a vendored matcher as a subprocess.

    Returns (blocked, warned, reasons, modified_output). ``modified_output`` is
    the sanitized tool result emitted by redaction-style PostToolUse atoms.
    """
    script = CORE_SCRIPTS / fname
    if not script.exists():
        return (False, False, [], "")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        p = subprocess.run([sys.executable, str(script)], input=json.dumps(cc_event),
                           capture_output=True, text=True, env=env, timeout=25)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] matcher {fname} error: {e}\n")
        return (False, False, [], "")
    if p.returncode not in {0, 2}:
        detail = (p.stderr or p.stdout or f"exit {p.returncode}").strip()[:1000]
        reason = f"Safety matcher {fname} failed: {detail}"
        sys.stderr.write(f"[codex_hook] {reason}\n")
        return (FAIL_CLOSED, not FAIL_CLOSED, [reason], "")
    reasons, warned, modified_output = [], False, ""
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
            except Exception:
                pass
    return (p.returncode == 2, warned, reasons, modified_output)


def main() -> int:
    codex_event = _read_event()
    ev = codex_event.get("hook_event_name", "")

    if ev in ("PreToolUse", "PermissionRequest"):
        latched_reason = _read_turn_latch(codex_event)
        if latched_reason:
            reason = ("A previous action was blocked in this turn. The safety "
                      "verdict is terminal; do not retry or rephrase it. "
                      f"Original reason: {latched_reason}")
            return _deny_tool_event(ev, reason)

    try:
        any_block = any_warn = False
        all_reasons = []
        modified_outputs = []
        for fname, cc_event in _jobs_for(codex_event):
            blocked, warned, reasons, modified_output = _run_matcher(fname, cc_event)
            any_block |= blocked
            any_warn |= warned
            all_reasons.extend(reasons)
            if modified_output:
                modified_outputs.append(modified_output)
    except Exception as e:
        sys.stderr.write(f"[codex_hook] {'fail-closed' if FAIL_CLOSED else 'fail-open'} on error: {e}\n")
        if FAIL_CLOSED and ev in ("PreToolUse", "PermissionRequest"):
            return _deny_tool_event(ev, "Safety adapter error (fail-closed).")
        return 0

    reason = "; ".join(dict.fromkeys(all_reasons)) or "Blocked by Safety Orchestrator policy."

    if ev == "Stop":
        _clear_turn_latch(codex_event)

    if any_block:
        if ev in ("PreToolUse", "PermissionRequest"):
            _write_turn_latch(codex_event, reason)
            # Belt-and-braces: structured deny + exit 2 both signal block.
            return _deny_tool_event(ev, reason)
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0
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
        print(json.dumps({"hookSpecificOutput": hook_output}))
        return 0
    return 0  # allow


if __name__ == "__main__":
    sys.exit(main())
