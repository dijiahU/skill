#!/usr/bin/env python3
"""Embed a sample of NON-KEPT Stage-3 candidates as a circularity control.

The 1210 audited artifacts were pre-selected for archetype relevance, so the
embedding structure found in them could in principle be an artifact of that
selection. This script embeds a sample of the candidates that stage-3 REJECTED
and lets the comparison step check whether they form coherent new clusters
(missed capabilities) or are spread out (noise).

Reads:   reports/dedup_stage3_embedding_2026-05-08.json  (all 8051 candidates)
Writes:  reports/embeddings/nonkept_embeddings.npy
         reports/embeddings/nonkept_meta.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dedup_stage3_embedding import (  # noqa: E402
    build_mcp_relevance_text,
    build_skill_relevance_text,
)

DEFAULT_MANIFEST = ROOT / "reports" / "dedup_stage3_embedding_2026-05-08.json"
DEFAULT_OUTDIR = ROOT / "reports" / "embeddings"
DEFAULT_MODEL_PATH = Path("/2024233123/skills/models/modelscope/BAAI/bge-m3")

SKILL_MAX_CHARS = 6000
MCP_README_MAX_CHARS = 2000


def parse_source(record_id: str) -> str:
    parts = record_id.split("/")
    category = parts[2] if len(parts) > 2 else "?"
    source = parts[3] if len(parts) > 3 else "?"
    return f"{category}/{source}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    ap.add_argument("--per-kind", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--batch-size", type=int, default=32)
    args = ap.parse_args(argv)

    if not args.model_path.is_dir():
        print(f"ERROR: model dir not found: {args.model_path}", file=sys.stderr)
        return 1

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cands = manifest["candidates"]
    nonkept = [c for c in cands if not c.get("kept")]

    rng = np.random.default_rng(args.seed)
    sample = []
    for kind in ("skill", "mcp"):
        kind_cands = [c for c in nonkept if c["kind"] == kind]
        pick = kind_cands if len(kind_cands) <= args.per_kind else \
            rng.choice(kind_cands, size=args.per_kind, replace=False).tolist()
        sample.extend(pick)
    print(f"Sampled {len(sample)} non-kept candidates "
          f"(from {len(nonkept)} total)")

    texts = []
    meta = []
    for c in sample:
        path = c["path"]
        if c["kind"] == "skill":
            text = build_skill_relevance_text(ROOT / path, SKILL_MAX_CHARS)
        else:
            text = build_mcp_relevance_text(ROOT / path, MCP_README_MAX_CHARS, SKILL_MAX_CHARS)
        if not text.strip():
            continue
        texts.append(text)
        meta.append({
            "record_id": path,
            "kind": c["kind"],
            "source": parse_source(path),
            "max_score": c.get("max_score"),
            "top1_anchor": c.get("top1_anchor"),
        })
    print(f"Built relevance text for {len(texts)} (empty skipped: "
          f"{len(sample) - len(texts)})")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(str(args.model_path), device="cpu")
    vecs = model.encode(texts, batch_size=args.batch_size,
                        normalize_embeddings=True,
                        show_progress_bar=False).astype(np.float32)

    args.outdir.mkdir(parents=True, exist_ok=True)
    np.save(args.outdir / "nonkept_embeddings.npy", vecs)
    (args.outdir / "nonkept_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote nonkept_embeddings.npy {vecs.shape} + nonkept_meta.json "
          f"({len(meta)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
