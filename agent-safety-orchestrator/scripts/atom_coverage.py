#!/usr/bin/env python3
"""Atom prototypes (centroids) + coverage analysis.

Problem: plotting an atom by its NAME/DEFINITION embedding puts all the short,
abstract atom texts near the semantic center, far from the concrete artifacts.
Fix: place each atom at the CENTROID of the artifacts that map to it.

Outputs:
  1. Sanity check: cosine(atom-text embedding, mapped-artifact centroid) per atom.
     Low similarity => "atom name as a point" is unreliable.
  2. Coverage: each artifact's distance to its nearest atom centroid; which
     blind clusters sit far from any atom (coverage holes).
  3. Two figures:
     Fig A (blind structure, no atom x)  -> does data have structure?
     Fig B (artifacts + atom centroids)  -> do atoms cover the capability space?

Reads:   reports/embeddings/{notes_embeddings.npy, notes_meta.json,
          atom_embeddings.npy, atom_meta.json}
Writes:  reports/figA_blind_structure.png, reports/figB_atom_coverage.png,
         reports/atom_centroid_sanity.json, reports/atom_coverage.json
"""

from __future__ import annotations

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


def atom_centroids(notes, meta):
    """Return {atom_id: normalized centroid vector} for atoms with >=1 artifact."""
    atoms_sets = [set(m["atoms"]) for m in meta]
    centroids = {}
    for z in sorted(set().union(*atoms_sets)):
        idx = [i for i in range(len(notes)) if z in atoms_sets[i]]
        if idx:
            c = notes[idx].mean(axis=0)
            c = c / (np.linalg.norm(c) + 1e-12)
            centroids[z] = c
    return centroids, atoms_sets


def sanity_check(atom, atom_meta, centroids):
    id2row = {am["id"]: i for i, am in enumerate(atom_meta)}
    rows = []
    for z, c in centroids.items():
        if z not in id2row:
            continue
        text_vec = atom[id2row[z]]
        sim = float(np.dot(text_vec, c))  # both normalized
        rows.append({"atom": z, "text_centroid_cosine": round(sim, 4)})
    sims = [r["text_centroid_cosine"] for r in rows]
    return {
        "n_atoms": len(rows),
        "cosine_p50": round(float(np.percentile(sims, 50)), 4),
        "cosine_p10": round(float(np.percentile(sims, 10)), 4),
        "n_below_0.4": int(sum(1 for s in sims if s < 0.4)),
        "n_below_0.5": int(sum(1 for s in sims if s < 0.5)),
        "per_atom": rows,
    }


def coverage(notes, meta, centroids, atoms_sets, labels):
    # nearest centroid cosine per artifact
    zs = list(centroids.keys())
    C = np.stack([centroids[z] for z in zs])  # (n_atoms, D)
    sim = notes @ C.T  # (n_artifacts, n_atoms)
    nearest = sim.max(axis=1)
    nearest_atom = [zs[i] for i in sim.argmax(axis=1)]

    # per-cluster: fraction of members whose nearest centroid is weak
    cluster_report = []
    for c in sorted(set(labels)):
        c = int(c)
        if c == -1:
            continue
        members = [i for i in range(len(labels)) if int(labels[i]) == c]
        nn = nearest[members]
        weak = float((nn < 0.5).mean())
        cluster_report.append({
            "cluster": c, "size": len(members),
            "nearest_cosine_p50": round(float(np.percentile(nn, 50)), 4),
            "frac_weak_lt0.5": round(weak, 4),
        })

    return {
        "nearest_atom_cosine": {
            "p50": round(float(np.percentile(nearest, 50)), 4),
            "p90": round(float(np.percentile(nearest, 90)), 4),
            "p10": round(float(np.percentile(nearest, 10)), 4),
            "frac_ge_0.6": round(float((nearest >= 0.6).mean()), 4),
            "frac_ge_0.7": round(float((nearest >= 0.7).mean()), 4),
            "frac_lt_0.5": round(float((nearest < 0.5).mean()), 4),
        },
        "per_cluster": cluster_report,
        "nearest_atom": nearest_atom,
        "nearest_cosine": nearest.tolist(),
    }


