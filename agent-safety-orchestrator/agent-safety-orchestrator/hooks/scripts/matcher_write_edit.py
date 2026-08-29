#!/usr/bin/env python3
"""Write|Edit|MultiEdit matcher — runs before agent modifies any file.

Atoms covered (9):
- detect-path-traversal
- run-sast-scan (lightweight built-in rules; production should call semgrep)
- detect-hardcoded-secret-in-code
- detect-insecure-cryptography
- detect-unsafe-deserialization
- detect-injection-flaw
- audit-ci-workflow-security
- audit-install-hook
- detect-malicious-postinstall-script

Per v0.7 design: this matcher is SCOPED to Write|Edit|MultiEdit so it runs
only when agent modifies a file — not on every turn.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, aggregate, check, soft_check,
    SECRET_PATTERNS, PATH_TRAVERSAL_PATTERNS,
)
from ported_atom_checks import (
    ci_workflow_findings,
    install_hook_findings,
    malicious_install_findings,
)

INSECURE_CRYPTO_PATTERNS = re.compile(
    r"\b(MD5|SHA-?1|DES|3DES|RC4|ECB)\b"
    r"|hashlib\.(md5|sha1)"
    r"|Cipher\.new\(.*MODE_ECB"
    r"|HmacAlgorithms\.HMAC_(MD5|SHA1)"
)

UNSAFE_DESERIALIZATION_PATTERNS = re.compile(
    r"\b(pickle\.loads?|pickle\.Unpickler|"
    r"yaml\.load\s*\([^)]*(?!Loader=yaml\.SafeLoader)|"
    r"marshal\.loads?|"
    r"Object(Input|Output)Stream\.readObject|"
    r"ObjectMapper.*readValue)\b"
)

INJECTION_FLAW_PATTERNS = re.compile(
    r"(execute\([\"']?[^\"']*\"\s*\+\s*\w+"        # SQL string concat
    r"|f[\"'].*SELECT.*\{\w+\}"                     # f-string SQL
    r"|innerHTML\s*=\s*\w+"                         # XSS sink
    r"|document\.write\("
    r"|os\.system\([\"']?[^\"']*\"\s*\+\s*\w+)"     # cmd injection
)


def main() -> int:
    event = read_event()
    tool_input = event.get("tool_input", {})
    path = tool_input.get("file_path", "") or event.get("file_path", "")
    content = tool_input.get("content", "") or tool_input.get("new_string", "") or ""

    verdicts = []

    # detect-path-traversal — check path itself
    if path and PATH_TRAVERSAL_PATTERNS.search(path):
        verdicts.append(check(
            "detect-path-traversal", True,
            f"Path traversal pattern in file_path: {path}",
        ))

    if not content:
        return aggregate(verdicts) if verdicts else 0

    # Supply-chain checks run on the exact content before it is committed.
    # These scanners also understand unified-diff prefixes, keeping Codex
    # apply_patch events on the same core implementation path.
    ci_findings = ci_workflow_findings(path, content)
    if ci_findings:
        reason = "; ".join(finding["reason"] for finding in ci_findings[:4])
        severe = any(
            finding["severity"] in {"critical", "high"}
            for finding in ci_findings
        )
        verdicts.append((check if severe else soft_check)(
            "audit-ci-workflow-security", True, reason,
        ))

    hook_findings = install_hook_findings(path, content)
    if hook_findings:
        reason = "; ".join(finding["reason"] for finding in hook_findings[:4])
        verdicts.append(soft_check("audit-install-hook", True, reason))

    malicious_hooks = malicious_install_findings(path, content)
    if malicious_hooks:
        reason = "; ".join(finding["reason"] for finding in malicious_hooks[:4])
        verdicts.append(check("detect-malicious-postinstall-script", True, reason))

    # detect-hardcoded-secret-in-code
    secret_hits = [name for name, rx in SECRET_PATTERNS.items() if rx.search(content)]
    if secret_hits:
        verdicts.append(check(
            "detect-hardcoded-secret-in-code", True,
            f"Hardcoded secret(s) in file content: {', '.join(secret_hits)}",
        ))

    # detect-insecure-cryptography
    if INSECURE_CRYPTO_PATTERNS.search(content):
        m = INSECURE_CRYPTO_PATTERNS.search(content)
        verdicts.append(soft_check(
            "detect-insecure-cryptography", True,
            f"Insecure crypto primitive: '{m.group()}'",
        ))

    # detect-unsafe-deserialization
    if UNSAFE_DESERIALIZATION_PATTERNS.search(content):
        verdicts.append(check(
            "detect-unsafe-deserialization", True,
            "Unsafe deserialization sink (pickle.loads / yaml.load / etc.)",
        ))

    # detect-injection-flaw
    if INJECTION_FLAW_PATTERNS.search(content):
        verdicts.append(check(
            "detect-injection-flaw", True,
            "Injection-flaw pattern (SQL concat / XSS sink / cmd injection) detected",
        ))

    # run-sast-scan — lightweight: count high-severity primitives
    # Production should call semgrep / CodeQL here.
    sast_high = sum(1 for rx in [
        INSECURE_CRYPTO_PATTERNS,
        UNSAFE_DESERIALIZATION_PATTERNS,
        INJECTION_FLAW_PATTERNS,
    ] if rx.search(content))
    if sast_high >= 2:
        verdicts.append(check(
            "run-sast-scan", True,
            f"SAST flagged {sast_high} high-severity patterns",
        ))

    return aggregate(verdicts) if verdicts else 0


if __name__ == "__main__":
    sys.exit(main())
