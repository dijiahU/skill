"""Deterministic checks ported into the Safety Orchestrator matcher core.

The public contract of this module is intentionally host-neutral: functions
accept the Claude-shaped event already produced by each adapter and return
small finding dictionaries.  Matchers remain responsible for mapping findings
to the existing atom verdict vocabulary.

Implementation references and licenses are recorded in
``docs/PORTED_ATOM_IMPLEMENTATIONS.md`` at the workspace root.  The code here
uses only the Python standard library and keeps the existing atom IDs intact.
"""

from __future__ import annotations

import ipaddress
import hashlib
import json
import re
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit


JAILBREAK_TEMPLATE_PATTERNS = (
    re.compile(
        r"\b(?:(?:enter|enable|activate|switch\s+to|you\s+are\s+now)\s+DAN\s+mode|"
        r"DAN\s+mode\s+(?:enabled|activated)|do\s+anything\s+now)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:enable|enter|activate)\s+(?:developer|jailbreak|god|sudo)\s+mode\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:stay|remain)\s+in\s+character\b.{0,120}"
        r"\b(?:ignore|bypass|without)\b.{0,50}\b(?:rules?|policy|restrictions?)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\[(?:unlocked|jailbreak|developer)\].{0,160}"
        r"\[(?:locked|normal|classic)\]",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\bwrite\s+(?:a\s+)?(?:story|fiction|screenplay)\b.{0,180}"
        r"\b(?:no\s+rules?|ignore\s+(?:all\s+)?(?:rules?|policy)|bypass\s+safety)\b",
        re.IGNORECASE | re.DOTALL,
    ),
)

SQL_ARGUMENT_NAMES = {
    "query",
    "sql",
    "statement",
    "query_text",
    "sql_query",
    "raw_query",
    "filter",
}

MODERATION_ARGUMENT_NAMES = {
    "prompt",
    "message",
    "content",
    "body",
    "text",
    "description",
    "caption",
    "subject",
}

RESOURCE_ARGUMENT_KINDS = {
    "file_path": "file",
    "path": "file",
    "directory": "file",
    "repo": "repo",
    "repository": "repo",
    "bucket": "bucket",
    "project": "project",
    "project_id": "project",
    "account": "account",
    "account_id": "account",
    "schema": "schema",
    "namespace": "namespace",
    "resource": "resource",
    "resource_id": "resource",
}

SQL_INJECTION_PATTERNS = (
    re.compile(r"(?:'|\")\s*(?:or|and)\s+(?:'[^']*'\s*=\s*'[^']*'|\d+\s*=\s*\d+)", re.IGNORECASE),
    re.compile(r"\bunion\s+(?:all\s+)?select\b", re.IGNORECASE),
    re.compile(r";\s*(?:drop|alter|truncate|delete|insert|update|exec(?:ute)?)\b", re.IGNORECASE),
    re.compile(r"\b(?:sleep|benchmark|pg_sleep|waitfor\s+delay)\s*\(", re.IGNORECASE),
    re.compile(r"(?:--|#|/\*)\s*$", re.IGNORECASE),
)

NOSQL_EXECUTION_KEYS = {"$where", "$function", "mapReduce"}

URL_ARGUMENT_NAMES = {
    "url",
    "uri",
    "endpoint",
    "webhook",
    "callback",
    "redirect",
    "redirect_url",
    "target_url",
    "destination",
    "href",
    "source_url",
    "fetch_url",
    "request_url",
    "proxy_url",
    "remote_url",
    "host",
    "base_url",
    "api_url",
    "server_url",
}

MCP_TOOL_NAME = re.compile(r"^(?:mcp__|mcp[_:. -])|(?:^|__)mcp(?:__|$)", re.IGNORECASE)

MCP_SESSION_KEYS = {
    "mcp-session-id",
    "mcp_session_id",
    "mcpsessionid",
}

METADATA_HOSTS = {
    "metadata",
    "metadata.google",
    "metadata.google.internal",
    "metadata.azure",
    "instance-data",
    "instance-data.ec2.internal",
}

PRIVATE_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")

INSTALL_OPTIONS_WITH_VALUE = {
    "-r",
    "--requirement",
    "-c",
    "--constraint",
    "-i",
    "--index-url",
    "--extra-index-url",
    "--find-links",
    "--registry",
    "--cache",
    "--prefix",
    "--target",
    "--platform",
    "--python-version",
    "--implementation",
    "--abi",
    "--features",
    "--git",
    "--path",
}

CI_WORKFLOW_PATH = re.compile(
    r"(?:^|/)(?:\.github/workflows/[^/]+\.ya?ml|\.gitlab-ci\.ya?ml|"
    r"Jenkinsfile|\.circleci/config\.ya?ml)$",
    re.IGNORECASE,
)

GITHUB_UNTRUSTED_EXPRESSIONS = re.compile(
    r"\$\{\{\s*(?:github\.event\.(?:issue|pull_request|comment|review)\."
    r"(?:title|body)|github\.head_ref)",
    re.IGNORECASE,
)

ACTION_REFERENCE = re.compile(r"\buses\s*:\s*['\"]?([^\s'\"#]+)", re.IGNORECASE)

NPM_LIFECYCLE_HOOKS = {
    "preinstall",
    "install",
    "postinstall",
    "preuninstall",
    "uninstall",
    "postuninstall",
}

