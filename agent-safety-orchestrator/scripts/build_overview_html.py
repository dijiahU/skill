#!/usr/bin/env python3
"""Build a dashboard-style HTML view of docs/PROJECT_OVERVIEW.md.

Goal: a *designed* read-friendly dashboard, not a 1:1 markdown render.

What it does:
  - Hero banner with the canonical funnel numbers (10223 → 1390 → 1211 → 95).
  - Module-1 pipeline visualization (6 steps with icons, auto-derived from
    the §4.0 progress table in the markdown — so status updates whenever
    the markdown is updated).
  - Each §4.X subsection rendered as a card with a status badge.
  - §4 deep-dive subsections (4.1.x / 4.2.x with detailed tables, Stage 3
    analysis, etc.) wrapped in <details> so they collapse by default.
  - Modules 2 / 3 shown as compact "queue" cards.
  - Next steps + repo layout pinned at the bottom.
  - Self-contained: no external CSS / JS / fonts.

Re-run after editing PROJECT_OVERVIEW.md:
  python scripts/build_overview_html.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown  # type: ignore
from markdown.extensions.toc import slugify_unicode  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "PROJECT_OVERVIEW.md"
DST = ROOT / "docs" / "PROJECT_OVERVIEW.html"


# -------------------- pipeline data extraction --------------------

PIPELINE_LABELS = [
    ("4.1", "数据收集", "10,223 候选"),
    ("4.2", "三层漏斗", "→ 1,390"),
    ("4.3", "词表 v0.3", "95 atoms"),
    ("4.4", "LLM 审计", "$2.51"),
    ("4.5", "词表迭代 freeze", "v1 = 95 atoms"),
    ("4.6", "SKILL.md 包装", "18 files (v1.1)"),
    ("4.7", "Pilot 验证", "Docker isolation"),
]


def extract_pipeline_status(md_text: str) -> list[str]:
    """Read §4.0 progress table → list of status emoji per pipeline step.

    Falls back to 'unknown' if the row isn't found. The progress table is
    expected to look like:
        | 4.X 名称 | ✅ ... | ... |
    """
    statuses: list[str] = []
    for code, _name, _meta in PIPELINE_LABELS:
        # Match the table row whose first cell starts with the step code.
        pattern = re.compile(
            r"^\|\s*(?:\*\*)?" + re.escape(code) + r"[^|]*\|\s*([^|]+)\|",
            re.M,
        )
        m = pattern.search(md_text)
        if not m:
            statuses.append("unknown")
            continue
        cell = m.group(1).strip()
        # The status cell can mention completed sub-steps (✅) while the
        # overall task is still active (🟡). Prefer the row-level active
        # marker so §4.7 is not rendered as complete just because §4.7.1 is.
        if "🟡" in cell:
            statuses.append("active")
        elif "✅" in cell:
            statuses.append("done")
        elif "⚪" in cell:
            statuses.append("todo")
        else:
            statuses.append("unknown")
    return statuses


def render_pipeline(statuses: list[str]) -> str:
    """Render the pipeline as a horizontal step indicator HTML fragment."""
    icons = {"done": "✓", "active": "→", "todo": "·", "unknown": "?"}
    out = ['<ol class="pipeline">']
    for (code, name, meta), st in zip(PIPELINE_LABELS, statuses):
        out.append(
            f'<li class="step step--{st}">'
            f'<div class="step-marker">{icons[st]}</div>'
            f'<div class="step-body">'
            f'<div class="step-code">§{code}</div>'
            f'<div class="step-name">{name}</div>'
            f'<div class="step-meta">{meta}</div>'
            f'</div>'
            f'</li>'
        )
    out.append("</ol>")
    return "\n".join(out)


# -------------------- markdown → HTML --------------------


def md_to_html(md_text: str) -> tuple[str, str]:
    md = markdown.Markdown(
        extensions=[
            "tables",
            "fenced_code",
            "codehilite",
            "toc",
            "sane_lists",
            "attr_list",
        ],
        extension_configs={
            "codehilite": {"css_class": "codehilite", "guess_lang": False},
            "toc": {
                "marker": "",
                "permalink": False,
                "slugify": slugify_unicode,
            },
        },
        output_format="html5",
    )
    body = md.convert(md_text)
    toc = md.toc  # type: ignore[attr-defined]
    return body, toc


# -------------------- post-processing --------------------


def post_process(body: str) -> str:
    """Apply visual enhancements to the rendered markdown body."""

    # 1. Wrap status emojis in colored pills.
    def repl_emoji(match: re.Match) -> str:
        emoji = match.group(0)
        cls = {
            "✅": "badge badge--done",
            "🟡": "badge badge--active",
            "⚪": "badge badge--todo",
            "⛔": "badge badge--blocked",
            "⭐": "badge badge--star",
        }.get(emoji, "")
        if not cls:
            return emoji
        return f'<span class="{cls}">{emoji}</span>'

    body = re.sub(r"[✅🟡⚪⛔⭐]", repl_emoji, body)

    # 2. Wrap §4 sub-section h4 deep-dive blocks (e.g. 4.1.1, 4.2.1) into
    #    collapsible <details> so the cards stay scannable. We detect these
    #    by their h4 anchor IDs starting with 4-1- / 4-2- / 4-3-.
    body = collapse_h4_blocks(body)

    # 3. Tag h3 sections under §4 with a class so we can card-style them.
    body = wrap_section4_h3(body)

    return body


def collapse_h4_blocks(body: str) -> str:
    """Wrap each <h4>…</h4>(content)… block under §4 deep-dives in a <details>.

    This catches per-stage analysis (Stage 2 results, Stage 3 first-run
    analysis, calibration entry) and similar verbose sub-sections without
    requiring a markdown-side change.
    """
    # Match h4 anchors of the form §4.X.Y (id starts with "4XY-" e.g. 411-, 422-)
    h4_pattern = re.compile(
        r'<h4 id="4\d\d-[^"]*">(.+?)</h4>(.*?)(?=<h[1-4][^>]*>|\Z)',
        re.S,
    )

    def replacer(m: re.Match) -> str:
        title_inner = m.group(1)
        content = m.group(2)
        # strip wrapping ws
        content = content.strip()
        title_text = re.sub(r"<[^>]+>", "", title_inner).strip()
        return (
            f'<details class="deep-dive">\n'
            f'<summary><span class="deep-dive-label">展开</span> {title_text}</summary>\n'
            f'{content}\n'
            f'</details>\n'
        )

    return h4_pattern.sub(replacer, body)


def wrap_section4_h3(body: str) -> str:
    """Wrap each <h3>4.X …</h3> + its content into a styled card.

    Each card runs from a §4.X h3 up to (but not including) the next h2 or
    next §4.Y h3. Output:
        <div class="section-card">
          <h3 ... class="section-card-head">...</h3>
          <div class="section-card-body">...</div>
        </div>
    """
    h3_pat = re.compile(
        r'(<h3 id="(4\d-[^"]*)">.+?</h3>)(.*?)(?=<h3 id="4\d-|<h2 |\Z)',
        re.S,
    )

    def replacer(m: re.Match) -> str:
        head_html = m.group(1)
        # inject the section-card-head class
        head_html = head_html.replace(
            '<h3 id="', '<h3 class="section-card-head" id="', 1
        )
        body_html = m.group(3).strip()
        return (
            f'<div class="section-card">\n{head_html}\n'
            f'<div class="section-card-body">\n{body_html}\n</div>\n</div>\n'
        )

    return h3_pat.sub(replacer, body)


# -------------------- CSS --------------------

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
  --accent-strong: #1d4ed8;
  --done: #16a34a;
  --done-soft: #d1fae5;
  --active: #d97706;
  --active-soft: #fef3c7;
  --todo: #94a3b8;
  --todo-soft: #f1f5f9;
  --blocked: #dc2626;
  --star: #ca8a04;
  --shadow: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-strong: 0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.04);
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
  font-size: 16px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}

.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

/* ---------- Hero ---------- */
.hero {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #2563eb 130%);
  color: #f8fafc;
  border-radius: 16px;
  padding: 36px 36px 28px;
  margin-bottom: 28px;
  box-shadow: var(--shadow-strong);
}
.hero__title {
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 4px;
  letter-spacing: -0.01em;
}
.hero__sub {
  margin: 0 0 24px;
  color: #cbd5e1;
  font-size: 15px;
}
.hero__stats {
  display: flex;
  align-items: stretch;
  gap: 4px;
  flex-wrap: wrap;
}
.hero__stat {
  flex: 1 1 0;
  min-width: 130px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.hero__stat--accent {
  background: rgba(96, 165, 250, 0.15);
  border-color: rgba(147, 197, 253, 0.4);
}
.hero__stat-num {
  font-size: 28px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  margin-bottom: 2px;
}
.hero__stat-label {
  font-size: 12px;
  color: #cbd5e1;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 2px;
}
.hero__stat-note {
  font-size: 12px;
  color: #94a3b8;
}
.hero__arrow {
  align-self: center;
  color: #64748b;
  font-size: 18px;
  padding: 0 4px;
  user-select: none;
}
.hero__meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 18px;
  font-size: 13px;
  color: #cbd5e1;
}
.hero__meta-item {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  padding: 4px 12px;
}

/* ---------- Pipeline ---------- */
.pipeline-section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px 28px;
  margin-bottom: 28px;
  box-shadow: var(--shadow);
}
.pipeline-section h2 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 600;
}
.pipeline-section .subtitle {
  margin: 0 0 20px;
  font-size: 13px;
  color: var(--fg-soft);
}
.pipeline {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}
.step {
  position: relative;
  background: var(--bg-soft);
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 14px 12px;
  text-align: center;
  transition: all 0.15s ease;
}
.step--done {
  background: var(--done-soft);
  border-color: var(--done);
}
.step--active {
  background: var(--active-soft);
  border-color: var(--active);
  box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.12);
}
.step--todo {
  background: var(--bg-soft);
  border-color: var(--border);
}
.step-marker {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
}
.step--done .step-marker { background: var(--done); color: white; }
.step--active .step-marker { background: var(--active); color: white; }
.step--todo .step-marker { background: var(--todo); color: white; opacity: 0.5; }
.step-code {
  font-size: 11px;
  color: var(--fg-soft);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.step-name {
  font-weight: 600;
  font-size: 14px;
  margin: 2px 0;
  color: var(--fg);
}
.step-meta {
  font-size: 12px;
  color: var(--fg-soft);
  font-variant-numeric: tabular-nums;
}

/* ---------- Content typography ---------- */
.content {
  background: transparent;
}
.content h1 {
  display: none; /* hero replaces title */
}
.content h2 {
  font-size: 22px;
  font-weight: 700;
  margin: 36px 0 12px;
  color: var(--fg);
  border-bottom: 1px solid var(--border);
  padding-bottom: 10px;
}
.content h3 {
  font-size: 17px;
  font-weight: 600;
  margin: 22px 0 8px;
  color: var(--fg);
}
.section-card {
  margin: 16px 0 24px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-card);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.section-card h3.section-card-head {
  margin: 0;
  padding: 14px 20px;
  background: linear-gradient(0deg, var(--bg-card) 0%, var(--bg-soft) 100%);
  border-bottom: 1px solid var(--border);
  font-size: 16px;
  font-weight: 600;
  color: var(--fg);
}
.section-card .section-card-body {
  padding: 18px 20px 6px;
}
.section-card .section-card-body > *:first-child { margin-top: 0; }
.section-card .section-card-body > *:last-child { margin-bottom: 0; }
.content h4 {
  font-size: 14.5px;
  font-weight: 600;
  margin: 18px 0 6px;
  color: var(--fg-muted);
  text-transform: none;
}
.content p { margin: 0.55em 0 0.75em; }
.content ul, .content ol { padding-left: 1.5em; }
.content li { margin: 0.2em 0; }
.content strong { font-weight: 600; }
.content em { font-style: italic; }
.content a { color: var(--accent); text-decoration: none; }
.content a:hover { text-decoration: underline; color: var(--accent-strong); }

.content blockquote {
  border-left: 3px solid var(--accent);
  background: var(--accent-soft);
  color: var(--fg-muted);
  padding: 8px 16px;
  margin: 1em 0;
  border-radius: 0 6px 6px 0;
  font-size: 14.5px;
}
.content blockquote p { margin: 0.4em 0; }

.content hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 28px 0;
}

/* ---------- Code ---------- */
.content code {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo,
               Consolas, "Liberation Mono", monospace;
  font-size: 0.88em;
  background: #f1f5f9;
  padding: 0.15em 0.4em;
  border-radius: 4px;
  border: 1px solid var(--border-soft);
}
.content pre {
  background: #0f172a;
  color: #e2e8f0;
  padding: 14px 18px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.55;
  margin: 1em 0;
}
.content pre code {
  background: transparent;
  border: none;
  padding: 0;
  color: inherit;
}

/* ---------- Tables ---------- */
.content table {
  border-collapse: collapse;
  margin: 0.8em 0;
  width: 100%;
  font-size: 13.5px;
  display: block;
  overflow-x: auto;
  border: 1px solid var(--border-soft);
  border-radius: 6px;
}
.content thead { background: var(--bg-soft); }
.content th, .content td {
  padding: 8px 12px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--border-soft);
}
.content th { font-weight: 600; color: var(--fg-muted); }
.content tbody tr:last-child td { border-bottom: none; }
.content tbody tr:hover { background: rgba(37, 99, 235, 0.025); }
.content th[align="right"], .content td[align="right"] { text-align: right; font-variant-numeric: tabular-nums; }
.content th[align="center"], .content td[align="center"] { text-align: center; }

/* ---------- Status badges (auto-wrapped) ---------- */
.badge {
  display: inline-block;
  font-size: 0.92em;
  vertical-align: middle;
}
.badge--done { color: var(--done); }
.badge--active { color: var(--active); }
.badge--todo { color: var(--todo); }
.badge--blocked { color: var(--blocked); }
.badge--star { color: var(--star); }

/* ---------- Collapsible deep-dives ---------- */
details.deep-dive {
  background: var(--bg-soft);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  margin: 0.8em 0;
  padding: 10px 14px;
}
details.deep-dive[open] {
  background: var(--bg-card);
  box-shadow: var(--shadow);
}
details.deep-dive summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
  color: var(--fg-muted);
  list-style: none;
  outline: none;
}
details.deep-dive summary::-webkit-details-marker { display: none; }
details.deep-dive summary::before {
  content: "▸";
  display: inline-block;
  margin-right: 8px;
  transition: transform 0.15s ease;
  color: var(--accent);
}
details.deep-dive[open] summary::before { transform: rotate(90deg); }
.deep-dive-label {
  font-size: 11px;
  background: var(--accent);
  color: white;
  padding: 2px 6px;
  border-radius: 3px;
  margin-right: 6px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 600;
}

/* ---------- Mobile ---------- */
@media (max-width: 820px) {
  .page { padding: 16px 12px 56px; }
  .hero { padding: 24px 20px; }
  .hero__title { font-size: 22px; }
  .hero__stat { min-width: 110px; }
  .hero__stat-num { font-size: 22px; }
  .pipeline { grid-template-columns: repeat(2, 1fr); }
  .content h2 { font-size: 19px; }
}

/* Pygments syntax highlighting (dark theme inside <pre>) */
.codehilite .c, .codehilite .ch, .codehilite .cm, .codehilite .cp,
.codehilite .cpf, .codehilite .c1, .codehilite .cs { color: #94a3b8; font-style: italic }
.codehilite .k, .codehilite .kc, .codehilite .kd, .codehilite .kn,
.codehilite .kp, .codehilite .kr, .codehilite .kt { color: #f472b6 }
.codehilite .o, .codehilite .ow { color: #fbbf24 }
.codehilite .gd { color: #fca5a5; }
.codehilite .gi { color: #86efac; }
.codehilite .nb, .codehilite .nc, .codehilite .nf, .codehilite .nn,
.codehilite .ne { color: #c4b5fd }
.codehilite .na, .codehilite .nt { color: #86efac }
.codehilite .nv, .codehilite .vc, .codehilite .vg, .codehilite .vi,
.codehilite .vm { color: #fdba74 }
.codehilite .m, .codehilite .mf, .codehilite .mh, .codehilite .mi,
.codehilite .mo { color: #fbbf24 }
.codehilite .s, .codehilite .sa, .codehilite .sb, .codehilite .sc,
.codehilite .dl, .codehilite .sd, .codehilite .s2, .codehilite .se,
.codehilite .sh, .codehilite .si, .codehilite .sx, .codehilite .sr,
.codehilite .s1, .codehilite .ss { color: #93c5fd }
"""


