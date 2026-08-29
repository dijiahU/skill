"""Lightweight `.env` loader — no third-party deps.

Reads `KEY=value` pairs from a `.env` file at the project root and exports
them to `os.environ` (only if the key is not already set in the shell, so an
explicit `export KEY=...` always wins).

Supports:
- comments (`# ...`)
- blank lines
- single- or double-quoted values (`KEY="value with spaces"`)
- inline `export KEY=value` (the leading `export` is stripped)

Does NOT support multi-line values, command substitution, or variable
expansion. Keep secrets one-line.

Usage:
    # at the top of any script that reads secrets from env vars
    from _env import load_dotenv
    load_dotenv()

The function is idempotent: calling it twice has no additional effect.
Returns the dict of values it read from the file (handy for logging which
keys were loaded — the values themselves should never be logged).
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | str | None = None, *, override: bool = False) -> dict[str, str]:
    """Load .env file. Defaults to <project_root>/.env.

    Args:
        path: explicit path to .env (defaults to project root)
        override: if True, overwrite existing env vars; default False
                  (existing shell exports take priority)

    Returns:
        dict of {key: value} pairs found in the file (values redacted-friendly:
        callers can log which keys were loaded without printing the values).

    Silently returns an empty dict if the .env file does not exist. This is
    the right behavior for production deployments where secrets come from
    a secret manager rather than a file.
    """
    if path is None:
        path = PROJECT_ROOT / ".env"
    path = Path(path)
    loaded: dict[str, str] = {}
    if not path.exists():
        return loaded

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # tolerate `export KEY=value`
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        # strip a single layer of matching surrounding quotes
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if not key:
            continue
        loaded[key] = val
        if override or key not in os.environ:
            os.environ[key] = val
    return loaded


if __name__ == "__main__":
    # CLI: `python scripts/_env.py` prints which keys were loaded (NOT the values)
    loaded = load_dotenv()
    if not loaded:
        print(f"No .env file found at {PROJECT_ROOT / '.env'} (or file is empty).")
    else:
        print(f"Loaded {len(loaded)} keys from {PROJECT_ROOT / '.env'}:")
        for k in sorted(loaded):
            shell_set = (k in os.environ and os.environ[k] != loaded[k])
            note = " (shell already set this; .env value ignored)" if shell_set else ""
            print(f"  {k}{note}")