def draw_figA(notes, meta, labels, top_n=12):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import umap

    emb = umap.UMAP(n_components=2, metric="cosine", random_state=42,
                    n_neighbors=15, min_dist=0.1).fit_transform(notes)
    fig, ax = plt.subplots(figsize=(8, 6))
    cmap = plt.get_cmap("tab20", max(len(set(labels)), 1))
    top = sorted(set(int(l) for l in labels), key=lambda c: -int((labels == c).sum()))[:top_n]
    for c in sorted(set(int(l) for l in labels)):
        idx = [i for i in range(len(labels)) if int(labels[i]) == c]
        color = cmap(c % 20) if c in top else "0.85"
        ax.scatter(emb[idx, 0], emb[idx, 1], s=7, alpha=0.75, color=color, linewidths=0)
    noise = [i for i in range(len(labels)) if int(labels[i]) == -1]
    ax.scatter(emb[noise, 0], emb[noise, 1], s=4, alpha=0.2, color="0.6", linewidths=0)
    ax.set_title("Blind capability clusters (no atom labels)", fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    png = REPORTS / "figA_blind_structure.png"
    fig.savefig(png, dpi=150)
    return png


def draw_figB(notes, meta, centroids, nearest, nearest_atom):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import umap

    C = np.stack(list(centroids.values()))
    allv = np.vstack([notes, C])
    emb = umap.UMAP(n_components=2, metric="cosine", random_state=42,
                    n_neighbors=15, min_dist=0.1).fit_transform(allv)
    art_emb = emb[: len(notes)]
    cent_emb = emb[len(notes):]

    fig, ax = plt.subplots(figsize=(8, 6))
    # artifacts colored by their nearest-atom cosine (coverage quality)
    sc = ax.scatter(art_emb[:, 0], art_emb[:, 1], c=nearest, s=7, alpha=0.7,
                    cmap="viridis", vmin=0.3, vmax=0.9, linewidths=0)
    ax.scatter(cent_emb[:, 0], cent_emb[:, 1], marker="x", s=60,
               color="#8FA3B0", linewidths=1.5, zorder=6)
    plt.colorbar(sc, ax=ax, label="nearest-atom cosine")
    ax.set_title("95 atom prototypes (x) over artifacts; color = coverage", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    png = REPORTS / "figB_atom_coverage.png"
    fig.savefig(png, dpi=150)
    return png


def main() -> int:
    from sklearn.cluster import HDBSCAN
    import umap

    notes, meta, atom, atom_meta = load()
    print(f"Loaded {len(notes)} notes, {len(atom)} atom texts")

    centroids, atoms_sets = atom_centroids(notes, meta)
    print(f"Computed {len(centroids)} atom centroids")

    # sanity check
    sanity = sanity_check(atom, atom_meta, centroids)
    print(f"\n=== Sanity: atom-text vs artifact-centroid cosine ===")
    print(f"  p50={sanity['cosine_p50']}  p10={sanity['cosine_p10']}  "
          f"below 0.5: {sanity['n_below_0.5']}/{sanity['n_atoms']}")
    (REPORTS / "atom_centroid_sanity.json").write_text(
        json.dumps(sanity, ensure_ascii=False, indent=2), encoding="utf-8")

    # blind clustering (UMAP8D -> HDBSCAN)
    red = umap.UMAP(n_components=8, metric="cosine", random_state=42,
                    n_neighbors=15, min_dist=0.0).fit_transform(notes)
    labels = HDBSCAN(min_cluster_size=10, metric="euclidean").fit_predict(red)
    n_clusters = len(set(int(l) for l in labels)) - (1 if -1 in labels else 0)
    print(f"\nBlind clustering: {n_clusters} clusters, "
          f"noise={int((labels == -1).sum())}")

    # coverage
    cov = coverage(notes, meta, centroids, atoms_sets, labels)
    print(f"\n=== Coverage: nearest-atom cosine ===")
    print(f"  p50={cov['nearest_atom_cosine']['p50']}  "
          f"p90={cov['nearest_atom_cosine']['p90']}  "
          f"p10={cov['nearest_atom_cosine']['p10']}")
    print(f"  frac>=0.6: {cov['nearest_atom_cosine']['frac_ge_0.6']}  "
          f"frac<0.5: {cov['nearest_atom_cosine']['frac_lt_0.5']}")
    (REPORTS / "atom_coverage.json").write_text(
        json.dumps(cov, ensure_ascii=False, indent=2), encoding="utf-8")

    # coverage holes: clusters with high weak-fraction
    holes = [c for c in cov["per_cluster"] if c["frac_weak_lt0.5"] > 0.5]
    print(f"\nCoverage holes (clusters where >50% members have nearest cosine <0.5): {len(holes)}")
    for c in sorted(holes, key=lambda c: -c["size"]):
        print(f"  cluster {c['cluster']:>3} size={c['size']:>3} "
              f"nearest_p50={c['nearest_cosine_p50']} weak={c['frac_weak_lt0.5']}")

    pngA = draw_figA(notes, meta, labels)
    pngB = draw_figB(notes, meta, centroids, np.array(cov["nearest_cosine"]), cov["nearest_atom"])
    print(f"\nWrote {pngA}")
    print(f"Wrote {pngB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
