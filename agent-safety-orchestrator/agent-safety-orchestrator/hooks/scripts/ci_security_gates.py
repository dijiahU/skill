"""Conservative before/after checks for active GitHub Actions security gates."""
from __future__ import annotations

import re
import shlex

_SCAN = re.compile(
    r'(?i)\b(?:security[-_](?:scan|check|audit)|(?:scan|check|audit)[-_]security|'
    r'semgrep|bandit|trivy|gitleaks|pip-audit|npm\s+audit|cargo\s+audit|'
    r'cosign\s+verify|codeql-action/(?:analyze|init))\b'
)
_DISABLED = re.compile(
    r'(?im)^\s*(?:continue-on-error|allow_failure)\s*:\s*(?:true|1)\s*(?:#.*)?$'
    r'|^\s*if\s*:\s*(?:false|\$\{\{\s*false\s*\}\})\s*(?:#.*)?$'
)
_SUPPRESS_FAILURE = re.compile(r'\|\|\s*(?:true|:|exit\s+0)\b')


def _jobs(content: str) -> dict[str, str]:
    lines = content.splitlines()
    start = next((i for i, line in enumerate(lines) if re.fullmatch(r'jobs:\s*(?:#.*)?', line)), None)
    if start is None:
        return {}
    body = []
    for line in lines[start + 1:]:
        if line and not line[0].isspace() and not line.lstrip().startswith('#'):
            break
        if line.strip() and not line.lstrip().startswith('#'):
            body.append(line)
    if not body:
        return {}
    indent = min(len(line) - len(line.lstrip()) for line in body)
    result: dict[str, list[str]] = {}
    current = None
    for line in body:
        match = re.fullmatch(r'\s{' + str(indent) + r'}([A-Za-z_][\w-]*):\s*(?:#.*)?', line)
        if match:
            current = match.group(1)
            result[current] = []
        elif current:
            result[current].append(line)
    return {name: '\n'.join(lines) for name, lines in result.items()}


def _dependencies(job: str) -> set[str]:
    match = re.search(r'(?m)^\s*needs:\s*([^\n]*)', job)
    if not match:
        return set()
    value = match.group(1).split('#', 1)[0].strip()
    if value:
        return set(re.findall(r'[A-Za-z_][\w-]*', value))
    tail = job[match.end():]
    values = []
    for line in tail.splitlines():
        if not line.strip():
            continue
        item = re.fullmatch(r'\s*-\s*([A-Za-z_][\w-]*)\s*', line)
        if not item:
            break
        values.append(item.group(1))
    return set(values)


def _scan_line(line: str) -> bool:
    # Labels, comments and echo/printf diagnostics are not a running gate.
    if re.match(r"\s*(?:#|(?:-\s*)?(?:name|id):)", line):
        return False
    command = re.sub(r"^\s*(?:-\s*)?run:\s*", "", line).strip()
    try:
        words = shlex.split(command, comments=True)
    except ValueError:
        return False
    if words and words[0] in {"echo", "printf"}:
        return False
    return bool(_SCAN.search(command))


def _scans(job: str) -> bool:
    return any(_scan_line(line) for line in job.splitlines())


def ci_security_gate_findings(path: str, before: str | None, after: str | None,
                              *, complete: bool) -> list[str]:
    if '/.github/workflows/' not in '/' + path.lstrip('/') or not complete or before is None or after is None:
        return []
    old, new = _jobs(before), _jobs(after)
    old_security = {name for name, job in old.items() if _scans(job)}
    new_security = {name for name, job in new.items() if _scans(job)}
    if not old_security:
        return []
    findings = []
    for name, job in new.items():
        if name in old and _dependencies(old[name]) & old_security:
            if not (_dependencies(job) & new_security):
                findings.append('CI job no longer depends on an active security verification job')
        if name in new_security:
            if _DISABLED.search(job) and not _DISABLED.search(old.get(name, '')):
                findings.append('CI security verification is disabled or made non-blocking')
            new_suppressed = any(_scan_line(line) and _SUPPRESS_FAILURE.search(line) for line in job.splitlines())
            old_suppressed = any(_scan_line(line) and _SUPPRESS_FAILURE.search(line) for line in old.get(name, '').splitlines())
            if new_suppressed and not old_suppressed:
                findings.append('CI security verification failure is unconditionally suppressed')
    return list(dict.fromkeys(findings))
