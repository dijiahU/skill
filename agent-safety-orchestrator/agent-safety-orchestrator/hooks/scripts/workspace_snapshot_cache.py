"""Share one immutable snapshot parse within a single matcher process."""
from functools import lru_cache
import json
import os


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@lru_cache(maxsize=1)
def _read(path, identity):
    with open(path, encoding='utf-8') as stream:
        if _identity(os.fstat(stream.fileno())) != identity:
            raise OSError('Workspace snapshot changed before reading')
        payload = json.load(stream)
        if _identity(os.fstat(stream.fileno())) != identity:
            raise OSError('Workspace snapshot changed during reading')
    if _identity(os.stat(path)) != identity:
        raise OSError('Workspace snapshot replaced during reading')
    return payload


def read_snapshot(path):
    # Atomic replacement and in-place writes invalidate the cache. Failure does
    # not return a previously cached document, including after invalidation.
    return _read(path, _identity(os.stat(path)))
