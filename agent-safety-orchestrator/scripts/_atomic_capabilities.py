"""Loader for the atomic safety capability vocabulary.

Single source of truth = `docs/SAFETY_ATOMIC_CAPABILITIES.md` §5 (按 archetype
组织的详细原子卡片). This module parses that section so downstream scripts
(LLM audit, manifest validators, packaging) all see the same vocabulary.

If you update the markdown, this loader picks up the change automatically.

Public API:
    load_atoms() -> list[dict]
        Each dict has keys: id, parent_archetype, phase, attack_surface,
        definition, scope_in, scope_out, signal_phrases, related (list[str]).

    atoms_for_prompt(atoms) -> list[dict]
        Compact form suitable for embedding in an LLM prompt (drops fields
        the LLM does not need to see, keeps disambiguation-critical ones).

    group_by_parent(atoms) -> dict[parent_archetype, list[atom]]
    group_by_phase(atoms) -> dict[phase, list[atom]]

CLI:
    python scripts/_atomic_capabilities.py
        Prints loaded atoms grouped by phase + parent for sanity check.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "SAFETY_ATOMIC_CAPABILITIES.md"

# Match the §5 archetype subsection start (### 5.X `archetype-id` 下属)
_SECTION_START_RE = re.compile(r"^## 5\. ", re.M)
_SECTION_END_RE = re.compile(r"^## 6\. ", re.M)

# Each atom card starts with `#### \`atom-id\`` optionally followed by *(v1: ...)*
_CARD_RE = re.compile(
    r"^#### `(?P<id>[\w-]+)`[^\n]*\n(?P<body>.*?)(?=^#### `|^### |\Z)",
    re.M | re.S,
)

# Field line: `- **field_name**: rest-of-line`
_FIELD_RE = re.compile(r"^- \*\*(?P<field>[\w_]+)\*\*: (?P<value>.+?)$", re.M)

# In the meta line `- **parent**: \`X\` · **phase**: Y · **attack_surface**: Z`
# we have to split on the middle dot separator
_META_DOT_SEP = re.compile(r"\s+·\s+")


def load_atoms(doc_path: Path | None = None) -> list[dict[str, Any]]:
    """Parse §5 atom cards. Returns a list of dicts."""
    path = doc_path or _DOC_PATH
    text = path.read_text(encoding="utf-8")

    m_start = _SECTION_START_RE.search(text)
    m_end = _SECTION_END_RE.search(text)
    if not m_start or not m_end:
        raise RuntimeError(
            f"could not locate §5 / §6 boundaries in {path}; "
            "did the section numbering change?"
        )
    section = text[m_start.end() : m_end.start()]

    atoms: list[dict[str, Any]] = []
    for card_match in _CARD_RE.finditer(section):
        atom_id = card_match.group("id")
        body = card_match.group("body")
        atom = _parse_card_body(atom_id, body)
        atoms.append(atom)

    if not atoms:
        raise RuntimeError(f"parsed 0 atoms from {path} §5 — parser likely broken")
    return atoms


_VALID_PHASES = {
    "input-understanding",
    "planning",
    "tool-invocation",
    "output-generation",
    "cross-cutting",
}


def _normalize_phase(raw: str) -> str:
    """Strip trailing parentheticals (e.g. "cross-cutting (highest priority)" → "cross-cutting").

    The §5 atom cards occasionally annotate the phase with a parenthetical note
    (priority hint, scope reminder). The parenthetical is documentation for the
    human reader; the canonical phase value is the leading token.
    """
    cleaned = re.sub(r"\s*\(.*?\)\s*$", "", raw).strip()
    if cleaned not in _VALID_PHASES:
        # Defensive: log the unrecognized phase to stderr but accept the cleaned value.
        # Loader callers can still validate via _VALID_PHASES if they need strict checking.
        print(
            f"warning: phase '{cleaned}' (from raw '{raw}') not in canonical set "
            f"{sorted(_VALID_PHASES)}",
            file=sys.stderr,
        )
    return cleaned


def _parse_card_body(atom_id: str, body: str) -> dict[str, Any]:
    """Parse the field list under one atom card."""
    atom: dict[str, Any] = {"id": atom_id}

    fields = {m.group("field"): m.group("value").strip() for m in _FIELD_RE.finditer(body)}

    # Meta line under key "parent" actually contains parent + phase + attack_surface,
    # joined by " · ". We split it.
    if "parent" in fields:
        meta = fields.pop("parent")
        # strip the leading backtick wrapper for the parent id, then split on the dot separator
        # The line looks like:  `parent_archetype` · **phase**: phase-name · **attack_surface**: surface...
        parts = _META_DOT_SEP.split(meta)
        # parts[0] should be `parent_id`
        parent_match = re.match(r"`([\w-]+)`", parts[0])
        if parent_match:
            atom["parent_archetype"] = parent_match.group(1)
        for extra in parts[1:]:
            # extra looks like "**phase**: input-understanding" or "**attack_surface**: OWASP LLM01.direct"
            sub = re.match(r"\*\*([\w_]+)\*\*:\s*(.+)", extra)
            if sub:
                key = sub.group(1)
                val = sub.group(2).strip()
                if key == "phase":
                    val = _normalize_phase(val)
                atom[key] = val

    # The rest of fields map directly
    for fname, fval in fields.items():
        atom[fname] = fval

    # Normalize list-shaped fields (signal_phrases, related, scope_in, scope_out)
    # The markdown stores them as comma-separated text. We keep them as strings
    # for prompt embedding (more compact + agent-readable) but also expose a
    # parsed list for `related` since downstream code needs the IDs.
    if "related" in atom:
        atom["related"] = _parse_related_ids(atom["related"])

    return atom


def _parse_related_ids(raw: str) -> list[str]:
    """Extract atom IDs from `related` field, dropping markdown decorations."""
    # raw looks like:  `id1`, `id2` (parent), `id3`
    return re.findall(r"`([\w-]+)`", raw)


# ---------- Helpers for downstream consumers ----------


def atoms_for_prompt(atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact form for embedding in LLM prompt.

    Drops `attack_surface` (informational, not used for classification) and
    converts `related` back to a comma-joined string for prompt brevity.
    """
    out = []
    for a in atoms:
        out.append(
            {
                "id": a["id"],
                "parent": a.get("parent_archetype", ""),
                "phase": a.get("phase", ""),
                "definition": a.get("definition", ""),
                "scope_in": a.get("scope_in", ""),
                "scope_out": a.get("scope_out", ""),
                "signal_phrases": a.get("signal_phrases", ""),
                "related": ", ".join(a.get("related", []) or []),
            }
        )
    return out


