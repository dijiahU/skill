#!/usr/bin/env python3
"""Blind capability structure + the 3-panel "why 95 atoms" figure.

Uses the capability-summary embeddings (free_form_notes) — NOT the raw text —
so the surface-form confound (skill vs MCP) is removed. Clustering is done on
the high-D embedding (HDBSCAN), never on the 2D UMAP (which is only for viz).

Panels:
  (a) Blind capability clusters (UMAP, colored by cluster, noise gray).
  (b) Same UMAP with representative atoms overlaid as black x + name.
  (c) Cluster-to-atom heatmap (rows = top clusters, cols = atoms, value =
      fraction of cluster members mapping to that atom).

Quantitative summary: cluster purity, top-1/top-3 atom coverage, uncovered rate.

Reads:   reports/embeddings/{notes_embeddings.npy, notes_meta.json, atom_embeddings.npy, atom_meta.json}
Writes:  reports/structure_blind_clusters.png
         reports/structure_blind_clusters.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
EMBDIR = ROOT / "reports" / "embeddings"
REPORTS = ROOT / "reports"


def load():
    notes = np.load(EMBDIR / "notes_embeddings.npy")
    meta = json.loads((EMBDIR / "notes_meta.json").read_text(encoding="utf-8"))
    atom = np.load(EMBDIR / "atom_embeddings.npy")
    atom_meta = json.loads((EMBDIR / "atom_meta.json").read_text(encoding="utf-8"))
    return notes, meta, atom, atom_meta


def cluster_metrics(labels, meta):
    atoms_sets = [set(m["atoms"]) for m in meta]
    cluster_info = {}
    for c in sorted(set(labels)):
        c = int(c)
        if c == -1:
            continue
        members = [i for i in range(len(labels)) if int(labels[i]) == c]
        cnt = Counter(a for i in members for a in atoms_sets[i])
        top = cnt.most_common(3)
        top1_atom, top1_n = top[0]
        top1_cov = top1_n / len(members)
        top3_atoms = {a for a, _ in top}
        top3_cov = sum(1 for i in members if atoms_sets[i] & top3_atoms) / len(members)
        cluster_info[c] = {
            "size": len(members),
            "top1_atom": top1_atom,
            "top1_coverage": round(top1_cov, 4),
            "top3_coverage": round(top3_cov, 4),
            "top3": [(a, int(n)) for a, n in top],
        }
    n_clusters = len(cluster_info)
    n_noise = int((labels == -1).sum())
    purity = float(np.mean([v["top1_coverage"] for v in cluster_info.values()])) if cluster_info else 0.0
    top1_mean = float(np.mean([v["top1_coverage"] for v in cluster_info.values()])) if cluster_info else 0.0
    top3_mean = float(np.mean([v["top3_coverage"] for v in cluster_info.values()])) if cluster_info else 0.0
    uncovered = sum(1 for v in cluster_info.values() if v["top1_coverage"] < 0.5)
    return {
        "n_clusters": n_clusters,
        "n_noise": n_noise,
        "mean_top1_coverage": round(top1_mean, 4),
        "mean_top3_coverage": round(top3_mean, 4),
        "uncovered_clusters": uncovered,
        "uncovered_rate": round(uncovered / n_clusters, 4) if n_clusters else None,
        "clusters": cluster_info,
    }


def draw(notes, meta, atom, atom_meta, labels, metrics, top_n=12):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import umap
    from matplotlib.lines import Line2D

    # UMAP 2D for visualization only (fit on combined artifacts + atoms)
    allv = np.vstack([notes, atom])
    emb = umap.UMAP(n_components=2, metric="cosine", random_state=42,
                    n_neighbors=15, min_dist=0.1).fit_transform(allv)
    art_emb = emb[: len(notes)]
    atom_emb = emb[len(notes):]
    atom_id2row = {am["id"]: i for i, am in enumerate(atom_meta)}

    # top clusters by size
    top_clusters = sorted(metrics["clusters"], key=lambda c: -metrics["clusters"][c]["size"])[:top_n]

    fig, axes = plt.subplots(1, 3, figsize=(20, 6.2))

    # ---- Panel A: blind clusters ----
    ax = axes[0]
    cmap = plt.get_cmap("tab20", max(len(metrics["clusters"]), 1))
    for c in sorted(metrics["clusters"]):
        idx = [i for i in range(len(labels)) if labels[i] == c]
        color = cmap(c % 20) if c in top_clusters else "0.8"
        ax.scatter(art_emb[idx, 0], art_emb[idx, 1], s=6, alpha=0.7,
                   color=color, linewidths=0)
    noise = [i for i in range(len(labels)) if labels[i] == -1]
    ax.scatter(art_emb[noise, 0], art_emb[noise, 1], s=4, alpha=0.2,
               color="0.6", linewidths=0)
    ax.set_title("(a) Blind capability clusters", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

    # ---- Panel B: same UMAP + representative atoms ----
    ax = axes[1]
    ax.scatter(art_emb[:, 0], art_emb[:, 1], s=5, alpha=0.25, color="0.8", linewidths=0)
    for c in top_clusters:
        info = metrics["clusters"][c]
        atom_id = info["top1_atom"]
        if atom_id not in atom_id2row:
            continue
        r = atom_id2row[atom_id]
        ax.scatter(atom_emb[r, 0], atom_emb[r, 1], marker="x", s=80,
                   color="black", linewidths=1.5, zorder=5)
        ax.annotate(atom_id, (atom_emb[r, 0], atom_emb[r, 1]),
                    fontsize=6, color="black",
                    xytext=(3, 3), textcoords="offset points")
    ax.set_title("(b) Interpreting clusters with atoms", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

    # ---- Panel C: cluster-to-atom heatmap ----
    ax = axes[2]
    atoms_sets = [set(m["atoms"]) for m in meta]
    # columns = union of top1 atoms of top clusters
    cols = []
    for c in top_clusters:
        a = metrics["clusters"][c]["top1_atom"]
        if a not in cols:
            cols.append(a)
    mat = np.zeros((len(top_clusters), len(cols)))
    row_labels = []
    for ri, c in enumerate(top_clusters):
        members = [i for i in range(len(labels)) if labels[i] == c]
        row_labels.append(f"#{c} (n={len(members)})")
        for ci, a in enumerate(cols):
            mat[ri, ci] = sum(1 for i in members if a in atoms_sets[i]) / len(members)
    im = ax.imshow(mat, aspect="auto", cmap="YlOrRd", vmin=0, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right", fontsize=6)
    ax.set_yticks(range(len(top_clusters)))
    ax.set_yticklabels(row_labels, fontsize=7)
    ax.set_title("(c) Each cluster ≈ a small set of atoms", fontsize=10)
    for ri in range(len(top_clusters)):
        for ci in range(len(cols)):
            v = mat[ri, ci]
            ax.text(ci, ri, f"{v:.0%}" if v >= 0.05 else "", ha="center",
                    va="center", fontsize=6, color="black" if v < 0.6 else "white")

    fig.tight_layout()
    png = REPORTS / "structure_blind_clusters.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    return png


def main(argv: list[str] | None = None) -> int:
    from sklearn.cluster import HDBSCAN

    notes, meta, atom, atom_meta = load()
    print(f"Loaded {len(notes)} capability-summary embeddings (dim {notes.shape[1]})")

    # blind clustering on the raw high-D embedding (cosine), not on 2D UMAP
    hdb = HDBSCAN(min_cluster_size=10, metric="cosine")
    labels = hdb.fit_predict(notes)
    metrics = cluster_metrics(labels, meta)
    print(f"\n=== Blind clustering (HDBSCAN on {notes.shape[1]}D, cosine) ===")
    print(f"  n_clusters={metrics['n_clusters']}  n_noise={metrics['n_noise']}")
    print(f"  mean top-1 atom coverage: {metrics['mean_top1_coverage']}")
    print(f"  mean top-3 atom coverage: {metrics['mean_top3_coverage']}")
    print(f"  uncovered clusters (top-1 <50%): {metrics['uncovered_clusters']}/{metrics['n_clusters']}")

    # also try UMAP-8D -> HDBSCAN as a comparison
    import umap
    red = umap.UMAP(n_components=8, metric="cosine", random_state=42,
                    n_neighbors=15, min_dist=0.0).fit_transform(notes)
    labels2 = HDBSCAN(min_cluster_size=10, metric="euclidean").fit_predict(red)
    m2 = cluster_metrics(labels2, meta)
    print(f"\n  (comparison) UMAP8D->HDBSCAN: n_clusters={m2['n_clusters']} "
          f"noise={m2['n_noise']} top1={m2['mean_top1_coverage']}")

    # use the better clustering (more clusters, higher top1) for the figure
    if m2["n_clusters"] > metrics["n_clusters"] and m2["mean_top1_coverage"] >= metrics["mean_top1_coverage"]:
        labels, metrics = labels2, m2
        print("\n  -> using UMAP8D->HDBSCAN for the figure")

    png = draw(notes, meta, atom, atom_meta, labels, metrics)
    (REPORTS / "structure_blind_clusters.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {png}")
    print("Wrote reports/structure_blind_clusters.json")

    print("\nTop clusters (size | top-1 atom | top-1/top-3 coverage):")
    for c in sorted(metrics["clusters"], key=lambda c: -metrics["clusters"][c]["size"])[:12]:
        v = metrics["clusters"][c]
        print(f"  #{c:>2} n={v['size']:>3}  {v['top1_atom']:35s} "
              f"{v['top1_coverage']*100:5.1f}% / {v['top3_coverage']*100:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
