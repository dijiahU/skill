#!/usr/bin/env python3
"""Ecosystem structure: UMAP viz, kNN consistency, blind clustering.

Runs on the bge-m3 embeddings produced by scripts/embed_artifacts.py.

1. UMAP 2D projection (artifacts + 95 atom anchors), colored by top archetype /
   phase / kind.
2. kNN consistency: do the nearest neighbors of an artifact share its archetype?
   Reported against a random (label-shuffled) baseline.
3. Blind clustering (HDBSCAN) + oracle KMeans(k=19) vs archetype labels
   (ARI / NMI / purity).

Reads:   reports/embeddings/{artifact,atom}_{embeddings,meta}.*
Writes:  reports/structure_umap.png
         reports/structure_knn.json
         reports/structure_clustering.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EMBDIR = ROOT / "reports" / "embeddings"
DEFAULT_REPORTS = ROOT / "reports"


def load(embdir: Path):
    art_vecs = np.load(embdir / "artifact_embeddings.npy")
    art_meta = json.loads((embdir / "artifact_meta.json").read_text(encoding="utf-8"))
    atom_vecs = np.load(embdir / "atom_embeddings.npy")
    atom_meta = json.loads((embdir / "atom_meta.json").read_text(encoding="utf-8"))
    return art_vecs, art_meta, atom_vecs, atom_meta


def top_archetype(meta: dict) -> str:
    counts = Counter(meta["archetypes"])
    if not counts:
        return "?"
    prim = [a for a in meta.get("primary_archetypes", []) if a in counts]
    if prim:
        return max(prim, key=lambda a: counts[a])
    return counts.most_common(1)[0][0]


def umap_viz(art_vecs, art_meta, atom_vecs, atom_meta, reports: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import umap

    all_vecs = np.vstack([art_vecs, atom_vecs])
    reducer = umap.UMAP(n_components=2, metric="cosine", random_state=42,
                        n_neighbors=15, min_dist=0.1)
    emb = reducer.fit_transform(all_vecs)
    art_emb = emb[: len(art_vecs)]
    atom_emb = emb[len(art_vecs):]

    tarch = [top_archetype(m) for m in art_meta]
    phases = [m["phases"][0] if m["phases"] else "?" for m in art_meta]
    kinds = [m["kind"] for m in art_meta]

    fig, axes = plt.subplots(1, 3, figsize=(19, 6))

    def _scatter(ax, colors, title, cmap="tab20", atom_color="0.3"):
        ax.scatter(art_emb[:, 0], art_emb[:, 1], c=colors, s=8, alpha=0.6,
                   cmap=cmap, linewidths=0)
        ax.scatter(atom_emb[:, 0], atom_emb[:, 1], marker="x", s=30,
                   color=atom_color, linewidths=0.8, label="atoms")
        ax.set_title(title, fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])

    # panel 1: top archetype
    arch_ids = sorted(set(tarch))
    arch_idx = {a: i for i, a in enumerate(arch_ids)}
    _scatter(axes[0], [arch_idx[a] for a in tarch],
             f"by archetype ({len(arch_ids)})")
    # panel 2: phase
    phase_ids = sorted(set(phases))
    phase_idx = {p: i for i, p in enumerate(phase_ids)}
    _scatter(axes[1], [phase_idx[p] for p in phases], f"by phase ({len(phase_ids)})",
             cmap="tab10")
    # panel 3: kind
    kind_ids = sorted(set(kinds))
    kind_idx = {k: i for i, k in enumerate(kind_ids)}
    _scatter(axes[2], [kind_idx[k] for k in kinds], f"by kind ({kind_ids})",
             cmap="Set1")

    fig.tight_layout()
    png = reports / "structure_umap.png"
    fig.savefig(png, dpi=150)
    plt.close(fig)
    return png


def knn_consistency(art_vecs, art_meta, k: int = 5, seed: int = 42):
    tarch = [top_archetype(m) for m in art_meta]
    arch_set = [set(m["archetypes"]) for m in art_meta]

    # normalized vectors => cosine = dot
    sim = art_vecs @ art_vecs.T
    n = len(art_vecs)
    np.fill_diagonal(sim, -np.inf)
    nn = np.argsort(-sim, axis=1)[:, :k]

    purity = []
    share_any = []
    for i in range(n):
        neigh_tarch = [tarch[j] for j in nn[i]]
        purity.append(sum(1 for t in neigh_tarch if t == tarch[i]) / k)
        share_any.append(sum(1 for j in nn[i] if arch_set[i] & arch_set[j]) / k)
    purity_mean = float(np.mean(purity))
    share_mean = float(np.mean(share_any))

    # random baseline: shuffle archetype labels many times, recompute purity
    rng = np.random.default_rng(seed)
    tarch_arr = np.array(tarch)
    base_purities = []
    for _ in range(20):
        shuf = rng.permutation(tarch_arr)
        p = []
        for i in range(n):
            p.append(sum(1 for j in nn[i] if shuf[j] == shuf[i]) / k)
        base_purities.append(float(np.mean(p)))
    baseline = float(np.mean(base_purities))

    return {
        "n_artifacts": n,
        "k": k,
        "purity_same_top_archetype@k": round(purity_mean, 4),
        "share_any_archetype@k": round(share_mean, 4),
        "random_baseline_purity": round(baseline, 4),
        "ratio_vs_baseline": round(purity_mean / baseline, 2) if baseline else None,
    }


def clustering(art_vecs, art_meta, seed: int = 42):
    from sklearn.cluster import HDBSCAN, KMeans
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
    import umap

    tarch = [top_archetype(m) for m in art_meta]
    arch_sets = [set(m["archetypes"]) for m in art_meta]
    results = {}

    def _multi_label_purity(labels):
        per = []
        for c in sorted(set(labels)):
            if c == -1:
                continue
            members = [i for i in range(len(labels)) if labels[i] == c]
            cnt = Counter(a for i in members for a in arch_sets[i])
            dom, dom_cnt = cnt.most_common(1)[0]
            coverage = sum(1 for i in members if dom in arch_sets[i]) / len(members)
            per.append({"cluster": int(c), "size": len(members),
                        "dominant_archetype": dom, "coverage": round(coverage, 3)})
        return per, (float(np.mean([p["coverage"] for p in per])) if per else 0.0)

    # blind: UMAP (density-preserving) -> HDBSCAN (no k specified)
    reducer = umap.UMAP(n_components=8, metric="cosine", random_state=seed,
                        n_neighbors=15, min_dist=0.0)
    red = reducer.fit_transform(art_vecs)
    hdb = HDBSCAN(min_cluster_size=10, metric="euclidean")
    hdb_labels = hdb.fit_predict(red)
    n_clusters_hdb = len(set(hdb_labels)) - (1 if -1 in hdb_labels else 0)
    per, mean_purity = _multi_label_purity(hdb_labels)
    results["hdbscan_umap"] = {
        "n_clusters": n_clusters_hdb,
        "n_noise": int((hdb_labels == -1).sum()),
        "mean_cluster_purity": round(mean_purity, 4),
        "ari_vs_archetype": round(float(adjusted_rand_score(tarch, hdb_labels)), 4),
        "nmi_vs_archetype": round(float(normalized_mutual_info_score(tarch, hdb_labels)), 4),
        "clusters": per,
    }

    # oracle-ish: KMeans(k=19) as an upper-bound reference
    km = KMeans(n_clusters=19, random_state=seed, n_init=10)
    km_labels = km.fit_predict(art_vecs)
    per_km, mean_purity_km = _multi_label_purity(km_labels)
    results["kmeans_19"] = {
        "n_clusters": 19,
        "mean_cluster_purity": round(mean_purity_km, 4),
        "ari_vs_archetype": round(float(adjusted_rand_score(tarch, km_labels)), 4),
        "nmi_vs_archetype": round(float(normalized_mutual_info_score(tarch, km_labels)), 4),
    }

    results["n_distinct_archetypes"] = len(set(tarch))
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--embdir", type=Path, default=DEFAULT_EMBDIR)
    ap.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args(argv)

    art_vecs, art_meta, atom_vecs, atom_meta = load(args.embdir)
    print(f"Loaded {len(art_vecs)} artifact embeddings (dim {art_vecs.shape[1]}) "
          f"and {len(atom_vecs)} atom anchors")

    png = umap_viz(art_vecs, art_meta, atom_vecs, atom_meta, args.reports)
    print(f"Wrote {png}")

    knn = knn_consistency(art_vecs, art_meta, k=args.k)
    print(f"\n=== kNN consistency (k={args.k}) ===")
    print(f"  purity (same top archetype): {knn['purity_same_top_archetype@k']}")
    print(f"  share any archetype:         {knn['share_any_archetype@k']}")
    print(f"  random baseline:             {knn['random_baseline_purity']}")
    print(f"  ratio vs baseline:           {knn['ratio_vs_baseline']}")
    (args.reports / "structure_knn.json").write_text(
        json.dumps(knn, ensure_ascii=False, indent=2), encoding="utf-8")

    clu = clustering(art_vecs, art_meta)
    print(f"\n=== Clustering ===")
    for name, r in clu.items():
        if isinstance(r, dict):
            print(f"  {name}: {r}")
    (args.reports / "structure_clustering.json").write_text(
        json.dumps(clu, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