# -------------------- HTML composition --------------------


def hero_html() -> str:
    """Hero banner. Numbers come from the §4.4 audit summary in the markdown,
    but they're stable enough to hardcode here. Update if data changes."""
    return r"""
<header class="hero">
  <h1 class="hero__title">Safety Orchestrator Skill</h1>
  <p class="hero__sub">统一的智能体安全调度层 — Atomic Safety Skill 库 + Safety Sentinel + Safety Router</p>
  <div class="hero__stats">
    <div class="hero__stat">
      <div class="hero__stat-num">10,223</div>
      <div class="hero__stat-label">原始候选</div>
      <div class="hero__stat-note">5 类来源</div>
    </div>
    <div class="hero__arrow">→</div>
    <div class="hero__stat">
      <div class="hero__stat-num">1,390</div>
      <div class="hero__stat-label">三层漏斗后</div>
      <div class="hero__stat-note">cut 86.4%</div>
    </div>
    <div class="hero__arrow">→</div>
    <div class="hero__stat">
      <div class="hero__stat-num">1,211</div>
      <div class="hero__stat-label">LLM 判定 safety-relevant</div>
      <div class="hero__stat-note">87% pass-rate</div>
    </div>
    <div class="hero__arrow">→</div>
    <div class="hero__stat hero__stat--accent">
      <div class="hero__stat-num">95</div>
      <div class="hero__stat-label">原子能力 v0.3</div>
      <div class="hero__stat-note">5 phases / 20 archetypes</div>
    </div>
  </div>
  <div class="hero__meta">
    <span class="hero__meta-item">📅 数据截止 2026-05-09</span>
    <span class="hero__meta-item">💰 LLM 审计成本 $2.51</span>
    <span class="hero__meta-item">⚡ DeepSeek cache 命中 92.8%</span>
    <span class="hero__meta-item">🎯 当前焦点：§4.5 词表迭代</span>
  </div>
</header>
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="page">
{hero}
<section class="pipeline-section">
  <h2>模块 1 实施流水线</h2>
  <p class="subtitle">每一步的状态自动从 markdown §4.0 进度表读取；点击各步可跳转到详细章节</p>
  {pipeline}
</section>
<article class="content">
{body}
</article>
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    if not SRC.exists():
        print(f"ERROR: source not found: {SRC}", file=sys.stderr)
        return 1

    md_text = SRC.read_text(encoding="utf-8")
    body, _toc = md_to_html(md_text)
    body = post_process(body)

    statuses = extract_pipeline_status(md_text)
    pipeline = render_pipeline(statuses)

    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title = (
        re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
        if title_match
        else "Project Overview"
    )

    html = HTML_TEMPLATE.format(
        title=title,
        css=CSS,
        hero=hero_html(),
        pipeline=pipeline,
        body=body,
    )
    DST.write_text(html, encoding="utf-8")

    print(f"Built dashboard: {DST}")
    print(f"  Size: {len(html):,} bytes")
    print(f"  Pipeline statuses: {dict(zip([s[1] for s in PIPELINE_LABELS], statuses))}")
    print()
    print("Open in browser:")
    print(f"  file://{DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
