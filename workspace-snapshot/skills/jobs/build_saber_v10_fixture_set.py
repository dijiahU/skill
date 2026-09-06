#!/usr/bin/env python3
"""Build a non-overwriting, versioned 716-task SABER v10 fixture tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from saber_v10_fixture_repairs import PATCH_INVENTORY, REPAIR_VERSION, repair_task


ROOT = Path("/2024233123")
DEFAULT_SOURCE = ROOT / "skills/projects/skill/saber/tasks"
DEFAULT_OUTPUT = ROOT / "skills/jobs/saber-v10-fixtures-20260906-r2"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def task_paths(root: Path) -> list[Path]:
    return sorted(root.glob("[ABC]/*/*.json"))


def build(source: Path, output: Path) -> dict[str, Any]:
    destination = output / "tasks"
    manifest_path = output / "manifest.json"
    if manifest_path.exists() or destination.exists():
        raise FileExistsError(
            f"refusing to overwrite an existing fixture revision: {output}"
        )
    paths = task_paths(source)
    if len(paths) != 716:
        raise ValueError(f"expected 716 source tasks, found {len(paths)}")

    entries = []
    seen_ids = set()
    changed = []
    rendered: list[tuple[Path, bytes]] = []
    for path in paths:
        original = json.loads(path.read_text(encoding="utf-8"))
        repaired = repair_task(original)
        task_id = repaired.get("id")
        relative = path.relative_to(source)
        if task_id in seen_ids:
            raise ValueError(f"duplicate task id: {task_id}")
        seen_ids.add(task_id)
        if relative.parts[:2] != (repaired.get("scenario"), repaired.get("category")):
            raise ValueError(f"path metadata mismatch: {relative}")
        original_bytes = canonical_bytes(original)
        repaired_bytes = canonical_bytes(repaired)
        is_changed = original_bytes != repaired_bytes
        expected_changed = task_id in PATCH_INVENTORY
        if is_changed != expected_changed:
            raise ValueError(
                f"repair inventory mismatch for {task_id}: changed={is_changed}"
            )
        if is_changed:
            changed.append(task_id)
        rendered.append((relative, repaired_bytes))
        entries.append({
            "id": task_id,
            "path": str(relative),
            "source_sha256": digest(original_bytes),
            "revised_sha256": digest(repaired_bytes),
            "changed": is_changed,
            "repair": PATCH_INVENTORY.get(task_id),
        })

    if set(changed) != set(PATCH_INVENTORY):
        raise ValueError("changed task set does not equal repair inventory")

    corpus_hash = hashlib.sha256()
    for entry in entries:
        corpus_hash.update(entry["path"].encode("utf-8") + b"\0")
        corpus_hash.update(entry["revised_sha256"].encode("ascii") + b"\n")

    output.mkdir(parents=True, exist_ok=False)
    for relative, data in rendered:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = {
        "fixture_revision": REPAIR_VERSION,
        "source_root": str(source),
        "task_root": str(destination),
        "task_count": len(entries),
        "changed_task_count": len(changed),
        "changed_task_ids": sorted(changed),
        "corpus_sha256": corpus_hash.hexdigest(),
        "tasks": entries,
        "invariants": {
            "source_tree_mutated": False,
            "unknown_capabilities_allowed": False,
            "network_mode": "none",
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    manifest = build(args.source.resolve(), args.output.resolve())
    print(json.dumps({
        "fixture_revision": manifest["fixture_revision"],
        "task_count": manifest["task_count"],
        "changed_task_count": manifest["changed_task_count"],
        "changed_task_ids": manifest["changed_task_ids"],
        "corpus_sha256": manifest["corpus_sha256"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
