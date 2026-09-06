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
from write_effects import extract_write_effects, review_write_effects

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

    # All host write tools and Bash-derived writes use the same effect review.
    for finding in review_write_effects(extract_write_effects(event)):
        verdicts.append((check if finding.severity == "block" else soft_check)(
            finding.atom_id, True,
            f"{finding.reason} (target={finding.path}, method={finding.method})",
        ))

    # detect-path-traversal — check path itself
    if path and PATH_TRAVERSAL_PATTERNS.search(path):
        verdicts.append(check(
            "detect-path-traversal", True,
            f"Path traversal pattern in file_path: {path}",
        ))

    if not content:
        return aggregate(verdicts) if verdicts else 0

    # Shared supply-chain and before/after controls were evaluated above.

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
