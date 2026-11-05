#!/usr/bin/env python3
"""Check framework packaging and generated files without network access."""

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for script in (
        "gen_atom_manifest.py",
        "gen_router_atom_catalog.py",
        "gen_archetype_skill_md.py",
    ):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--check"],
            cwd=ROOT,
            check=True,
        )

    for folder in ("hooks", "helpers", "adapters", "scripts", "tests"):
        for path in (ROOT / folder).rglob("*.py"):
            compile(path.read_bytes(), str(path), "exec")

    for path in (
        "install.sh",
        "adapters/claude/install.sh",
        "adapters/codex/install.sh",
        "adapters/dsh/install.sh",
    ):
        subprocess.run(["bash", "-n", str(ROOT / path)], check=True)

    for path in ("adapters/dsh/index.mjs", "tests/test_dsh_adapter.mjs"):
        subprocess.run(["node", "--check", str(ROOT / path)], check=True)

    manifests = {}
    for path in (
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        "hooks/hooks.json",
        "adapters/codex/hooks.json",
        "atoms.json",
    ):
        manifests[path] = json.loads((ROOT / path).read_text())

    atoms = manifests["atoms.json"]
    if len(atoms) != 95 or len({atom["id"] for atom in atoms}) != 95:
        raise ValueError("Expected 95 unique atoms")
    counts = (
        (list((ROOT / "skills").rglob("SKILL.md")), 1, "Router skill"),
        (
            list(
                (ROOT / "skills/safety-router-skill/references/archetypes").glob("*.md")
            ),
            14,
            "archetype references",
        ),
        (list((ROOT / "hooks/scripts").glob("matcher_*.py")), 8, "matchers"),
    )
    for paths, expected, label in counts:
        if len(paths) != expected:
            raise ValueError(f"Expected {expected} {label}, found {len(paths)}")

    codex = manifests["adapters/codex/hooks.json"]
    if set(codex) - {"description", "hooks"}:
        raise ValueError("Unsupported top-level Codex hook configuration keys")
    for groups in manifests["hooks/hooks.json"]["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                match = re.search(r"hooks/scripts/\S+\.py", hook["command"])
                if not match or not (ROOT / match.group()).is_file():
                    raise ValueError(f"Missing matcher: {hook['command']}")

    plugin = manifests[".claude-plugin/plugin.json"]
    entries = manifests[".claude-plugin/marketplace.json"]["plugins"]
    entry = next(item for item in entries if item["name"] == plugin["name"])
    if entry["version"] != plugin["version"] or entry["source"] != "./":
        raise ValueError("Plugin and marketplace metadata are inconsistent")
    print("Repository checks passed: syntax, manifests, hook paths and structure")


if __name__ == "__main__":
    main()