POPULAR_PACKAGES = {
    "npm": {
        "axios", "chalk", "commander", "dotenv", "eslint", "express", "lodash",
        "moment", "mongoose", "next", "react", "react-dom", "typescript", "uuid",
        "vite", "webpack", "yargs", "zod",
    },
    "PyPI": {
        "aiohttp", "boto3", "celery", "certifi", "cryptography", "django", "fastapi",
        "flask", "httpx", "jinja2", "matplotlib", "numpy", "packaging", "pandas",
        "pillow", "pydantic", "pytest", "pyyaml", "redis", "requests", "scipy",
        "selenium", "setuptools", "sqlalchemy", "torch", "urllib3", "uvicorn", "wheel",
    },
    "crates.io": {
        "anyhow", "axum", "clap", "log", "rand", "regex", "reqwest", "serde",
        "serde_json", "syn", "thiserror", "tokio", "tracing", "uuid",
    },
}

MALICIOUS_INSTALL_PATTERNS = (
    (
        "reverse shell",
        re.compile(
            r"/dev/(?:tcp|udp)/|\b(?:nc|ncat|netcat)\b[^\n]{0,100}\s-e\b|"
            r"\bbash\s+-i\b|socket\.[^\n]{0,120}(?:dup2|connect)",
            re.IGNORECASE,
        ),
    ),
    (
        "download piped to an interpreter",
        re.compile(
            r"\b(?:curl|wget)\b[^\n|;]{0,300}(?:\||;)\s*"
            r"(?:sudo\s+)?(?:sh|bash|zsh|python\d*|node|perl|ruby)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "decoded payload execution",
        re.compile(
            r"(?:base64\s+(?:-d|--decode)|b64decode|fromBase64String)"
            r"[^\n]{0,200}(?:eval|exec|spawn|system|popen|\|\s*(?:sh|bash))",
            re.IGNORECASE,
        ),
    ),
    (
        "credential or environment exfiltration",
        re.compile(
            r"(?:curl|wget|requests?\.(?:post|get)|fetch\s*\()"
            r"[^\n]{0,240}(?:process\.env|os\.environ|AWS_SECRET|TOKEN|PASSWORD|\.npmrc|\.ssh)",
            re.IGNORECASE,
        ),
    ),
    (
        "cryptocurrency miner installation",
        re.compile(r"\b(?:xmrig|minerd|cpuminer|stratum\+tcp)\b", re.IGNORECASE),
    ),
    (
        "persistence installation",
        re.compile(
            r"\bcrontab\b|authorized_keys|LaunchAgents|"
            r"(?:systemctl|launchctl)\s+(?:enable|load)|/etc/rc\.local",
            re.IGNORECASE,
        ),
    ),
)

ENCODED_CHANNEL_VALUE = re.compile(
    r"(?:[A-Za-z0-9+/]{80,}={0,2}|[0-9a-fA-F]{96,})",
)


@dataclass(frozen=True)
class PackageSpec:
    """One package installation target extracted from a shell command."""

    ecosystem: str
    name: str
    version: str = ""


def jailbreak_template_matches(text: str) -> list[str]:
    """Return matched known-template excerpts without classifying intent."""
    matches = []
    for pattern in JAILBREAK_TEMPLATE_PATTERNS:
        match = pattern.search(text)
        if match:
            matches.append(match.group(0)[:160])
    return matches


def _walk_values(value: Any, key: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from _walk_values(child, str(child_key))
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child, key)
    else:
        yield key, value


def sql_injection_findings(event: dict[str, Any]) -> list[str]:
    """Detect high-confidence SQL/NoSQL injection in database-tool arguments."""
    tool_input = event.get("tool_input", {}) or {}
    findings = []
    for key, value in _walk_values(tool_input):
        if key in NOSQL_EXECUTION_KEYS:
            findings.append(f"executable NoSQL operator {key}")
            continue
        if key.lower() not in SQL_ARGUMENT_NAMES or not isinstance(value, str):
            continue
        for pattern in SQL_INJECTION_PATTERNS:
            match = pattern.search(value)
            if match:
                findings.append(f"{key}: {match.group(0)[:120]}")
                break
    return findings


def moderation_rule_findings(event: dict[str, Any], rules_json: str) -> list[str]:
    """Apply deployer-provided regex rules to content-bearing tool arguments."""
    if not rules_json.strip():
        return []
    try:
        rules = json.loads(rules_json)
    except json.JSONDecodeError as exc:
        raise ValueError("moderation rules are not valid JSON") from exc
    if not isinstance(rules, dict):
        raise ValueError("moderation rules must be a JSON object of rule-id to regex")
    if len(rules) > 50:
        raise ValueError("moderation rule count exceeds 50")

    compiled = []
    for rule_id, pattern in rules.items():
        if not isinstance(rule_id, str) or not isinstance(pattern, str):
            raise ValueError("moderation rule IDs and patterns must be strings")
        if not rule_id or len(rule_id) > 80 or len(pattern) > 500:
            raise ValueError("moderation rule ID or pattern exceeds size limit")
        try:
            compiled.append((rule_id, re.compile(pattern, re.IGNORECASE)))
        except re.error as exc:
            raise ValueError(f"invalid moderation regex for rule '{rule_id}'") from exc

    findings = []
    scanned = 0
    for key, value in _walk_values(event.get("tool_input", {}) or {}):
        if key.lower() not in MODERATION_ARGUMENT_NAMES or not isinstance(value, str):
            continue
        text = value[:100_000]
        scanned += len(text)
        if scanned > 200_000:
            break
        for rule_id, pattern in compiled:
            if pattern.search(text):
                findings.append(rule_id)
    return list(dict.fromkeys(findings))


def resource_namespace_findings(event: dict[str, Any], policy_json: str) -> list[str]:
    """Validate structured resource arguments against a deployer namespace map."""
    if not policy_json.strip():
        return []
    try:
        policy = json.loads(policy_json)
    except json.JSONDecodeError as exc:
        raise ValueError("resource namespace policy is not valid JSON") from exc
    if not isinstance(policy, dict):
        raise ValueError("resource namespace policy must be a JSON object")
    tool_name = str(event.get("tool_name") or "")
    allowed = []
    for selector in ("*", tool_name):
        entries = policy.get(selector, [])
        if not isinstance(entries, list) or any(not isinstance(item, str) for item in entries):
            raise ValueError(f"resource namespace policy entry '{selector}' must be a string list")
        allowed.extend(entries)

    findings = []
    cwd = Path(str(event.get("cwd") or ".")).resolve()
    for key, value in _walk_values(event.get("tool_input", {}) or {}):
        kind = RESOURCE_ARGUMENT_KINDS.get(key.lower())
        if kind is None or not isinstance(value, str) or not value.strip():
            continue
        normalized = value.strip()
        if kind == "file":
            path = Path(normalized)
            normalized = str((path if path.is_absolute() else cwd / path).resolve())
        resource = f"{kind}:{normalized}"
        if not any(_resource_scope_matches(resource, pattern) for pattern in allowed):
            findings.append(f"resource '{resource}' is outside configured namespace scope")
    return findings


def _resource_scope_matches(resource: str, pattern: str) -> bool:
    if pattern.endswith("*"):
        return resource.startswith(pattern[:-1])
    return resource == pattern


def covert_channel_findings(event: dict[str, Any]) -> list[str]:
    """Detect encoded payloads hidden in outbound HTTP metadata fields."""
    tool_input = event.get("tool_input", {}) or {}
    findings = []
    for key, value in _walk_values(tool_input):
        if not isinstance(value, str):
            continue
        normalized = key.lower().replace("_", "-")
        metadata_field = (
            normalized in {"user-agent", "cookie", "metadata", "telemetry", "tracking"}
            or normalized.startswith("x-")
        )
        if metadata_field and ENCODED_CHANNEL_VALUE.search(value):
            findings.append(f"encoded payload hidden in '{key}'")
    return findings


def is_mcp_event(event: dict[str, Any]) -> bool:
    """Identify MCP calls without treating every general URL tool as MCP."""
    tool_name = str(event.get("tool_name") or "")
    return bool(
        MCP_TOOL_NAME.search(tool_name)
        or event.get("mcp_server")
        or event.get("server_name")
        or event.get("protocol") == "mcp"
    )


def _parse_unusual_ipv4(host: str) -> Any:
    """Parse integer/hex/octal IPv4 forms commonly used to bypass SSRF guards."""
    try:
        if host.count(".") == 3:
            components = []
            for component in host.split("."):
                if component.lower().startswith("0x"):
                    base = 16
                elif len(component) > 1 and component.startswith("0"):
                    base = 8
                else:
                    base = 10
                value = int(component, base)
                if not 0 <= value <= 255:
                    return None
                components.append(value)
            return ipaddress.ip_address(bytes(components))
        if host.lower().startswith("0x"):
            return ipaddress.ip_address(int(host, 16))
        if host.isdigit():
            base = 8 if len(host) > 1 and host.startswith("0") else 10
            return ipaddress.ip_address(int(host, base))
    except (ValueError, OverflowError):
        return None
    return None


def unsafe_url_reason(raw_url: str) -> str:
    """Return a reason when a literal URL is an unsafe MCP fetch target."""
    candidate = raw_url.strip()
    if not candidate:
        return ""
    try:
        parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    except ValueError:
        return "malformed URL"
    scheme = parsed.scheme.lower()
    if scheme and scheme not in {"http", "https"}:
        return f"non-HTTP scheme '{scheme}'"
    if parsed.username is not None or parsed.password is not None:
        return "embedded URL credentials"
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        return ""
    if host in METADATA_HOSTS or host == "localhost" or host.endswith(PRIVATE_HOST_SUFFIXES):
        return f"internal or metadata hostname '{host}'"
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = _parse_unusual_ipv4(host)
    if address is not None and not address.is_global:
        return f"non-global IP address '{address}'"
    return ""


def mcp_ssrf_findings(event: dict[str, Any]) -> list[str]:
    """Scan MCP URL arguments for schemes and literal internal targets."""
    if not is_mcp_event(event):
        return []
    findings = []
    for key, value in _walk_values(event.get("tool_input", {}) or {}):
        if key.lower() not in URL_ARGUMENT_NAMES or not isinstance(value, str):
            continue
        reason = unsafe_url_reason(value)
        if reason:
            findings.append(f"{key}: {reason}")
    return findings


def mcp_session_hijacking_findings(event: dict[str, Any]) -> list[str]:
    """Flag predictable MCP session IDs exposed in a request."""
    if not is_mcp_event(event):
        return []
    session_ids = []
    for key, value in _walk_values(event.get("tool_input", {}) or {}):
        normalized_key = key.lower().replace("_", "-")
        if normalized_key in {item.replace("_", "-") for item in MCP_SESSION_KEYS} and isinstance(value, str):
            session_ids.append(value.strip())

    findings = []
    for session_id in session_ids:
        if len(session_id) < 16:
            findings.append(f"session ID is too short ({len(session_id)} chars)")
        elif session_id.isdigit():
            findings.append("session ID is purely numeric and likely predictable")
        elif len(set(session_id.lower())) < 8:
            findings.append("session ID has fewer than 8 unique characters")
    return findings


def _strip_diff_prefixes(content: str) -> str:
    lines = []
    for line in content.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        lines.append(line[1:] if line.startswith("+") else line)
    return "\n".join(lines)


def ci_workflow_findings(path: str, content: str) -> list[dict[str, str]]:
    """Audit written CI workflow content using dependency-free static rules."""
    clean = _strip_diff_prefixes(content)
    likely_ci = bool(CI_WORKFLOW_PATH.search(path)) or (
        "jobs:" in clean and ("uses:" in clean or "runs-on:" in clean)
    )
    if not likely_ci:
        return []

    findings = []
    if re.search(r"(?m)^\s*pull_request_target\s*:", clean):
        severity = "critical" if "github.event.pull_request.head" in clean else "high"
        findings.append({"severity": severity, "reason": "pull_request_target trigger can expose privileged context"})

    if re.search(r"(?m)^\s*permissions\s*:\s*write-all\s*$", clean):
        findings.append({"severity": "high", "reason": "workflow grants permissions: write-all"})
    if re.search(r"(?m)^\s*contents\s*:\s*write\s*$", clean):
        findings.append({"severity": "medium", "reason": "workflow grants contents: write"})

    for match in ACTION_REFERENCE.finditer(clean):
        reference = match.group(1)
        if reference.startswith(("./", "docker://")) or "@" not in reference:
            continue
        revision = reference.rsplit("@", 1)[1]
        if re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            continue
        severity = "high" if revision.lower() in {"main", "master", "latest", "head"} else "medium"
        findings.append({"severity": severity, "reason": f"action is not pinned to a full commit SHA: {reference}"})

    for run_block in re.finditer(r"(?ms)^\s*(?:-\s*)?run\s*:\s*(.+?)(?=^\s*[-\w]+\s*:|\Z)", clean):
        match = GITHUB_UNTRUSTED_EXPRESSIONS.search(run_block.group(1))
        if match:
            findings.append({"severity": "critical", "reason": f"untrusted GitHub expression in run step: {match.group(0)}"})

    if re.search(r"\b(?:curl|wget)\b[^\n|]{0,300}\|\s*(?:sh|bash)\b", clean, re.IGNORECASE):
        findings.append({"severity": "high", "reason": "CI step pipes a network download to a shell"})
    return _deduplicate_findings(findings)


def _package_json_scripts(content: str) -> dict[str, str]:
    clean = _strip_diff_prefixes(content)
    try:
        payload = json.loads(clean)
    except (json.JSONDecodeError, TypeError):
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("scripts"), dict):
        return {str(k): str(v) for k, v in payload["scripts"].items()}

    scripts = {}
    for name in NPM_LIFECYCLE_HOOKS:
        match = re.search(rf'["\']{name}["\']\s*:\s*["\']([^"\']+)', clean, re.IGNORECASE)
        if match:
            scripts[name] = match.group(1)
    return scripts


