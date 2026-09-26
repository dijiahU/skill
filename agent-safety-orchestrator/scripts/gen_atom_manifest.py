#!/usr/bin/env python3
"""Build atoms.json from capability cards and the enforcement-mode registry."""
import argparse
import json
from pathlib import Path

from _atomic_capabilities import load_atoms
from build_review_dashboard import ATOM_ENFORCEMENT_MODE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = Path(__file__).resolve().parents[1] / "agent-safety-orchestrator/atoms.json"
    atoms = [dict(atom, enforcement_mode=ATOM_ENFORCEMENT_MODE[atom["id"]])
             for atom in load_atoms()]
    rendered = json.dumps(atoms, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if destination.read_text(encoding="utf-8") != rendered:
            print("atoms.json is stale; run python3 scripts/gen_atom_manifest.py")
            return 1
        print(f"atoms.json: {len(atoms)} atoms in sync")
    else:
        destination.write_text(rendered, encoding="utf-8")
        print(f"Wrote {len(atoms)} atoms to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
