#!/usr/bin/env python3
"""Fail-closed startup probe for the SABER v10 Mistral compatibility layer."""
from __future__ import annotations

import os
import sys


def fail(message: str) -> None:
    print("Mistral v10 compatibility activation failed: " + message, file=sys.stderr)
    raise SystemExit(2)


if os.environ.get("SABER_MISTRAL_UTF8_COMPAT_V10") != "1":
    fail("SABER_MISTRAL_UTF8_COMPAT_V10 is not exactly 1")

import vllm.tokenizers.detokenizer_utils as utils
import vllm.v1.engine.detokenizer as engine_detokenizer

expected = "saber-mistral-utf8-v10.0"
if getattr(utils, "_saber_mistral_utf8_patch", None) != expected:
    fail("detokenizer_utils patch marker is absent or has the wrong version")
if getattr(engine_detokenizer, "_saber_mistral_utf8_patch", None) != expected:
    fail("engine detokenizer patch marker is absent or has the wrong version")
if engine_detokenizer.detokenize_incrementally is not utils.detokenize_incrementally:
    fail("engine holds an unpatched incremental detokenizer reference")

if os.environ.get("SABER_MISTRAL_DEVELOPER_ROLE_COMPAT") == "1":
    from mistral_common.protocol.instruct import converters

    if not getattr(converters.convert_openai_messages, "_saber_mistral_compat", False):
        fail("developer-role message compatibility is not active")
    if not getattr(converters.convert_openai_tools, "_saber_mistral_compat", False):
        fail("developer-role tool compatibility is not active")

if os.environ.get("SABER_MISTRAL_TOOL_STRICT_COMPAT_V10") == "1":
    from mistral_common.protocol.instruct import converters

    if getattr(
        converters.convert_openai_tools,
        "_saber_mistral_tool_strict_patch",
        None,
    ) != "saber-mistral-tool-strict-v10.0":
        fail("Responses tool strict compatibility is not active")

print(expected + " active")
