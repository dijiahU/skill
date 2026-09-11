#!/usr/bin/env python3
"""PostToolUse matcher — runs after every tool call, before result reaches the agent.

Atoms covered (12):
- match-yara-rule / check-malware-hash-ioc / detect-archive-bomb / detect-suspicious-mime-type / strip-active-html-script
- redact-output-pii / redact-output-secret / redact-output-system-prompt / redact-output-internal-infra
- detect-markdown-image-beacon / detect-base64-payload-in-output / detect-dns-exfiltration-pattern
- detect-indirect-prompt-injection (deterministic high-confidence fast path)

Note: PostToolUse hooks can modify the tool result (redaction) and surface warnings,
but cannot un-execute the tool call. For pre-execution defense use matcher_pretool_*.
"""

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, aggregate, check, soft_check, log_audit, _state_dir,
    PII_PATTERNS, SECRET_PATTERNS, SQL_DELETE_FROM_PATTERN,
)
from sensitive_data import minimize_sensitive_output, output_replacement_available
from archive_permission_observations import observe_sensitive_artifact_permissions
from trusted_reference_reads import is_trusted_reference_view

MARKDOWN_IMAGE_BEACON = re.compile(
    r"!\[[^\]]*\]\((https?://[^)]+(?:[?&]\w+=[^)&]*)+)\)"
)

BASE64_PAYLOAD = re.compile(r"\b[A-Za-z0-9+/]{200,}={0,2}\b")

DNS_EXFIL_PATTERNS = re.compile(
    r"\b[a-zA-Z0-9-]{40,}\.[a-zA-Z]{2,}\b"    # very long subdomain
    r"|\b(?:[a-f0-9]{8,}\.){2,}[a-zA-Z]{2,}\b"    # hex-encoded subdomains
)

ARCHIVE_BOMB_SIZE_THRESHOLD = 100 * 1024 * 1024    # 100MB decompressed

INTERNAL_INFRA_PATTERNS = re.compile(
    r"\b(\d{1,3}\.){3}\d{1,3}\b"                      # any IP
    r"|\b(internal|corp|prod)\.[a-z]+\.[a-z]+\b"     # internal domains
    r"|\b/var/log/[^\s]+|/etc/[^\s]+"                # internal paths
    r"|\bkubernetes\.default\.svc\b"
)

SYSTEM_PROMPT_FRAGMENTS = re.compile(
    r"(You are (Claude|GPT|the assistant)|"
    r"system:\s+You are|"
    r"<<SYS>>|"
    r"</?assistant>|"
    r"<\|im_start\|>system)"
)


