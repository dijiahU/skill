#!/usr/bin/env python3
"""Generate atom catalog for the Safety Orchestrator Router skill.

Reads `agent-safety-orchestrator/atoms.json` (the 95-atom dataset built by
`_atomic_capabilities.load_atoms()` joined with `ATOM_ENFORCEMENT_MODE`)
and writes two derived views in the progressive-disclosure tier:

  1. **Router §7 (abridged)** — phase × mode count matrix + pointer.
     Path: `agent-safety-orchestrator/skills/safety-router-skill/SKILL.md`
     Eagerly loaded at session start.

  2. **Full atom catalog (on demand)** — complete 95-atom table.
     Path: `agent-safety-orchestrator/skills/safety-router-skill/references/atoms-catalog.md`
     Loaded by the agent only when it fetches the reference.

Idempotent — re-run any time atoms.json changes; §7 is replaced in place.

CLI:
    python3 scripts/gen_router_atom_catalog.py           # regenerate both files
    python3 scripts/gen_router_atom_catalog.py --check   # exit non-zero if out of sync
"""
import argparse
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "agent-safety-orchestrator"
ROUTER = BUNDLE / "skills" / "safety-router-skill" / "SKILL.md"
CATALOG = BUNDLE / "skills" / "safety-router-skill" / "references" / "atoms-catalog.md"
ATOMS_JSON = BUNDLE / "atoms.json"

PHASE_ORDER = ['input-understanding', 'planning', 'tool-invocation', 'output-generation', 'cross-cutting']
MODE_BADGE = {"hook": "🔒 hook", "hybrid": "⚡ hybrid", "skill": "🧠 skill"}


def _sort_key(a):
    return (PHASE_ORDER.index(a.get('phase', '?')) if a.get('phase') in PHASE_ORDER else 99,
            a.get('parent_archetype', ''), a['id'])


def _normalize_fp(raw: str) -> str:
    m = re.match(r'(fail-(?:open-warn|soft-block|closed))', (raw or '').strip())
    return f"`{m.group(1)}`" if m else "—"


def _normalize_rn(raw: str) -> str:
    r = (raw or '').strip().lower()
    if r.startswith('true'):  return "✅"
    if r.startswith('false'): return "❌"
    return "—"