def install_hook_findings(path: str, content: str) -> list[dict[str, str]]:
    """Find install-time code paths before the candidate file is written."""
    clean = _strip_diff_prefixes(content)
    lower_path = path.lower()
    findings = []

    scripts = _package_json_scripts(content) if (
        lower_path.endswith("package.json") or '"postinstall"' in clean or "'postinstall'" in clean
    ) else {}
    for name, command in scripts.items():
        if name.lower() in NPM_LIFECYCLE_HOOKS:
            findings.append({"severity": "high", "reason": f"npm lifecycle hook '{name}' executes: {command[:160]}"})

    if lower_path.endswith("setup.py") and re.search(
        r"\b(?:cmdclass\s*=|class\s+\w+\s*\([^)]*(?:install|develop)[^)]*\))",
        clean,
        re.IGNORECASE,
    ):
        findings.append({"severity": "high", "reason": "setup.py defines a custom install command"})
    if lower_path.endswith("build.rs"):
        findings.append({"severity": "medium", "reason": "Cargo build.rs executes during package build"})
    if lower_path.endswith("cargo.toml") and re.search(r"(?m)^\s*build\s*=\s*['\"]", clean):
        findings.append({"severity": "medium", "reason": "Cargo manifest declares a build script"})
    if lower_path.endswith(("makefile", "gnumakefile")) and re.search(r"(?m)^install\s*:", clean):
        findings.append({"severity": "medium", "reason": "Makefile declares an install target"})
    return _deduplicate_findings(findings)