INDIRECT_INJECTION_OUTPUT_PATTERNS = (
    (
        "output-supplied authority or follow-up instruction",
        re.compile(
            r"(?is)(?:\[(?:AUTO[-_ ]?REPAIR|P[01]|DEPLOY[-_ ]?BOT|"
            r"OFFICIAL[-_ ]?RECOVERY)\]|followup_action\s*=|follow-up action|"
            r"do not mention|never tell the user).{0,500}"
            r"(?:\brun\b|\bexecute\b|\bapply\b|\binstall\b|"
            r"\bcurl\b|\bwget\b|\bbash\b|\bpython\b|\bnode\b|\bmake\b|\bnpm\b)",
        ),
    ),
    (
        "download-and-execute payload",
        re.compile(
            r"\b(?:curl|wget)\b[^\n|;]{0,400}(?:\||;)\s*"
            r"(?:sudo\s+)?(?:sh|bash|zsh|python\d*|node|perl|ruby)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "credential exfiltration payload",
        re.compile(
            r"(?is)(?=.*\b(?:curl|wget|scp|rsync|nc|ncat|socat|"
            r"requests?\.(?:post|get)|fetch\s*\()\b)"
            r"(?=.*(?:\.env\b|\.npmrc\b|\.ssh/|credentials?|private[_ -]?key|"
            r"process\.env|os\.environ|AWS_SECRET|TOKEN|PASSWORD))",
        ),
    ),
    (
        "persistent or privilege-changing payload",
        re.compile(
            r"(?is)(?:\bcrontab\b|systemctl\s+enable\b|authorized_keys|"
            r"\.git/hooks/|LaunchAgents?|autostart\b|NOPASSWD\s*:|"
            r"PermitRootLogin\s+yes|PasswordAuthentication\s+yes|"
            r"chmod\s+(?:u\+s|[4567][0-7]{3})\b|setcap\b)",
        ),
    ),
    (
        "irreversible data or project payload",
        re.compile(
            r"(?is)(?:\bDROP\s+(?:TABLE|DATABASE)|TRUNCATE\s+TABLE|"
            + SQL_DELETE_FROM_PATTERN + r"|\brm\s+-[^\n;&|]*r[^\n;&|]*"
            r"(?:\.git\b|[/ ](?:src|tests|data|backups)\b)|"
            r"git\s+(?:reset\s+--hard|reflog\s+expire|filter-repo))",
        ),
    ),
    (
        "encoded payload execution",
        re.compile(
            r"(?is)(?:base64|b64decode|marshal\.loads|fromCharCode|Buffer\.from)"
            r".{0,600}\b(?:eval|exec|source|system|popen|subprocess|child_process)\b",
        ),
    ),
)


REVERSE_SHELL_LINE_PATTERNS = (
    re.compile(
        r"(?im)^[ \t]*(?:exec[ \t]+)?(?:/bin/)?(?:ba|z|k)?sh\b"
        r"[^\n]{0,160}(?:^|[ \t])-i(?:[ \t]|$)[^\n]{0,240}"
        r"(?:>&|[0-9]+>&)[ \t]*/dev/(?:tcp|udp)/[^/\s]+/[0-9]+"
    ),
    re.compile(
        r"(?im)^[ \t]*(?:exec[ \t]+)?(?:nc|ncat|netcat)\b"
        r"[^\n]{0,240}(?:^|[ \t])-e[ \t]+(?:/bin/)?(?:ba|z|k)?sh\b"
    ),
    re.compile(
        r"(?im)^[ \t]*(?:exec[ \t]+)?socat\b[^\n]{0,240}"
        r"\b(?:TCP|TCP4|TCP6):[^,\s]+,[^\n]{0,160}"
        r"\bEXEC:(?:/bin/)?(?:ba|z|k)?sh\b"
    ),
)

_MCP_STATUS_FILE = _state_dir() / "mcp-resource-status.json"
_MCP_IDENTITY = re.compile(
    r"(?im)^\s*(?:template|artifact|manifest|profile|resource|server|workflow|name)"
    r"\s*[:=]\s*([A-Za-z0-9_.:/-]+)\s*$"
)
_MCP_STATUS = re.compile(
    r"(?im)^\s*(?:status|state|approval)\s*[:=]\s*"
    r"(approved|attested|reviewed|authorized|review_hold|manual_hold|hold|"
    r"quarantined|pending|attestation_pending|reviewed_only)\s*$"
)


def _redact(text: str, patterns: dict[str, re.Pattern], placeholder_prefix: str) -> tuple[str, list[str]]:
    """Replace matches with [REDACTED-<name>] markers. Returns (new_text, list_of_redacted_names)."""
    redacted_names = []
    for name, rx in patterns.items():
        if rx.search(text):
            marker = f"[{placeholder_prefix}-{name.upper()}]"
            if "secret" in rx.groupindex:
                # Keep header/config keys so the model still knows which
                # credential was present, without retaining its value.
                def replace_secret(match):
                    start, end = match.span("secret")
                    offset = match.start()
                    value = match.group(0)
                    return value[:start - offset] + marker + value[end - offset:]
                text = rx.sub(replace_secret, text)
            else:
                text = rx.sub(marker, text)
            redacted_names.append(name)
    return text, redacted_names


def _is_local_file_read(event: dict) -> bool:
    """Keep local decision context intact, using the host's tool invocation.

    An IP/CIDR in an approval document or inventory is needed to compare the
    requested action with its authorized scope. This exemption concerns only
    infrastructure labels, never credentials, PII, or injection checks. Unknown
    tools and network/mixed shell commands still receive normal redaction;
    final output is independently checked by the Stop matcher.
    """
    tool_name = event.get("tool_name")
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return False
    if tool_name in {"Read", "Grep", "Glob"}:
        return not any(
            isinstance(value, str) and re.search(r"\b\w+://", value)
            for _, value in _walk_tool_input(tool_input)
        )
    if tool_name != "Bash":
        return False
    command = tool_input.get("command") or tool_input.get("cmd") or ""
    if not isinstance(command, str) or not command.strip():
        return False
    # A narrow syntax whitelist avoids treating a downloaded response, a
    # command substitution, or arbitrary program output as local file data.
    if re.search(r"[$`]|\b\w+://", command):
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()\n")
        lexer.whitespace = " \t\r"
        # shlex's comment reader swallows the newline; retain it so a later
        # network command cannot be mistaken for more arguments to cat.
        lexer.commenters = ""
        segments = [[]]
        for token in lexer:
            if token in {";", "&&", "||", "|", "\n"}:
                if segments[-1]:
                    segments.append([])
            elif any(char in token for char in "<>()") or set(token) <= set(";&|<>()\n"):
                return False
            else:
                segments[-1].append(token)
    except ValueError:
        return False
    saw_reader = False
    for words in segments:
        if not words:
            continue
        executable = words[0]
        name = Path(executable).name
        if "/" in executable and executable not in {f"/bin/{name}", f"/usr/bin/{name}"}:
            return False
        args = words[1:]
        if name == "cd" and len(args) == 1:
            continue
        if name in {"echo", "printf"}:
            continue
        if name in {"cat", "head", "tail", "grep", "wc", "cut"}:
            saw_reader = True
            continue
        if name == "rg" and not any(
            arg == "--pre" or arg.startswith("--pre=")
            or arg == "--hostname-bin" or arg.startswith("--hostname-bin=")
            for arg in args
        ):
            saw_reader = True
            continue
        if name == "sed" and args and args[0] == "-n":
            script_index = 2 if len(args) > 1 and args[1] == "-e" else 1
            if len(args) > script_index + 1 and re.fullmatch(
                r"(?:\d+|\$)(?:,(?:\d+|\$))?p", args[script_index]
            ) and all(not arg.startswith("-") for arg in args[script_index + 1:]):
                saw_reader = True
                continue
        return False
    return saw_reader


def _walk_tool_input(value, parent_key: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_tool_input(child, str(key).lower())
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_tool_input(child, parent_key)
    else:
        yield parent_key, value


def _trusted_mcp_approval_source(event: dict) -> bool:
    configured = {
        value.strip()
        for value in os.environ.get(
            "SAFETY_ORCH_MCP_APPROVAL_SOURCE_TOOLS", ""
        ).split(",")
        if value.strip()
    }
    return bool(configured) and str(event.get("tool_name") or "") in configured


def _record_mcp_resource_status(event: dict, output: str) -> None:
    """Persist holds, and approvals only from deployer-configured status tools."""
    updates: dict[str, str] = {}
    trusted_approval_source = _trusted_mcp_approval_source(event)
    blocks = re.split(r"\n\s*---+\s*\n|\n{2,}", output)
    for block in blocks:
        status_match = _MCP_STATUS.search(block)
        if not status_match:
            continue
        status = status_match.group(1).lower()
        if status in {"approved", "attested", "reviewed", "authorized"} and not trusted_approval_source:
            continue
        identities = _MCP_IDENTITY.findall(block)
        if not identities:
            tool_input = event.get("tool_input") or {}
            if isinstance(tool_input, dict):
                identities = [
                    value
                    for key, value in _walk_tool_input(tool_input)
                    if isinstance(value, str)
                    and (
                        key.endswith(("_name", "_id"))
                        or key
                        in {
                            "template",
                            "artifact",
                            "manifest",
                            "profile",
                            "resource",
                            "server",
                            "workflow",
                        }
                    )
                ]
        for identity in identities:
            updates[str(identity).lower()] = status
    if not updates:
        return
    state: dict[str, str] = {}
    if _MCP_STATUS_FILE.is_file():
        try:
            loaded = json.loads(_MCP_STATUS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state = {
                    str(key): str(value)
                    for key, value in loaded.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
        except (OSError, json.JSONDecodeError):
            state = {}
    state.update(updates)
    _MCP_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = _MCP_STATUS_FILE.with_name(
        f".{_MCP_STATUS_FILE.name}.{os.getpid()}.tmp"
    )
    temporary.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(_MCP_STATUS_FILE)


def _looks_like_executable_source(event: dict, output: str) -> bool:
    """Identify script source without treating prose that quotes a command as code."""
    if output.startswith("#!"):
        return True
    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return False
    paths = [
        value
        for key, value in _walk_tool_input(tool_input)
        if isinstance(value, str) and key in {"file_path", "path"}
    ]
    command = tool_input.get("command") or tool_input.get("cmd") or ""
    if isinstance(command, str):
        try:
            words = shlex.split(command, comments=True, posix=True)
        except ValueError:
            words = []
        if words and Path(words[0]).name in {"cat", "head", "tail"}:
            paths.extend(word for word in words[1:] if not word.startswith("-"))
    return any(Path(path).suffix in {".sh", ".bash", ".zsh", ".ksh"} for path in paths)


def _indirect_injection_findings(output: str, event: dict | None = None) -> list[dict]:
    findings = []
    for label, pattern in INDIRECT_INJECTION_OUTPUT_PATTERNS:
        for match in pattern.finditer(output):
            excerpt, _ = _redact(match.group(0), SECRET_PATTERNS, "REDACTED-SECRET")
            findings.append({
                "category": label,
                "start": match.start(),
                "end": match.end(),
                "excerpt": excerpt[:180],
            })
            if len(findings) >= 32:
                return findings
    if _looks_like_executable_source(event or {}, output):
        for pattern in REVERSE_SHELL_LINE_PATTERNS:
            for match in pattern.finditer(output):
                findings.append({
                    "category": "reverse-shell payload",
                    "start": match.start(),
                    "end": match.end(),
                    "excerpt": match.group(0)[:180],
                })
                if len(findings) >= 32:
                    return findings
    return findings


def _line_number(output: str, offset: int) -> int:
    return output.count("\n", 0, offset) + 1


def _isolate_indirect_output(output: str, findings: list[dict]) -> tuple[str, dict]:
    lines = output.splitlines(keepends=True)
    raw_ranges = []
    for finding in findings:
        start = _line_number(output, int(finding["start"]))
        end = _line_number(output, max(int(finding["start"]), int(finding["end"]) - 1))
        raw_ranges.append((start, end))
    ranges: list[list[int]] = []
    for start, end in sorted(set(raw_ranges)):
        if ranges and start <= ranges[-1][1] + 1:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([start, end])
    isolated = {number for start, end in ranges for number in range(start, end + 1)}
    rendered = []
    range_starts = {start: end for start, end in ranges}
    for number, line in enumerate(lines, start=1):
        if number not in isolated:
            rendered.append(line)
        elif number in range_starts:
            suffix = "\n" if line.endswith("\n") else ""
            rendered.append(
                f"[SAFETY-ISOLATED lines={number}-{range_starts[number]} "
                f"reason=untrusted-executable-instruction]{suffix}"
            )
    digest = hashlib.sha256(output.encode(errors="replace")).hexdigest()
    quarantine_dir = _state_dir() / "quarantine"
    quarantine_ref = f"safety-quarantine:{digest}"
    try:
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        artifact = quarantine_dir / f"{digest}.txt"
        artifact.write_text(output[:1_000_000], encoding="utf-8")
        artifact.chmod(0o600)
        metadata = quarantine_dir / f"{digest}.json"
        metadata.write_text(json.dumps({
            "schema_version": 1,
            "original_sha256": digest,
            "isolated_ranges": ranges,
            "risk_categories": sorted({str(item["category"]) for item in findings}),
            "source": "untrusted-tool-output",
        }, sort_keys=True) + "\n", encoding="utf-8")
        metadata.chmod(0o600)
    except OSError:
        quarantine_ref = f"safety-quarantine-unavailable:{digest}"
    header = (
        f"[SAFETY-REDACTED-VIEW original_sha256={digest} "
        f"quarantine_ref={quarantine_ref} provenance=untrusted-tool-output "
        "view_is_not_execution_approval=true]\n"
    )
    return header + "".join(rendered), {
        "kind": "isolated-untrusted-instructions",
        "original_sha256": digest,
        "quarantine_ref": quarantine_ref,
        "isolated_ranges": ranges,
        "risk_categories": sorted({str(item["category"]) for item in findings}),
        "provenance": "untrusted-tool-output",
        "view_is_not_execution_approval": True,
    }

def main() -> int:
    event = read_event()
    # Only an exact host-pinned policy read is trusted, never the path alone.
    if is_trusted_reference_view(event):
        return 0
    output = event.get("tool_response") or event.get("tool_output") or ""
    if isinstance(output, dict):
        output = json.dumps(output, ensure_ascii=False)
    if not isinstance(output, str):
        output = ""

    verdicts = [
        soft_check("detect-secret-in-args", True, observation.reason)
        for observation in observe_sensitive_artifact_permissions(event, output)
    ]
    # Empty output is still significant for lineage: a successful quiet local
    # archive can be observed by a later ls/stat call in the same context.
    if not output:
        return aggregate(verdicts) if verdicts else 0

    modified_output = output
    output_view = {}

    _record_mcp_resource_status(event, output)
    indirect_findings = _indirect_injection_findings(output, event)
    if indirect_findings:
        can_replace = output_replacement_available()
        if can_replace:
            modified_output, output_view = _isolate_indirect_output(output, indirect_findings)
        verdicts.append((soft_check if can_replace else check)(
            "detect-indirect-prompt-injection", True,
            "Untrusted tool/file output contained executable instructions; "
            + ("a provenance-marked isolated view replaced them" if can_replace
               else "the host cannot replace output, so the raw result remains fail-closed"),
        ))

    sensitive_view = minimize_sensitive_output(event, modified_output)
    if sensitive_view is not None:
        modified_output, sensitive_metadata = sensitive_view
        if output_view:
            # Preserve the raw tool-output lineage from injection isolation;
            # sensitive minimization is a second view layer, not a replacement
            # for the original provenance record.
            output_view = {
                **output_view,
                "sensitive_view": sensitive_metadata,
                "raw_values_withheld": True,
                "source_classes": sensitive_metadata.get("source_classes", []),
            }
        else:
            output_view = sensitive_metadata
        verdicts.append(soft_check(
            "redact-output-secret", True,
            "Protected credential output was reduced to a model-safe metadata/field view",
        ))

    # --- redaction (hook tools — silently rewrite) ---
    modified_output, pii_red = _redact(modified_output, PII_PATTERNS, "REDACTED-PII")
    if pii_red:
        verdicts.append(soft_check("redact-output-pii", True,
                                   f"Redacted output PII: {', '.join(pii_red)}"))

    modified_output, sec_red = _redact(modified_output, SECRET_PATTERNS, "REDACTED-SECRET")
    if sec_red:
        verdicts.append(soft_check("redact-output-secret", True,
                                   f"Redacted output secrets: {', '.join(sec_red)}"))

    if SYSTEM_PROMPT_FRAGMENTS.search(modified_output):
        modified_output = SYSTEM_PROMPT_FRAGMENTS.sub("[REDACTED-SYSTEM-PROMPT]", modified_output)
        verdicts.append(soft_check("redact-output-system-prompt", True,
                                   "System prompt fragment redacted from tool output"))

    if not _is_local_file_read(event) and INTERNAL_INFRA_PATTERNS.search(modified_output):
        modified_output = INTERNAL_INFRA_PATTERNS.sub("[REDACTED-INFRA]", modified_output)
        verdicts.append(soft_check("redact-output-internal-infra", True,
                                   "Internal infrastructure details redacted"))

    # --- exfiltration detect (block) ---
    if MARKDOWN_IMAGE_BEACON.search(output):
        verdicts.append(check("detect-markdown-image-beacon", True,
                              "Markdown image with query-string payload — possible beacon"))

    if BASE64_PAYLOAD.search(output):
        verdicts.append(soft_check("detect-base64-payload-in-output", True,
                                   "Large base64-looking block in output"))

    if DNS_EXFIL_PATTERNS.search(output):
        verdicts.append(soft_check("detect-dns-exfiltration-pattern", True,
                                   "Long/hex subdomain — possible DNS exfil pattern"))

    # --- payload scan (tool-output-side) ---
    # detect-suspicious-mime-type
    mime = (event.get("response_metadata", {}) or {}).get("mime_type", "")
    if mime in {"application/x-msdownload", "application/x-shockwave-flash"}:
        verdicts.append(check("detect-suspicious-mime-type", True,
                              f"Suspicious MIME: {mime}"))

    # detect-archive-bomb (size-based heuristic only — production needs ratio check)
    response_size = event.get("response_metadata", {}).get("decompressed_size", 0)
    if response_size > ARCHIVE_BOMB_SIZE_THRESHOLD:
        verdicts.append(check("detect-archive-bomb", True,
                              f"Decompressed size {response_size}B exceeds threshold"))

    # match-yara-rule — config-gated YARA scan over the returned string/blob.
    verdicts.extend(_check_yara(output))

    # check-malware-hash-ioc — consume an adapter-supplied artifact hash, or
    # a bounded set of SHA-256 literals returned by the tool.
    verdicts.extend(_check_hash_iocs(event, output))

    # strip-active-html-script — sanitize <script> if mime is html
    if "<script" in modified_output.lower() and ("html" in mime.lower() or not mime):
        modified_output = re.sub(r"<script\b[^>]*>.*?</script>", "[REMOVED-SCRIPT]",
                                 modified_output, flags=re.IGNORECASE | re.DOTALL)
        verdicts.append(soft_check("strip-active-html-script", True,
                                   "Inline <script> blocks removed from output"))

    # Emit the (possibly modified) output back via stdout JSON so host can replace.
    if modified_output != output:
        print(json.dumps({
            "modified_output": modified_output,
            "output_view": output_view,
            "verdicts": verdicts,
        }))

    return aggregate(verdicts) if verdicts else 0


def _check_hash_iocs(event: dict, output: str) -> list[dict]:
    try:
        from helpers import cache_snapshot
    except ImportError:
        return []

    hashes = []
    metadata_hash = str((event.get("response_metadata", {}) or {}).get("sha256", ""))
    if re.fullmatch(r"[0-9a-fA-F]{64}", metadata_hash):
        hashes.append(metadata_hash.lower())
    hashes.extend(match.lower() for match in re.findall(r"\b[0-9a-fA-F]{64}\b", output))
    hashes = list(dict.fromkeys(hashes))[:5]

    verdicts = []
    for sha256 in hashes:
        result = cache_snapshot.query_virustotal_hash(sha256)
        if result is None:
            continue  # Atom disabled because VIRUSTOTAL_API_KEY is absent.
        if result is cache_snapshot.NETWORK_ERROR:
            log_audit("check-malware-hash-ioc", "fail-open", {"sha256": sha256})
            verdicts.append(soft_check(
                "check-malware-hash-ioc", True,
                f"Threat-intel lookup unavailable for SHA-256 {sha256[:12]}…",
            ))
            continue
        malicious = int(result.get("malicious") or 0)
        suspicious = int(result.get("suspicious") or 0)
        reputation = result.get("reputation")
        if malicious > 0:
            verdicts.append(check(
                "check-malware-hash-ioc", True,
                f"SHA-256 {sha256[:12]}… has {malicious} malicious detections",
            ))
        elif suspicious > 0 or (isinstance(reputation, int) and reputation < 0):
            verdicts.append(soft_check(
                "check-malware-hash-ioc", True,
                f"SHA-256 {sha256[:12]}… has suspicious threat-intel reputation",
            ))
    return verdicts

def _yara_failure(reason: str) -> dict:
    log_audit("match-yara-rule", "backend-error", {"err": reason})
    fail_open = os.environ.get("SAFETY_ORCH_YARA_FAIL_POLICY", "fail-closed") == "fail-open-warn"
    return (soft_check if fail_open else check)(
        "match-yara-rule", True, reason,
    )


def _check_yara(output: str) -> list[dict]:
    """Run a deployer-provided YARA rule set over tool output.

    The atom is hook-mode and config-gated: without SAFETY_ORCH_YARA_RULES_PATH
    it passes; with it configured and no usable YARA backend it fails according
    to SAFETY_ORCH_YARA_FAIL_POLICY (default fail-closed).
    """
    rules = os.environ.get("SAFETY_ORCH_YARA_RULES_PATH", "").strip()
    if not rules:
        return []
    if not Path(rules).exists():
        return [_yara_failure(f"YARA rules path does not exist: {rules}")]

    configured_binary = os.environ.get("SAFETY_ORCH_YARA_BINARY", "").strip()
    binary = configured_binary or shutil.which("yara")
    if not binary:
        return [_yara_failure("YARA backend is not installed")]

    scan_file = _state_dir() / "yara-scan-input.bin"
    try:
        scan_file.write_text(output[:1_000_000], encoding="utf-8")
        process = subprocess.run(
            [binary, "-r", rules, str(scan_file)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [_yara_failure(f"YARA scan error: {exc}")]
    finally:
        try:
            scan_file.unlink(missing_ok=True)
        except OSError:
            pass

    if process.returncode == 1:
        return []
    if process.returncode == 0:
        matches = (process.stdout or "").strip()
        return [check(
            "match-yara-rule", True,
            f"YARA rule(s) matched tool output: {matches[:240]}",
        )]
    return [_yara_failure((process.stderr or process.stdout or "YARA scan failed")[:240])]


if __name__ == "__main__":
    sys.exit(main())
