#!/usr/bin/env python3
"""PostToolUse matcher — runs after every tool call, before result reaches the agent.

Atoms covered (12):
- match-yara-rule / check-malware-hash-ioc / detect-archive-bomb / detect-suspicious-mime-type / strip-active-html-script
- redact-output-pii / redact-output-secret / redact-output-system-prompt / redact-output-internal-infra
- detect-markdown-image-beacon / detect-base64-payload-in-output / detect-dns-exfiltration-pattern

Note: PostToolUse hooks can modify the tool result (redaction) and surface warnings,
but cannot un-execute the tool call. For pre-execution defense use matcher_pretool_*.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, aggregate, check, soft_check, log_audit, _state_dir,
    PII_PATTERNS, SECRET_PATTERNS,
)

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


def _redact(text: str, patterns: dict[str, re.Pattern], placeholder_prefix: str) -> tuple[str, list[str]]:
    """Replace matches with [REDACTED-<name>] markers. Returns (new_text, list_of_redacted_names)."""
    redacted_names = []
    for name, rx in patterns.items():
        if rx.search(text):
            text = rx.sub(f"[{placeholder_prefix}-{name.upper()}]", text)
            redacted_names.append(name)
    return text, redacted_names


def main() -> int:
    event = read_event()
    output = event.get("tool_response") or event.get("tool_output") or ""
    if isinstance(output, dict):
        output = json.dumps(output, ensure_ascii=False)
    if not output or not isinstance(output, str):
        return 0

    verdicts = []
    modified_output = output

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

    if INTERNAL_INFRA_PATTERNS.search(modified_output):
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
        print(json.dumps({"modified_output": modified_output, "verdicts": verdicts}))

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
