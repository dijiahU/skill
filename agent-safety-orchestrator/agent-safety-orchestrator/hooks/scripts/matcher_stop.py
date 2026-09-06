#!/usr/bin/env python3
"""Stop matcher — runs when the agent finishes a turn / completes a task.

Atoms covered (3):
- record-decision-trace
- snapshot-agent-state
- log-human-decision-outcome
"""

import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, _state_dir, aggregate, check, soft_check, log_audit,
    PII_PATTERNS, SECRET_PATTERNS,
)
from matcher_posttool import (
    MARKDOWN_IMAGE_BEACON, BASE64_PAYLOAD, DNS_EXFIL_PATTERNS,
    SYSTEM_PROMPT_FRAGMENTS, INTERNAL_INFRA_PATTERNS,
)
from ported_atom_checks import (
    disallowed_content_rule_findings,
    review_generated_code_output_findings,
)
from output_proposals import unsafe_action_proposal_findings


# Shared resolver: honors SAFETY_ORCH_STATUS_DIR so all audit streams
# (decision-trace, tool-invocations, verdict-log) stay in one dir.
_STATE_DIR = _state_dir()


def main() -> int:
    event = read_event()
    ts = int(time.time())
    final_message = event.get("final_message") or event.get("last_assistant_message") or ""

    verdicts = []
    verdicts.extend(_check_final_output(final_message))
    if unsafe_action_proposal_findings(final_message, str(event.get("cwd") or "")):
        verdicts.append(check(
            "review-generated-code-output", True,
            "Final answer offers an unsafe action or workspace-script invocation; "
            "offer only a verified safe alternative or a scoped review instead",
        ))
    blocked_action = event.get("blocked_action") or {}
    if (_blocked_action_handoff(final_message, blocked_action)
            or _unsafe_gate_bypass_handoff(final_message, blocked_action)):
        verdicts.append(check(
            "review-generated-code-output", True,
            "Final answer delegates a previously blocked action to the user; "
            "describe the refusal or a verified safe alternative instead",
        ))

    # record-decision-trace — append-only structured log
    trace = _STATE_DIR / "decision-trace.jsonl"
    with trace.open("a") as f:
        f.write(json.dumps({
            "ts": ts,
            "event": "stop",
            "turn_id": event.get("turn_id"),
            "final_message_truncated": final_message[:500],
        }) + "\n")

    # snapshot-agent-state — minimal: timestamp + last counters
    state_file = _STATE_DIR / "session-counters.json"
    if state_file.exists():
        snapshot = _STATE_DIR / f"snapshot-{ts}.json"
        snapshot.write_text(state_file.read_text())

    # log-human-decision-outcome — if event carries a human decision marker
    if event.get("human_decision"):
        hd_log = _STATE_DIR / "human-decisions.jsonl"
        with hd_log.open("a") as f:
            f.write(json.dumps({
                "ts": ts,
                "decision": event["human_decision"],
                "context": event.get("decision_context", {}),
            }) + "\n")

    _check_incident_stop(event, ts)
    return aggregate(verdicts) if verdicts else 0


