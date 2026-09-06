#!/usr/bin/env python3
"""Embed the LLM capability summaries (free_form_notes) with bge-m3.

The raw SKILL.md / MCP metadata text is dominated by surface form (markdown vs
metadata). The audit's free_form_notes field is a uniform, capability-focused
prose summary for every artifact, so embedding it isolates capability signal.

Reads:   reports/llm_audit_classify_2026-05-09_frozen_v1.jsonl
Writes:  reports/embeddings/notes_embeddings.npy
         reports/embeddings/notes_meta.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "reports" / "llm_audit_classify_2026-05-09_frozen_v1.jsonl"
DEFAULT_OUTDIR = ROOT / "reports" / "embeddings"
DEFAULT_MODEL_PATH = Path("/2024233123/skills/models/modelscope/BAAI/bge-m3")


def parse_source(record_id: str) -> str:
    parts = record_id.split("/")
    return f"{parts[2] if len(parts) > 2 else '?'}/{parts[3] if len(parts) > 3 else '?'}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args(argv)

    if not args.model_path.is_dir():
        print(f"ERROR: model dir not found: {args.model_path}", file=sys.stderr)
        return 1

    notes = []
    meta = []
    for line in args.input.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if not r.get("is_safety_relevant"):
            continue
        note = (r.get("free_form_notes") or "").strip()
        if not note:
            continue
        atoms = set()
        archetypes = set()
        primary_atoms = set()
        primary_archetypes = set()
        for lbl in (r.get("primary_atoms") or []):
            if "/" in lbl:
                a, at = lbl.split("/", 1)
                atoms.add(at); archetypes.add(a)
                primary_atoms.add(at); primary_archetypes.add(a)
        for lbl in (r.get("secondary_atoms") or []):
            if "/" in lbl:
                a, at = lbl.split("/", 1)
                atoms.add(at); archetypes.add(a)
        notes.append(note)
        meta.append({
            "record_id": r["record_id"],
            "kind": r.get("kind"),
            "source": parse_source(r["record_id"]),
            "atoms": sorted(atoms),
            "archetypes": sorted(archetypes),
            "primary_atoms": sorted(primary_atoms),
            "primary_archetypes": sorted(primary_archetypes),
            "note": note,
        })
    print(f"Loaded {len(notes)} capability summaries")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(str(args.model_path), device="cpu")
    vecs = model.encode(notes, batch_size=args.batch_size,
                        normalize_embeddings=True,
                        show_progress_bar=False).astype(np.float32)

    args.outdir.mkdir(parents=True, exist_ok=True)
    np.save(args.outdir / "notes_embeddings.npy", vecs)
    (args.outdir / "notes_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote notes_embeddings.npy {vecs.shape} + notes_meta.json ({len(meta)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
