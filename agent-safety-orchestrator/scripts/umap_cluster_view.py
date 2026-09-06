#!/usr/bin/env python3
"""Honest UMAP view: color by blind cluster, annotate each cluster's archetype.

The naive "color by archetype" UMAP is a rainbow mess because capabilities are
multi-label and overlapping. This version colors by the BLIND clusters that
HDBSCAN found, and annotates each cluster with its dominant archetype + purity,
which is the claim we can actually defend.

Reads:   reports/embeddings/{artifact,atom}_{embeddings,meta}.*
Writes:  reports/structure_umap_clusters.png
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
EMBDIR = ROOT / "reports" / "embeddings"
REPORTS = ROOT / "reports"


def top_archetype(m):
    c = Counter(m["archetypes"])
    prim = [a for a in m.get("primary_archetypes", []) if a in c]
    return max(prim, key=lambda a: c[a]) if prim else c.most_common(1)[0][0]


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import umap
    from sklearn.cluster import HDBSCAN

    art = np.load(EMBDIR / "artifact_embeddings.npy")
    meta = json.loads((EMBDIR / "artifact_meta.json").read_text(encoding="utf-8"))
    atom = np.load(EMBDIR / "atom_embeddings.npy")
    tarch = [top_archetype(m) for m in meta]
    arch_sets = [set(m["archetypes"]) for m in meta]

    # joint UMAP
    allv = np.vstack([art, atom])
    emb = umap.UMAP(n_components=2, metric="cosine", random_state=42,
                    n_neighbors=15, min_dist=0.1).fit_transform(allv)
    art_emb = emb[: len(art)]
    atom_emb = emb[len(art):]

    # blind clustering (same pipeline as structure experiment)
    red = umap.UMAP(n_components=8, metric="cosine", random_state=42,
                    n_neighbors=15, min_dist=0.0).fit_transform(art)
    labels = HDBSCAN(min_cluster_size=10, metric="euclidean").fit_predict(red)

    # dominant archetype + purity per cluster
    cluster_info = {}
    for c in sorted(set(labels)):
        if c == -1:
            continue
        members = [i for i in range(len(labels)) if labels[i] == c]
        cnt = Counter(a for i in members for a in arch_sets[i])
        dom, _ = cnt.most_common(1)[0]
        cov = sum(1 for i in members if dom in arch_sets[i]) / len(members)
        cluster_info[c] = (dom, cov, len(members))

    # color map for clusters
    nclu = len(cluster_info)
    cmap = plt.get_cmap("tab20", nclu)
    color_of = {c: cmap(i) for i, c in enumerate(sorted(cluster_info))}

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))

    ax = axes[0]
    for c, (dom, cov, size) in cluster_info.items():
        idx = [i for i in range(len(labels)) if labels[i] == c]
        ax.scatter(art_emb[idx, 0], art_emb[idx, 1], s=8, alpha=0.7,
                   color=color_of[c], linewidths=0,
                   label=f"{dom} ({cov*100:.0f}%)" if size >= 10 else None)
    noise = [i for i in range(len(labels)) if labels[i] == -1]
    ax.scatter(art_emb[noise, 0], art_emb[noise, 1], s=5, alpha=0.25,
               color="0.7", linewidths=0, label="noise")
    ax.scatter(atom_emb[:, 0], atom_emb[:, 1], marker="x", s=30,
               color="black", linewidths=0.8, label="95 atoms")
    ax.set_title(f"Blind clusters (HDBSCAN): {nclu} clusters, "
                 f"mean purity {np.mean([v[1] for v in cluster_info.values()])*100:.0f}%",
                 fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
    ax.legend(fontsize=6, loc="upper left", bbox_to_anchor=(1.01, 1), ncol=2)

    ax = axes[1]
    kind_idx = {"skill": 0, "mcp": 1}
    colors = [["#5B8DB8", "#D9A066"][kind_idx[m["kind"]]] for m in meta]
    ax.scatter(art_emb[:, 0], art_emb[:, 1], c=colors, s=8, alpha=0.6, linewidths=0)
    ax.scatter(atom_emb[:, 0], atom_emb[:, 1], marker="x", s=30,
               color="black", linewidths=0.8)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([0], [0], marker="o", ls="", color="#5B8DB8", label="skill"),
                       Line2D([0], [0], marker="o", ls="", color="#D9A066", label="mcp")],
              fontsize=8)
    ax.set_title("by kind (surface form)", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

    fig.tight_layout()
    png = REPORTS / "structure_umap_clusters.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    print(f"Wrote {png}")

    # print cluster table
    print("\ncluster -> dominant archetype (purity, size):")
    for c in sorted(cluster_info, key=lambda c: -cluster_info[c][2]):
        dom, cov, size = cluster_info[c]
        print(f"  {c:>3} {dom:40s} {cov*100:5.1f}%  size={size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
