"""Parse evaluator output without mistaking diagnostics or failures for scores."""

import json
import math
from typing import Any


def parse_evaluator_output(stdout: str, stderr: str, exit_code: int) -> dict[str, Any]:
    """Accept a JSON document or a final JSON line, never a failed process."""
    diagnostics = {"stdout": stdout[-4000:], "stderr": stderr[-4000:]}
    if exit_code != 0:
        return {
            "error": f"Evaluator failed with exit code {exit_code}: "
            f"{(stderr or stdout).strip()[-1000:]}",
            "evaluator_diagnostics": diagnostics,
        }
    output = stdout.strip()
    if not output:
        return {
            "error": "Empty output from evaluator",
            "evaluator_diagnostics": diagnostics,
        }
    prefixed = False
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        try:
            parsed = json.loads(output.splitlines()[-1])
            prefixed = True
        except json.JSONDecodeError as exc:
            return {
                "error": f"Evaluator JSON decode error: {exc}",
                "evaluator_diagnostics": diagnostics,
            }
    if not isinstance(parsed, dict):
        return {
            "error": "Evaluator result is not an object",
            "evaluator_diagnostics": diagnostics,
        }
    if not parsed.get("error"):
        score = parsed.get("final_score")
        if (
            not isinstance(score, dict)
            or not all(
                isinstance(score.get(key), (int, float))
                and not isinstance(score[key], bool)
                and math.isfinite(score[key])
                for key in ("result", "total")
            )
            or not 0 <= score["result"] <= score["total"]
            or score["total"] <= 0
        ):
            return {
                "error": "Evaluator result has no valid final_score",
                "evaluator_diagnostics": diagnostics,
            }
    if prefixed or stderr or parsed.get("error"):
        parsed["evaluator_diagnostics"] = diagnostics
    return parsed