def render_phase_mode_matrix(atoms):
    """Phase × mode count matrix for Router §7."""
    bucket = defaultdict(Counter)
    for a in atoms:
        bucket[a.get('phase', '?')][a['enforcement_mode']] += 1
    lines = ["| Phase \\ Mode | 🔒 hook | ⚡ hybrid | 🧠 skill | total |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for ph in PHASE_ORDER:
        c = bucket[ph]
        total = sum(c.values())
        lines.append(f"| `{ph}` | {c['hook']} | {c['hybrid']} | {c['skill']} | **{total}** |")
    totals = Counter(a['enforcement_mode'] for a in atoms)
    lines.append(f"| **total** | **{totals['hook']}** | **{totals['hybrid']}** | **{totals['skill']}** | **{sum(totals.values())}** |")
    return "\n".join(lines)


def render_full_table(atoms):
    rows = ["| atom_id | parent archetype | phase | mode | fail_policy | requires_network |",
            "| --- | --- | --- | --- | --- | --- |"]
    for a in sorted(atoms, key=_sort_key):
        rows.append(
            f"| `{a['id']}` | `{a['parent_archetype']}` | {a.get('phase','?')} | "
            f"{MODE_BADGE.get(a['enforcement_mode'], a['enforcement_mode'])} | "
            f"{_normalize_fp(a.get('fail_policy',''))} | {_normalize_rn(a.get('requires_network',''))} |"
        )
    return "\n".join(rows)


def build_router_section(atoms):
    n_total = len(atoms)
    n_arch = len({a['parent_archetype'] for a in atoms})
    n_phase = len({a.get('phase', '?') for a in atoms})
    counts = Counter(a['enforcement_mode'] for a in atoms)
    hook_network_ids = [a['id'] for a in atoms
                        if (a.get('requires_network') or '').strip().lower().startswith('true')
                        or (a.get('requires_api_key') or '').strip()
                        or a['id'] in {'check-package-typosquat','check-dependency-confusion',
                                       'verify-skill-signature','verify-tool-publisher-identity'}]
    return f"""## 7. Atom coverage (summary)

**{n_total} atoms / {n_arch} archetypes / {n_phase} phases.** Enforcement breakdown:

{render_phase_mode_matrix(atoms)}

For the full per-atom table (atom_id × archetype × phase × mode × fail_policy × requires_network), load [`references/atoms-catalog.md`](references/atoms-catalog.md) — it is loaded on demand, not at session start. You only need it when you require atom-level granularity (debugging, audit, fine-grained degraded-atom handling).

The {len(hook_network_ids)} hook-network atoms carrying v1.1 deployment metadata (`requires_network` + `fail_policy`): {', '.join(f'`{aid}`' for aid in hook_network_ids)}. fail_policy values per §3.4.
"""


def build_catalog_doc(atoms):
    counts = Counter(a['enforcement_mode'] for a in atoms)
    n_total = len(atoms)
    return f"""# Safety Orchestrator — Full atom catalog

> **Generated from `agent-safety-orchestrator/atoms.json`** by `scripts/gen_router_atom_catalog.py`. Regenerate whenever the vocabulary changes:
> ```bash
> python3 scripts/gen_router_atom_catalog.py
> ```
>
> **This is an on-demand reference file** — loaded by the agent only when explicitly fetched from Router §7. It is not part of session-start context.

**Coverage**: {n_total} atoms / {len({a['parent_archetype'] for a in atoms})} archetypes / {len({a.get('phase','?') for a in atoms})} phases / {counts['hook']} hook + {counts['hybrid']} hybrid + {counts['skill']} skill. fail_policy and requires_network columns reflect v1.1 deployment metadata.

Atoms are sorted by phase → parent archetype → atom_id (matches Router §3.2 routing order).

{render_full_table(atoms)}

## How to use this catalog

- **Agents routed by Router** generally do NOT need this file — Router's §3.2 phase routing table is sufficient for everyday safety decisions.
- **Debug an unexpected verdict**: find the atom in the table → see which archetype owns it → open `references/archetypes/<archetype>.md` §4 for the atom's definition + implementation notes (these archetype docs sit beside this catalog under the Router skill; they are not top-level skills).
- **Audit which atoms are degraded**: cross-reference the `requires_network: ✅` rows against `~/.safety-orch/atom-status.json` (written by `helpers/health_status.py`).
- **Plan a fail_policy override**: `fail-closed` atoms cannot be overridden. `fail-soft-block` atoms require user `--accept-degraded` flag. `fail-open-warn` atoms log + proceed silently in the user-facing flow.

## Cross-references

- Vocabulary source of truth: [`docs/SAFETY_ATOMIC_CAPABILITIES.md`](../../../docs/SAFETY_ATOMIC_CAPABILITIES.md) §5
- enforcement_mode: each atom in [`atoms.json`](../../../atoms.json) carries an `enforcement_mode` field
- Deployment metadata (`requires_network` / `fail_policy`): SAFETY_ATOMIC_CAPABILITIES.md §12.2-12.3
- v1.1 changelog: SAFETY_ATOMIC_CAPABILITIES.md §0
"""


def _replace_section(text: str, new_section: str) -> tuple[str, str]:
    """Replace §7 block in Router SKILL.md. Returns (new_text, action)."""
    pattern = re.compile(r"\n## 7\..*?(?=\n## |\Z)", re.S)
    if pattern.search(text):
        return pattern.sub("\n" + new_section, text), "replaced"
    return text.rstrip() + "\n\n" + new_section, "appended"


def write(args) -> int:
    atoms = json.loads(ATOMS_JSON.read_text())
    new_router_section = build_router_section(atoms)
    new_catalog = build_catalog_doc(atoms)

    cur_router = ROUTER.read_text()
    new_router, action = _replace_section(cur_router, new_router_section)
    ROUTER.write_text(new_router)

    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(new_catalog)

    print(f"  Router §7: {action} → {len(new_router.splitlines())} lines total")
    print(f"  Catalog:   {CATALOG.relative_to(REPO)} → {len(new_catalog.splitlines())} lines")
    return 0


def check(args) -> int:
    """Exit non-zero (with diff) if Router §7 or catalog is out of sync with atoms.json."""
    atoms = json.loads(ATOMS_JSON.read_text())
    expected_router_section = build_router_section(atoms)
    expected_catalog = build_catalog_doc(atoms)
    cur_router = ROUTER.read_text()
    new_router, _ = _replace_section(cur_router, expected_router_section)
    cur_catalog = CATALOG.read_text() if CATALOG.exists() else ""

    drift = False
    if cur_router != new_router:
        drift = True
        print("DRIFT: Router §7 is out of sync with atoms.json", file=sys.stderr)
        for line in difflib.unified_diff(cur_router.splitlines(), new_router.splitlines(),
                                          lineterm="", n=2, fromfile="current", tofile="expected"):
            print(line, file=sys.stderr)
    if cur_catalog != expected_catalog:
        drift = True
        print("DRIFT: atoms-catalog.md is out of sync with atoms.json", file=sys.stderr)

    if drift:
        print("\nRun `python3 scripts/gen_router_atom_catalog.py` to fix.", file=sys.stderr)
        return 1
    print("  Router §7 + catalog are in sync with atoms.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if Router §7 or catalog is out of sync (CI mode)")
    args = parser.parse_args()
    return check(args) if args.check else write(args)


if __name__ == "__main__":
    sys.exit(main())
