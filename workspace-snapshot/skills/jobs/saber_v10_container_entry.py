#!/usr/bin/env python3
"""Frozen container entry for v10; validates scope then starts SABER."""

from __future__ import annotations

import os
import re
import sys


_SCOPE = re.compile(r"[a-z0-9][a-z0-9_.-]{0,47}\Z")


def validate_environment() -> None:
    if os.environ.get("SABER_IDLE_SESSION"):
        raise RuntimeError("formal v10 results must not use an idle session")
    batch = os.environ.get("SABER_BATCH_ID", "")
    run = os.environ.get("SABER_BATCH_MODEL", "")
    scope = os.environ.get("SABER_RESOURCE_SCOPE", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", batch):
        raise RuntimeError("invalid or missing SABER_BATCH_ID")
    if not re.fullmatch(r"[a-z0-9_.-]{1,80}", run):
        raise RuntimeError("invalid or missing SABER_BATCH_MODEL")
    if not _SCOPE.fullmatch(scope):
        raise RuntimeError("invalid or missing SABER_RESOURCE_SCOPE")


def main() -> int:
    validate_environment()
    # The entry script is mounted under /run, outside the read-only checkout.
    # Python otherwise searches /run rather than the configured working tree.
    sys.path.insert(0, "/workspace/saber")
    import run_harness
    return run_harness.main()


if __name__ == "__main__":
    raise SystemExit(main())
