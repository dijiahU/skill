"""Birth- and session-anchored ownership for explicitly captured SABER jobs.

This module never searches by command name or trusts old PID-only records.
``capture`` and ``inspect`` are read-only. Persist their returned records before
cleanup. Linux pidfds pin individual verified members, so group-ID reuse cannot
redirect a signal. A process that leaves the captured session/group is rejected,
not chased. No Docker resources or filesystem contents are mutated here.
"""

import errno
import math
import os
from pathlib import Path
import re
import signal
import time


VERSION = 1
PROC = Path('/proc')
IDENTITY_FIELDS = ('pid', 'birth', 'pgid', 'sid')
TAG_NAMES = ('SABER_BATCH_ID', 'SABER_BATCH_MODEL')


class OwnershipError(RuntimeError):
    """Ownership could not be established; no permissive fallback is allowed."""


def _scope(batch, model):
    if (not isinstance(batch, str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', batch)
            or not isinstance(model, str)
            or not re.fullmatch(r'[a-z0-9_]{1,80}', model)):
        raise OwnershipError('invalid requested ownership scope')


def _boot_id():
    try:
        value = (PROC / 'sys/kernel/random/boot_id').read_text().strip()
    except OSError as exc:
        raise OwnershipError('cannot read host boot identity') from exc
    if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value):
        raise OwnershipError('invalid host boot identity')
    return value


def _read_stat(pid):
    try:
        text = (PROC / str(pid) / 'stat').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    except OSError as exc:
        raise OwnershipError('cannot inspect process identity') from exc
    try:
        if not text.startswith(f'{pid} ('):
            raise ValueError
        fields = text.rsplit(')', 1)[1].split()
        return {'pid': pid, 'birth': int(fields[19]), 'pgid': int(fields[2]),
                'sid': int(fields[3]), 'state': fields[0]}
    except (ValueError, IndexError) as exc:
        raise OwnershipError('malformed process identity') from exc


def _read_environ(pid):
    try:
        return (PROC / str(pid) / 'environ').read_bytes().split(b'\0')
    except (FileNotFoundError, ProcessLookupError):
        return None
    except OSError as exc:
        raise OwnershipError('cannot inspect process ownership tags') from exc


def _scan():
    try:
        paths = list(PROC.iterdir())
    except OSError as exc:
        raise OwnershipError('cannot enumerate process identities') from exc
    rows = {}
    for path in paths:
        if path.name.isdigit():
            row = _read_stat(int(path.name))
            if row is not None:
                rows[row['pid']] = row
    return rows


def _identity(row):
    return {field: row[field] for field in IDENTITY_FIELDS}


def _same(left, right):
    return all(left.get(field) == right.get(field) for field in IDENTITY_FIELDS)


def _check_tags(row, batch, model, require=False):
    """Read only the two ownership fields; never return environment contents."""
    values = _read_environ(row['pid'])
    after = _read_stat(row['pid'])
    if after is None:
        return False
    if not _same(row, after):
        raise OwnershipError('process identity changed while checking tags')
    if values is None:
        raise OwnershipError('ownership tags disappeared for a live process')
    for name, expected in zip(TAG_NAMES, (batch, model)):
        prefix = (name + '=').encode()
        found = [item[len(prefix):] for item in values if item.startswith(prefix)]
        if any(value != expected.encode() for value in found):
            raise OwnershipError('explicit process ownership tag conflicts with scope')
        if require and not found:
            raise OwnershipError('session leader lacks required ownership tags')
    return True


def _check_record(record, batch, model, boot):
    if (not isinstance(record, dict) or record.get('version') != VERSION
            or record.get('batch') != batch or record.get('model') != model
            or record.get('boot_id') != boot):
        raise OwnershipError('ownership record version, scope, or boot identity mismatch')
    if any(type(record.get(key)) is not int or record[key] <= 0 for key in IDENTITY_FIELDS):
        raise OwnershipError('ownership record lacks process birth identity')
    if record['pid'] <= 1 or record['pid'] != record['pgid'] or record['pid'] != record['sid']:
        raise OwnershipError('ownership record is not an independent session leader')
    if record['pgid'] == os.getpgrp() or record['sid'] == os.getsid(0):
        raise OwnershipError('refuse to target the cleanup caller session')
    members = record.get('members')
    if not isinstance(members, list) or not members:
        raise OwnershipError('ownership record has no captured identity anchors')
    seen = set()
    for member in members:
        if (not isinstance(member, dict)
                or any(type(member.get(key)) is not int or member[key] <= 0
                       for key in IDENTITY_FIELDS)
                or member['pid'] in seen or member['birth'] < record['birth']
                or member['pgid'] != record['pgid'] or member['sid'] != record['sid']):
            raise OwnershipError('invalid captured member identity')
        seen.add(member['pid'])
    if not any(_same(record, member) for member in members):
        raise OwnershipError('ownership record lost its original leader identity')


def capture(pid, batch, model):
    """Capture a tagged independent session leader and its current group members.

    The leader must still exist and carry both tags at capture time. Children
    may have lost tags after changing their process title; conflicting tags are
    always rejected. The return value is JSON-serializable and contains no env.
    """
    _scope(batch, model)
    if type(pid) is not int or pid <= 1:
        raise OwnershipError('invalid leader PID')
    boot = _boot_id()
    leader = _read_stat(pid)
    if leader is None or leader['state'] in ('Z', 'X', 'x'):
        raise OwnershipError('capture requires a live session leader')
    if leader['pid'] != leader['pgid'] or leader['pid'] != leader['sid']:
        raise OwnershipError('capture requires an independent session and process group')
    if not _check_tags(leader, batch, model, require=True):
        raise OwnershipError('session leader exited during capture')
    record = {'version': VERSION, 'batch': batch, 'model': model, 'boot_id': boot,
              **_identity(leader), 'members': [_identity(leader)]}
    return inspect([record], batch, model)['records'][0]


