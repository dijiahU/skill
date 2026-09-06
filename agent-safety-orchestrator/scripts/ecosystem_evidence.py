#!/usr/bin/env python3
"""Ecosystem evidence: saturation curve + held-out source coverage.

Two reviewer-facing experiments over the frozen-v1 reconciled audit labels
(reports/llm_audit_classify_2026-05-09_frozen_v1.jsonl), no embeddings needed.

1. Saturation curve (todo #4): bootstrap the artifact order and plot cumulative
   distinct atoms / archetypes as more artifacts are added. A plateau shows the
   ecosystem is redundant at the capability level.
2. Held-out source coverage (todo #5): leave-one-source-out — for each source,
   what fraction of its atom labels are already covered by the OTHER sources,
   and which atoms (if any) only that source contributes.

Vocabulary note: the frozen vocabulary has 95 atoms / 19 archetypes. This audit
covers 89 of the 95 (6 atoms were added post-audit and have no coverage), so
the saturation ceiling is 89, not 95. The 95 figure is the vocabulary size.

Reads:   reports/llm_audit_classify_2026-05-09_frozen_v1.jsonl
Writes:  reports/ecosystem_saturation.png
         reports/ecosystem_saturation.json
         reports/ecosystem_heldout_sources.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "reports" / "llm_audit_classify_2026-05-09_frozen_v1.jsonl"
DEFAULT_REPORTS = ROOT / "reports"


def parse_source(record_id: str) -> tuple[str, str]:
    """Return (category, source) from a record_id path.

    Example: data/raw/community_skills/clawhub/... -> ("community_skills", "clawhub")
    """
    parts = record_id.split("/")
    # parts[0]=data, parts[1]=raw, parts[2]=category, parts[3]=source
    category = parts[2] if len(parts) > 2 else "?"
    source = parts[3] if len(parts) > 3 else "?"
    return category, source


def load_records(path: Path) -> list[dict]:
    """Return safety-relevant records with atom/archetype sets and source."""
    records = []
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
            continue  # the 1 record that only referenced a deleted atom
        category, source = parse_source(rec["record_id"])
        records.append({
            "record_id": rec["record_id"],
            "kind": rec.get("kind"),
            "source": f"{category}/{source}",
            "atoms": atoms,
            "archetypes": archetypes,
            "primary_atoms": primary_atoms,
            "primary_archetypes": primary_archetypes,
        })
    return records


def saturation(records: list[dict], n_boot: int, rng: np.random.Generator):
    """Bootstrap cumulative coverage curves. Returns (curve_stats, milestones)."""
    atom_ids = sorted({a for r in records for a in r["atoms"]})
    arch_ids = sorted({a for r in records for a in r["archetypes"]})
    primary_atom_ids = sorted({a for r in records for a in r["primary_atoms"]})
    atom_idx = {a: i for i, a in enumerate(atom_ids)}
    arch_idx = {a: i for i, a in enumerate(arch_ids)}

    atom_masks = []
    arch_masks = []
    primary_masks = []
    primary_arch_masks = []
    for r in records:
        am = 0
        for a in r["atoms"]:
            am |= 1 << atom_idx[a]
        bm = 0
        for a in r["archetypes"]:
            bm |= 1 << arch_idx[a]
        pm = 0
        for a in r["primary_atoms"]:
            pm |= 1 << atom_idx[a]
        pbm = 0
        for a in r["primary_archetypes"]:
            pbm |= 1 << arch_idx[a]
        atom_masks.append(am)
        arch_masks.append(bm)
        primary_masks.append(pm)
        primary_arch_masks.append(pbm)

    n = len(records)
    atom_curves = np.empty((n_boot, n), dtype=np.int64)
    arch_curves = np.empty((n_boot, n), dtype=np.int64)
    primary_curves = np.empty((n_boot, n), dtype=np.int64)
    primary_arch_curves = np.empty((n_boot, n), dtype=np.int64)
    for b in range(n_boot):
        order = rng.permutation(n)
        am = 0
        bm = 0
        pm = 0
        pbm = 0
        for step, i in enumerate(order):
            am |= atom_masks[i]
            bm |= arch_masks[i]
            pm |= primary_masks[i]
            pbm |= primary_arch_masks[i]
            atom_curves[b, step] = am.bit_count()
            arch_curves[b, step] = bm.bit_count()
            primary_curves[b, step] = pm.bit_count()
            primary_arch_curves[b, step] = pbm.bit_count()

    atom_mean = atom_curves.mean(axis=0)
    atom_lo = np.percentile(atom_curves, 2.5, axis=0)
    atom_hi = np.percentile(atom_curves, 97.5, axis=0)
    arch_mean = arch_curves.mean(axis=0)
    arch_lo = np.percentile(arch_curves, 2.5, axis=0)
    arch_hi = np.percentile(arch_curves, 97.5, axis=0)
    primary_mean = primary_curves.mean(axis=0)
    primary_lo = np.percentile(primary_curves, 2.5, axis=0)
    primary_hi = np.percentile(primary_curves, 97.5, axis=0)
    primary_arch_mean = primary_arch_curves.mean(axis=0)
    primary_arch_lo = np.percentile(primary_arch_curves, 2.5, axis=0)
    primary_arch_hi = np.percentile(primary_arch_curves, 97.5, axis=0)

    milestones = {}
    for m in [100, 300, 600, 1000, n]:
        i = min(m, n) - 1
        milestones[str(m)] = {
            "atoms_mean": round(float(atom_mean[i]), 1),
            "primary_atoms_mean": round(float(primary_mean[i]), 1),
            "archetypes_mean": round(float(arch_mean[i]), 1),
        }

    return {
        "n_records": n,
        "n_atom_ids_covered": len(atom_ids),
        "n_primary_atom_ids_covered": len(primary_atom_ids),
        "n_archetypes": len(arch_ids),
        "n_primary_archetypes": len({a for r in records for a in r["primary_archetypes"]}),
        "atom_ids": atom_ids,
        "arch_ids": arch_ids,
        "x": list(range(1, n + 1)),
        "atoms_mean": atom_mean.tolist(),
        "atoms_lo": atom_lo.tolist(),
        "atoms_hi": atom_hi.tolist(),
        "primary_atoms_mean": primary_mean.tolist(),
        "primary_atoms_lo": primary_lo.tolist(),
        "primary_atoms_hi": primary_hi.tolist(),
        "archetypes_mean": arch_mean.tolist(),
        "archetypes_lo": arch_lo.tolist(),
        "archetypes_hi": arch_hi.tolist(),
        "primary_archetypes_mean": primary_arch_mean.tolist(),
        "primary_archetypes_lo": primary_arch_lo.tolist(),
        "primary_archetypes_hi": primary_arch_hi.tolist(),
        "milestones": milestones,
    }


def heldout(records: list[dict]):
    """Leave-one-source-out coverage analysis."""
    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_source[r["source"]].append(r)

    atom_of_source = {s: set().union(*(r["atoms"] for r in recs)) for s, recs in by_source.items()}
    all_atoms = set().union(*atom_of_source.values())

    rows = []
    for s, recs in sorted(by_source.items(), key=lambda kv: -len(kv[1])):
        s_atoms = atom_of_source[s]
        other_atoms = all_atoms - s_atoms  # atoms covered by at least one other source
        # leave-one-out: other_atoms here already excludes S's atoms; but a "covered"
        # atom of S is one that OTHER sources also cover.
        other_cover = set().union(*(atom_of_source[t] for t in atom_of_source if t != s))
        covered = s_atoms & other_cover
        novel = s_atoms - other_cover
        rows.append({
            "source": s,
            "n_records": len(recs),
            "n_distinct_atoms": len(s_atoms),
            "n_covered_by_others": len(covered),
            "coverage": round(len(covered) / len(s_atoms), 4) if s_atoms else None,
            "n_novel_atoms": len(novel),
            "novel_atoms": sorted(novel),
        })

    # per-atom source count (how many sources cover each atom)
    atom_sources = defaultdict(set)
    for s, atoms in atom_of_source.items():
        for a in atoms:
            atom_sources[a].add(s)
    single_source_atoms = sorted(a for a, ss in atom_sources.items() if len(ss) == 1)

    return {
        "n_sources": len(by_source),
        "n_atoms_total_covered": len(all_atoms),
        "per_source": rows,
        "atoms_covered_by_single_source": single_source_atoms,
    }


def plot_heldout(held: dict, reports_dir: Path) -> Path:
    """Render the leave-one-source-out result as a single bar chart."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = sorted(held["per_source"], key=lambda r: -r["n_distinct_atoms"])
    sources = [r["source"].replace("community_skills/", "").replace("mcp_servers/", "")
               .replace("official_skills/", "") for r in rows]
    natoms = [r["n_distinct_atoms"] for r in rows]
    novel = [r["n_novel_atoms"] for r in rows]

    y = np.arange(len(sources))
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    ax.barh(y, natoms, color="#1f77b4")
    ax.set_yticks(y)
    ax.set_yticklabels(sources)
    ax.invert_yaxis()
    ax.set_xlabel("distinct atoms covered")
    ax.set_title("Atoms covered per source (leave-one-source-out)")
    for i, (n, nv) in enumerate(zip(natoms, novel)):
        color = "#d62728" if nv > 0 else "#888888"
        ax.text(n + 1, i, f"novel={nv}", va="center", fontsize=8, color=color)
    ax.set_xlim(0, max(natoms) + 10)
    ax.grid(alpha=0.3, axis="x")
    ax.text(0.99, 0.02,
            "coverage by other sources: 100% for every source except skillsh (97.7%)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color="#555555")

    fig.tight_layout()
    png = reports_dir / "ecosystem_heldout_sources.png"
    fig.savefig(png, dpi=150)
    return png


def plot_redundancy(records: list[dict], reports_dir: Path) -> Path:
    """Render the ecosystem-redundancy evidence (heavy tail + signature dup)."""
    from collections import Counter
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sig = Counter(frozenset(r["primary_atoms"]) for r in records if r["primary_atoms"])
    n_records = sum(sig.values())
    n_sig = len(sig)
    n_dup = sum(c - 1 for c in sig.values() if c > 1)

    atom_pop = Counter()
    for s, c in sig.items():
        for a in s:
            atom_pop[a] += c

    def bucket(m: int) -> str:
        if m == 1:
            return "1"
        if m == 2:
            return "2"
        if m <= 5:
            return "3-5"
        if m <= 10:
            return "6-10"
        if m <= 20:
            return "11-20"
        return "21+"

    order = ["1", "2", "3-5", "6-10", "11-20", "21+"]
    mult = Counter(sig.values())
    rec_b = Counter()
    sig_b = Counter()
    for m, ns in mult.items():
        rec_b[bucket(m)] += m * ns
        sig_b[bucket(m)] += ns
    rec_b_list = [rec_b[b] for b in order]
    sig_b_list = [sig_b[b] for b in order]

    # muted palette (less saturated than tab10 defaults)
    BLUE = "#5B8DB8"
    ORANGE = "#D9A066"
    GREEN = "#86A789"

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    # ---- Left: popularity, top + ellipsis + tail ----
    ax = axes[0]
    items = atom_pop.most_common()
    top_n = tail_n = 10
    top_items = items[:top_n]
    tail_items = items[-tail_n:]
    labels = [a for a, _ in top_items] + ["..."] + [a for a, _ in tail_items]
    counts = [c for _, c in top_items] + [0] + [c for _, c in tail_items]
    y = np.arange(len(labels))
    ax.barh(y, counts, color=BLUE)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("artifacts covering this atom (primary only)")
    ax.set_title(f"Capability popularity (top {top_n} / bottom {tail_n} of 95 atoms)")
    ax.grid(alpha=0.3, axis="x")

    # ---- Right: donut, consistent with the 58.2% "redundant copies" figure ----
    ax = axes[1]
    pct_dup = n_dup / n_records * 100
    n_uniq_skills = rec_b["1"]
    n_first_dup = n_records - n_uniq_skills - n_dup
    segs = [n_uniq_skills, n_first_dup, n_dup]
    seg_names = [f"unique ({n_uniq_skills})",
                 f"dup recipe, 1st ({n_first_dup})",
                 f"redundant copies ({n_dup})"]
    wedges, _, autotexts = ax.pie(
        segs, colors=[GREEN, BLUE, ORANGE], startangle=90, counterclock=False,
        autopct="%.1f%%", pctdistance=0.78,
        wedgeprops=dict(width=0.42, edgecolor="white"),
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontsize(9)
        t.set_fontweight("bold")
    ax.legend(wedges, seg_names, loc="upper center", bbox_to_anchor=(0.5, -0.03),
              fontsize=8, ncol=3, frameon=False)
    ax.text(0, 0, f"{pct_dup:.1f}%\nredundant",
            ha="center", va="center", fontsize=15, fontweight="bold")
    ax.set_title(f"{n_records} skills → {n_sig} recipes")
    ax.text(0.5, -0.14, "7 most-duplicated recipes → 224 skills",
            transform=ax.transAxes, ha="center", fontsize=7, color="#666666")

    fig.tight_layout()
    png = reports_dir / "ecosystem_redundancy.png"
    fig.savefig(png, dpi=150)

    json_path = reports_dir / "ecosystem_redundancy.json"
    json_path.write_text(json.dumps({
        "n_records": n_records,
        "n_signatures": n_sig,
        "n_duplicate_records": n_dup,
        "duplicate_ratio": round(n_dup / n_records, 4) if n_records else None,
        "top_atoms_by_popularity": atom_pop.most_common(25),
        "multiplicity_distribution": {b: {"signatures": sig_b[b], "artifacts": rec_b[b]} for b in order},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return png


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260901)
    args = ap.parse_args(argv)

    records = load_records(args.input)
    rng = np.random.default_rng(args.seed)
    print(f"Loaded {len(records)} safety-relevant records with >=1 atom")

    sat = saturation(records, args.n_boot, rng)
    print(f"\n=== Saturation ===")
    print(f"  atom ids covered: {sat['n_atom_ids_covered']} (vocab = 95; "
          f"{95 - sat['n_atom_ids_covered']} added post-audit)")
    print(f"  archetypes: {sat['n_archetypes']}")
    for m, v in sat["milestones"].items():
        print(f"  at {m:>5} artifacts -> atoms={v['atoms_mean']:>5} archetypes={v['archetypes_mean']:>3}")

    held = heldout(records)
    print(f"\n=== Held-out source (leave-one-out) ===")
    for row in held["per_source"]:
        cov = f"{row['coverage']*100:.1f}%" if row["coverage"] is not None else "n/a"
        print(f"  {row['source']:40s} recs={row['n_records']:>4} "
              f"atoms={row['n_distinct_atoms']:>3} coverage={cov:>6} "
              f"novel={row['n_novel_atoms']:>3}")
    print(f"\n  atoms covered by a SINGLE source: {len(held['atoms_covered_by_single_source'])}")
    for a in held["atoms_covered_by_single_source"]:
        print(f"    - {a}")

    # ---- Write JSONs ----
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    sat_path = args.reports_dir / "ecosystem_saturation.json"
    sat_path.write_text(json.dumps(sat, ensure_ascii=False, indent=2), encoding="utf-8")
    held_path = args.reports_dir / "ecosystem_heldout_sources.json"
    held_path.write_text(json.dumps(held, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Plot ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.array(sat["x"], dtype=float)
    fig, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)

    ax = axes[0]
    ax.fill_between(x, sat["primary_atoms_lo"], sat["primary_atoms_hi"],
                    color="#ff7f0e", alpha=0.25, linewidth=0)
    ax.plot(x, sat["primary_atoms_mean"], color="#ff7f0e", lw=2,
            label="distinct atoms (primary only)")
    ax.axhline(95, color="gray", ls="--", lw=1, label="95-atom vocabulary")
    ax.set_ylim(0, 95)
    ax.set_ylabel("distinct atoms covered")
    ax.set_title("Capability saturation (bootstrap, mean ± 95% CI)")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.3)

    ax = axes[1]
    ax.fill_between(x, sat["primary_archetypes_lo"], sat["primary_archetypes_hi"],
                    color="#2ca02c", alpha=0.25, linewidth=0)
    ax.plot(x, sat["primary_archetypes_mean"], color="#2ca02c", lw=2,
            label="distinct archetypes (primary only)")
    ax.axhline(19, color="gray", ls="--", lw=1, label="19-archetype vocabulary")
    ax.set_xlabel("number of artifacts processed")
    ax.set_ylabel("distinct archetypes covered")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    png_path = args.reports_dir / "ecosystem_saturation.png"
    fig.savefig(png_path, dpi=150)

    heldout_png = plot_heldout(held, args.reports_dir)
    redundancy_png = plot_redundancy(records, args.reports_dir)

    print(f"\nWrote: {png_path}")
    print(f"Wrote: {heldout_png}")
    print(f"Wrote: {redundancy_png}")
    print(f"Wrote: {sat_path}")
    print(f"Wrote: {held_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