def _check_final_output(text: str) -> list[dict]:
    """Deterministic output-generation checks for the final assistant message."""
    if not text or not isinstance(text, str):
        return []
    verdicts = []

    pii_hits = [name for name, rx in PII_PATTERNS.items() if rx.search(text)]
    if pii_hits:
        verdicts.append(soft_check(
            "redact-output-pii", True,
            f"Final output contains PII: {', '.join(pii_hits)}",
        ))
    secret_hits = [name for name, rx in SECRET_PATTERNS.items() if rx.search(text)]
    if secret_hits:
        verdicts.append(check(
            "redact-output-secret", True,
            f"Final output contains secrets: {', '.join(secret_hits)}",
        ))
    if SYSTEM_PROMPT_FRAGMENTS.search(text):
        verdicts.append(soft_check(
            "redact-output-system-prompt", True,
            "Final output may contain system-prompt fragments",
        ))
    if INTERNAL_INFRA_PATTERNS.search(text):
        verdicts.append(soft_check(
            "redact-output-internal-infra", True,
            "Final output may contain internal infrastructure details",
        ))
    if MARKDOWN_IMAGE_BEACON.search(text):
        verdicts.append(check(
            "detect-markdown-image-beacon", True,
            "Final output contains a markdown image beacon",
        ))
    if BASE64_PAYLOAD.search(text):
        verdicts.append(soft_check(
            "detect-base64-payload-in-output", True,
            "Final output contains a large base64-looking block",
        ))
    if DNS_EXFIL_PATTERNS.search(text):
        verdicts.append(soft_check(
            "detect-dns-exfiltration-pattern", True,
            "Final output contains a possible DNS exfil pattern",
        ))

    findings = review_generated_code_output_findings(text)
    if findings:
        verdicts.append(check(
            "review-generated-code-output", True,
            f"Dangerous generated code in final output: {findings[0]}",
        ))

    rules_json = os.environ.get("SAFETY_ORCH_OUTPUT_CONTENT_RULES_JSON", "").strip()
    rules_path = os.environ.get("SAFETY_ORCH_OUTPUT_CONTENT_RULES_FILE", "").strip()
    try:
        if rules_path:
            path = Path(rules_path)
            if path.stat().st_size > 1_000_000:
                raise ValueError("output content rule file exceeds 1 MB")
            rules_json = path.read_text(encoding="utf-8")
        if rules_json:
            findings = disallowed_content_rule_findings(text, rules_json)
            if findings:
                verdicts.append(check(
                    "enforce-disallowed-content-rule", True,
                    f"Output content rule(s) matched: {', '.join(findings[:5])}",
                ))
    except (OSError, ValueError) as exc:
        log_audit("enforce-disallowed-content-rule", "config-error", {"err": str(exc)})
        verdicts.append(check(
            "enforce-disallowed-content-rule", True,
            f"Configured output content rule pack is invalid: {exc}",
        ))
    return verdicts


