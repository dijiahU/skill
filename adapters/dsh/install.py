#!/usr/bin/env python3
"""Install only the framework bundle; leave DSH's existing settings untouched."""

import json
import os
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    home = Path(os.environ.get("DSH_HOME", "~/.dsh")).expanduser().resolve()
    target = home / "safety-orchestrator"
    if target == root or root in target.parents:
        raise SystemExit("DSH_HOME must be outside the source repository")
    for folder in ("hooks", "helpers", "skills", "docs"):
        shutil.copytree(
            root / folder,
            target / folder,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for file in (
        "atoms.json",
        "LICENSE",
        "adapters/codex/codex_hook.py",
        "adapters/dsh/index.mjs",
        "adapters/dsh/README.md",
    ):
        destination = target / file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / file, destination)
    patch = home / "safety-orchestrator.patch.json"
    patch.write_text(
        json.dumps(
            [
                {
                    "insert": [
                        {
                            "id": "safety-orchestrator",
                            "name": str(target / "adapters/dsh/index.mjs"),
                            "config": {"python": "python3", "timeoutMs": 120000},
                        }
                    ]
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Installed framework: {target}")
    print(f"DSH patch: {patch}")
    print(
        "Start DSH with --patch and the patch path above (quote paths containing spaces)."
    )
    print("Existing DSH settings and provider credentials were not changed.")


if __name__ == "__main__":
    main()
