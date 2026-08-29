#!/usr/bin/env python3
"""Vendor a USER-FACING subset of the atom vocabulary into the plugin.

Reads `docs/SAFETY_ATOMIC_CAPABILITIES.md` (the research source of truth) and
writes a trimmed copy to `agent-safety-orchestrator/docs/` — keeping the
reference sections (field schema, atom cards, counts, packaging, Router
architecture, deployment / fail_policy) and dropping the research front-matter
(changelog, methodology, LLM-output schema, review checklist, v1 todos).

Reproducible so the vendored plugin copy never drifts; re-run whenever the
source vocab doc changes. Preserves the §5 / §10 / §11.3 / §12.2 / §12.3
headers (hence their GitHub anchor slugs) that the shipped SKILL.md / README /
atoms-catalog deep-link to.

Sections are segmented by EXACT header text, NOT by number — §10 embeds a
SKILL.md template whose `## 1. Purpose` … `## 5. Aggregate verdict` headers
restart the numbering, so a numeric split would mis-segment.

CLI:
    python3 scripts/vendor_plugin_docs.py           # regenerate vendored copy
    python3 scripts/vendor_plugin_docs.py --check    # exit nonzero if out of sync
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "docs" / "SAFETY_ATOMIC_CAPABILITIES.md"
DST = REPO / "agent-safety-orchestrator" / "docs" / "SAFETY_ATOMIC_CAPABILITIES.md"

# Real top-level section headers, in document order (verbatim). Boundaries for
# segmentation; embedded SKILL.md-template headers are absent here on purpose.
BOUNDARIES = [
    "## 0. Changelog",
    "## 1. 这份文档干什么用",
    "## 2. 字段 schema（每个原子单元的定义格式）",
    "## 3. 全局设计原则",
    "## 4. 按 Agent 执行阶段组织（Safety Router 查表视图，主审阅入口）",
    "## 5. 按 Archetype 组织（详细原子卡片，对照参考）",
    "## 6. 计数与分布（按阶段 + 按 archetype 双视图）",
    "## 7. LLM 输出 schema（受控词表的使用契约）",
    "## 8. 复审 checklist（请用户审 v0.1 时对照）",
    "## 9. 已知 v1 待办（审定后的执行项）",
    "## 10. 包装标准（v0.5：enforcement_mode + archetype-as-skill 双维度）",
    "## 11. Router 架构定位（meta-skill 路径）",
    "## 12. 部署配置与降级语义（v1.1 新增）",
]

# Sections kept in the user-facing copy (by their exact boundary header).
KEEP = {
    "## 2. 字段 schema（每个原子单元的定义格式）",
    "## 5. 按 Archetype 组织（详细原子卡片，对照参考）",
    "## 6. 计数与分布（按阶段 + 按 archetype 双视图）",
    "## 10. 包装标准（v0.5：enforcement_mode + archetype-as-skill 双维度）",
    "## 11. Router 架构定位（meta-skill 路径）",
    "## 12. 部署配置与降级语义（v1.1 新增）",
}

INTRO = """# Safety Orchestrator — Atom Vocabulary Reference

> **User-facing reference** for the Agent Safety Orchestrator plugin, vendored into this repo.
> Covers the 95-atom field schema (§2), the detailed atom cards (§5), counts (§6),
> the packaging model (§10), Router architecture (§11), and deployment / `fail_policy`
> semantics (§12). The research history (data collection, LLM audit, v0.x changelog)
> is intentionally omitted. Regenerate with `python3 scripts/vendor_plugin_docs.py`.
"""


def build() -> str:
    lines = SRC.read_text().splitlines()
    idx = {}
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s in BOUNDARIES and s not in idx:
            idx[s] = i
    missing = [b for b in BOUNDARIES if b not in idx]
    if missing:
        raise SystemExit(f"vendor_plugin_docs: boundary header(s) not found "
                         f"(source doc structure changed — update BOUNDARIES): {missing}")
    ordered = sorted((idx[b], b) for b in BOUNDARIES)
    out = [INTRO.rstrip(), ""]
    for n, (start, b) in enumerate(ordered):
        end = ordered[n + 1][0] if n + 1 < len(ordered) else len(lines)
        if b in KEEP:
            out.append("\n".join(lines[start:end]).rstrip())
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    content = build()
    if "--check" in sys.argv:
        cur = DST.read_text() if DST.exists() else ""
        if cur != content:
            print("vendor_plugin_docs: plugin copy OUT OF SYNC — "
                  "run `python3 scripts/vendor_plugin_docs.py`")
            return 1
        print("vendor_plugin_docs: plugin copy in sync")
        return 0
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(content)
    print(f"vendor_plugin_docs: wrote {DST.relative_to(REPO)} "
          f"({len(content.splitlines())} lines, kept {len(KEEP)} sections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
