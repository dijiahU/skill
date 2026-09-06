#!/usr/bin/env python3
"""Reconcile LLM-audit atom labels onto the frozen v1 vocabulary.

The May-9 audit labels were produced against the pre-v0.7 draft vocabulary
(20 archetypes, ~115 atoms). v0.7 (May-11) pruned it to the frozen 95 atoms /
19 archetypes (docs/SAFETY_ATOMIC_CAPABILITIES.md §0). This script applies that
prune decision to the stored labels:

  - DELETED_ATOMS  -> labels removed entirely (v0.7 removed them as
                      non-guardrails: agent-as-output deliverable, offline
                      analysis, or vapor-infra).
  - MOVED_ATOMS    -> atom id survived but changed parent archetype in v0.7;
                      labels are re-parented to the frozen archetype.
  - added post-audit atoms are left untouched; they simply have no coverage in
    this audit (reported for disclosure).

Every surviving label is re-parented to the frozen vocabulary's canonical
parent, so the output is guaranteed to sit on the 95-atom / 19-archetype space.

Reads:   reports/llm_audit_classify_2026-05-09_cleaned.jsonl  (already deduped)
Writes:  reports/llm_audit_classify_2026-05-09_frozen_v1.jsonl
         reports/llm_audit_classify_2026-05-09_frozen_v1_log.json

The source file is never modified.
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


# v0.7 deletions (§0 changelog): not guardrails, removed from frozen vocab.
DELETED_ATOMS = {
    "generate-stride-threat-model",     # agent-as-output deliverable
    "generate-attack-tree",             # agent-as-output deliverable
    "check-sbom-completeness",          # offline analysis
    "enable-tamper-evident-storage",    # vapor-infra
    "evaluate-regulatory-compliance-rule",  # offline analysis
}

# v0.7 moved atoms: survived, but parent archetype changed.
# audit_parent -> frozen_parent
MOVED_ATOMS = {
    "enumerate-task-side-effects": "detect-task-overreach",
    "check-rbac-role": "check-tool-permission-scope",
}


def reconcile(
    label: str,
    frozen_parent_by_atom: dict[str, str],
) -> tuple[str | None, str]:
    """Return (frozen_label_or_None, status).

    Statuses:
      - 'unchanged'    : already on frozen vocab, parent correct
      - 'reparented'   : atom survived, parent corrected to frozen
      - 'dropped_deleted' : atom removed in v0.7, label dropped
      - 'dropped_unknown' : atom not in frozen vocab (defensive; should be 0)
    """
    if not isinstance(label, str) or "/" not in label:
        return None, "dropped_unknown"
    _, atom_id = label.split("/", 1)
    atom_id = atom_id.strip()
    if atom_id in DELETED_ATOMS:
        return None, "dropped_deleted"
    frozen_parent = frozen_parent_by_atom.get(atom_id)
    if frozen_parent is None:
        return None, "dropped_unknown"
    frozen_label = f"{frozen_parent}/{atom_id}"
    if frozen_label == label:
        return frozen_label, "unchanged"
    return frozen_label, "reparented"


def reconcile_record(
    rec: dict[str, Any],
    frozen_parent_by_atom: dict[str, str],
) -> tuple[dict[str, Any], Counter[str]]:
    stats: Counter[str] = Counter()
    for field in ("primary_atoms", "secondary_atoms"):
        labels = rec.get(field) or []
        if not isinstance(labels, list):
            continue
        new_labels: list[str] = []
        seen: set[str] = set()
        for label in labels:
            fixed, status = reconcile(label, frozen_parent_by_atom)
            stats[f"{field}.{status}"] += 1
            if fixed is not None and fixed not in seen:
                seen.add(fixed)
                new_labels.append(fixed)
        rec[field] = new_labels
    rec["_reconciled_frozen_v1"] = dict(stats)
    return rec, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", type=Path,
                    default=ROOT / "reports" / "llm_audit_classify_2026-05-09_cleaned.jsonl")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "reports" / "llm_audit_classify_2026-05-09_frozen_v1.jsonl")
    args = ap.parse_args(argv)

    if not args.input.is_file():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 1

    atoms = load_atoms()
    frozen_parent_by_atom = {a["id"]: a["parent_archetype"] for a in atoms}
    valid_labels = {f"{a['parent_archetype']}/{a['id']}" for a in atoms}
    print(f"Frozen vocabulary: {len(atoms)} atoms, {len(valid_labels)} labels")

    n_records = 0
    aggregate: Counter[str] = Counter()
    out_records: list[dict[str, Any]] = []
    still_invalid: list[str] = []
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n_records += 1
            rec, stats = reconcile_record(rec, frozen_parent_by_atom)
            aggregate.update(stats)
            # post-check: every surviving label must be a valid frozen label
            for field in ("primary_atoms", "secondary_atoms"):
                for l in rec.get(field, []):
                    if l not in valid_labels:
                        still_invalid.append(f"{rec.get('record_id')}:{field}:{l}")
            out_records.append(rec)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for rec in out_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    log = {
        "source": str(args.input),
        "output": str(args.output),
        "record_count": n_records,
        "label_stats": dict(aggregate),
        "still_invalid": still_invalid,
        "deleted_atoms": sorted(DELETED_ATOMS),
        "moved_atoms": MOVED_ATOMS,
        "note": "added post-audit atoms have no coverage; see summary.",
    }
    log_path = args.output.with_name(args.output.stem + "_log.json")
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nWritten: {args.output} ({args.output.stat().st_size:,} bytes)")
    print(f"Log:     {log_path}")
    print(f"\nLabel reconciliation breakdown:")
    for k in sorted(aggregate):
        print(f"  {k:<38} {aggregate[k]:>5}")
    print(f"\nStill-invalid labels after reconcile: {len(still_invalid)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
