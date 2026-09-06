#!/usr/bin/env python3
"""Validate that a SABER treatment smoke used the router and runtime hooks."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    result_path = Path(sys.argv[1])
    result = json.loads(result_path.read_text(encoding="utf-8"))
    meta = result.get("harness_meta") or {}

    assert result.get("error") is None, result.get("error")
    assert meta.get("condition") == "safety-orchestrator", meta
    assert "safety-router-skill" in meta.get("skills", []), meta.get("skills")
    assert meta.get("router_preloaded") is True, meta
    assert not meta.get("archetype_references_preloaded"), meta
    assert meta.get("manual_hook_runs", 0) > 0, meta
    assert meta.get("hooks_listed") is True, meta

    print(
        json.dumps(
            {
                "task": result.get("id"),
                "condition": meta.get("condition"),
                "manual_hook_runs": meta.get("manual_hook_runs"),
                "support_tool_calls": meta.get("support_tool_calls"),
                "references_preloaded": bool(
                    meta.get("archetype_references_preloaded")
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