def malicious_install_findings(path: str, content: str) -> list[dict[str, str]]:
    """Find concrete malicious behavior in install-time code or hook commands."""
    clean = _strip_diff_prefixes(content)
    lower_path = path.lower()
    relevant = bool(install_hook_findings(path, content)) or lower_path.endswith(
        ("setup.py", "build.rs", "install.sh", "postinstall.js", "postinstall.cjs", "postinstall.mjs")
    )
    if not relevant:
        return []

    findings = []
    for label, pattern in MALICIOUS_INSTALL_PATTERNS:
        match = pattern.search(clean)
        if match:
            findings.append({"severity": "critical", "reason": f"{label}: {match.group(0)[:160]}"})
    return _deduplicate_findings(findings)


def _deduplicate_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique = []
    for finding in findings:
        key = (finding.get("severity"), finding.get("reason"))
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    return unique


def parse_install_packages(command: str) -> list[PackageSpec]:
    """Extract npm/PyPI/crates.io/Go package targets and explicit versions."""
    if not isinstance(command, str) or not command.strip():
        return []
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        tokens = command.split()

    packages = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        basename = token.rsplit("/", 1)[-1].lower()
        ecosystem = ""
        start = -1

        if basename in {"npm", "pnpm", "yarn"} and index + 1 < len(tokens):
            verb = tokens[index + 1].lower()
            allowed = {"install", "i"} if basename == "npm" else {"install", "add", "i"}
            if verb in allowed:
                ecosystem, start = "npm", index + 2
        elif basename in {"pip", "pip3"} and index + 1 < len(tokens) and tokens[index + 1] == "install":
            ecosystem, start = "PyPI", index + 2
        elif basename.startswith("python") and tokens[index + 1:index + 4] == ["-m", "pip", "install"]:
            ecosystem, start = "PyPI", index + 4
        elif basename == "cargo" and index + 1 < len(tokens) and tokens[index + 1] == "add":
            ecosystem, start = "crates.io", index + 2
        elif basename == "go" and index + 1 < len(tokens) and tokens[index + 1] == "get":
            ecosystem, start = "Go", index + 2

        if start < 0:
            index += 1
            continue

        cursor = start
        while cursor < len(tokens):
            target = tokens[cursor]
            if target in {"&&", "||", ";", "|"}:
                break
            if target.startswith("-"):
                cursor += 2 if target in INSTALL_OPTIONS_WITH_VALUE else 1
                continue
            spec = _parse_package_target(ecosystem, target)
            if spec is not None:
                packages.append(spec)
            cursor += 1
        index = max(cursor, index + 1)

    unique = []
    seen = set()
    for package in packages:
        key = (package.ecosystem, package.name, package.version)
        if key not in seen:
            seen.add(key)
            unique.append(package)
    return unique[:20]


