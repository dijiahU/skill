#!/usr/bin/env python3
"""Build a per-atom review dashboard for §4.5 vocabulary review.

Joins the v0.3 vocabulary (docs/SAFETY_ATOMIC_CAPABILITIES.md §5) with the
cleaned LLM audit output (reports/llm_audit_classify_*_cleaned.jsonl) and
produces a single self-contained HTML file:

    reports/review_dashboard_v0.3.html

The dashboard answers — per atom — the questions raised in
PROJECT_OVERVIEW.md §4.5.1 (the 5 carving decisions: keep / drop /
merge-sibling / new / rewrite-scope):

  * Primary + secondary hit counts                    → keep / drop signal
  * Sibling co-occurrence within same archetype       → merge signal
  * Cross-archetype co-occurrence                     → rewrite-scope signal
  * Per-atom confidence distribution (median, IQR)    → rewrite-scope signal
  * Wrong-parent occurrences (from pre-cleanup)       → rewrite-scope signal
  * Sample records (5 random hits per atom)           → carving sanity
  * suggested_new_atoms cross-record clustering        → new-atom signal
  * 0-hit atoms auto-flagged at top                    → drop signal

This is NOT for grading the LLM. It's for evaluating whether the v0.3
vocabulary's carving of the safety space matches reality.

Usage:
  python scripts/build_review_dashboard.py \
      --cleaned reports/llm_audit_classify_2026-05-09_cleaned.jsonl \
      --raw reports/llm_audit_classify_2026-05-09.jsonl \
      --output reports/review_dashboard_v0.3.html
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _atomic_capabilities import load_atoms, group_by_parent, group_by_phase  # noqa: E402


# -------------------- data loading --------------------


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def extract_wrong_parent_counts(raw_records: list[dict[str, Any]]) -> dict[str, int]:
    """From RAW (pre-cleanup) records, count how often each atom_id was
    attached to a wrong parent. Returns map atom_id -> count.
    """
    pat = re.compile(
        r"(?:primary|secondary)_atoms label not in vocabulary: ([^/]+)/([\w-]+)"
    )
    counts: Counter[str] = Counter()
    for rec in raw_records:
        for w in rec.get("_validation_warnings", []) or []:
            m = pat.search(w)
            if m:
                _wrong_parent, atom_id = m.group(1), m.group(2)
                counts[atom_id] += 1
    return dict(counts)


# -------------------- per-atom signals --------------------


def compute_signals(
    cleaned: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
    wrong_parent_counts: dict[str, int],
    sample_seed: int = 42,
) -> dict[str, dict[str, Any]]:
    """For each atom (keyed by full label '<parent>/<atom_id>'), compute:
        primary_hits, secondary_hits,
        confidence_stats: {n, median, mean, q25, q75, low_conf_count},
        sibling_cooccur: Counter(other_label -> count) within same record,
        wrong_parent_count,
        sample_records: list of {record_id, confidence, free_form_notes,
                                  kind, top1_anchor_from_stage3}
    """
    rng = random.Random(sample_seed)

    by_label: dict[str, dict[str, Any]] = {}
    for a in atoms:
        label = f"{a['parent_archetype']}/{a['id']}"
        by_label[label] = {
            "atom": a,
            "primary_hits": 0,
            "secondary_hits": 0,
            "confidences": [],
            "cooccur": Counter(),  # label -> count
            "wrong_parent_count": wrong_parent_counts.get(a["id"], 0),
            "_sample_pool": [],  # list of records to sample from
        }

    for rec in cleaned:
        if not rec.get("is_safety_relevant"):
            continue
        primary = rec.get("primary_atoms") or []
        secondary = rec.get("secondary_atoms") or []
        all_labels_in_rec = list(primary) + list(secondary)

        for label in primary:
            if label in by_label:
                by_label[label]["primary_hits"] += 1
                conf = rec.get("confidence")
                if isinstance(conf, (int, float)):
                    by_label[label]["confidences"].append(float(conf))
                # co-occurrence with other labels in same record
                for other in all_labels_in_rec:
                    if other != label and other in by_label:
                        by_label[label]["cooccur"][other] += 1
                by_label[label]["_sample_pool"].append(rec)

        for label in secondary:
            if label in by_label:
                by_label[label]["secondary_hits"] += 1

    # finalize: sample records + confidence stats
    for label, sig in by_label.items():
        # sample 5 records
        pool = sig.pop("_sample_pool")
        if len(pool) > 5:
            samples = rng.sample(pool, 5)
        else:
            samples = pool[:]
        sig["sample_records"] = [
            {
                "record_id": s.get("record_id", "?"),
                "kind": s.get("kind", "?"),
                "confidence": s.get("confidence"),
                "free_form_notes": s.get("free_form_notes") or "",
                "primary_atoms": s.get("primary_atoms") or [],
                "secondary_atoms": s.get("secondary_atoms") or [],
                "self_risk_flags": s.get("self_risk_flags") or [],
            }
            for s in samples
        ]
        # confidence stats
        cs = sig["confidences"]
        if cs:
            sig["confidence_stats"] = {
                "n": len(cs),
                "median": statistics.median(cs),
                "mean": statistics.mean(cs),
                "q25": statistics.quantiles(cs, n=4)[0] if len(cs) >= 4 else min(cs),
                "q75": statistics.quantiles(cs, n=4)[2] if len(cs) >= 4 else max(cs),
                "low_conf_count": sum(1 for c in cs if c < 0.7),
            }
        else:
            sig["confidence_stats"] = None
        del sig["confidences"]

    return by_label


def compute_global(
    cleaned: list[dict[str, Any]],
    by_label: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute global / cross-atom stats."""
    safety_relevant = [r for r in cleaned if r.get("is_safety_relevant")]
    skip_reasons = Counter(
        r.get("skip_reason") for r in cleaned if not r.get("is_safety_relevant")
    )
    confs = [
        r["confidence"]
        for r in cleaned
        if isinstance(r.get("confidence"), (int, float))
    ]
    conf_buckets = [(0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    conf_hist = []
    for lo, hi in conf_buckets:
        n = sum(1 for c in confs if lo <= c < hi)
        conf_hist.append((f"[{lo:.1f}, {hi:.2f})", n))

    # phase distribution
    phase_counter: Counter[str] = Counter()
    for r in safety_relevant:
        for p in r.get("covered_phases") or []:
            phase_counter[p] += 1

    # self_risk_flags
    risk_flags: Counter[str] = Counter()
    for r in cleaned:
        for f in r.get("self_risk_flags") or []:
            risk_flags[f] += 1

    # suggested_new_atoms aggregation
    suggestions = []
    for r in cleaned:
        for s in r.get("suggested_new_atoms") or []:
            pid = s.get("proposed_id", "?")
            suggestions.append({
                "proposed_id": pid,
                "suggested_parent_archetype": s.get("suggested_parent_archetype", "?"),
                "evidence_from_this_record": s.get("evidence_from_this_record", ""),
                "rough_definition": s.get("rough_definition", ""),
                "from_record": r.get("record_id", "?"),
            })

    sugg_freq = Counter(s["proposed_id"] for s in suggestions)

    # auto-flags: 0-hit, low-hit, high-wrong-parent, low-confidence atoms
    zero_hit = []
    low_hit = []  # primary < 5
    high_wp = []  # wrong_parent > 2
    low_conf_atoms = []  # median confidence < 0.7

    for label, sig in by_label.items():
        ph = sig["primary_hits"]
        sh = sig["secondary_hits"]
        if ph == 0 and sh == 0:
            zero_hit.append(label)
        elif ph < 5:
            low_hit.append((label, ph, sh))
        if sig["wrong_parent_count"] > 2:
            high_wp.append((label, sig["wrong_parent_count"]))
        cs = sig.get("confidence_stats")
        if cs and cs["median"] < 0.7 and cs["n"] >= 5:
            low_conf_atoms.append((label, cs["median"], cs["n"]))

    low_hit.sort(key=lambda x: x[1])
    high_wp.sort(key=lambda x: -x[1])
    low_conf_atoms.sort(key=lambda x: x[1])

    return {
        "total_records": len(cleaned),
        "safety_relevant": len(safety_relevant),
        "non_safety_relevant": len(cleaned) - len(safety_relevant),
        "skip_reasons": dict(skip_reasons.most_common()),
        "confidence_histogram": conf_hist,
        "confidence_stats": {
            "n": len(confs),
            "median": statistics.median(confs) if confs else 0,
            "mean": statistics.mean(confs) if confs else 0,
        },
        "phase_distribution": dict(phase_counter.most_common()),
        "self_risk_flags": dict(risk_flags.most_common(15)),
        "suggested_new_atoms": suggestions,
        "suggestion_frequency": dict(sugg_freq.most_common()),
        "auto_flags": {
            "zero_hit": zero_hit,
            "low_hit": low_hit,
            "high_wrong_parent": high_wp,
            "low_confidence_atoms": low_conf_atoms,
        },
    }


# -------------------- HTML rendering --------------------

CSS = r"""
:root {
  --fg: #0f172a;
  --fg-muted: #475569;
  --fg-soft: #64748b;
  --bg: #f7f8fb;
  --bg-card: #ffffff;
  --bg-soft: #f1f5f9;
  --border: #e2e8f0;
  --border-soft: #eef2f6;
  --accent: #2563eb;
  --accent-soft: #dbeafe;
  --done: #16a34a;
  --done-soft: #d1fae5;
  --active: #d97706;
  --active-soft: #fef3c7;
  --danger: #dc2626;
  --danger-soft: #fee2e2;
  --info: #0891b2;
  --info-soft: #cffafe;
  --shadow: 0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04);
  --shadow-strong: 0 4px 6px -1px rgba(15,23,42,0.08), 0 2px 4px -2px rgba(15,23,42,0.04);
  --radius: 10px;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
               "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
               "Noto Sans CJK SC", Helvetica, Arial, sans-serif;
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
.page { max-width: 1180px; margin: 0 auto; padding: 28px 24px 96px; }

/* hero */
.hero {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0891b2 130%);
  color: #f8fafc;
  border-radius: 14px;
  padding: 28px 32px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-strong);
}
.hero h1 { margin: 0 0 4px; font-size: 24px; font-weight: 700; }
.hero .sub { color: #cbd5e1; margin: 0 0 18px; font-size: 14px; }
.hero .meta-row { display: flex; gap: 10px; flex-wrap: wrap; }
.hero .meta-pill {
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 13px;
}

/* section */
section { margin-bottom: 24px; }
section > h2 {
  font-size: 20px;
  font-weight: 700;
  margin: 32px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
section > h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 20px 0 8px;
  color: var(--fg);
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  box-shadow: var(--shadow);
  margin-bottom: 12px;
}

/* global stat grid */
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; }
.stat-grid .stat {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 14px;
}
.stat .num { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat .lbl { font-size: 12px; color: var(--fg-soft); }

/* histogram */
.histogram { display: flex; align-items: flex-end; gap: 6px; height: 100px; padding: 8px 0; }
.histogram .bar {
  flex: 1;
  background: var(--accent-soft);
  border: 1px solid var(--accent);
  border-radius: 3px 3px 0 0;
  position: relative;
  min-height: 4px;
}
.histogram .bar .label { position: absolute; top: -18px; left: 0; right: 0; text-align: center; font-size: 11px; color: var(--fg-muted); font-variant-numeric: tabular-nums; }
.histogram-axis { display: flex; gap: 6px; font-size: 11px; color: var(--fg-soft); margin-top: 2px; }
.histogram-axis div { flex: 1; text-align: center; }

/* auto-flag boxes */
.flag-box {
  background: var(--bg-card);
  border-left: 4px solid var(--active);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 8px;
}
.flag-box.flag-zero { border-left-color: var(--danger); }
.flag-box.flag-low { border-left-color: var(--active); }
.flag-box.flag-wp { border-left-color: var(--info); }
.flag-box.flag-conf { border-left-color: #ca8a04; }
.flag-box h3 { margin: 0 0 6px; font-size: 14px; }
.flag-box ul { margin: 4px 0 0; padding-left: 20px; font-size: 14px; }
.flag-box code { font-size: 12.5px; }

/* archetype groupings */
.archetype-group {
  margin: 16px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-card);
  overflow: hidden;
}
.archetype-group > summary {
  cursor: pointer;
  padding: 14px 18px;
  background: var(--bg-soft);
  border-bottom: 1px solid var(--border);
  font-weight: 600;
  font-size: 16px;
  list-style: none;
  outline: none;
}
.archetype-group > summary::-webkit-details-marker { display: none; }
.archetype-group > summary::before {
  content: "▸";
  display: inline-block;
  margin-right: 8px;
  transition: transform 0.15s ease;
  color: var(--accent);
}
.archetype-group[open] > summary::before { transform: rotate(90deg); }
.archetype-group .arche-meta {
  font-size: 12px;
  color: var(--fg-soft);
  font-weight: normal;
  margin-left: 8px;
}
.exec-type {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  margin-left: 4px;
  vertical-align: middle;
}
.exec-type--workflow  { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.exec-type--checklist { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
.exec-type--mixed     { background: #ede9fe; color: #5b21b6; border: 1px solid #ddd6fe; }

/* enforcement_mode badge per atom (v0.5) */
.enforce-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  vertical-align: middle;
}
.enforce-badge--hook   { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.enforce-badge--skill  { background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
.enforce-badge--hybrid { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }

/* archetype-level packaging badge */
.archetype-packaging {
  display: inline-block;
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 4px;
  vertical-align: middle;
  font-variant-numeric: tabular-nums;
}
.archetype-packaging--pure-hook   { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.archetype-packaging--pure-skill  { background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
.archetype-packaging--pure-hybrid { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.archetype-packaging--mixed-enforce { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }

/* atom card */
.atom-card {
  border-bottom: 1px solid var(--border-soft);
  padding: 14px 20px;
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: 18px;
}
.atom-card:last-child { border-bottom: none; }
.atom-card-left { min-width: 0; }
.atom-card-right { min-width: 0; }
.atom-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.atom-id {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--fg);
}
.atom-phase {
  font-size: 11px;
  background: var(--info-soft);
  color: var(--info);
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 500;
}
.hit-badge {
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 13px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
}
.hit-high { background: var(--done-soft); color: var(--done); }
.hit-med  { background: var(--info-soft); color: var(--info); }
.hit-low  { background: var(--active-soft); color: var(--active); }
.hit-zero { background: var(--danger-soft); color: var(--danger); }

.atom-def { font-size: 13px; color: var(--fg-muted); }
.atom-def .def { margin: 4px 0; }
.atom-def .scope-line { margin: 4px 0; font-size: 12.5px; }
.atom-def .scope-key { font-weight: 600; color: var(--fg); }
.atom-def code {
  font-size: 11.5px;
  background: var(--bg-soft);
  padding: 1px 5px;
  border-radius: 3px;
}

.signals-table {
  font-size: 13px;
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 8px;
}
.signals-table td {
  padding: 4px 0;
  border-bottom: 1px dotted var(--border-soft);
  vertical-align: top;
}
.signals-table td:first-child {
  color: var(--fg-soft);
  width: 50%;
  white-space: nowrap;
}
.signals-table td:last-child { font-variant-numeric: tabular-nums; font-weight: 500; }

.cooccur-list {
  font-size: 12.5px;
  list-style: none;
  padding: 0;
  margin: 4px 0 0;
}
.cooccur-list li {
  padding: 2px 0;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.cooccur-list .sibling { color: var(--active); font-weight: 500; }
.cooccur-list .outside { color: var(--fg-soft); }
.cooccur-list code { font-size: 11.5px; }
.cooccur-empty { color: var(--fg-soft); font-style: italic; font-size: 12.5px; }

details.samples {
  margin-top: 8px;
  font-size: 12.5px;
}
details.samples > summary {
  cursor: pointer;
  color: var(--accent);
  font-weight: 500;
  outline: none;
}
details.samples > summary::-webkit-details-marker { display: none; }
details.samples > summary::before { content: "▸ "; }
details.samples[open] > summary::before { content: "▾ "; }
details.samples .sample {
  background: var(--bg-soft);
  border-radius: 4px;
  padding: 6px 8px;
  margin: 4px 0;
}
details.samples .sample-head {
  font-family: ui-monospace, monospace;
  font-size: 11.5px;
  color: var(--fg-muted);
  word-break: break-all;
}
details.samples .sample-conf {
  display: inline-block;
  background: white;
  border: 1px solid var(--border);
  padding: 0 5px;
  border-radius: 3px;
  margin-left: 6px;
  font-weight: 600;
}
details.samples .sample-notes {
  color: var(--fg);
  font-size: 12px;
  margin-top: 3px;
  line-height: 1.5;
}

@media (max-width: 880px) {
  .atom-card { grid-template-columns: 1fr; }
  .page { padding: 16px 12px 56px; }
}

/* phase navigation pills (in hero) */
.phase-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}
.nav-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.18);
  color: #f8fafc;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  text-decoration: none;
  transition: background 0.15s ease;
}
.nav-pill:hover {
  background: rgba(255,255,255,0.2);
  text-decoration: none;
}
.nav-pill-num {
  background: rgba(8,145,178,0.6);
  border-radius: 999px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* phase sections (top-level grouping in §3) */
.phase-section {
  margin: 24px 0;
}
.phase-header {
  background: linear-gradient(135deg, var(--accent-soft) 0%, var(--info-soft) 100%);
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  padding: 16px 22px;
  margin-bottom: 12px;
}
.phase-header h3 {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 700;
  color: var(--fg);
}
.phase-header h3 code {
  font-size: 13px;
  background: rgba(255,255,255,0.6);
  border: 1px solid rgba(37,99,235,0.2);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--accent-strong);
}
.phase-stats {
  font-size: 13px;
  color: var(--fg-muted);
  font-variant-numeric: tabular-nums;
}
.phase-stats strong { color: var(--fg); }

/* research flag (new framing — replaces flag-zero / flag-low) */
.flag-research { border-left-color: #16a34a; }
.flag-info { border-left-color: var(--info); }
.thin-phase-block,
.sugg-parent-block {
  margin: 10px 0;
  padding: 8px 12px;
  background: var(--bg-soft);
  border-radius: 6px;
  font-size: 13px;
}
.thin-phase-block h4,
.sugg-parent-block h4 {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--fg);
}
.thin-phase-block h4 code,
.sugg-parent-block h4 code {
  font-size: 11.5px;
  color: var(--fg-soft);
}
.thin-phase-block ul,
.sugg-parent-block ul {
  margin: 4px 0 0;
  padding-left: 18px;
  font-size: 12.5px;
}

/* suggestion table */
table.sugg-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-top: 8px;
}
table.sugg-table th, table.sugg-table td {
  border: 1px solid var(--border-soft);
  padding: 6px 10px;
  text-align: left;
  vertical-align: top;
}
table.sugg-table th { background: var(--bg-soft); font-weight: 600; }
table.sugg-table code { font-size: 12px; }
"""


def hit_class(n: int) -> str:
    if n == 0: return "hit-zero"
    if n < 5: return "hit-low"
    if n < 30: return "hit-med"
    return "hit-high"


def fmt_pct(part: int, total: int) -> str:
    if total == 0: return "—"
    return f"{100 * part / total:.1f}%"


def render_atom_card(label: str, sig: dict[str, Any], by_label: dict[str, dict[str, Any]]) -> str:
    a = sig["atom"]
    parent = a["parent_archetype"]
    atom_id = a["id"]
    ph = sig["primary_hits"]
    sh = sig["secondary_hits"]
    cs = sig.get("confidence_stats")
    wp = sig["wrong_parent_count"]

    # cooccur top 8
    cooccur_list_html = ""
    top_cooccur = sig["cooccur"].most_common(8)
    if top_cooccur:
        items = []
        for other_label, n in top_cooccur:
            other_parent = other_label.split("/", 1)[0]
            is_sibling = (other_parent == parent)
            cls = "sibling" if is_sibling else "outside"
            label_short = other_label.split("/", 1)[1] if "/" in other_label else other_label
            arche_marker = "" if is_sibling else f' <span style="color:#94a3b8;font-size:10.5px">({other_parent})</span>'
            items.append(
                f'<li class="{cls}"><code>{html.escape(label_short)}</code>{arche_marker}<span>{n}</span></li>'
            )
        cooccur_list_html = '<ul class="cooccur-list">' + "".join(items) + "</ul>"
    else:
        cooccur_list_html = '<div class="cooccur-empty">无（该原子很少与其他原子同时出现）</div>'

    # confidence stats text
    if cs:
        conf_text = (
            f"median {cs['median']:.2f} · IQR [{cs['q25']:.2f}, {cs['q75']:.2f}] · n={cs['n']} · "
            f"{cs['low_conf_count']} 条 < 0.7"
        )
    else:
        conf_text = "—（无 primary 命中）"

    # samples
    samples_html_parts = []
    for s in sig["sample_records"]:
        notes = s.get("free_form_notes") or ""
        if len(notes) > 280:
            notes = notes[:280] + "…"
        primary = ", ".join(html.escape(p.split("/", 1)[1]) for p in s.get("primary_atoms", []))
        secondary = ", ".join(html.escape(p.split("/", 1)[1]) for p in s.get("secondary_atoms", []))
        risk = ", ".join(html.escape(r) for r in s.get("self_risk_flags", []))
        conf_txt = f"{s['confidence']:.2f}" if isinstance(s.get('confidence'), (int, float)) else "?"
        samples_html_parts.append(
            f'<div class="sample">'
            f'<div class="sample-head">'
            f'{html.escape(s["record_id"])}'
            f'<span class="sample-conf">{html.escape(s.get("kind","?"))} · conf {conf_txt}</span>'
            f'</div>'
            f'<div class="sample-notes">'
            f'<strong>primary</strong>: {primary or "—"}<br>'
            f'<strong>secondary</strong>: {secondary or "—"}<br>'
            f'<strong>self_risk_flags</strong>: {risk or "—"}<br>'
            f'<strong>notes</strong>: {html.escape(notes) or "—"}'
            f'</div>'
            f'</div>'
        )
    samples_html = (
        f'<details class="samples"><summary>样本 records ({len(sig["sample_records"])})'
        f'</summary>{"".join(samples_html_parts) or "<em>无</em>"}</details>'
    )

    # related atoms (from definition) — show as quick hint
    related_html = ""
    if a.get("related"):
        related_codes = ", ".join(f"<code>{html.escape(r)}</code>" for r in a["related"])
        related_html = (
            f'<p class="scope-line"><span class="scope-key">related (词表定义):</span> {related_codes}</p>'
        )

    # enforcement_mode badge (v0.5)
    mode = ATOM_ENFORCEMENT_MODE.get(atom_id, "skill")
    mode_emoji, mode_name, mode_hint = ENFORCEMENT_BADGE[mode]
    enforcement_badge = (
        f'<span class="enforce-badge enforce-badge--{mode}" title="{mode_hint}">'
        f'{mode_emoji} {mode_name}</span>'
    )

    return f"""
<article class="atom-card" id="atom-{html.escape(atom_id)}">
  <div class="atom-card-left">
    <div class="atom-head">
      <span class="atom-id">{html.escape(label)}</span>
      <span class="atom-phase">{html.escape(a.get('phase',''))}</span>
      {enforcement_badge}
      <span class="hit-badge {hit_class(ph)}">primary {ph}</span>
      <span class="hit-badge {hit_class(sh)}" title="secondary hits">sec {sh}</span>
    </div>
    <div class="atom-def">
      <p class="def">{html.escape(a.get('definition',''))}</p>
      <p class="scope-line"><span class="scope-key">scope_in:</span> {html.escape(a.get('scope_in',''))}</p>
      <p class="scope-line"><span class="scope-key">scope_out:</span> {html.escape(a.get('scope_out',''))}</p>
      {related_html}
    </div>
  </div>
  <div class="atom-card-right">
    <table class="signals-table">
      <tr><td>Primary hits</td><td>{ph}</td></tr>
      <tr><td>Secondary hits</td><td>{sh}</td></tr>
      <tr><td>Wrong-parent (pre-cleanup)</td><td>{wp}</td></tr>
      <tr><td>Confidence (primary records)</td><td>{conf_text}</td></tr>
    </table>
    <div style="margin-top:8px;">
      <strong style="font-size:12.5px;color:var(--fg-muted);">Co-occurrence (top 8 in same record)</strong>
      {cooccur_list_html}
    </div>
    {samples_html}
  </div>
</article>
"""


def render_archetype_group(parent: str, atoms_in: list[dict[str, Any]], by_label: dict[str, dict[str, Any]]) -> str:
    cards_html = []
    total_primary = 0
    for a in atoms_in:
        label = f"{parent}/{a['id']}"
        sig = by_label[label]
        total_primary += sig["primary_hits"]
        cards_html.append(render_atom_card(label, sig, by_label))

    # v0.4 archetype-as-skill: show packaging type badge (workflow / checklist / mixed)
    exec_type = ARCHETYPE_EXECUTION_TYPE.get(parent)
    if exec_type:
        emoji, name, hint = EXEC_TYPE_BADGE[exec_type]
        type_badge = (
            f'<span class="exec-type exec-type--{exec_type}" title="{hint}">'
            f'{emoji} {name}'
            f'</span>'
        )
    else:
        type_badge = ""

    # v0.5 enforcement_mode mix per archetype
    mode_counts = Counter(ATOM_ENFORCEMENT_MODE.get(a["id"], "skill") for a in atoms_in)
    if len(mode_counts) == 1:
        only_mode = next(iter(mode_counts))
        em, mn, mh = ENFORCEMENT_BADGE[only_mode]
        archetype_packaging = (
            f'<span class="archetype-packaging archetype-packaging--pure-{only_mode}" '
            f'title="所有 {len(atoms_in)} 个 atoms 都是 {mn} 模式 → archetype 是 pure-{mn}">'
            f'pure {em} {mn}</span>'
        )
    else:
        parts = []
        for m in ("hook", "hybrid", "skill"):
            if mode_counts.get(m):
                em, mn, _ = ENFORCEMENT_BADGE[m]
                parts.append(f'{mode_counts[m]} {em}')
        archetype_packaging = (
            f'<span class="archetype-packaging archetype-packaging--mixed-enforce" '
            f'title="archetype 内部 atoms 跨多种 enforcement_mode → mixed-enforcement">'
            f'mix: {" + ".join(parts)}</span>'
        )

    return f"""
<details class="archetype-group" open>
  <summary>{html.escape(parent)} {type_badge} {archetype_packaging} <span class="arche-meta">{len(atoms_in)} atoms · {total_primary} primary hits</span></summary>
  {"".join(cards_html)}
</details>
"""


# Phase ordering matches the project book and the §4 phase view in
# SAFETY_ATOMIC_CAPABILITIES.md: input → planning → tool → output → cross-cutting.
PHASE_ORDER = [
    ("input-understanding", "输入理解阶段", "input"),
    ("planning",            "规划决策阶段",  "planning"),
    ("tool-invocation",     "工具调用阶段",  "tool-inv"),
    ("output-generation",   "输出生成阶段",  "output"),
    ("cross-cutting",       "全周期 / cross-cutting", "cross"),
]


# v0.4 archetype-as-skill packaging model: each archetype is a single SKILL.md
# with internal tools. This dict assigns each archetype an execution_type
# (workflow / checklist / mixed). See SAFETY_ATOMIC_CAPABILITIES.md §10.4.
ARCHETYPE_EXECUTION_TYPE = {
    "detect-prompt-injection": "checklist",
    "classify-input-intent-ambiguity": "workflow",
    "scan-input-for-pii-and-secrets": "mixed",
    "threat-model-task": "checklist",
    "enforce-policy-as-code": "checklist",
    "check-tool-permission-scope": "checklist",
    "detect-task-overreach": "workflow",
    "validate-tool-argument-safety": "checklist",
    "constrain-workspace-boundary": "mixed",
    "validate-agent-tool-trust": "checklist",
    "detect-supply-chain-risk": "checklist",
    "scan-code-for-vulnerabilities": "checklist",
    "detect-malicious-payload-in-tool-output": "checklist",
    "enforce-rate-and-quota-limits": "mixed",
    "redact-sensitive-output": "mixed",
    "detect-data-exfiltration": "checklist",
    "enforce-output-content-policy": "checklist",
    "audit-trail-recording": "checklist",
    "incident-response-handler": "workflow",
    "escalate-to-human-sentinel": "workflow",
}

EXEC_TYPE_BADGE = {
    "workflow":  ("🔄", "workflow",  "顺序执行，后步依赖前步"),
    "checklist": ("☑",  "checklist", "并行 fan-out，互相独立"),
    "mixed":     ("🔀", "mixed",     "先并行 detect，后串行 enforce"),
}


# v0.5 enforcement_mode per atom (2026-05-10), extended to 115 atoms in v0.6 (2026-05-11),
# pruned to 98 atoms in v0.7, 95 atoms in v0.7.1, then frozen as v1 (= v0.7.1 content).
# - hook   : deterministic regex / lookup / OS config / signature verify; 由 host hook 硬强制
# - skill  : 需要 LLM 语义判断 / 推理；由 agent 顺着 SKILL.md 调用
# - hybrid : hook fast path + skill semantic fallback; 复杂 case 升级给 LLM
# Counts (v1 freeze): 60 hook + 21 hybrid + 14 skill = 95.
ATOM_ENFORCEMENT_MODE = {
    # detect-prompt-injection (5)
    "detect-direct-prompt-injection": "skill",
    "detect-indirect-prompt-injection": "skill",
    "detect-jailbreak-template": "hybrid",
    "detect-system-prompt-extraction": "skill",
    "detect-roleplay-escape": "skill",
    # classify-input-intent-ambiguity (3)
    "classify-request-ambiguity-level": "skill",
    "detect-destructive-action-keyword": "hook",
    "elicit-clarification-before-act": "skill",
    # scan-input-for-pii-and-secrets (5)
    "detect-pii-in-input": "hybrid",
    "detect-payment-card-data": "hook",
    "detect-credential-in-input": "hybrid",
    "detect-private-key-input": "hook",
    "redact-input-pii": "hook",
    # threat-model-task: REMOVED in v0.7 (archetype out-of-scope: agent-as-output deliverable)
    # enforce-policy-as-code (2) — v0.7: dropped evaluate-formal-policy-constraint (research) +
    # evaluate-regulatory-compliance-rule (enterprise-infra-dependent)
    "evaluate-opa-rego-rule": "hook",
    "evaluate-content-moderation-rule": "hybrid",
    # check-tool-permission-scope (4) — gained check-rbac-role in v0.6
    "verify-allowed-tool-list": "hook",
    "verify-resource-namespace-scope": "hook",
    "verify-capability-token": "hook",
    "check-rbac-role": "hook",
    # detect-task-overreach (4) — v0.7: dropped check-logic-consistency (SMT/research),
    # gained enumerate-task-side-effects (moved from threat-model-task)
    "compare-plan-vs-stated-intent": "skill",
    "flag-unjustified-side-effect": "skill",
    "detect-autonomy-budget-exceeded": "hook",
    "enumerate-task-side-effects": "skill",
    # validate-tool-argument-safety (8)
    "detect-shell-command-injection": "hybrid",
    "detect-sql-injection": "hybrid",
    "detect-path-traversal": "hook",
    "detect-destructive-flag": "hook",
    "detect-unsafe-url": "hook",
    "detect-secret-in-args": "hook",
    "detect-overbroad-resource-selector": "hook",
    "validate-tool-argument-schema": "hook",
    # constrain-workspace-boundary (6) — +2 in v0.6 (multi-agent)
    "enforce-filesystem-sandbox": "hook",
    "enforce-network-egress-allowlist": "hook",
    "enforce-process-sandbox": "hook",
    "detect-sandbox-escape-attempt": "hook",
    "enforce-subagent-scope-isolation": "hook",
    "enforce-swarm-race-condition-safety": "hook",
    # validate-agent-tool-trust (11) — v0.7.1: also dropped 3 planning-phase A2A trust atoms
    # (verify-delegation-chain, verify-agent-identity, evaluate-mcp-server-trustworthiness)
    # — too forward-looking; A2A protocols / agent identity registries not mainstream yet.
    "check-tool-typosquat-name": "hook",
    "verify-skill-signature": "hook",
    "verify-tool-publisher-identity": "hook",
    "detect-hidden-instruction-in-tool-description": "hybrid",
    "detect-tool-loader-exploit": "hybrid",
    "detect-skill-permission-overrequest": "hybrid",
    "detect-mcp-confused-deputy": "hybrid",
    "detect-mcp-token-passthrough": "hook",
    "detect-mcp-session-hijacking": "hook",
    "detect-mcp-ssrf": "hook",
    "detect-delayed-payload-pattern": "skill",
    # detect-supply-chain-risk (8) — v0.7: dropped check-sbom-completeness (CI-time)
    "check-package-typosquat": "hook",
    "check-package-cve": "hook",
    "check-dependency-confusion": "hook",
    "audit-install-hook": "hybrid",
    "check-package-recency-anomaly": "hook",
    "detect-malicious-postinstall-script": "hybrid",
    "detect-hallucinated-package": "hook",
    "audit-ci-workflow-security": "hybrid",
    # scan-code-for-vulnerabilities (5) — v0.7: dropped 3 v0.6-new analytical SAST atoms
    # (BOLA / mass-assignment / CORS audit). Remaining 5 are matcher-scoped to Write|Edit|MultiEdit.
    "run-sast-scan": "hook",
    "detect-hardcoded-secret-in-code": "hook",
    "detect-insecure-cryptography": "hook",
    "detect-unsafe-deserialization": "hook",
    "detect-injection-flaw": "hook",
    # detect-malicious-payload-in-tool-output (5)
    "match-yara-rule": "hook",
    "check-malware-hash-ioc": "hook",
    "detect-archive-bomb": "hook",
    "detect-suspicious-mime-type": "hook",
    "strip-active-html-script": "hook",
    # enforce-rate-and-quota-limits (4)
    "enforce-tool-call-rate-limit": "hook",
    "enforce-token-budget-cap": "hook",
    "enforce-cost-cap-per-task": "hook",
    "detect-runaway-loop": "hybrid",
    # redact-sensitive-output (4)
    "redact-output-pii": "hook",
    "redact-output-secret": "hook",
    "redact-output-system-prompt": "hybrid",
    "redact-output-internal-infra": "hybrid",
    # detect-data-exfiltration (4) — v0.7: dropped detect-c2-beaconing-pattern (multi-call network stats)
    "detect-markdown-image-beacon": "hook",
    "detect-base64-payload-in-output": "hybrid",
    "detect-dns-exfiltration-pattern": "hook",
    "detect-covert-channel-in-tool-call": "hybrid",
    # enforce-output-content-policy (5)
    "review-generated-code-output": "hybrid",
    "review-generated-message-output": "skill",
    "review-generated-file-write": "skill",
    "detect-dangerous-instruction-in-output": "skill",
    "enforce-disallowed-content-rule": "hybrid",
    # audit-trail-recording (3) — v0.7: dropped enable-tamper-evident-storage (infra) +
    # cryptographic-intent-binding (research-grade crypto chain)
    "record-decision-trace": "hook",
    "record-tool-invocation-trace": "hook",
    "record-prompt-and-context-snapshot": "hook",
    # incident-response-handler (5)
    "halt-in-flight-action": "hook",
    "snapshot-agent-state": "hook",
    "isolate-affected-resource": "hook",
    "notify-oncall-and-open-ticket": "hook",
    "execute-recovery-playbook": "hybrid",
    # escalate-to-human-sentinel (4) ⭐
    "request-human-confirmation": "hook",
    "present-risk-rationale": "skill",
    "await-human-decision-or-timeout": "hook",
    "log-human-decision-outcome": "hook",
}

ENFORCEMENT_BADGE = {
    "hook":   ("🔒", "hook",   "host 硬强制；agent 无法绕过；regex / OS / sig / log / counter"),
    "skill":  ("🧠", "skill",  "需要 agent LLM 语义判断；通过 SKILL.md tool 调用"),
    "hybrid": ("⚡", "hybrid", "hook fast path + LLM 语义 fallback"),
}


def render_phase_section(
    phase_id: str,
    phase_zh: str,
    atoms_in_phase: list[dict[str, Any]],
    by_label: dict[str, dict[str, Any]],
) -> str:
    """Render one phase's section: header + sub-grouped by archetype."""
    # group atoms in this phase by parent_archetype
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for a in atoms_in_phase:
        by_parent.setdefault(a["parent_archetype"], []).append(a)

    total_primary = sum(by_label[f"{a['parent_archetype']}/{a['id']}"]["primary_hits"] for a in atoms_in_phase)
    avg_primary = total_primary / max(len(atoms_in_phase), 1)

    archetype_blocks = []
    for parent in sorted(by_parent):
        archetype_blocks.append(
            render_archetype_group(parent, by_parent[parent], by_label)
        )

    return f"""
<div class="phase-section" id="phase-{phase_id}">
  <header class="phase-header">
    <h3>📍 {phase_zh} <code>({phase_id})</code></h3>
    <div class="phase-stats">
      <span><strong>{len(atoms_in_phase)}</strong> atoms</span>
      <span>· <strong>{len(by_parent)}</strong> archetypes</span>
      <span>· <strong>{total_primary}</strong> primary hits</span>
      <span>· avg <strong>{avg_primary:.1f}</strong>/atom</span>
    </div>
  </header>
  {"".join(archetype_blocks)}
</div>
"""


def render_global_section(g: dict[str, Any]) -> str:
    # confidence histogram
    max_count = max(n for _, n in g["confidence_histogram"]) or 1
    bar_html = []
    label_html = []
    for lbl, n in g["confidence_histogram"]:
        h = max(4, int(80 * n / max_count))
        bar_html.append(f'<div class="bar" style="height:{h}px;"><div class="label">{n}</div></div>')
        label_html.append(f'<div>{lbl}</div>')

    # phase / risk-flag tables
    phase_rows = "".join(
        f'<tr><td><code>{html.escape(p)}</code></td><td>{n}</td></tr>'
        for p, n in g["phase_distribution"].items()
    )
    risk_rows = "".join(
        f'<tr><td><code>{html.escape(f)}</code></td><td>{n}</td></tr>'
        for f, n in g["self_risk_flags"].items()
    )

    return f"""
<div class="card">
  <div class="stat-grid">
    <div class="stat"><div class="num">{g['total_records']}</div><div class="lbl">总 records</div></div>
    <div class="stat"><div class="num">{g['safety_relevant']}</div><div class="lbl">safety-relevant ({fmt_pct(g['safety_relevant'], g['total_records'])})</div></div>
    <div class="stat"><div class="num">{g['non_safety_relevant']}</div><div class="lbl">non-safety</div></div>
    <div class="stat"><div class="num">{g['confidence_stats']['median']:.2f}</div><div class="lbl">confidence median</div></div>
    <div class="stat"><div class="num">{len(g['suggested_new_atoms'])}</div><div class="lbl">建议新原子（待聚类）</div></div>
  </div>
</div>

<h3>Confidence 分布</h3>
<div class="card">
  <div class="histogram">{"".join(bar_html)}</div>
  <div class="histogram-axis">{"".join(label_html)}</div>
</div>

<h3>Covered phases (per record，多选)</h3>
<div class="card">
  <table class="sugg-table">
    <thead><tr><th>Phase</th><th>出现次数</th></tr></thead>
    <tbody>{phase_rows}</tbody>
  </table>
</div>

<h3>self_risk_flags Top 15</h3>
<div class="card">
  <table class="sugg-table">
    <thead><tr><th>Flag</th><th>计数</th></tr></thead>
    <tbody>{risk_rows}</tbody>
  </table>
</div>
"""


def _phase_of_label(label: str, atoms_by_label: dict[str, dict[str, Any]]) -> str:
    a = atoms_by_label.get(label, {}).get("atom") if atoms_by_label else None
    return (a or {}).get("phase", "?")


def _group_low_coverage_by_phase(
    items: list[tuple],  # (label, ...)
    by_label: dict[str, dict[str, Any]],
) -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = {phase: [] for phase, _, _ in PHASE_ORDER}
    for item in items:
        label = item[0]
        phase = _phase_of_label(label, by_label)
        if phase not in out:
            out.setdefault(phase, []).append(item)
        else:
            out[phase].append(item)
    return out


def render_auto_flags(g: dict[str, Any], by_label: dict[str, dict[str, Any]]) -> str:
    """Render signal sections — re-framed as research / scope-rewrite signals,
    NOT delete candidates. User's stance: thin-coverage atoms represent
    research gaps to fill, not categories to remove.
    """
    f = g["auto_flags"]

    # Combine 0-hit + low-hit into one "thin-coverage" set, grouped by phase.
    # Each entry: (label, primary_hits, secondary_hits)
    thin = [(l, 0, by_label[l]["secondary_hits"]) for l in f["zero_hit"]]
    thin += [(l, ph, sh) for l, ph, sh in f["low_hit"]]
    # dedupe (zero_hit might overlap with low_hit if low_hit < 5 includes 0)
    seen = set()
    thin_unique = []
    for entry in thin:
        if entry[0] not in seen:
            seen.add(entry[0])
            thin_unique.append(entry)
    thin_unique.sort(key=lambda x: (x[1], x[0]))  # primary asc, then label

    thin_by_phase = _group_low_coverage_by_phase(thin_unique, by_label)
    thin_phase_blocks = []
    for phase_id, phase_zh, _short in PHASE_ORDER:
        items = thin_by_phase.get(phase_id, [])
        if not items:
            continue
        lis = "".join(
            f'<li><a href="#atom-{html.escape(l.split("/")[1])}"><code>{html.escape(l)}</code></a> '
            f'· primary {ph} · secondary {sh}</li>'
            for l, ph, sh in items
        )
        thin_phase_blocks.append(
            f'<div class="thin-phase-block">'
            f'<h4>📍 {phase_zh} <code>({phase_id})</code> · {len(items)} 个</h4>'
            f'<ul>{lis}</ul>'
            f'</div>'
        )

    # wrong-parent: still useful (signals scope ambiguity, actionable for rewriting)
    wp_lis = "".join(
        f'<li><a href="#atom-{html.escape(l.split("/")[1])}"><code>{html.escape(l)}</code></a> · {wp} 次 wrong-parent</li>'
        for l, wp in f["high_wrong_parent"]
    )

    # suggestions
    sugg_top = list(g["suggestion_frequency"].items())
    sugg_top.sort(key=lambda x: -x[1])
    if sugg_top:
        # Group suggestions by suggested_parent_archetype to make them more useful
        sugg_by_parent: dict[str, list[dict[str, Any]]] = {}
        for s in g["suggested_new_atoms"]:
            sugg_by_parent.setdefault(s["suggested_parent_archetype"], []).append(s)

        # Build rows: parent → 该 parent 下提议的 proposed_ids
        sugg_blocks = []
        for parent in sorted(sugg_by_parent):
            entries = sugg_by_parent[parent]
            row_lines = "".join(
                f'<li><code>{html.escape(s["proposed_id"])}</code> — '
                f'<span style="color:var(--fg-muted)">{html.escape(s["rough_definition"][:120])}</span></li>'
                for s in entries[:8]
            )
            sugg_blocks.append(
                f'<div class="sugg-parent-block">'
                f'<h4><code>{html.escape(parent)}</code> · {len(entries)} 条建议</h4>'
                f'<ul>{row_lines}</ul>'
                f'</div>'
            )
        sugg_section = f"""
<div class="flag-box flag-info">
<h3>📥 新原子建议（按 suggested_parent_archetype 分组）</h3>
<p style="font-size:12.5px;color:var(--fg-soft);margin-top:0;">
  LLM 在审计中提出 <strong>{len(g['suggested_new_atoms'])}</strong> 条建议，distinct proposed_ids = <strong>{len(g['suggestion_frequency'])}</strong>。当前每个 proposed_id 都只出现一次——但分组到 archetype 下能看出 LLM 觉得哪些 archetype 容量可以扩展。下面每个 archetype 至多展示前 8 条建议。
</p>
{"".join(sugg_blocks)}
</div>"""
    else:
        sugg_section = ""

    return f"""
<p style="font-size:13.5px;color:var(--fg-muted);background:var(--bg-soft);padding:10px 14px;border-radius:6px;border-left:3px solid var(--accent);">
<strong>🔒 v1 freeze（2026-05-11）</strong>：词表演化路径 95 (v0.3) → 115 (v0.6 LLM 审计扩容) → 98 (v0.7 轻量化裁减) → <strong>95 (v1)</strong>。v1 = 95 atoms / 19 archetypes / 16 出货文件。判据：(a) 单 turn / tool-call 运行时点；(b) 作用对象是 agent 自己的 input/plan/args/output；(c) 2025-2026 有现成实现；(d) 粒度适中。下游 §4.6 archetype SKILL.md 包装基于此版本启动。
</p>

<div class="flag-box flag-research">
<h3>🌱 覆盖薄的原子 — 待研发方向（按 phase 分组）</h3>
<p style="font-size:12.5px;color:var(--fg-soft);margin-top:0;">primary 命中 &lt; 5 的原子。在该 phase 下你可能想：① 自研 / 总结具体子能力来填这块空白；② 在 §3 卡片里看它当前命中的少量样本，确认是不是需要把 scope_in 写得更宽；③ 决定是不是要新增更细的兄弟原子。<strong>共 {len(thin_unique)} 个</strong>，按 phase 分组：</p>
{"".join(thin_phase_blocks)}
</div>

<div class="flag-box flag-wp">
<h3>🟠 高 wrong-parent 原子（LLM 反复挂错 archetype 的信号）</h3>
<p style="font-size:12.5px;color:var(--fg-soft);margin-top:0;">候选 <strong>重写 scope_in / scope_out</strong> 或重新审视 archetype 归属。LLM 把 atom_id 反复挂到错的 archetype，暗示该原子的边界 LLM 看不清——可能是 scope 写得不够区分，或这个原子其实跨两个 archetype。这些数据来自 cleanup 之前的原始审计。</p>
<ul>{wp_lis or "<li><em>无</em></li>"}</ul>
</div>

{sugg_section}
"""


def render_dashboard(
    atoms: list[dict[str, Any]],
    by_label: dict[str, dict[str, Any]],
    g: dict[str, Any],
    src_paths: dict[str, str],
) -> str:
    by_phase = group_by_phase(atoms)

    # Phase navigation (anchor links)
    nav_pills = []
    for phase_id, phase_zh, _ in PHASE_ORDER:
        n = len(by_phase.get(phase_id, []))
        nav_pills.append(
            f'<a href="#phase-{phase_id}" class="nav-pill">'
            f'{phase_zh} <span class="nav-pill-num">{n}</span>'
            f'</a>'
        )
    nav_html = '<div class="phase-nav">' + "".join(nav_pills) + '</div>'

    # Per-phase coverage summary table
    summary_rows = []
    for phase_id, phase_zh, _ in PHASE_ORDER:
        phase_atoms = by_phase.get(phase_id, [])
        archetypes = {a["parent_archetype"] for a in phase_atoms}
        total_p = sum(by_label[f"{a['parent_archetype']}/{a['id']}"]["primary_hits"] for a in phase_atoms)
        total_s = sum(by_label[f"{a['parent_archetype']}/{a['id']}"]["secondary_hits"] for a in phase_atoms)
        avg = total_p / max(len(phase_atoms), 1)
        thin_in_phase = sum(
            1 for a in phase_atoms
            if by_label[f"{a['parent_archetype']}/{a['id']}"]["primary_hits"] < 5
        )
        summary_rows.append(
            f'<tr>'
            f'<td><a href="#phase-{phase_id}"><strong>{phase_zh}</strong></a> <code>{phase_id}</code></td>'
            f'<td>{len(phase_atoms)}</td>'
            f'<td>{len(archetypes)}</td>'
            f'<td>{total_p}</td>'
            f'<td>{total_s}</td>'
            f'<td>{avg:.1f}</td>'
            f'<td>{thin_in_phase}{" 🌱" if thin_in_phase else ""}</td>'
            f'</tr>'
        )

    # Phase sections (atom cards grouped phase → archetype → atom)
    phase_sections_html = "".join(
        render_phase_section(
            phase_id, phase_zh,
            by_phase.get(phase_id, []),
            by_label,
        )
        for phase_id, phase_zh, _ in PHASE_ORDER
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>词表 Review Dashboard — v0.3 (按 phase 组织)</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">

<header class="hero">
  <h1>词表 Review Dashboard — v0.3</h1>
  <p class="sub"><strong>95 个原子</strong>（<strong>v1 freeze</strong>）按 agent 执行阶段组织（对齐项目书 §3 Safety Router 查表方式）。每个 atom 卡片左上挂 enforcement_mode badge（🔒 hook / 🧠 skill / ⚡ hybrid），archetype 头挂 packaging badge（pure-hook / mixed-enforce）+ execution_type（🔄 workflow / ☑ checklist / 🔀 mixed）。</p>
  <div class="meta-row">
    <span class="meta-pill">📦 {len(atoms)} atoms · 5 phases</span>
    <span class="meta-pill">📊 {g['total_records']} records audited</span>
    <span class="meta-pill">✅ {g['safety_relevant']} safety-relevant</span>
    <span class="meta-pill">📥 {len(g['suggested_new_atoms'])} new-atom 建议</span>
    <span class="meta-pill">📁 {html.escape(src_paths['cleaned'])}</span>
  </div>
  {nav_html}
</header>

<section>
<h2>1. 全局统计</h2>
{render_global_section(g)}

<h3>每个 phase 的覆盖小结</h3>
<div class="card">
<table class="sugg-table">
  <thead>
    <tr><th>Phase</th><th>原子数</th><th>archetypes</th><th>primary 命中总和</th><th>secondary 命中总和</th><th>avg/atom</th><th>覆盖薄 (&lt;5)</th></tr>
  </thead>
  <tbody>{"".join(summary_rows)}</tbody>
</table>
</div>
</section>

<section>
<h2>2. 95 个原子按 phase 分类的卡片</h2>
<p style="font-size:13.5px;color:var(--fg-soft);">5 个 phase 顺序按项目书 §3 Safety Router 的查表方式排列：input-understanding → planning → tool-invocation → output-generation → cross-cutting。每个 phase 内部按 parent_archetype 子分组（archetype 折叠卡片可点击折叠 / 展开）。每个原子卡片左半边是词表定义（definition / scope_in / scope_out / related），右半边是审计实证信号（命中数 / wrong-parent / confidence / 共现 top 8 / 抽样 records）。</p>

<details class="card legend-card" open style="margin:14px 0 18px;">
<summary style="font-weight:600;font-size:14px;cursor:pointer;">📖 卡片上的 badge 含义（点击折叠）</summary>
<div style="margin-top:12px;font-size:13px;line-height:1.7;">

<p style="margin:0 0 6px;"><strong>① enforcement_mode</strong>（贴在每个 atom 卡片头）—— 这个原子的<strong>强制方式</strong>，是 v0.5/v0.6 包装的"第一刀"。决定该原子最终是落进 hooks/ 还是 SKILL.md。</p>
<table class="sugg-table" style="margin:6px 0 14px;">
<thead><tr><th style="width:130px;">Badge</th><th>含义</th><th>典型实现</th></tr></thead>
<tbody>
<tr><td><span class="enforce-badge enforce-badge--hook">🔒 hook</span></td><td>host 硬强制，agent 无法绕过</td><td>regex / OS config / 签名校验 / 日志写入 / counter 阈值</td></tr>
<tr><td><span class="enforce-badge enforce-badge--skill">🧠 skill</span></td><td>需要 agent LLM 语义判断；通过 SKILL.md 内的 tool 调用</td><td>意图比对、攻击树生成、威胁清单分析</td></tr>
<tr><td><span class="enforce-badge enforce-badge--hybrid">⚡ hybrid</span></td><td>hook 快速通道 + LLM 语义 fallback（hook 抓不住的复杂 case 升级给 LLM）</td><td>带模糊语义的 jailbreak 检测、unsafe-deser 跨语言变种、CI workflow 审计</td></tr>
</tbody>
</table>

<p style="margin:0 0 6px;"><strong>② archetype packaging</strong>（贴在每个 archetype 折叠头）—— 由该 archetype 内部 atoms 的 enforcement_mode 分布决定 archetype 最终怎么<strong>出货</strong>。</p>
<table class="sugg-table" style="margin:6px 0 14px;">
<thead><tr><th style="width:200px;">Badge</th><th>含义</th><th>出货</th></tr></thead>
<tbody>
<tr><td><span class="archetype-packaging archetype-packaging--pure-hook">pure 🔒 hook</span></td><td>所有 atoms 都是 hook 模式</td><td><strong>不出 SKILL.md</strong>，所有 atom 直接进 hooks/ bundle（agent 无需路由调用）</td></tr>
<tr><td><span class="archetype-packaging archetype-packaging--pure-skill">pure 🧠 skill</span></td><td>所有 atoms 都是 skill 模式（v0.6 已无此情形）</td><td>1 个完整 SKILL.md，内部所有 tools 都需要 LLM 推理</td></tr>
<tr><td><span class="archetype-packaging archetype-packaging--mixed-enforce">mix: M 🔒 + N ⚡ + K 🧠</span></td><td>跨多种 enforcement_mode（混合）</td><td>1 个 SKILL.md（含 skill/hybrid tools）+ hook 部分进 hooks/</td></tr>
</tbody>
</table>

<p style="margin:0 0 6px;"><strong>③ execution_type</strong>（贴在每个 archetype 折叠头，仅对 SKILL.md 出货的 archetype 有意义）—— SKILL.md 内部的 <strong>skill/hybrid tools 怎么协调</strong>。是 v0.4 引入的次要维度，告诉 agent "我读这个 SKILL.md 时是按啥模式去依次调内部 tool"。</p>
<table class="sugg-table" style="margin:6px 0 0;">
<thead><tr><th style="width:160px;">Badge</th><th>含义</th><th>典型场景</th></tr></thead>
<tbody>
<tr><td><span class="exec-type exec-type--workflow">🔄 workflow</span></td><td>顺序执行，后步依赖前步</td><td>classify-input-intent-ambiguity（先 classify → 再 ask clarification）、incident-response-handler（halt → snapshot → isolate → notify → recover）</td></tr>
<tr><td><span class="exec-type exec-type--checklist">☑ checklist</span></td><td>并行 fan-out，互相独立</td><td>detect-prompt-injection（5 种 injection 类型独立检测）、validate-tool-argument-safety（8 种参数风险并行扫描）</td></tr>
<tr><td><span class="exec-type exec-type--mixed">🔀 mixed</span></td><td>先并行 detect，后串行 enforce</td><td>scan-input-for-pii-and-secrets（先并行检测 5 种 PII → 后串行 redact）、enforce-rate-and-quota-limits</td></tr>
</tbody>
</table>

<p style="margin:14px 0 0;font-size:12.5px;color:var(--fg-soft);">完整定义见 <a href="../docs/SAFETY_ATOMIC_CAPABILITIES.md">SAFETY_ATOMIC_CAPABILITIES.md</a> §10.1（enforcement_mode）/ §10.2（archetype packaging）/ §10.4（execution_type）。</p>

</div>
</details>

{phase_sections_html}
</section>

</div>
</body>
</html>
"""


# -------------------- main --------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cleaned", type=Path,
                    default=ROOT / "reports" / "llm_audit_classify_2026-05-09_cleaned.jsonl")
    ap.add_argument("--raw", type=Path,
                    default=ROOT / "reports" / "llm_audit_classify_2026-05-09.jsonl")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "reports" / "review_dashboard_v0.3.html")
    args = ap.parse_args(argv)

    if not args.cleaned.exists():
        print(f"ERROR: cleaned file not found: {args.cleaned}\n"
              f"Run scripts/cleanup_audit_jsonl.py first.", file=sys.stderr)
        return 1

    atoms = load_atoms()
    print(f"Loaded vocabulary: {len(atoms)} atoms")

    cleaned = load_jsonl(args.cleaned)
    print(f"Loaded cleaned audit: {len(cleaned)} records")

    raw = load_jsonl(args.raw)
    wp_counts = extract_wrong_parent_counts(raw)
    print(f"Extracted wrong-parent counts from raw: {sum(wp_counts.values())} occurrences across {len(wp_counts)} atom_ids")

    by_label = compute_signals(cleaned, atoms, wp_counts)
    g = compute_global(cleaned, by_label)

    html_text = render_dashboard(
        atoms, by_label, g,
        src_paths={"cleaned": str(args.cleaned.relative_to(ROOT)) if ROOT in args.cleaned.parents else str(args.cleaned)},
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_text, encoding="utf-8")

    print(f"\nWritten: {args.output} ({args.output.stat().st_size:,} bytes)")
    print(f"  Open: file://{args.output}")

    # NOTE: v0.6 删除了 dashboard §2 "信号 dashboard" — wrong-parent / 覆盖薄 / suggested_new_atoms
    # 信号都已经在 v0.6 词表迭代中行动过了（搬家 1 / 加 20 新 / merge 11 / drop 65）。
    # 这里仍保留 CLI 计数仅作存档参考，不再作为 review TODO。
    f = g["auto_flags"]
    print(f"\n=== v0.3-vocab 历史信号（v0.6 已 actioned，仅作存档）===")
    print(f"  zero-hit:           {len(f['zero_hit'])} (含 v0.6 新加的 20 个 0-hit)")
    print(f"  low-hit (<5):       {len(f['low_hit'])}")
    print(f"  wrong-parent:       {len(f['high_wrong_parent'])} (v0.6: search check-rbac-role 已搬家)")
    print(f"  suggested_new:      {len(g['suggested_new_atoms'])} 条 (v0.6: keep 20 / merge 11 / drop 63)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
