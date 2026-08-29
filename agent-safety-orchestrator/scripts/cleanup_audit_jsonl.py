#!/usr/bin/env python3
"""Clean up the LLM audit JSONL output.

Three deterministic fixes (no LLM calls):

1. **Dedupe by record_id**: keep the last occurrence (overwrites earlier
   test-run entries that were appended before the full run).
2. **Wrong-parent labels**: if a label `<wrong>/<atom_id>` has a valid
   `atom_id` but wrong `<wrong>`, replace with `<correct>/<atom_id>` looked
   up from the vocabulary.
3. **No-slash labels**: if a label is just a bare atom id without parent
   prefix, prepend the correct parent.

Reads:    reports/llm_audit_classify_<date>.jsonl
Writes:   reports/llm_audit_classify_<date>_cleaned.jsonl
          reports/llm_audit_classify_<date>_cleanup_log.json

The dashboard reads the *_cleaned* file. The original is left untouched
for forensic comparison.

Usage:
  python scripts/cleanup_audit_jsonl.py \
      --input reports/llm_audit_classify_2026-05-09.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _atomic_capabilities import load_atoms  # noqa: E402


def fix_label(
    label: str,
    atom_id_to_parent: dict[str, str],
    valid_labels: set[str],
) -> tuple[str | None, str]:
    """Return (fixed_label_or_None, status).

    Statuses:
      - 'valid'           : already valid, no change
      - 'wrong_parent'    : was wrong-parent, fixed
      - 'no_slash'        : was bare atom_id, fixed by prepending parent
      - 'unknown_atom'    : atom_id not in vocab, dropped (None)
      - 'malformed'       : couldn't parse, dropped (None)
    """
    if not isinstance(label, str) or not label.strip():
        return None, "malformed"

    label = label.strip()
    if label in valid_labels:
        return label, "valid"

    if "/" in label:
        wrong_parent, atom_id = label.split("/", 1)
        atom_id = atom_id.strip()
        if atom_id in atom_id_to_parent:
            correct = atom_id_to_parent[atom_id]
            return f"{correct}/{atom_id}", "wrong_parent"
        return None, "unknown_atom"

    # No slash → treat as bare atom_id
    atom_id = label
    if atom_id in atom_id_to_parent:
        return f"{atom_id_to_parent[atom_id]}/{atom_id}", "no_slash"
    return None, "unknown_atom"


def clean_record(
    rec: dict[str, Any],
    atom_id_to_parent: dict[str, str],
    valid_labels: set[str],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Apply label fixes in-place on a record. Return (record, stats)."""
    stats: Counter[str] = Counter()

    for field in ("primary_atoms", "secondary_atoms"):
        labels = rec.get(field) or []
        if not isinstance(labels, list):
            continue
        new_labels = []
        for label in labels:
            fixed, status = fix_label(label, atom_id_to_parent, valid_labels)
            stats[f"{field}.{status}"] += 1
            if fixed is not None:
                new_labels.append(fixed)
        # dedupe while preserving order
        seen = set()
        deduped = []
        for l in new_labels:
            if l not in seen:
                seen.add(l)
                deduped.append(l)
        rec[field] = deduped

    # re-validate; replace _validation_warnings with the post-cleanup state
    new_warnings: list[str] = []
    for field in ("primary_atoms", "secondary_atoms"):
        for l in rec.get(field, []) or []:
            if l not in valid_labels:
                new_warnings.append(f"{field} label still not in vocabulary after cleanup: {l}")
    valid_phases = {
        "input-understanding", "planning", "tool-invocation",
        "output-generation", "cross-cutting",
    }
    for ph in rec.get("covered_phases", []) or []:
        if ph not in valid_phases:
            new_warnings.append(f"unknown phase: {ph}")
    rec["_validation_warnings"] = new_warnings

    # preserve a record of cleanup actions
    rec["_cleanup_stats"] = dict(stats)

    return rec, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", required=True, type=Path,
                    help="Path to llm_audit_classify_<date>.jsonl")
    args = ap.parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 1

    atoms = load_atoms()
    atom_id_to_parent = {a["id"]: a["parent_archetype"] for a in atoms}
    valid_labels = {f"{a['parent_archetype']}/{a['id']}" for a in atoms}

    print(f"Vocabulary loaded: {len(atoms)} atoms, {len(valid_labels)} valid labels")
    print(f"Reading: {args.input}")

    # Read all → dedupe by record_id (keep LAST)
    raw_lines = 0
    by_rid: dict[str, dict[str, Any]] = {}
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            raw_lines += 1
            rid = rec.get("record_id")
            if rid:
                by_rid[rid] = rec

    print(f"Raw lines: {raw_lines}, unique record_ids: {len(by_rid)}, "
          f"dupes dropped: {raw_lines - len(by_rid)}")

    # Apply cleanup
    aggregate: Counter[str] = Counter()
    cleaned_records = []
    for rec in by_rid.values():
        cleaned, stats = clean_record(rec, atom_id_to_parent, valid_labels)
        cleaned_records.append(cleaned)
        aggregate.update(stats)

    # Write outputs
    out_jsonl = args.input.with_name(args.input.stem + "_cleaned.jsonl")
    log_path = args.input.with_name(args.input.stem + "_cleanup_log.json")
    with out_jsonl.open("w", encoding="utf-8") as f:
        for rec in cleaned_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    log = {
        "source": str(args.input),
        "output": str(out_jsonl),
        "raw_line_count": raw_lines,
        "unique_record_count": len(by_rid),
        "dupes_dropped": raw_lines - len(by_rid),
        "label_stats": dict(aggregate),
        "still_invalid_records": [
            r["record_id"] for r in cleaned_records if r.get("_validation_warnings")
        ],
    }
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nWritten: {out_jsonl} ({out_jsonl.stat().st_size:,} bytes)")
    print(f"Log:     {log_path}")
    print(f"\nLabel-fix breakdown:")
    for k in sorted(aggregate):
        print(f"  {k:<35} {aggregate[k]:>5}")
    print(f"\nRemaining records with validation warnings: {len(log['still_invalid_records'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