def inspect(records, batch, model):
    """Validate records read-only; return previews plus updated anchor records.

    New members are admitted only while at least one previously recorded birth
    identity still anchors the same session/group. Keep ``report['records']``
    when saving a preview, including members already exited. No active members
    means a validated no-op, not permission to signal a bare group number.
    """
    _scope(batch, model)
    if not isinstance(records, list):
        raise OwnershipError('records must be a list of complete captured identities')
    boot = _boot_id()
    seen_groups = set()
    for record in records:
        _check_record(record, batch, model, boot)
        if record['pgid'] in seen_groups:
            raise OwnershipError('duplicate ownership group record')
        seen_groups.add(record['pgid'])
    processes = _scan()
    groups = []
    for record in records:
        known = {row['pid']: _identity(row) for row in record['members']}
        anchors = []
        for pid, identity in known.items():
            current = processes.get(pid)
            if current is not None:
                if not _same(identity, current):
                    raise OwnershipError('captured PID reused or session/group identity changed')
                anchors.append(pid)
        members = []
        for row in processes.values():
            if row['sid'] != record['sid'] and row['pgid'] != record['pgid']:
                continue
            if row['sid'] != record['sid'] or row['pgid'] != record['pgid']:
                raise OwnershipError('captured session/group has an out-of-scope member')
            if row['birth'] < record['birth']:
                raise OwnershipError('session member predates the captured leader')
            if row['state'] in ('Z', 'X', 'x'):
                continue
            if _check_tags(row, batch, model):
                members.append(row)
        # Recheck anchors after tag reads; a vanished leader cannot authorize
        # unobserved descendants just because it was in the earlier /proc scan.
        anchors = [pid for pid in anchors if (current := _read_stat(pid)) is not None
                   and _same(known[pid], current)]
        if members and not anchors:
            raise OwnershipError('live group has no surviving verified identity anchor')
        for row in members:
            known[row['pid']] = _identity(row)
        updated = {**record, 'members': [known[pid] for pid in sorted(known)]}
        groups.append({'record': updated, 'active_pids': sorted(row['pid'] for row in members),
                       'anchor_pids': sorted(anchors), 'gone': not members})
    return {'passed': True, 'groups': groups, 'records': [group['record'] for group in groups]}


def validate(records, batch, model):
    """Read-only alias for inspect, raising OwnershipError on unsafe evidence."""
    return inspect(records, batch, model)


def _signal_members(report, batch, model, sig, sent):
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise OwnershipError('safe cleanup requires Linux pidfd support')
    pinned = []
    try:
        for group in report['groups']:
            known = {row['pid']: row for row in group['record']['members']}
            for pid in group['active_pids']:
                identity = known[pid]
                key = (pid, identity['birth'])
                if key in sent:
                    continue
                try:
                    fd = os.pidfd_open(pid, 0)
                except ProcessLookupError:
                    continue
                except OSError as exc:
                    raise OwnershipError('cannot pin verified process identity') from exc
                pinned.append((fd, key))
                current = _read_stat(pid)
                if current is None:
                    continue
                if not _same(identity, current):
                    raise OwnershipError('PID identity changed before signal')
                _check_tags(current, batch, model)
        # Validate every group before the first signal, including new conflicts.
        refreshed = inspect(report['records'], batch, model)
        for fd, key in pinned:
            try:
                signal.pidfd_send_signal(fd, sig, None, 0)
            except ProcessLookupError:
                pass
            except OSError as exc:
                if exc.errno != errno.ESRCH:
                    raise OwnershipError('cannot signal pinned owned process') from exc
            sent.add(key)
        return refreshed['records']
    finally:
        for fd, _ in pinned:
            os.close(fd)


def _phase(records, batch, model, sig, timeout):
    deadline = time.monotonic() + timeout
    sent = set()
    while True:
        report = inspect(records, batch, model)
        records = report['records']
        if all(group['gone'] for group in report['groups']):
            return records, True
        records = _signal_members(report, batch, model, sig, sent)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            final = inspect(records, batch, model)
            return final['records'], all(group['gone'] for group in final['groups'])
        time.sleep(min(0.2, remaining))


def cleanup(records, batch, model, term_timeout=45, kill_timeout=10):
    """TERM then KILL only pidfd-pinned members of validated captured groups.

    Previously verified children remain birth-identity anchors after leader
    exit. New descendants are observed and signalled during each bounded phase.
    Returns only after no active scoped members remain; otherwise raises.
    """
    for timeout in (term_timeout, kill_timeout):
        if (type(timeout) not in (int, float) or not math.isfinite(timeout)
                or timeout < 0 or timeout > 3600):
            raise OwnershipError('invalid cleanup timeout')
    report = inspect(records, batch, model)
    if all(group['gone'] for group in report['groups']):
        return
    updated, done = _phase(report['records'], batch, model, signal.SIGTERM, term_timeout)
    if not done:
        _, done = _phase(updated, batch, model, signal.SIGKILL, kill_timeout)
    if not done:
        raise OwnershipError('verified owned process group did not exit before deadline')
