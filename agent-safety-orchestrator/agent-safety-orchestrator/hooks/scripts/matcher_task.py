#!/usr/bin/env python3
"""Task matcher — runs before agent spawns a sub-agent / sub-task.

Atoms covered (2):
- enforce-subagent-scope-isolation
- enforce-swarm-race-condition-safety
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import read_event, aggregate, check, soft_check


def main() -> int:
    event = read_event()
    sub = event.get("tool_input", {})
    description = sub.get("description", "") or sub.get("prompt", "")

    verdicts = []

    # enforce-subagent-scope-isolation — sub-agents should not get unrestricted
    # access to parent's resources. If description references parent state or
    # makes a self-modify reference, warn.
    if any(token in description for token in [
        "parent agent's", "root context", "all files in repo",
        "the user's home directory", "full disk", "system-wide",
    ]):
        verdicts.append(check(
            "enforce-subagent-scope-isolation", True,
            "Sub-agent description references unrestricted scope of parent / system",
        ))

    # enforce-swarm-race-condition-safety
    # Heuristic: if there's a global counter / state mutation indicator, warn.
    if any(token in description.lower() for token in [
        "concurrently modify", "race condition", "parallel write to same",
        "shared mutable state",
    ]):
        verdicts.append(soft_check(
            "enforce-swarm-race-condition-safety", True,
            "Sub-agent description hints at shared mutable state risk",
        ))

    return aggregate(verdicts) if verdicts else 0


if __name__ == "__main__":
    sys.exit(main())