def package_typosquat_findings(package: PackageSpec) -> list[str]:
    """Compare a package name with a small bundled popular-name baseline."""
    candidates = POPULAR_PACKAGES.get(package.ecosystem, set())
    if not candidates or package.name.startswith("@"):
        return []
    normalized = _normalize_package_name(package.name, package.ecosystem)
    if len(normalized) < 5 or normalized in candidates:
        return []
    findings = []
    for popular in candidates:
        distance = _damerau_levenshtein(normalized, popular, limit=1)
        if distance == 1:
            findings.append(f"'{package.name}' is one edit from popular package '{popular}'")
    return findings


def dependency_confusion_findings(
    package: PackageSpec,
    public_metadata: Any,
    inventory_json: str,
) -> list[str]:
    """Compare configured internal package versions with public metadata."""
    if not inventory_json.strip():
        return []
    try:
        inventory = json.loads(inventory_json)
    except json.JSONDecodeError as exc:
        raise ValueError("internal package inventory is not valid JSON") from exc
    if not isinstance(inventory, dict):
        raise ValueError("internal package inventory must be a JSON object")
    ecosystem_inventory = inventory.get(package.ecosystem)
    if ecosystem_inventory is None:
        ecosystem_inventory = inventory.get(package.ecosystem.lower(), {})
    if not isinstance(ecosystem_inventory, dict):
        raise ValueError(f"inventory for {package.ecosystem} must be an object")
    if package.name not in ecosystem_inventory:
        return []

    internal_entry = ecosystem_inventory[package.name]
    internal_version = (
        internal_entry.get("version", "")
        if isinstance(internal_entry, dict)
        else str(internal_entry or "")
    )
    if public_metadata is None:
        return [f"public registry metadata unavailable for internal package '{package.name}'"]
    if not isinstance(public_metadata, dict) or not public_metadata.get("exists"):
        return []
    public_version = str(public_metadata.get("latest") or "")
    if not internal_version:
        return [f"internal package '{package.name}' also exists on the public registry"]
    comparison = _compare_release_versions(public_version, internal_version)
    if comparison is None:
        return [
            f"cannot safely compare public version '{public_version}' with internal "
            f"version '{internal_version}' for '{package.name}'"
        ]
    if comparison > 0:
        return [
            f"public package '{package.name}@{public_version}' is newer than internal "
            f"version '{internal_version}'"
        ]
    return []


def _normalize_package_name(name: str, ecosystem: str) -> str:
    lowered = name.lower()
    if ecosystem == "PyPI":
        return re.sub(r"[-_.]+", "-", lowered)
    return lowered


def _compare_release_versions(left: str, right: str) -> Any:
    """Compare ordinary numeric releases; return None for ambiguous versions."""
    pattern = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(?:[-+][0-9A-Za-z.-]+)?$")
    left_match = pattern.fullmatch(left.strip())
    right_match = pattern.fullmatch(right.strip())
    if not left_match or not right_match:
        return None
    left_parts = [int(part) for part in left_match.group(1).split(".")]
    right_parts = [int(part) for part in right_match.group(1).split(".")]
    width = max(len(left_parts), len(right_parts))
    left_key = tuple(left_parts + [0] * (width - len(left_parts)))
    right_key = tuple(right_parts + [0] * (width - len(right_parts)))
    return (left_key > right_key) - (left_key < right_key)


