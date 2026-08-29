#!/usr/bin/env python3
"""PreToolUse generic matcher — runs before every tool call regardless of name.

Heaviest hook group (30 declared atoms): generic permission/rate/trust/supply-chain
checks that apply to all tools. Delegates network-dependent checks to
helpers/cache_snapshot.py.

Atoms declared in hooks config (30):
- verify-allowed-tool-list / verify-resource-namespace-scope / verify-capability-token / check-rbac-role
- evaluate-opa-rego-rule / evaluate-content-moderation-rule / detect-sql-injection
- detect-covert-channel-in-tool-call
- enforce-tool-call-rate-limit / enforce-token-budget-cap / enforce-cost-cap-per-task / detect-runaway-loop
- check-tool-typosquat-name / verify-skill-signature / verify-tool-publisher-identity
- detect-hidden-instruction-in-tool-description / detect-tool-loader-exploit / detect-skill-permission-overrequest
- detect-mcp-confused-deputy / detect-mcp-token-passthrough / detect-mcp-session-hijacking / detect-mcp-ssrf
- detect-delayed-payload-pattern
- check-package-typosquat / check-package-cve / check-dependency-confusion /
  check-package-recency-anomaly / detect-hallucinated-package
- record-tool-invocation-trace / record-prompt-and-context-snapshot
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import read_event, aggregate, check, soft_check, log_audit, _state_dir
from ported_atom_checks import (
    capability_token_findings,
    covert_channel_findings,
    dependency_confusion_findings,
    hidden_instruction_findings,
    mcp_confused_deputy_findings,
    mcp_session_hijacking_findings,
    mcp_ssrf_findings,
    mcp_token_passthrough_findings,
    moderation_rule_findings,
    package_typosquat_findings,
    parse_install_packages,
    parse_publish_time,
    RESOURCE_ARGUMENT_KINDS,
    resource_namespace_findings,
    skill_permission_overrequest_findings,
    skill_signature_findings,
    sql_injection_findings,
    tool_loader_exploit_findings,
    tool_publisher_identity_findings,
)

# ---- session-scoped state (persisted across hook invocations via simple file) ----

_BUNDLE = Path(__file__).resolve().parent.parent.parent
# Shared resolver: honors SAFETY_ORCH_STATUS_DIR so all audit streams
# (decision-trace, tool-invocations, verdict-log) stay in one dir.
_STATE_DIR = _state_dir()
_STATE_FILE = _STATE_DIR / "session-counters.json"


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"calls": 0, "tokens": 0, "cost_cents": 0, "started_at": int(time.time()),
            "last_calls": [], "tool_call_history": [],
            "writes": 0, "irreversible_actions": 0, "external_messages": 0}


def _save_state(s: dict) -> None:
    _STATE_FILE.write_text(json.dumps(s))


# ---- atom checks ----

def _update_usage_state(state: dict, event: dict) -> None:
    """Update token/cost counters from host-supplied usage fields when present."""
    usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
    tokens = usage.get("total_tokens") or usage.get("tokens") or event.get("tokens")
    cost = usage.get("cost_cents") or event.get("cost_cents")
    if isinstance(tokens, int):
        state["tokens"] += tokens
    if isinstance(cost, (int, float)):
        state["cost_cents"] += int(cost)
    elif isinstance(cost, str) and cost.isdigit():
        state["cost_cents"] += int(cost)


def _check_rate_quota(state: dict, event: dict) -> list[dict]:
    verdicts = []
    _update_usage_state(state, event)
    cap_calls = int(os.environ.get("SAFETY_ORCH_RATE_LIMIT", "1000"))
    cap_tokens = int(os.environ.get("SAFETY_ORCH_TOKEN_BUDGET", "1000000"))
    cap_cost = int(os.environ.get("SAFETY_ORCH_COST_CAP_CENTS", "500"))

    state["calls"] += 1
    if state["calls"] > cap_calls:
        verdicts.append(check("enforce-tool-call-rate-limit", True,
                              f"Session tool calls {state['calls']} exceeds cap {cap_calls}"))
    if state["tokens"] > cap_tokens:
        verdicts.append(check("enforce-token-budget-cap", True,
                              f"Session tokens {state['tokens']} exceeds cap {cap_tokens}"))
    if state["cost_cents"] > cap_cost:
        verdicts.append(check("enforce-cost-cap-per-task", True,
                              f"Session cost ¢{state['cost_cents']} exceeds cap ¢{cap_cost}"))

    # detect-runaway-loop — same tool+args called 10+ times in last minute
    now = int(time.time())
    sig = f"{event.get('tool_name','?')}|{json.dumps(event.get('tool_input',{}),sort_keys=True)[:200]}"
    state["last_calls"] = [(t, s) for t, s in state.get("last_calls", []) if now - t < 60] + [(now, sig)]
    repeat = sum(1 for _, s in state["last_calls"] if s == sig)
    if repeat >= 10:
        verdicts.append(check("detect-runaway-loop", True,
                              f"Same call repeated {repeat}x in last 60s"))
    return verdicts


def _check_autonomy_budget(state: dict, event: dict) -> list[dict]:
    """Cumulative task-scope budget gate (writes and irreversible actions)."""
    verdicts = []
    max_writes = int(os.environ.get("SAFETY_ORCH_AUTONOMY_MAX_WRITES", "0"))
    max_irreversible = int(os.environ.get("SAFETY_ORCH_AUTONOMY_MAX_IRREVERSIBLE", "0"))
    if max_writes <= 0 and max_irreversible <= 0:
        return verdicts

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""

    if tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        state["writes"] += 1
    if _looks_irreversible(tool_name, command):
        state["irreversible_actions"] += 1

    if max_writes > 0 and state["writes"] > max_writes:
        verdicts.append(check(
            "detect-autonomy-budget-exceeded", True,
            f"Task writes {state['writes']} exceeds autonomy budget {max_writes}",
        ))
    if max_irreversible > 0 and state["irreversible_actions"] > max_irreversible:
        verdicts.append(check(
            "detect-autonomy-budget-exceeded", True,
            f"Irreversible actions {state['irreversible_actions']} exceeds autonomy budget "
            f"{max_irreversible}",
        ))
    return verdicts


def _looks_irreversible(tool_name: str, command: str) -> bool:
    if tool_name in {"Bash"} and re.search(
        r"\b(?:rm\s+-[a-z]*[rf]|git\s+push\s+--force|drop\s+(?:table|database)|"
        r"truncate\s+table|chmod\s+777|mkfs|dd\s+if=/dev/zero|shutdown|reboot)\b",
        command, re.IGNORECASE,
    ):
        return True
    return tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _check_hitl(event: dict) -> list[dict]:
    """Deterministic human-in-the-loop gate for deployer-defined high-risk actions."""
    policy_json = os.environ.get("SAFETY_ORCH_HITL_POLICY_JSON", "").strip()
    if not policy_json:
        return []
    try:
        policy = json.loads(policy_json)
    except json.JSONDecodeError:
        return [check("request-human-confirmation", True,
                      "HITL policy is not valid JSON; failing closed")]
    if not isinstance(policy, dict):
        return [check("request-human-confirmation", True,
                      "HITL policy must be a JSON object")]

    tool_name = event.get("tool_name", "")
    patterns = policy.get(tool_name) or policy.get("*")
    if not patterns:
        return []
    if isinstance(patterns, str):
        patterns = [patterns]
    if not isinstance(patterns, list):
        return [check("request-human-confirmation", True,
                      "HITL policy patterns must be a string or list of strings")]

    serialized = json.dumps(event, ensure_ascii=False, sort_keys=True)
    matched = next((p for p in patterns if isinstance(p, str) and re.search(p, serialized)), None)
    if matched is None:
        return []

    sig = hashlib.sha256(f"{tool_name}\0{matched}".encode("utf-8")).hexdigest()[:24]
    pending_file = _STATE_DIR / "hitl-pending.json"
    approvals_file = _STATE_DIR / "hitl-approvals.json"
    pending = {}
    if pending_file.exists():
        try:
            pending = json.loads(pending_file.read_text())
        except (json.JSONDecodeError, OSError):
            pending = {}
    approvals = {}
    if approvals_file.exists():
        try:
            approvals = json.loads(approvals_file.read_text())
        except (json.JSONDecodeError, OSError):
            approvals = {}

    if approvals.get(sig):
        pending.pop(sig, None)
        pending_file.write_text(json.dumps(pending, indent=2))
        return []

    try:
        timeout = max(1, int(os.environ.get("SAFETY_ORCH_HITL_TIMEOUT_SECONDS", "300")))
    except ValueError:
        timeout = 300

    entry = pending.get(sig)
    now = int(time.time())
    if entry:
        if int(entry.get("expires", now - 1)) < now:
            pending.pop(sig, None)
            pending_file.write_text(json.dumps(pending, indent=2))
            return [check("await-human-decision-or-timeout", True,
                          "Timed out awaiting human decision; default deny")]
        return [check("await-human-decision-or-timeout", True,
                      "Human confirmation pending for this action; default deny until approved")]

    pending[sig] = {"pattern": matched, "expires": now + timeout, "created_at": now}
    pending_file.write_text(json.dumps(pending, indent=2))
    return [check("request-human-confirmation", True,
                  f"Human confirmation required for action matching '{matched}'")]


def _check_incident(event: dict) -> list[dict]:
    """Read a deployer-written incident state file and enforce halt / isolation."""
    incident_file = _STATE_DIR / "incident-state.json"
    if not incident_file.exists():
        return []
    try:
        incident = json.loads(incident_file.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(incident, dict):
        return []

    verdicts = []
    if incident.get("halt"):
        verdicts.append(check(
            "halt-in-flight-action", True,
            "Incident halt is active; all tool calls are stopped",
        ))
    isolated = incident.get("isolated_resources") or []
    if isinstance(isolated, str):
        isolated = [isolated]
    if isinstance(isolated, list):
        serialized = json.dumps(event, ensure_ascii=False, sort_keys=True)
        resource_candidates = _resource_candidates(event)
        for pattern in isolated:
            if not isinstance(pattern, str) or not pattern:
                continue
            if re.search(pattern, serialized) or any(
                re.search(pattern, candidate) for candidate in resource_candidates
            ):
                verdicts.append(check(
                    "isolate-affected-resource", True,
                    f"Tool call touches isolated resource pattern '{pattern}'",
                ))
                break
    return verdicts


def _resource_candidates(event: dict) -> list[str]:
    """Return structured resource strings for an event (e.g. file:/etc/passwd)."""
    candidates = []
    tool_input = event.get("tool_input", {}) or {}
    if isinstance(tool_input, dict):
        cwd = Path(str(event.get("cwd") or ".")).resolve()
        for key, value in tool_input.items():
            kind = RESOURCE_ARGUMENT_KINDS.get(str(key).lower())
            if kind is None or not isinstance(value, str) or not value.strip():
                continue
            normalized = value.strip()
            if kind == "file":
                path = Path(normalized)
                normalized = str((path if path.is_absolute() else cwd / path).resolve())
            candidates.append(f"{kind}:{normalized}")
            candidates.append(normalized)
    return candidates


def _check_permissions(event: dict) -> list[dict]:
    verdicts = []
    tool_name = event.get("tool_name", "")

    # verify-allowed-tool-list
    allowed = os.environ.get("SAFETY_ORCH_TOOL_ALLOWLIST", "")
    if allowed:
        allowed_set = {t.strip() for t in allowed.split(",") if t.strip()}
        if tool_name and tool_name not in allowed_set:
            verdicts.append(check("verify-allowed-tool-list", True,
                                  f"Tool '{tool_name}' not in allowlist"))

    # check-rbac-role — minimal: if SAFETY_ORCH_ROLE=readonly, block writes
    role = os.environ.get("SAFETY_ORCH_ROLE", "").lower()
    if role == "readonly" and tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        verdicts.append(check("check-rbac-role", True,
                              f"Role '{role}' may not invoke {tool_name}"))

    namespace_policy = os.environ.get("SAFETY_ORCH_RESOURCE_NAMESPACES_JSON", "")
    if namespace_policy.strip():
        try:
            scope_findings = resource_namespace_findings(event, namespace_policy)
        except ValueError as exc:
            verdicts.append(check(
                "verify-resource-namespace-scope", True,
                f"Resource namespace policy is invalid: {exc}",
            ))
        else:
            if scope_findings:
                verdicts.append(check(
                    "verify-resource-namespace-scope", True, scope_findings[0],
                ))

    return verdicts


def _check_supply_chain(event: dict) -> list[dict]:
    """Check registry existence, recency and CVEs for package installs."""
    verdicts = []
    cmd = event.get("tool_input", {}).get("command", "")
    packages = parse_install_packages(cmd)
    if not packages:
        return verdicts

    try:
        from helpers import cache_snapshot
        osv_targets = []
        for package in packages[:5]:
            typosquat_findings = package_typosquat_findings(package)
            if typosquat_findings:
                verdicts.append(check(
                    "check-package-typosquat", True, typosquat_findings[0],
                ))
                continue
            meta = _query_package_metadata(cache_snapshot, package)
            if meta is cache_snapshot.NETWORK_ERROR:
                verdicts.extend(_check_dependency_confusion(package, None))
                log_audit("detect-hallucinated-package", "fail-open", {"pkg": package.name})
                verdicts.append(soft_check(
                    "check-package-recency-anomaly", True,
                    f"Registry metadata unavailable for '{package.name}'; recency check degraded",
                ))
            elif meta is not None:
                verdicts.extend(_check_dependency_confusion(package, meta))
                if not meta.get("exists"):
                    verdicts.append(check(
                        "detect-hallucinated-package", True,
                        f"Package '{package.name}' not found in registry — likely hallucinated",
                    ))
                    continue
                verdicts.extend(_check_package_recency(package.name, meta))
            else:
                verdicts.extend(_check_dependency_confusion(package, None))

            version = package.version or (meta or {}).get("latest", "")
            if version:
                osv_targets.append((package.ecosystem, package.name, str(version)))

        if osv_targets:
            osv_results = cache_snapshot.query_osv(osv_targets)
            if osv_results is cache_snapshot.NETWORK_ERROR:
                log_audit("check-package-cve", "fail-soft-block", {"packages": osv_targets})
                accept_degraded = os.environ.get("SAFETY_ORCH_ACCEPT_DEGRADED", "0") == "1"
                verdicts.append((soft_check if accept_degraded else check)(
                    "check-package-cve", True,
                    "OSV and offline snapshot unavailable; CVE check cannot complete"
                    + (" (explicit degraded mode accepted)" if accept_degraded else ""),
                ))
            else:
                for result in osv_results:
                    verdicts.extend(_cve_verdicts(result))
    except Exception as e:
        log_audit("check-package-cve", "helper-error", {"err": str(e)})
        accept_degraded = os.environ.get("SAFETY_ORCH_ACCEPT_DEGRADED", "0") == "1"
        verdicts.append((soft_check if accept_degraded else check)(
            "check-package-cve", True,
            "Package security helper failed; CVE check cannot complete"
            + (" (explicit degraded mode accepted)" if accept_degraded else ""),
        ))

    return verdicts


def _query_package_metadata(cache_snapshot, package):
    if package.ecosystem == "npm":
        return cache_snapshot.query_npm_metadata(
            package.name, atom_id="check-package-recency-anomaly",
        )
    if package.ecosystem == "PyPI":
        return cache_snapshot.query_pypi_metadata(
            package.name, atom_id="check-package-recency-anomaly",
        )
    if package.ecosystem == "crates.io":
        return cache_snapshot.query_crates_metadata(
            package.name, atom_id="check-package-recency-anomaly",
        )
    return None


def _check_dependency_confusion(package, public_metadata) -> list[dict]:
    inventory = os.environ.get("SAFETY_ORCH_INTERNAL_PACKAGES_JSON", "")
    if not inventory.strip():
        return []
    try:
        findings = dependency_confusion_findings(package, public_metadata, inventory)
    except ValueError as exc:
        return [check(
            "check-dependency-confusion", True,
            f"Internal package inventory is invalid: {exc}",
        )]
    if findings:
        return [check("check-dependency-confusion", True, findings[0])]
    return []


def _check_package_recency(package_name: str, meta: dict) -> list[dict]:
    published = parse_publish_time(meta.get("first_publish"))
    if published is None:
        return []
    try:
        threshold_days = max(1, int(os.environ.get("SAFETY_ORCH_PACKAGE_MIN_AGE_DAYS", "30")))
    except ValueError:
        threshold_days = 30
    age_days = max(0, (datetime.now(timezone.utc) - published).days)
    if age_days < threshold_days:
        return [soft_check(
            "check-package-recency-anomaly", True,
            f"Package '{package_name}' was first published {age_days}d ago "
            f"(< {threshold_days}d threshold)",
        )]
    return []


def _cve_verdicts(result) -> list[dict]:
    cves = result.cves or []
    if not cves:
        return []
    ids = [str(cve.get("id") or "unknown") for cve in cves[:5]]
    scores = [
        cve.get("cvss") for cve in cves
        if isinstance(cve.get("cvss"), (int, float))
    ]
    try:
        threshold = float(os.environ.get("SAFETY_ORCH_CVE_BLOCK_CVSS", "7.0"))
    except ValueError:
        threshold = 7.0
    highest = max(scores) if scores else None
    reason = (
        f"Package '{result.package}@{result.version}' has {len(cves)} known advisory(s): "
        f"{', '.join(ids)}"
    )
    if highest is not None and highest >= threshold:
        return [check("check-package-cve", True, f"{reason}; max CVSS {highest:g}")]
    return [soft_check("check-package-cve", True, reason)]


def _check_argument_security(event: dict) -> list[dict]:
    verdicts = []
    sql_findings = sql_injection_findings(event)
    if sql_findings:
        verdicts.append(check(
            "detect-sql-injection", True,
            f"SQL/NoSQL injection pattern detected: {sql_findings[0]}",
        ))

    ssrf_findings = mcp_ssrf_findings(event)
    if ssrf_findings:
        verdicts.append(check(
            "detect-mcp-ssrf", True,
            f"Unsafe MCP fetch target: {ssrf_findings[0]}",
        ))

    session_findings = mcp_session_hijacking_findings(event)
    if session_findings:
        verdicts.append(check(
            "detect-mcp-session-hijacking", True,
            f"Predictable MCP session identifier: {session_findings[0]}",
        ))

    covert_findings = covert_channel_findings(event)
    if covert_findings:
        verdicts.append(check(
            "detect-covert-channel-in-tool-call", True,
            f"Possible covert channel in tool arguments: {covert_findings[0]}",
        ))
    return verdicts


def _check_policy(event: dict) -> list[dict]:
    verdicts = []
    verdicts.extend(_check_content_moderation(event))
    verdicts.extend(_check_opa(event))
    return verdicts


def _check_content_moderation(event: dict) -> list[dict]:
    rules_json = os.environ.get("SAFETY_ORCH_MODERATION_RULES_JSON", "").strip()
    rules_path = os.environ.get("SAFETY_ORCH_MODERATION_RULES_FILE", "").strip()
    try:
        if rules_path:
            path = Path(rules_path)
            if path.stat().st_size > 1_000_000:
                raise ValueError("moderation rule file exceeds 1 MB")
            rules_json = path.read_text(encoding="utf-8")
        if not rules_json:
            return []
        findings = moderation_rule_findings(event, rules_json)
    except (OSError, ValueError) as exc:
        log_audit("evaluate-content-moderation-rule", "config-error", {"err": str(exc)})
        return [check(
            "evaluate-content-moderation-rule", True,
            f"Configured moderation rule pack is invalid: {exc}",
        )]
    if findings:
        return [check(
            "evaluate-content-moderation-rule", True,
            f"Content moderation rule(s) matched: {', '.join(findings[:5])}",
        )]
    return []


def _check_opa(event: dict) -> list[dict]:
    policy_path = os.environ.get("SAFETY_ORCH_OPA_POLICY_PATH", "").strip()
    if not policy_path:
        return []
    query = os.environ.get("SAFETY_ORCH_OPA_QUERY", "data.safety.allow").strip()
    if not query.startswith("data.") or any(
        not (char.isalnum() or char in "._-") for char in query
    ):
        return [_opa_failure("OPA query is not a valid data path")]
    if not Path(policy_path).exists():
        return [_opa_failure(f"OPA policy path does not exist: {policy_path}")]

    configured_binary = os.environ.get("SAFETY_ORCH_OPA_BINARY", "").strip()
    opa_binary = configured_binary or shutil.which("opa")
    if not opa_binary:
        return [_opa_failure("OPA backend is not installed")]
    try:
        process = subprocess.run(
            [
                opa_binary,
                "eval",
                "--format=json",
                "--data",
                policy_path,
                "--stdin-input",
                query,
            ],
            input=json.dumps(event, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if process.returncode != 0:
            detail = (process.stderr or process.stdout or "OPA evaluation failed")[:240]
            return [_opa_failure(detail)]
        payload = json.loads(process.stdout)
        results = payload.get("result") or []
        if not results:
            return [check(
                "evaluate-opa-rego-rule", True,
                f"OPA query '{query}' is undefined; default deny",
            )]
        expressions = results[0].get("expressions") or []
        if not expressions:
            return [check(
                "evaluate-opa-rego-rule", True,
                f"OPA query '{query}' returned no expression; default deny",
            )]
        value = expressions[0].get("value")
        allowed = value if isinstance(value, bool) else (
            value.get("allow") if isinstance(value, dict) else False
        )
        if allowed is not True:
            rule_ids = []
            if isinstance(value, dict):
                raw_ids = value.get("rule_ids") or value.get("deny") or value.get("reasons") or []
                rule_ids = raw_ids if isinstance(raw_ids, list) else [raw_ids]
            suffix = f"; rule ids: {', '.join(str(item) for item in rule_ids[:5])}" if rule_ids else ""
            return [check(
                "evaluate-opa-rego-rule", True,
                f"OPA denied planned action via '{query}'{suffix}",
            )]
    except (json.JSONDecodeError, OSError, subprocess.SubprocessError) as exc:
        return [_opa_failure(f"OPA evaluation error: {exc}")]
    return []


def _opa_failure(reason: str) -> dict:
    log_audit("evaluate-opa-rego-rule", "backend-error", {"err": reason})
    fail_open = os.environ.get("SAFETY_ORCH_OPA_FAIL_POLICY", "fail-closed") == "fail-open-warn"
    return (soft_check if fail_open else check)(
        "evaluate-opa-rego-rule", True, reason,
    )


def _check_trust(event: dict) -> list[dict]:
    """MCP-/skill-trust checks now wired for all previously declared atoms."""
    verdicts = []
    tool_name = event.get("tool_name", "")

    # check-tool-typosquat-name — naive: known-good list
    known = {"Bash", "Read", "Write", "Edit", "MultiEdit", "WebFetch", "WebSearch",
             "Task", "Grep", "Glob", "NotebookEdit", "TodoWrite", "ExitPlanMode"}
    if tool_name and tool_name not in known and len(tool_name) > 2:
        for ref in known:
            if _close_match(tool_name, ref):
                verdicts.append(check("check-tool-typosquat-name", True,
                                      f"Tool name '{tool_name}' may be typosquat of '{ref}'"))
                break

    # hidden instructions in tool/skill descriptions
    findings = hidden_instruction_findings(event)
    if findings:
        verdicts.append(check(
            "detect-hidden-instruction-in-tool-description", True,
            f"Hidden instruction in tool/skill description: {findings[0]}",
        ))

    # loader-abuse signals
    findings = tool_loader_exploit_findings(event)
    if findings:
        verdicts.append(check(
            "detect-tool-loader-exploit", True,
            f"Tool/skill loader exploit signal: {findings[0]}",
        ))

    # permission overrequest
    findings = skill_permission_overrequest_findings(event)
    if findings:
        verdicts.append(check(
            "detect-skill-permission-overrequest", True,
            f"Skill/tool permission overrequest: {findings[0]}",
        ))

    # MCP confused deputy and token passthrough
    findings = mcp_confused_deputy_findings(event)
    if findings:
        verdicts.append(check(
            "detect-mcp-confused-deputy", True,
            f"MCP confused-deputy signal: {findings[0]}",
        ))
    findings = mcp_token_passthrough_findings(event)
    if findings:
        verdicts.append(check(
            "detect-mcp-token-passthrough", True,
            f"MCP token passthrough signal: {findings[0]}",
        ))

    # deployer-configured trust policies
    verdicts.extend(_check_trust_policies(event))
    return verdicts


def _check_trust_policies(event: dict) -> list[dict]:
    """Config-gated trust policies (capability token, skill signature, publisher)."""
    verdicts = []

    cap_policy = os.environ.get("SAFETY_ORCH_CAPABILITY_TOKEN_POLICY_JSON", "").strip()
    if cap_policy:
        try:
            findings = capability_token_findings(event, cap_policy)
        except ValueError as exc:
            verdicts.append(check("verify-capability-token", True, str(exc)))
        else:
            if findings:
                verdicts.append(check("verify-capability-token", True, findings[0]))

    sig_policy = os.environ.get("SAFETY_ORCH_SKILL_SIGNATURE_POLICY_JSON", "").strip()
    if sig_policy:
        try:
            findings = skill_signature_findings(event, sig_policy)
        except ValueError as exc:
            verdicts.append(check("verify-skill-signature", True, str(exc)))
        else:
            if findings:
                verdicts.append(check("verify-skill-signature", True, findings[0]))

    pub_policy = os.environ.get("SAFETY_ORCH_PUBLISHER_ALLOWLIST_JSON", "").strip()
    if pub_policy:
        try:
            findings = tool_publisher_identity_findings(event, pub_policy)
        except ValueError as exc:
            verdicts.append(check("verify-tool-publisher-identity", True, str(exc)))
        else:
            if findings:
                verdicts.append(check("verify-tool-publisher-identity", True, findings[0]))

    return verdicts


def _close_match(a: str, b: str) -> bool:
    """Levenshtein ≤ 1 for short tool names."""
    if abs(len(a) - len(b)) > 1:
        return False
    if a == b:
        return False
    diffs = 0
    for i in range(min(len(a), len(b))):
        if a[i].lower() != b[i].lower():
            diffs += 1
            if diffs > 1:
                return False
    return True


def _record_trace(event: dict) -> None:
    """record-tool-invocation-trace — append-only audit log.

    `detail` surfaces the identifying VALUE for tools where the tool name alone
    isn't enough — most importantly the Skill tool, so the trace shows WHICH of
    our archetypes the model invoked (model-invoked skills are otherwise
    unobservable from hooks). Falls back to input_keys only."""
    tool = event.get("tool_name", "?")
    ti = event.get("tool_input", {}) or {}
    detail = ""
    if tool == "Skill":
        detail = str(ti.get("skill", ""))
    elif tool == "Task":
        detail = str(ti.get("subagent_type", ""))
    elif tool == "Bash":
        detail = str(ti.get("command", ""))[:120]
    trace = _STATE_DIR / "tool-invocations.jsonl"
    with trace.open("a") as f:
        f.write(json.dumps({
            "ts": int(time.time()),
            "tool": tool,
            "detail": detail,
            "input_keys": list(ti.keys()),
        }) + "\n")


# ---- main ----

def main() -> int:
    event = read_event()
    state = _load_state()
    try:
        verdicts = []
        verdicts.extend(_check_incident(event))
        verdicts.extend(_check_hitl(event))
        verdicts.extend(_check_rate_quota(state, event))
        verdicts.extend(_check_autonomy_budget(state, event))
        verdicts.extend(_check_permissions(event))
        verdicts.extend(_check_policy(event))
        verdicts.extend(_check_argument_security(event))
        verdicts.extend(_check_supply_chain(event))
        verdicts.extend(_check_trust(event))
        _record_trace(event)
        return aggregate(verdicts) if verdicts else 0
    finally:
        _save_state(state)


if __name__ == "__main__":
    sys.exit(main())
