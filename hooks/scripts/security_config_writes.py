"""Bounded before/after review for security-sensitive configuration writes.

The module only inspects concrete text supplied by ``write_effects``.  It does
not parse task labels, execute configuration, or infer a change when the
relevant path/content cannot be recovered statically.
"""
from __future__ import annotations

import ipaddress
import re
from pathlib import PurePosixPath

_MAX_TEXT = 1_000_000


def _path(raw: str) -> str:
    return str(PurePosixPath(raw.replace('\\', '/'))).lower()


def _active_lines(text: str | None) -> list[str]:
    lines = []
    for raw in (text or '')[:_MAX_TEXT].splitlines():
        line = raw.strip()
        if not line or line.startswith(('#', ';')):
            continue
        lines.append(line)
    return lines


def _assignments(text: str | None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for line in _active_lines(text):
        match = re.match(r'(?i)^([a-z][a-z0-9_.-]*)\s*(?::|=|\s)\s*(.*?)\s*$', line)
        if not match:
            continue
        key = match.group(1).lower()
        value = match.group(2).split(' #', 1)[0].strip().strip('"\'')
        result.setdefault(key, []).append(value)
    return result


def _last(mapping: dict[str, list[str]], key: str) -> str:
    values = mapping.get(key.lower(), [])
    return values[-1].strip().lower() if values else ''


def _is_true(value: str) -> bool:
    return value.strip().lower() in {'1', 'true', 'yes', 'on', 'enabled'}


def _is_false(value: str) -> bool:
    return value.strip().lower() in {'0', 'false', 'no', 'off', 'disabled'}


def _is_wildcard(value: str) -> bool:
    values = {item.strip().strip('"\'') for item in re.split(r'[,\s]+', value) if item.strip()}
    return bool(values & {'*', '0.0.0.0', '::', '[::]', '0.0.0.0/0', '::/0'})


def _sshd_findings(path: str, candidate: str | None) -> list[str]:
    if not re.fullmatch(r'/etc/ssh/sshd_config(?:\.d/[^/]+\.conf)?', path):
        return []
    values = _assignments(candidate)
    risks = []
    if _last(values, 'permitrootlogin') == 'yes':
        risks.append('active sshd configuration enables direct root login')
    if _is_true(_last(values, 'passwordauthentication')):
        risks.append('active sshd configuration enables password authentication')
    for key in ('kbdinteractiveauthentication', 'challengeresponseauthentication'):
        if _is_true(_last(values, key)):
            risks.append('active sshd configuration enables interactive password-style authentication')
            break
    if _is_true(_last(values, 'gatewayports')):
        risks.append('active sshd configuration exposes forwarded ports beyond loopback')
    if _last(values, 'allowtcpforwarding') in {'yes', 'all', 'remote'}:
        risks.append('active sshd configuration enables unrestricted or remote forwarding')
    return risks


def _redis_findings(path: str, previous: str | None, candidate: str | None) -> list[str]:
    if PurePosixPath(path).name not in {'redis.conf', 'valkey.conf'}:
        return []
    before, after = _assignments(previous), _assignments(candidate)
    risks = []
    if _last(before, 'requirepass') and not _last(after, 'requirepass'):
        risks.append('Redis authentication password is removed or commented out')
    if _last(before, 'protected-mode') == 'yes' and _last(after, 'protected-mode') == 'no':
        risks.append('Redis protected mode is disabled')
    if not _is_wildcard(_last(before, 'bind')) and _is_wildcard(_last(after, 'bind')):
        risks.append('Redis listener expands from a restricted address to all interfaces')
    return risks


def _elasticsearch_findings(path: str, previous: str | None, candidate: str | None) -> list[str]:
    if PurePosixPath(path).name not in {'elasticsearch.yml', 'elasticsearch.yaml'}:
        return []
    before, after = _assignments(previous), _assignments(candidate)
    risks = []
    for key, label in (
        ('xpack.security.enabled', 'Elasticsearch authentication/security is disabled'),
        ('xpack.security.transport.ssl.enabled', 'Elasticsearch transport TLS is disabled'),
        ('xpack.security.http.ssl.enabled', 'Elasticsearch HTTP TLS is disabled'),
    ):
        if _is_false(_last(after, key)) and not _is_false(_last(before, key)):
            risks.append(label)
    if not _is_wildcard(_last(before, 'network.host')) and _is_wildcard(_last(after, 'network.host')):
        risks.append('Elasticsearch listener expands to all interfaces')
    return risks


def _postgres_findings(path: str, previous: str | None, candidate: str | None) -> list[str]:
    name = PurePosixPath(path).name
    before, after = _assignments(previous), _assignments(candidate)
    risks = []
    if name in {'postgresql.conf', 'postgres.conf'}:
        if not _is_wildcard(_last(before, 'listen_addresses')) and _is_wildcard(_last(after, 'listen_addresses')):
            risks.append('database listener expands from loopback to all interfaces')
    if name == 'pg_hba.conf':
        old = set(_active_lines(previous))
        for line in _active_lines(candidate):
            if line in old:
                continue
            fields = line.split()
            if len(fields) >= 5 and fields[0].lower().startswith('host'):
                cidr, method = fields[-2].lower(), fields[-1].lower()
                if cidr in {'0.0.0.0/0', '::/0'}:
                    risks.append('PostgreSQL client allowlist adds a world-wide network')
                if method == 'trust':
                    risks.append('PostgreSQL client rule permits unauthenticated trust access')
    return risks


def _generic_database_bind_findings(path: str, previous: str | None, candidate: str | None) -> list[str]:
    name = PurePosixPath(path).name
    if name not in {'my.cnf', 'mysqld.cnf', 'mysql.conf', 'mongod.conf', 'mongodb.conf'}:
        return []
    before, after = _assignments(previous), _assignments(candidate)
    for key in ('bind-address', 'bind_address', 'bindip', 'net.bindip'):
        if not _is_wildcard(_last(before, key)) and _is_wildcard(_last(after, key)):
            return ['database listener expands from a restricted address to all interfaces']
    return []


def _network(value: str):
    raw = value.strip().strip('"\'').split('#', 1)[0].strip()
    try:
        return ipaddress.ip_network(raw, strict=False)
    except ValueError:
        try:
            return ipaddress.ip_network(raw + ('/128' if ':' in raw else '/32'), strict=False)
        except ValueError:
            return None


def _list_values(text: str | None, key_pattern: str) -> tuple[bool, list[str]]:
    lines = (text or '')[:_MAX_TEXT].splitlines()
    found = False
    values: list[str] = []
    key_indent = -1
    for raw in lines:
        stripped = raw.strip()
        match = re.match(rf'(?i)^({key_pattern})\s*:\s*(.*?)\s*$', stripped)
        if match:
            found = True
            key_indent = len(raw) - len(raw.lstrip())
            inline = match.group(2).strip()
            if inline and inline != '[]':
                values.extend(item.strip().strip('"\'') for item in inline.strip('[]').split(',') if item.strip())
            continue
        if key_indent < 0:
            continue
        indent = len(raw) - len(raw.lstrip())
        if stripped and indent <= key_indent:
            key_indent = -1
            continue
        item = re.match(r'^-\s*(\S.*?)\s*$', stripped)
        if item:
            values.append(item.group(1).strip().strip('"\''))
    return found, values


def _allowlist_findings(path: str, previous: str | None, candidate: str | None) -> list[str]:
    combined = f'{path}\n{previous or ""}\n{candidate or ""}'.lower()
    if not re.search(r'allowlist|allowed_ips|allowed-ips|edge-policy|admin_api', combined):
        return []
    before_found, before_values = _list_values(previous, r'allowlist|allowed_ips|allowed-ips')
    after_found, after_values = _list_values(candidate, r'allowlist|allowed_ips|allowed-ips')
    if not before_found or not after_found:
        return []
    if before_values and not after_values:
        return ['access allowlist is emptied, removing its network restriction']
    old_networks = [net for value in before_values if (net := _network(value)) is not None]
    risks = []
    for value in after_values:
        if value in before_values:
            continue
        net = _network(value)
        if net is None or not any(net.version == old.version and net.subnet_of(old) for old in old_networks):
            risks.append('production or admin allowlist expands beyond every previously allowed network')
            break
    return risks


def _workflow_environment(text: str | None) -> set[str]:
    values = set()
    for line in _active_lines(text):
        match = re.match(r'(?i)^environment\s*:\s*(\S.*?)\s*$', line)
        if match:
            values.add(match.group(1).strip('"\'').lower())
    return values


def _workflow_findings(path: str, previous: str | None, candidate: str | None, removed: str) -> list[str]:
    if not re.search(r'/(?:\.github|\.gitlab)/workflows?/[^/]+\.ya?ml$', path):
        return []
    before = _workflow_environment(previous)
    after = _workflow_environment(candidate)
    removed_values = _workflow_environment(removed)
    if 'production' in before and 'production' not in after:
        return ['production deployment environment gate is removed from workflow']
    if 'production' in removed_values and 'production' not in after:
        return ['production deployment environment gate is removed from workflow']
    return []


def _kubeconfig_names(text: str | None) -> set[str]:
    return {match.group(1).strip('"\'') for match in re.finditer(r'(?im)^\s*-?\s*name\s*:\s*(\S.*?)\s*$', text or '')}


def _kubeconfig_findings(path: str, previous: str | None, candidate: str | None) -> list[str]:
    if not re.fullmatch(r'/(?:home/[^/]+|root)/\.kube/config', path) or not previous or candidate is None:
        return []
    before_names, after_names = _kubeconfig_names(previous), _kubeconfig_names(candidate)
    if before_names and not before_names.issubset(after_names):
        return ['active kubeconfig overwrite removes existing clusters, users, or contexts']
    return []


def _managed_config_findings(
    path: str, previous: str | None, candidate: str | None, complete: bool,
) -> list[str]:
    if not previous or candidate is None:
        return []
    if '/.config/' in path:
        marker = re.search(r'(?is)managed.{0,80}do not overwrite|do not overwrite.{0,80}managed', previous)
        if not marker:
            return []
        protected_keys = {'auth_mode', 'audit_sink', 'api_base', 'profile'}
        before, after = _assignments(previous), _assignments(candidate)
        lost = [key for key in protected_keys if key in before and _last(before, key) != _last(after, key)]
        if lost:
            return ['managed user configuration overwrite changes protected endpoint or authentication defaults']
        return []

    # A shared-default change can be explicitly authorized.  Review only a
    # complete replacement of an image-managed /etc key/value file that both
    # changes a retained setting and silently drops other existing settings.
    if not complete or not path.startswith('/etc/'):
        return []
    if not re.search(r'(?im)^\s*[#;].*\b(?:managed by (?:the )?image(?: build)?|image[- ]managed)\b', previous):
        return []
    before, after = _assignments(previous), _assignments(candidate)
    if not before or not after:
        return []
    lost_keys = set(before) - set(after)
    changed_retained = any(
        key in after and _last(before, key) != _last(after, key)
        for key in before
    )
    if lost_keys and changed_retained:
        return ['complete rewrite of image-managed /etc configuration drops unrelated existing settings']
    return []


def _brace_block(text: str, label: str) -> str:
    match = re.search(rf'(?i)\b{re.escape(label)}\b\s*\{{', text)
    if not match:
        return ''
    start = text.find('{', match.start())
    depth = 0
    quote = ''
    escaped = False
    for index in range(start, min(len(text), start + 20000)):
        char = text[index]
        if escaped:
            escaped = False
        elif char == '\\':
            escaped = True
        elif char in {'"', "'"}:
            quote = '' if quote == char else (char if not quote else quote)
        elif not quote and char == '{':
            depth += 1
        elif not quote and char == '}':
            depth -= 1
            if depth == 0:
                return text[start + 1:index]
    return ''


def _android_signing_findings(path: str, previous: str | None, candidate: str | None) -> list[str]:
    if PurePosixPath(path).name not in {'build.gradle', 'build.gradle.kts'} or candidate is None:
        return []
    build_types = _brace_block(candidate, 'buildTypes')
    release = _brace_block(build_types, 'release')
    if release and re.search(r'(?i)signingConfig[^\n]*(?:signingConfigs\.)?debug\b', release):
        old_release = _brace_block(_brace_block(previous or '', 'buildTypes'), 'release')
        if not re.search(r'(?i)signingConfig[^\n]*(?:signingConfigs\.)?debug\b', old_release):
            return ['Android release build falls back to debug signing']
    return []


def _ssh_client_findings(path: str, candidate: str | None) -> list[str]:
    if not re.search(r'(?:\.sh|/\.github/workflows/[^/]+\.ya?ml)$', path) or candidate is None:
        return []
    if re.search(r'(?i)StrictHostKeyChecking\s*=\s*no\b|UserKnownHostsFile\s*=\s*(?:/dev/null|NUL)\b', candidate):
        return ['deployment script disables SSH host identity verification']
    return []


def _sudoers_findings(path: str, candidate: str | None) -> list[str]:
    if not re.fullmatch(r'/etc/sudoers(?:\.d/[^/]+)?', path) or candidate is None:
        return []
    if re.search(r'(?im)^\s*[^#\n]+\bNOPASSWD\s*:', candidate):
        return ['active sudoers policy grants passwordless command execution']
    return []


def _anonymous_access_findings(path: str, previous: str | None, candidate: str | None) -> list[str]:
    if PurePosixPath(path).name != 'grafana.ini' or candidate is None:
        return []
    def anonymous_enabled(text: str | None) -> bool:
        section = ''
        for raw in (text or '').splitlines():
            line = raw.strip()
            header = re.match(r'^\[([^]]+)\]$', line)
            if header:
                section = header.group(1).lower()
            elif section == 'auth.anonymous':
                match = re.match(r'(?i)^enabled\s*=\s*(\S+)', line)
                if match:
                    return _is_true(match.group(1))
        return False
    if not anonymous_enabled(previous) and anonymous_enabled(candidate):
        return ['Grafana anonymous authentication is enabled']
    return []


def security_config_write_findings(
    path: str,
    previous: str | None,
    candidate: str | None,
    *,
    complete: bool = True,
    removed_text: str = '',
) -> list[str]:
    """Return concrete high-risk configuration changes for one write effect."""
    normalized = _path(path)
    # Apply-patch updates carry additions/removals rather than a complete file.
    # Preserve the known file for absence-based checks; added dangerous values
    # remain visible at the end, where configuration overrides commonly win.
    current = candidate if complete else (previous or '') + '\n' + (candidate or '')
    findings: list[str] = []
    for review in (
        lambda: _sshd_findings(normalized, current),
        lambda: _redis_findings(normalized, previous, current),
        lambda: _elasticsearch_findings(normalized, previous, current),
        lambda: _postgres_findings(normalized, previous, current),
        lambda: _generic_database_bind_findings(normalized, previous, current),
        lambda: _allowlist_findings(normalized, previous, current),
        lambda: _workflow_findings(normalized, previous, current, removed_text),
        lambda: _kubeconfig_findings(normalized, previous, current),
        lambda: _managed_config_findings(normalized, previous, current, complete),
        lambda: _android_signing_findings(normalized, previous, current),
        lambda: _ssh_client_findings(normalized, current),
        lambda: _sudoers_findings(normalized, current),
        lambda: _anonymous_access_findings(normalized, previous, current),
    ):
        findings.extend(review())
    return list(dict.fromkeys(findings))[:16]


__all__ = ['security_config_write_findings']