def group_by_parent(atoms: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for a in atoms:
        out.setdefault(a.get("parent_archetype", "?"), []).append(a)
    return out


def group_by_phase(atoms: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for a in atoms:
        out.setdefault(a.get("phase", "?"), []).append(a)
    return out


def all_valid_atom_labels(atoms: list[dict[str, Any]]) -> set[str]:
    """Returns the set of valid `<parent_archetype>/<atom_id>` labels.

    Used by the LLM audit script to validate model output.
    """
    return {f"{a['parent_archetype']}/{a['id']}" for a in atoms if a.get("parent_archetype")}


# ---------- CLI ----------


def _main() -> int:
    atoms = load_atoms()
    by_phase = group_by_phase(atoms)
    by_parent = group_by_parent(atoms)

    print(f"Loaded {len(atoms)} atoms from {_DOC_PATH}")
    print(f"  Distinct parent archetypes: {len(by_parent)}")
    print(f"  Distinct phases: {len(by_phase)}")

    print("\nBy phase:")
    for phase in sorted(by_phase):
        print(f"  {phase}: {len(by_phase[phase])}")

    print("\nBy parent archetype:")
    for parent in sorted(by_parent):
        print(f"  {parent}: {len(by_parent[parent])}")

    # Print first atom in full for sanity
    print("\nFirst atom (full record, json):")
    print(json.dumps(atoms[0], indent=2, ensure_ascii=False))

    # Print compact form for prompt
    print(f"\nPrompt-form sample (first 2):")
    print(json.dumps(atoms_for_prompt(atoms[:2]), indent=2, ensure_ascii=False))

    print(f"\nValid label set size: {len(all_valid_atom_labels(atoms))}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
