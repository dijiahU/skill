#!/usr/bin/env python3
"""CPU-only real Responses constructor regression for Mistral strict=None."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from openai.types.responses import FunctionTool
from vllm.entrypoints.openai.responses.utils import construct_tool_dicts
from mistral_common.protocol.instruct import converters


def make_tool(strict):
    return FunctionTool(
        type="function",
        name="saber_bash",
        description="run",
        parameters={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
        strict=strict,
    )


raw_none = construct_tool_dicts([make_tool(None)], "auto")
baseline_error = None
try:
    converters.convert_openai_tools(raw_none)
except Exception as exc:
    baseline_error = {
        "type": type(exc).__name__,
        "message": str(exc),
    }

os.environ["SABER_MISTRAL_TOOL_STRICT_COMPAT_V10"] = "1"
from mistral_tool_strict_compat import (
    PATCH_VERSION,
    _omit_unspecified_strict,
    install,
)

installed_first = install()
installed_second = install()
cases = {}
for strict in (None, False, True):
    name = "none" if strict is None else str(strict).lower()
    tool_dicts = construct_tool_dicts([make_tool(strict)], "auto")
    cleaned = [_omit_unspecified_strict(tool) for tool in tool_dicts]
    converted = converters.convert_openai_tools(tool_dicts)
    nested = tool_dicts[0]["function"]
    cleaned_nested = cleaned[0]["function"]
    converted_strict = getattr(converted[0].function, "strict", None)
    cases[name] = {
        "constructor_nested_strict_present": "strict" in nested,
        "constructor_nested_strict": nested.get("strict"),
        "cleaned_nested_strict_present": "strict" in cleaned_nested,
        "cleaned_nested_strict": cleaned_nested.get("strict"),
        "converted_strict": converted_strict,
        "conversion_succeeded": True,
    }

checks = {
    "baseline_reproduces_validation_error": (
        baseline_error is not None
        and baseline_error["type"] == "ValidationError"
        and "strict" in baseline_error["message"]
    ),
    "patch_installs_idempotently": installed_first and not installed_second,
    "none_is_omitted": (
        cases["none"]["constructor_nested_strict_present"]
        and cases["none"]["constructor_nested_strict"] is None
        and not cases["none"]["cleaned_nested_strict_present"]
    ),
    "false_is_preserved": (
        cases["false"]["cleaned_nested_strict_present"]
        and cases["false"]["cleaned_nested_strict"] is False
        and cases["false"]["converted_strict"] is False
    ),
    "true_is_preserved": (
        cases["true"]["cleaned_nested_strict_present"]
        and cases["true"]["cleaned_nested_strict"] is True
        and cases["true"]["converted_strict"] is True
    ),
}
result = {
    "patch_version": PATCH_VERSION,
    "baseline_construct_tool_dicts": raw_none,
    "baseline_error": baseline_error,
    "cases": cases,
    "checks": checks,
    "passed": all(checks.values()),
}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["passed"] else 1)
