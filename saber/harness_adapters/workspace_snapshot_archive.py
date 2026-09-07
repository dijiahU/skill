"""Private content-addressed evidence for offline workspace snapshot replay."""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = 'saber-workspace-snapshot-archive-v1'


@contextmanager
def _locked(root: Path, exclusive: bool):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(root / '.lock', os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield


def _store(root: Path, data: bytes) -> str:
    with _locked(root, True):
        digest = hashlib.sha256(data).hexdigest()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = root / (digest + '.json.gz')
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if gzip.decompress(target.read_bytes()) != data:
                raise ValueError('snapshot archive content mismatch')
        else:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(gzip.compress(data, mtime=0))
                stream.flush()
                os.fsync(stream.fileno())
        return digest


def _read(root: Path, digest: str) -> bytes:
    with _locked(root, False):
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('invalid snapshot archive digest')
        data = gzip.decompress((root / (digest + '.json.gz')).read_bytes())
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('snapshot archive hash mismatch')
        return data


def archive_snapshot(root: Path, payload: dict[str, Any]) -> dict[str, str]:
    root = Path(root)
    if not root.is_absolute():
        raise ValueError('snapshot archive root must be absolute')
    snapshot = dict(payload)
    for field in ('file_contents', 'policy_file_contents'):
        refs = {}
        for path, content in payload.get(field, {}).items():
            if not isinstance(path, str) or not isinstance(content, str):
                raise ValueError('snapshot text manifest is invalid')
            data = content.encode('utf-8')
            refs[path] = {'sha256': _store(root / 'blobs', data), 'utf8_bytes': len(data)}
        snapshot[field] = refs
    manifest = {'schema_version': SCHEMA, 'snapshot': snapshot}
    data = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode('utf-8')
    digest = _store(root / 'manifests', data)
    return {'schema_version': SCHEMA, 'root': str(root), 'manifest_sha256': digest}


def restore_snapshot(root: Path, digest: str) -> dict[str, Any]:
    manifest = json.loads(_read(Path(root) / 'manifests', digest))
    if manifest.get('schema_version') != SCHEMA:
        raise ValueError('unsupported snapshot archive schema')
    snapshot = manifest['snapshot']
    for field in ('file_contents', 'policy_file_contents'):
        files = {}
        for path, ref in snapshot[field].items():
            data = _read(Path(root) / 'blobs', ref['sha256'])
            if len(data) != ref['utf8_bytes']:
                raise ValueError('snapshot archive length mismatch')
            files[path] = data.decode('utf-8')
        snapshot[field] = files
    return snapshot
