"""Mistral Responses compatibility for the SABER Codex harness.

Enabled only when SABER_MISTRAL_DEVELOPER_ROLE_COMPAT=1. It maps equivalent
Responses message fields to Mistral chat fields and passes only named function
tools to Mistral. Unnamed Codex built-ins are disabled by the SABER host gate
and cannot be represented by Mistral's function-only tool protocol.
"""

from __future__ import annotations

import hashlib
import os
import re
from typing import Any


def _normalize_content(content: Any) -> Any:
    if not isinstance(content, list):
        return content
    return [
        {**chunk, "type": "text"}
        if isinstance(chunk, dict)
        and chunk.get("type") in {"input_text", "output_text"}
        else chunk
        for chunk in content
    ]


def _named_function_tool(tool: Any) -> dict[str, Any] | None:
    if not isinstance(tool, dict):
        return None
    nested = tool.get("function")
    if isinstance(nested, dict):
        function = dict(nested)
        if not function.get("name") and tool.get("name"):
            function["name"] = tool["name"]
        return (
            {"type": "function", "function": function}
            if function.get("name")
            else None
        )
    if tool.get("type") == "function" and tool.get("name"):
        function = {
            key: tool[key]
            for key in ("name", "description", "parameters", "strict")
            if key in tool
        }
        return {"type": "function", "function": function}
    return None



def _mistral_tool_call_id(tool_call_id: Any) -> Any:
    """Map OpenAI Responses call IDs to Mistral 9-character wire format."""
    if not isinstance(tool_call_id, str) or tool_call_id == "null":
        return tool_call_id
    if re.fullmatch(r"[A-Za-z0-9]{9}", tool_call_id):
        return tool_call_id
    return hashlib.sha256(tool_call_id.encode("utf-8")).hexdigest()[:9]


def _normalize_tool_call_ids(message: dict[str, Any]) -> None:
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        normalized_calls = []
        for tool_call in tool_calls:
            if isinstance(tool_call, dict) and "id" in tool_call:
                normalized_call = dict(tool_call)
                normalized_call["id"] = _mistral_tool_call_id(normalized_call["id"])
                normalized_calls.append(normalized_call)
            else:
                normalized_calls.append(tool_call)
        message["tool_calls"] = normalized_calls
    if "tool_call_id" in message:
        message["tool_call_id"] = _mistral_tool_call_id(message["tool_call_id"])

if os.environ.get("SABER_MISTRAL_DEVELOPER_ROLE_COMPAT") == "1":
    from mistral_common.protocol.instruct import converters

    _original_convert_openai_messages = converters.convert_openai_messages
    _original_convert_openai_tools = converters.convert_openai_tools

    def _convert_openai_messages_with_responses_compat(
        messages: list[dict[str, Any]],
    ) -> list[Any]:
        normalized: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                normalized.append(message)
                continue
            normalized_message = dict(message)
            if normalized_message.get("role") == "developer":
                normalized_message["role"] = "system"
            normalized_message["content"] = _normalize_content(
                normalized_message.get("content")
            )
            _normalize_tool_call_ids(normalized_message)
            normalized.append(normalized_message)
        return _original_convert_openai_messages(normalized)

    def _convert_openai_tools_with_responses_compat(
        tools: list[dict[str, Any]],
    ) -> list[Any]:
        normalized = [
            converted
            for tool in tools
            if (converted := _named_function_tool(tool)) is not None
        ]
        return _original_convert_openai_tools(normalized)

    _convert_openai_messages_with_responses_compat._saber_mistral_compat = True  # type: ignore[attr-defined]
    _convert_openai_tools_with_responses_compat._saber_mistral_compat = True  # type: ignore[attr-defined]
    converters.convert_openai_messages = _convert_openai_messages_with_responses_compat
    converters.convert_openai_tools = _convert_openai_tools_with_responses_compat
