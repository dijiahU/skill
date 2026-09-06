#!/usr/bin/env python3
"""Embed safety artifacts + atom definitions with BAAI/bge-m3.

Reconstructs each artifact's relevance text using the SAME builder functions as
the Stage-3 pipeline (dedup_stage3_embedding.py), embeds with bge-m3, and caches
the vectors + metadata for the ecosystem-structure experiments (UMAP viz, kNN
consistency, blind clustering).

Reads:
  reports/llm_audit_classify_2026-05-09_frozen_v1.jsonl  (reconciled labels)
  docs/SAFETY_ATOMIC_CAPABILITIES.md §5                   (95 atoms)
Writes (reports/embeddings/):
  artifact_embeddings.npy   (N x 1024, L2-normalized)
  artifact_meta.json        ([{record_id, source, kind, atoms, archetypes, ...}])
  atom_embeddings.npy       (95 x 1024, L2-normalized)
  atom_meta.json            ([{id, parent, phase, ...}])

Model: BAAI/bge-m3. CPU-only in this environment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _atomic_capabilities import load_atoms  # noqa: E402
from dedup_stage3_embedding import (  # noqa: E402
    build_mcp_relevance_text,
    build_skill_relevance_text,
)

DEFAULT_INPUT = ROOT / "reports" / "llm_audit_classify_2026-05-09_frozen_v1.jsonl"
DEFAULT_OUTDIR = ROOT / "reports" / "embeddings"
DEFAULT_MODEL_PATH = Path("/2024233123/skills/models/modelscope/BAAI/bge-m3")

SKILL_MAX_CHARS = 6000
MCP_README_MAX_CHARS = 2000


def parse_source(record_id: str) -> str:
    parts = record_id.split("/")
    category = parts[2] if len(parts) > 2 else "?"
    source = parts[3] if len(parts) > 3 else "?"
    return f"{category}/{source}"


def build_artifact_text(record_id: str, kind: str) -> str:
    p = ROOT / record_id
    if kind == "skill":
        return build_skill_relevance_text(p, SKILL_MAX_CHARS)
    return build_mcp_relevance_text(p, MCP_README_MAX_CHARS, SKILL_MAX_CHARS)


def build_atom_text(a: dict) -> str:
    parts = [
        a.get("id", ""),
        a.get("definition", ""),
        a.get("scope_in", ""),
        a.get("scope_out", ""),
        a.get("signal_phrases", ""),
    ]
    return " ".join(x for x in parts if x)


def load_artifacts(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if not rec.get("is_safety_relevant"):
            continue
        atoms = set()
        archetypes = set()
        primary_atoms = set()
        primary_archetypes = set()
        for lbl in (rec.get("primary_atoms") or []):
            if "/" in lbl:
                arch, atom = lbl.split("/", 1)
                atoms.add(atom)
                archetypes.add(arch)
                primary_atoms.add(atom)
                primary_archetypes.add(arch)
        for lbl in (rec.get("secondary_atoms") or []):
            if "/" in lbl:
                arch, atom = lbl.split("/", 1)
                atoms.add(atom)
                archetypes.add(arch)
        if not atoms:
            continue
        rows.append({
            "record_id": rec["record_id"],
            "kind": rec.get("kind"),
            "source": parse_source(rec["record_id"]),
            "atoms": sorted(atoms),
            "archetypes": sorted(archetypes),
            "primary_atoms": sorted(primary_atoms),
            "primary_archetypes": sorted(primary_archetypes),
            "phases": sorted(rec.get("covered_phases") or []),
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    if not args.model_path.is_dir():
        print(f"ERROR: model dir not found: {args.model_path}", file=sys.stderr)
        return 1

    artifacts = load_artifacts(args.input)
    if args.limit > 0:
        artifacts = artifacts[: args.limit]
    print(f"Loaded {len(artifacts)} safety-relevant artifacts with >=1 atom")

    # ---- Build texts ----
    artifact_texts = []
    kept_artifacts = []
    for a in artifacts:
        text = build_artifact_text(a["record_id"], a["kind"])
        if not text.strip():
            continue
        artifact_texts.append(text)
        kept_artifacts.append(a)
    print(f"Built relevance text for {len(artifact_texts)} artifacts "
          f"({len(artifacts) - len(kept_artifacts)} empty skipped)")

    atoms = load_atoms()
    atom_texts = [build_atom_text(a) for a in atoms]
    print(f"Loaded {len(atoms)} atom definitions")

    # ---- Embed ----
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(args.model_path), device="cpu")
    print("Embedding artifacts...")
    art_vecs = model.encode(
        artifact_texts, batch_size=args.batch_size,
        normalize_embeddings=True, show_progress_bar=False,
    ).astype(np.float32)
    print("Embedding atom definitions...")
    atom_vecs = model.encode(
        atom_texts, batch_size=args.batch_size,
        normalize_embeddings=True, show_progress_bar=False,
    ).astype(np.float32)

    # ---- Save ----
    args.outdir.mkdir(parents=True, exist_ok=True)
    np.save(args.outdir / "artifact_embeddings.npy", art_vecs)
    np.save(args.outdir / "atom_embeddings.npy", atom_vecs)
    (args.outdir / "artifact_meta.json").write_text(
        json.dumps(kept_artifacts, ensure_ascii=False, indent=2), encoding="utf-8")
    atom_meta = [
        {"id": a["id"], "parent": a.get("parent_archetype"), "phase": a.get("phase")}
        for a in atoms
    ]
    (args.outdir / "atom_meta.json").write_text(
        json.dumps(atom_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nWrote to {args.outdir}:")
    print(f"  artifact_embeddings.npy  {art_vecs.shape}")
    print(f"  atom_embeddings.npy      {atom_vecs.shape}")
    print(f"  artifact_meta.json       {len(kept_artifacts)} records")
    print(f"  atom_meta.json           {len(atom_meta)} atoms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