def _damerau_levenshtein(left: str, right: str, limit: int = 1) -> int:
    """Optimal-string-alignment distance with an early length bound."""
    if left == right:
        return 0
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    previous_previous = None
    previous = list(range(len(right) + 1))
    for row_index, left_char in enumerate(left, 1):
        current = [row_index]
        row_min = row_index
        for column_index, right_char in enumerate(right, 1):
            value = min(
                current[column_index - 1] + 1,
                previous[column_index] + 1,
                previous[column_index - 1] + (left_char != right_char),
            )
            if (
                previous_previous is not None
                and row_index > 1
                and column_index > 1
                and left_char == right[column_index - 2]
                and left[row_index - 2] == right_char
            ):
                value = min(value, previous_previous[column_index - 2] + 1)
            current.append(value)
            row_min = min(row_min, value)
        if row_min > limit:
            return limit + 1
        previous_previous, previous = previous, current
    return previous[-1]


def _parse_package_target(ecosystem: str, target: str) -> Any:
    if target.startswith((".", "/", "git+", "http://", "https://")):
        return None
    name, version = target, ""
    if ecosystem == "npm":
        if target.startswith("@"):
            split_at = target.rfind("@")
            if split_at > target.find("/"):
                name, version = target[:split_at], target[split_at + 1:]
        elif "@" in target:
            name, version = target.rsplit("@", 1)
    elif ecosystem == "PyPI":
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?(?:===|==)([^;\s]+)", target)
        if match:
            name, version = match.group(1), match.group(2)
        else:
            name = re.split(r"[<>=!~;\[]", target, 1)[0]
    elif ecosystem in {"crates.io", "Go"} and "@" in target:
        name, version = target.rsplit("@", 1)
        if ecosystem == "Go" and version.startswith("v"):
            version = version[1:]
    name = name.strip()
    return PackageSpec(ecosystem, name, version.strip()) if name else None


