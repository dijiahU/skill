"""Bounded tag-read stabilization for a newly created, unreaped Popen child.

Only startup tag absence can be retried. Birth, boot, SID/PGID and explicit
scope conflicts remain strict. This module does not signal or launch processes.
"""

import time

import saber_treatment_v9_process_ownership as ownership


MISSING_TAGS = 'session leader lacks required ownership tags'


def capture_spawn(process, batch, model):
    ownership._scope(batch, model)
    pid = process.pid
    boot = ownership._boot_id()
    anchor = ownership._read_stat(pid)
    if (anchor is None or anchor['state'] in ('Z', 'X', 'x')
            or anchor['pid'] != anchor['pgid'] or anchor['pid'] != anchor['sid']):
        raise ownership.OwnershipError('new child is not a live independent session leader')
    anchor = ownership._identity(anchor)
    started = time.monotonic()
    deadline = started + 2.0
    retries = 0

    def recheck():
        current = ownership._read_stat(pid)
        if (ownership._boot_id() != boot or current is None
                or current['state'] in ('Z', 'X', 'x')
                or not ownership._same(anchor, current)):
            raise ownership.OwnershipError('new child identity changed during tag stabilization')
        return current

    while True:
        recheck()
        values = ownership._read_environ(pid)
        recheck()
        if values is None:
            raise ownership.OwnershipError('new child environment disappeared')
        missing = False
        # Inspect BOTH scope fields for conflicts before deciding absence can retry.
        for name, expected in zip(ownership.TAG_NAMES, (batch, model)):
            prefix = (name + '=').encode()
            found = [value[len(prefix):] for value in values if value.startswith(prefix)]
            if any(value != expected.encode() for value in found):
                raise ownership.OwnershipError('explicit new child ownership tag conflicts with scope')
            missing = missing or not found
        if not missing:
            try:
                record = ownership.capture(pid, batch, model)
            except ownership.OwnershipError as error:
                if str(error) != MISSING_TAGS:
                    raise
                # Another exec may overlap capture's second tag read. The same
                # immutable startup identity is still required on the next pass.
            else:
                recheck()
                if record['boot_id'] != boot or not ownership._same(anchor, record):
                    raise ownership.OwnershipError('capture returned a different startup identity')
                record['startup_tag_read_retries'] = retries
                record['startup_tag_wait_ms'] = round((time.monotonic() - started) * 1000)
                return record
        if process.poll() is not None:
            raise ownership.OwnershipError('new child exited before ownership capture')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ownership.OwnershipError('new child ownership tags remained unavailable for 2 seconds')
        retries += 1
        time.sleep(min(0.05, remaining))