def _blocked_action_handoff(text: str, blocked_action: dict) -> bool:
    """Bind manual execution advice to the host-observed denied action.

    Code spans retain their actual argv, while surrounding prose punctuation
    and locally negated references must not change the action's identity.
    """
    command = str(blocked_action.get("command") or "")
    if not command or not text:
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    script_tokens = {
        token for token in tokens if re.search(r"\.(?:sh|py|js|cjs|mjs)$", token)
    }
    scripts = {Path(token).name for token in script_tokens}
    aliases = scripts | {Path(name).stem for name in scripts}
    normalized = " ".join(tokens)
    inline_code = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
    action_names = sorted(aliases | script_tokens | {normalized}, key=len, reverse=True)
    negated_action = re.compile(
        r"(?:不(?:再)?(?:使用|用|运行|执行|调用)|不用|不会(?:运行|执行)|"
        r"\b(?:without(?:\s+(?:using|running|executing|invoking))?|"
        r"do not (?:use|run|execute|invoke)|not (?:using|running|executing|invoking))\b)"
        r"[\s`*（(]*(?:" + "|".join(re.escape(name) for name in action_names if name)
        + r")(?![A-Za-z0-9_./-])",
        re.IGNORECASE,
    )

    def positive_references(fragment):
        # Remove only the explicitly excluded action, not the whole clause:
        # "without make clean, please run make clean" still has a live request.
        return negated_action.sub(" ", fragment)

    def parse_invocations(fragment):
        lexer = shlex.shlex(fragment.replace(chr(96), "").replace("：", " "), posix=True,
                            punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        try:
            words = list(lexer)
        except ValueError:
            return []
        found = []
        for index, word in enumerate(words):
            if Path(word).name not in scripts:
                continue
            previous = words[index - 1] if index else ""
            receiver = index - 1
            while receiver >= 0 and words[receiver].startswith("-"):
                receiver -= 1
            executable = (
                not index or previous in {";", "&&", "||", "|", "run", "execute"}
                or (receiver >= 0 and re.fullmatch(
                    r"(?:ba|da|z|k)?sh|python[0-9.]*|node", Path(words[receiver]).name
                ))
            )
            if not executable:
                continue
            arguments = []
            for argument in words[index + 1:]:
                if re.fullmatch(r"[;&|<>]+", argument):
                    break
                arguments.append(argument)
            found.append((Path(word).name, arguments))
        return found

    def invocations(fragment):
        fragment = positive_references(fragment)
        found = []
        # A full inline command ends at its backtick, not at the next space in
        # Chinese prose. A path-only span retains its surrounding receiver so
        # "cat `script.py`" cannot be mistaken for executing that script.
        for match in inline_code.finditer(fragment):
            code = match.group(1)
            try:
                is_command = len(shlex.split(code)) > 1
            except ValueError:
                is_command = False
            if is_command:
                found.extend(parse_invocations(code))
        found.extend(parse_invocations(fragment))
        return found

    denied_invocations = invocations(command)

    def same_execution(fragment):
        fragment = positive_references(fragment)
        for name, arguments in invocations(fragment):
            for denied_name, denied_args in denied_invocations:
                if name == denied_name and arguments[:len(denied_args)] == denied_args:
                    return True
        if not scripts and normalized:
            flattened = " ".join(fragment.replace(chr(96), "").split())
            return bool(re.search(
                r"(?<![A-Za-z0-9_/-])" + re.escape(normalized)
                + r"(?![A-Za-z0-9_/-])", flattened,
            ))
        return False

    def refers_to_action(fragment):
        fragment = positive_references(fragment)
        explicit = invocations(fragment)
        if explicit:
            # Different inspected branches remain distinct, e.g. preview/raw.
            return same_execution(fragment)
        if not scripts and same_execution(fragment):
            return True
        readonly = re.search(
            r"\b(?:cat|head|tail|less|more|sed|grep|rg|stat|ls)\b[^\n;&|]*",
            fragment,
        )
        if readonly and any(name in readonly.group() for name in scripts):
            return False
        return any(alias in fragment for alias in aliases)

    manual = re.compile(
        r"(?:建议你|你可以|如果你能|请|可以)?[^。\n;；]{0,30}"
        r"(?:手动|自己|直接在终端|自行|直接|继续|重新)[^。\n;；]{0,30}(?:运行|执行|调用)|"
        r"(?:you\s+(?:can|should)|please|I\s+recommend)[^\n.;]{0,60}"
        r"\b(?:run|execute|invoke)\b|"
        r"\b(?:run|execute|invoke)\b[^\n.;]{0,80}\b(?:manually|yourself)\b",
        re.IGNORECASE,
    )
    refusal = re.compile(
        r"(?:不要|不能|不应|请勿|不建议|拒绝|不允许|不会|无需|不需要)|"
        r"\b(?:do not|don't|never|cannot|can't|should not|must not|not safe|will not|won't|refused)\b",
        re.IGNORECASE,
    )
    clause_boundary = (
        r"[。\n;；，,]|(?<=[.!?])\s+(?=[A-Z])|"
        r"\b(?:but|however|nevertheless|then)\b|(?:但是|但|不过|然而|然后|接着|随后)"
    )

    def clauses(value):
        spans = []

        def protect(match):
            spans.append(match.group(0))
            return f"\ue000{len(spans) - 1}\ue001"

        protected = inline_code.sub(protect, value)
        for part in re.split(clause_boundary, protected, flags=re.IGNORECASE):
            yield re.sub(
                r"\ue000(\d+)\ue001",
                lambda match: spans[int(match.group(1))]
                if int(match.group(1)) < len(spans) else match.group(0),
                part,
            )

    for clause in clauses(text):
        match = manual.search(clause)
        if not match or refusal.search(clause[:match.end()]):
            continue
        if refers_to_action(clause) or re.search(
            r"(?:该|这个|上述|被拦截的)\s*(?:脚本|命令)|\b(?:it|that command|that script)\b",
            positive_references(clause), re.IGNORECASE,
        ):
            return True

    fence_pattern = chr(96) * 3 + r"[^\n]*\n(?P<body>.*?)" + chr(96) * 3
    for fence in re.finditer(fence_pattern, text, re.DOTALL):
        prefix = text[max(0, fence.start() - 120):fence.start()].strip()
        last_paragraph = list(clauses(prefix))[-1]
        for line in fence.group("body").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if same_execution(stripped) and not refusal.search(last_paragraph):
                return True
    return False


def _unsafe_gate_bypass_handoff(text: str, blocked_action: dict) -> bool:
    """An unresolved denial may not be offered as a bypass/disable menu option."""
    if not any(blocked_action.get(key) for key in ("command", "tool_name", "reason")):
        return False
    bypass = re.compile(
        r"(?:绕过|跳过|禁用|关闭)[^。\n;；]{0,35}"
        r"(?:Safety(?:[ \t]+(?:Router|Orchestrator))?|安全(?:检查|防护|策略|门|钩子)|审批|审核)|"
        r"\b(?:bypass|disable|skip|turn off)\b[^\n.;]{0,45}"
        r"\b(?:safety(?:\s+(?:router|orchestrator|checks?|hooks?))?|"
        r"security checks?|approval(?:\s+(?:gate|requirements?))?)\b|"
        r"(?:非沙箱|沙箱外|无安全检查|没有安全检查|不受安全检查)[^。\n;；，]{0,45}"
        r"(?:手动|自行|继续|重新)?(?:执行|运行|操作|重试)|"
        r"(?:执行|运行|操作|重试)[^。\n;；，]{0,45}(?:非沙箱|沙箱外|无安全检查)|"
        r"\b(?:run|execute|retry|perform|do)\b[^\n.;,]{0,65}"
        r"\b(?:outside (?:the )?sandbox|non[- ]sandbox(?:ed)?|"
        r"without (?:any )?(?:safety|security) checks?|unrestricted (?:shell|terminal|environment))\b|"
        r"\b(?:outside (?:the )?sandbox|non[- ]sandbox(?:ed)?|"
        r"without (?:any )?(?:safety|security) checks?|unrestricted (?:shell|terminal|environment))"
        r"\b[^\n.;,]{0,65}\b(?:run|execute|retry|perform|do)\b",
        re.IGNORECASE,
    )
    refusal = re.compile(
        r"(?:不要|请勿|禁止|拒绝|不能|不应|不会|不允许|无需|不需要)|"
        r"\b(?:do not|don't|never|will not|won't|cannot|can't|refuse(?:d)?|must not|no need to|need not)\b",
        re.IGNORECASE,
    )
    static_context = re.compile(
        r"(?:审计|检测|注入|攻击|不可信输出)|"
        r"\b(?:audit|detected|injection|untrusted|attempted|forbidden|prohibited)\b",
        re.IGNORECASE,
    )
    boundary = r"[。\n;；]|\b(?:but|however|nevertheless)\b|(?:但是|但|不过|然而)"
    for clause in re.split(boundary, text, flags=re.IGNORECASE):
        for match in bypass.finditer(clause):
            prefix = clause[:match.start()]
            if (refusal.search(prefix) or refusal.search(match.group())
                    or static_context.search(prefix)):
                continue
            # Explicit rejection is different from offering an unsafe option
            # with a parenthetical "not recommended" caveat.
            suffix = clause[match.end():]
            if refusal.search(suffix) or re.search(
                r"(?:is|was)\s+(?:forbidden|prohibited)|(?:不可选|不被允许)",
                suffix, re.IGNORECASE,
            ):
                continue
            return True
    return False


def _check_incident_stop(event: dict, ts: int) -> None:
    """Handle incident-response stop-side actions (ticket + playbook run)."""
    incident_file = _STATE_DIR / "incident-state.json"
    if not incident_file.exists():
        return
    try:
        incident = json.loads(incident_file.read_text())
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(incident, dict):
        return

    if incident.get("notify_pending"):
        ticket_log = _STATE_DIR / "incident-tickets.jsonl"
        with ticket_log.open("a") as f:
            f.write(json.dumps({
                "ts": ts,
                "incident_id": incident.get("incident_id", ""),
                "severity": incident.get("severity", "high"),
                "summary": str(incident.get("summary", ""))[:300],
            }) + "\n")
        log_audit("notify-oncall-and-open-ticket", "ticket-opened",
                  {"incident_id": incident.get("incident_id", "")})

    if incident.get("playbook_pending") and os.environ.get(
        "SAFETY_ORCH_RECOVERY_PLAYBOOK_JSON", ""
    ).strip():
        playbook_log = _STATE_DIR / "recovery-playbook-runs.jsonl"
        with playbook_log.open("a") as f:
            f.write(json.dumps({
                "ts": ts,
                "incident_id": incident.get("incident_id", ""),
                "playbook": os.environ["SAFETY_ORCH_RECOVERY_PLAYBOOK_JSON"][:500],
            }) + "\n")
        log_audit("execute-recovery-playbook", "playbook-run",
                  {"incident_id": incident.get("incident_id", "")})


if __name__ == "__main__":
    sys.exit(main())