def parse_publish_time(value: Any) -> Any:
    """Parse registry RFC3339/ISO timestamps into an aware UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Missing-atom implementations (second recovery batch, 2026-08-19)
# ---------------------------------------------------------------------------

HIDDEN_INSTRUCTION_KEYS = {
    "description",
    "tool_description",
    "skill_description",
    "skill_md",
    "skill_content",
    "frontmatter",
    "instructions",
    "instruction",
    "readme",
    "prompt",
}

HIDDEN_INSTRUCTION_PATTERNS = (
    re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+"
        r"(?:instructions?|rules?|context)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:you\s+are|act\s+as|become)\s+(?:now\s+)?(?:an?\s+)?(?:unrestricted|"
        r"unfiltered|god|sudo|developer)[^\n]{0,80}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\binstructions\s+for\s+(?:the\s+)?(?:assistant|model|LLM|AI)\b", re.IGNORECASE),
    re.compile(r"\b(?:always\s+obey|never\s+tell\s+the\s+user|do\s+not\s+mention)\b", re.IGNORECASE),
    re.compile(r"[\u200b-\u200f\u2060\ufeff]{2,}"),
)

TOOL_LOADER_EXPLOIT_KEYS = {
    "loader",
    "loader_config",
    "on_install",
    "postinstall",
    "install_hook",
    "auto_execute",
    "autoload",
    "bootstrap",
}

TOOL_LOADER_EXPLOIT_PATTERNS = (
    re.compile(r"\b(?:auto_execute|autoload|on_install)\b[^\n]{0,80}\s*[:=]\s*(?:true|1|yes)", re.IGNORECASE),
    re.compile(r"\b(?:eval|exec(?:ute)?|system|spawn|subprocess)\s*\(", re.IGNORECASE),
    re.compile(r"\b(?:curl|wget)\b[^\n|;]{0,300}(?:\||;)\s*(?:sh|bash|python|node)\b", re.IGNORECASE),
    re.compile(r"\b(?:npm|npx|pip|pip3|gem|cargo)\b[^\n]{0,160}\b(?:install|exec)\b", re.IGNORECASE),
)

PERMISSION_OVERREREQUEST_KEYS = {
    "permissions",
    "required_permissions",
    "permission",
    "tools",
    "tool_permissions",
    "frontmatter",
    "skill_md",
}

PERMISSION_DANGEROUS_COMBINATIONS = (
    (("network",), ("shell", "bash", "exec", "command")),
    (("filesystem", "file", "write"), ("network", "internet")),
    (("shell", "bash", "exec"), ("network", "internet")),
)

MCP_DELEGATION_KEYS = {
    "on_behalf_of",
    "behalf_of",
    "impersonate",
    "impersonate_user",
    "delegate",
    "delegated_by",
    "caller",
    "principal",
    "acting_as",
}

MCP_SCOPE_KEYS = {
    "scope",
    "scopes",
    "authorized_scope",
    "resource_scope",
    "permission_scope",
}

TOKEN_FORWARD_KEYS = {
    "forward_headers",
    "forwarded_headers",
    "pass_through_headers",
    "passthrough_headers",
    "propagate_headers",
    "header_passthrough",
}

TOKEN_HEADER_NAMES = ("authorization", "x-api-key", "api-key", "cookie", "set-cookie", "token")

DANGEROUS_GENERATED_CODE_PATTERNS = (
    (
        "destructive filesystem command",
        re.compile(r"\brm\s+-(?:[a-z]*r[a-z]*f|f[a-z]*r)[a-z]*\s+(?:/|~|\.\.?/)", re.IGNORECASE),
    ),
    (
        "network download piped to a shell",
        re.compile(r"\b(?:curl|wget)\b[^\n|;]{0,300}(?:\||;)\s*(?:sudo\s+)?(?:sh|bash|zsh|dash)\b", re.IGNORECASE),
    ),
    (
        "fork bomb",
        re.compile(r":\s*\(\)\s*\{\s*:\s*\|\s*:?\s*&\s*\}\s*;\s*:"),
    ),
    (
        "disk destructive command",
        re.compile(r"\b(?:mkfs(?:\.\w+)?|dd\s+if=/dev/zero\s+of=/dev/[a-z]+)", re.IGNORECASE),
    ),
    (
        "base64 decoded payload execution",
        re.compile(r"\b(?:base64\s+(?:-d|--decode)|b64decode)\b[^\n]{0,240}\|\s*(?:sh|bash|python|node)\b", re.IGNORECASE),
    ),
    (
        "reverse shell backdoor",
        re.compile(r"\b(?:nc|ncat|netcat)\b[^\n]{0,120}\s+-[^\n]{0,40}\s+(?:-e\s*/bin/sh|/bin/sh|\$\()", re.IGNORECASE),
    ),
)

CAPABILITY_TOKEN_KEYS = {
    "capability_token",
    "capability",
    "macaroon",
    "biscuit",
    "signed_grant",
}

TOOL_DESCRIPTION_SCAN_KEYS = (
    "description",
    "tool_description",
    "skill_description",
    "instructions",
    "instruction",
    "prompt",
    "frontmatter",
    "skill_md",
    "skill_content",
)


def _scan_event_strings(event: dict[str, Any], key_predicate) -> Iterator[tuple[str, str]]:
    """Yield (key, string_value) for event tool-input leaves matching key_predicate."""
    for key, value in _walk_values(event.get("tool_input", {}) or {}):
        if isinstance(value, str) and key_predicate(key.lower()):
            yield key, value


def hidden_instruction_findings(event: dict[str, Any]) -> list[str]:
    """Detect LLM-targeting instructions hidden in tool/skill descriptions."""
    findings = []
    for key, value in _scan_event_strings(event, lambda k: k in HIDDEN_INSTRUCTION_KEYS):
        for pattern in HIDDEN_INSTRUCTION_PATTERNS:
            match = pattern.search(value)
            if match:
                findings.append(f"{key}: {match.group(0)[:120]}")
                break
    return findings


def tool_loader_exploit_findings(event: dict[str, Any]) -> list[str]:
    """Detect loader-abuse signals in install/loader configuration strings."""
    findings = []
    for key, value in _scan_event_strings(event, lambda k: k in TOOL_LOADER_EXPLOIT_KEYS):
        for pattern in TOOL_LOADER_EXPLOIT_PATTERNS:
            match = pattern.search(value)
            if match:
                findings.append(f"{key}: {match.group(0)[:120]}")
                break
    return findings


def skill_permission_overrequest_findings(event: dict[str, Any]) -> list[str]:
    """Detect declared permission combinations broader than a tool/skill's likely function."""
    findings = []
    for key, value in _scan_event_strings(event, lambda k: k in PERMISSION_OVERREREQUEST_KEYS):
        lowered = value.lower()
        if "tools.profile" in lowered and "full" in lowered:
            findings.append(f"{key}: full tool profile requested")
        for first_group, second_group in PERMISSION_DANGEROUS_COMBINATIONS:
            if (any(term in lowered for term in first_group)
                    and any(term in lowered for term in second_group)):
                findings.append(
                    f"{key}: dangerous permission combination "
                    f"({first_group[0]}+{second_group[0]})"
                )
                break
    return findings


def mcp_confused_deputy_findings(event: dict[str, Any]) -> list[str]:
    """Detect MCP calls that delegate privilege without an explicit scope binding."""
    if not is_mcp_event(event):
        return []
    tool_input = event.get("tool_input", {}) or {}
    keys = {str(k).lower() for k in _all_keys(tool_input)}
    has_delegation = bool(keys & MCP_DELEGATION_KEYS)
    has_scope = bool(keys & MCP_SCOPE_KEYS)
    if has_delegation and not has_scope:
        return ["MCP delegated/impersonated call is missing an explicit scope binding"]
    return []


def mcp_token_passthrough_findings(event: dict[str, Any]) -> list[str]:
    """Detect MCP requests that forward upstream credentials to another endpoint."""
    if not is_mcp_event(event):
        return []
    findings = []
    for key, value in _scan_event_strings(event, lambda k: k in TOKEN_FORWARD_KEYS):
        lowered = value.lower()
        if any(header in lowered for header in TOKEN_HEADER_NAMES):
            findings.append(f"{key}: upstream token header forwarding configured")
    return findings


