"""Opt-in Mistral conversion repair for Responses tools with strict=None."""
from __future__ import annotations

import os
from functools import wraps
from typing import Any

ENV_FLAG = "SABER_MISTRAL_TOOL_STRICT_COMPAT_V10"
PATCH_VERSION = "saber-mistral-tool-strict-v10.0"


def _enabled() -> bool:
    return os.environ.get(ENV_FLAG, "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _omit_unspecified_strict(tool: Any) -> Any:
    if not isinstance(tool, dict):
        return tool
    cleaned = dict(tool)
    nested = cleaned.get("function")
    if isinstance(nested, dict):
        function = dict(nested)
        if function.get("strict") is None:
            function.pop("strict", None)
        cleaned["function"] = function
    elif cleaned.get("strict") is None:
        cleaned.pop("strict", None)
    return cleaned


def install() -> bool:
    """Wrap the Mistral converter; preserve explicit strict=False and True."""
    if not _enabled():
        return False

    from mistral_common.protocol.instruct import converters

    current = converters.convert_openai_tools
    if getattr(current, "_saber_mistral_tool_strict_patch", None) == PATCH_VERSION:
        return False

    @wraps(current)
    def convert_openai_tools_without_null_strict(tools):
        cleaned = [_omit_unspecified_strict(tool) for tool in tools]
        return current(cleaned)

    convert_openai_tools_without_null_strict._saber_mistral_tool_strict_patch = (
        PATCH_VERSION
    )
    # Preserve the role/tool shim activation marker for startup probes.
    if getattr(current, "_saber_mistral_compat", False):
        convert_openai_tools_without_null_strict._saber_mistral_compat = True
    converters.convert_openai_tools = convert_openai_tools_without_null_strict
    return True
