#!/usr/bin/env python3
"""Compare non-kept candidates to the kept set (circularity control).

Answers: did stage-3 selection keep the coherent capability structure and
discard noise, or did it discard a whole region of capability space?

Metrics:
1. Atom-anchor similarity: max cosine of each non-kept candidate to the 95
   atom definitions, vs the same for the kept set.
2. Clusterability: UMAP+HDBSCAN on the non-kept set alone — does it find
   coherent clusters (missed capabilities) or mostly noise?

Reads:  reports/embeddings/{artifact,atom,nonkept}_embeddings.npy
Writes: reports/nonkept_control.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EMBDIR = ROOT / "reports" / "embeddings"
DEFAULT_REPORTS = ROOT / "reports"


def pct(a, q):
    return round(float(np.percentile(a, q)), 4)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--embdir", type=Path, default=DEFAULT_EMBDIR)
    ap.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    args = ap.parse_args(argv)

    kept = np.load(args.embdir / "artifact_embeddings.npy")
    atoms = np.load(args.embdir / "atom_embeddings.npy")
    nonkept = np.load(args.embdir / "nonkept_embeddings.npy")
    print(f"kept {kept.shape}, atoms {atoms.shape}, nonkept {nonkept.shape}")

    # 1. max cosine to atom anchors (normalized => dot)
    kept_atom = (kept @ atoms.T).max(axis=1)
    nk_atom = (nonkept @ atoms.T).max(axis=1)
    # max cosine to the KEPT set (are non-kept near an existing artifact?)
    nk_kept = (nonkept @ kept.T).max(axis=1)

    summary = {
        "n_nonkept": int(len(nonkept)),
        "kept_max_atom_similarity": {
            "p50": pct(kept_atom, 50), "p90": pct(kept_atom, 90),
            "p10": pct(kept_atom, 10),
        },
        "nonkept_max_atom_similarity": {
            "p50": pct(nk_atom, 50), "p90": pct(nk_atom, 90),
            "p10": pct(nk_atom, 10),
        },
        "nonkept_max_similarity_to_kept": {
            "p50": pct(nk_kept, 50), "p90": pct(nk_kept, 90),
            "frac_ge_0.7": round(float((nk_kept >= 0.7).mean()), 4),
            "frac_ge_0.6": round(float((nk_kept >= 0.6).mean()), 4),
        },
    }

    # 2. clusterability of non-kept alone
    from sklearn.cluster import HDBSCAN
    import umap
    reducer = umap.UMAP(n_components=8, metric="cosine", random_state=42,
                        n_neighbors=15, min_dist=0.0)
    red = reducer.fit_transform(nonkept)
    hdb = HDBSCAN(min_cluster_size=10, metric="euclidean")
    labels = hdb.fit_predict(red)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int((labels == -1).sum())
    summary["nonkept_clustering"] = {
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "noise_fraction": round(n_noise / len(nonkept), 4),
        "cluster_sizes": sorted(Counter(labels).values(), reverse=True)[:10],
    }

    (args.reports / "nonkept_control.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== non-kept control ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