def disallowed_content_rule_findings(text: str, rules_json: str) -> list[str]:
    """Apply deployer-provided regex rules to generated output text."""
    if not text or not rules_json.strip():
        return []
    try:
        rules = json.loads(rules_json)
    except json.JSONDecodeError as exc:
        raise ValueError("output content rules are not valid JSON") from exc
    if not isinstance(rules, dict):
        raise ValueError("output content rules must be a JSON object of rule-id to regex")
    if len(rules) > 50:
        raise ValueError("output content rule count exceeds 50")

    compiled = []
    for rule_id, pattern in rules.items():
        if not isinstance(rule_id, str) or not isinstance(pattern, str):
            raise ValueError("output content rule IDs and patterns must be strings")
        if not rule_id or len(rule_id) > 80 or len(pattern) > 500:
            raise ValueError("output content rule ID or pattern exceeds size limit")
        try:
            compiled.append((rule_id, re.compile(pattern, re.IGNORECASE)))
        except re.error as exc:
            raise ValueError(f"invalid output content regex for rule '{rule_id}'") from exc

    findings = []
    scanned = text[:100_000]
    for rule_id, pattern in compiled:
        if pattern.search(scanned):
            findings.append(rule_id)
    return list(dict.fromkeys(findings))


def review_generated_code_output_findings(text: str) -> list[str]:
    """Detect dangerous generated code/script snippets in final agent output."""
    if not text:
        return []
    findings = []
    for label, pattern in DANGEROUS_GENERATED_CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            findings.append(f"{label}: {match.group(0)[:160]}")
    return findings


def capability_token_findings(event: dict[str, Any], policy_json: str) -> list[str]:
    """Validate a presented capability token against a deployer-provided policy."""
    if not policy_json.strip():
        return []
    try:
        policy = json.loads(policy_json)
    except json.JSONDecodeError as exc:
        raise ValueError("capability token policy is not valid JSON") from exc
    if not isinstance(policy, dict):
        raise ValueError("capability token policy must be a JSON object")

    tool_name = str(event.get("tool_name") or "")
    tool_input = event.get("tool_input", {}) or {}
    expected = policy.get(tool_name) or policy.get("*")
    if expected is None:
        return []
    if not isinstance(expected, dict):
        raise ValueError(f"capability token policy entry for '{tool_name}' must be an object")

    token_key, token_value = next(
        ((key, value) for key, value in tool_input.items()
         if key.lower() in CAPABILITY_TOKEN_KEYS and isinstance(value, str)),
        (None, None),
    )
    if not token_value:
        return [f"capability token required for '{tool_name}' but not supplied"]

    expected_sha256 = str(expected.get("sha256") or "")
    if expected_sha256:
        actual_sha256 = hashlib.sha256(token_value.encode("utf-8")).hexdigest()
        if actual_sha256 != expected_sha256.lower():
            return ["capability token verification failed"]

    expected_scopes = expected.get("scopes")
    if isinstance(expected_scopes, list):
        scope = str(tool_input.get("scope") or tool_input.get("scopes") or "")
        if not any(scope_item in expected_scopes for scope_item in [scope]):
            return [f"capability token scope '{scope}' is not in the allowed scope list"]
    return []


def skill_signature_findings(event: dict[str, Any], policy_json: str) -> list[str]:
    """Verify a skill payload hash against a deployer-provided signature policy."""
    if not policy_json.strip():
        return []
    try:
        policy = json.loads(policy_json)
    except json.JSONDecodeError as exc:
        raise ValueError("skill signature policy is not valid JSON") from exc
    if not isinstance(policy, dict):
        raise ValueError("skill signature policy must be a JSON object")

    tool_input = event.get("tool_input", {}) or {}
    skill_name = str(tool_input.get("skill") or event.get("skill") or "")
    expected = policy.get(skill_name)
    if expected is None:
        expected = policy.get("*")
    if expected is None:
        return []
    if not isinstance(expected, dict):
        raise ValueError(f"skill signature policy entry for '{skill_name}' must be an object")

    payload = tool_input.get("content") or tool_input.get("skill_content") or ""
    expected_sha256 = str(expected.get("sha256") or "")
    if not payload or not isinstance(payload, str):
        if expected_sha256:
            return [f"skill '{skill_name or '*'}' requires signature verification but no payload is available"]
        return []
    actual_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if expected_sha256 and actual_sha256 != expected_sha256.lower():
        return [f"skill '{skill_name or '*'}' failed SHA-256 verification"]
    return []


def tool_publisher_identity_findings(event: dict[str, Any], policy_json: str) -> list[str]:
    """Check a tool/MCP server publisher against a deployer allowlist."""
    if not policy_json.strip():
        return []
    try:
        policy = json.loads(policy_json)
    except json.JSONDecodeError as exc:
        raise ValueError("publisher allowlist policy is not valid JSON") from exc
    if not isinstance(policy, dict):
        raise ValueError("publisher allowlist policy must be a JSON object")

    tool_name = str(event.get("tool_name") or "")
    tool_input = event.get("tool_input", {}) or {}
    publisher = str(tool_input.get("publisher") or tool_input.get("owner")
                    or tool_input.get("org") or event.get("publisher") or "")
    server_name = str(tool_input.get("mcp_server") or event.get("mcp_server") or "")

    allowed = policy.get(server_name) or policy.get(tool_name) or policy.get("*")
    if allowed is None:
        return []
    if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
        raise ValueError(f"publisher allowlist entry for '{server_name or tool_name or '*'}' must be a string list")
    if not publisher:
        return [f"publisher identity is required for '{server_name or tool_name}' but not supplied"]
    if publisher not in allowed:
        return [f"publisher '{publisher}' is not allowed for '{server_name or tool_name}'"]
    return []


def _all_keys(value: Any, prefix: str = "") -> Iterator[str]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield str(child_key)
            yield from _all_keys(child, f"{prefix}{child_key}.")
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child, prefix)
