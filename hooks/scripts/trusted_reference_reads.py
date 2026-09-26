"""Verify exact, host-pinned OpenHands safety-reference observations.

The manifest is supplied by the host in the hook command, never by tool input.
Only full file_editor views of canonical bundle paths are supported. Unknown
formats, partial reads, terminal output and modified content stay untrusted.
"""

import hashlib
import json
import os
import re


MANIFEST_ENV = "SAFETY_ORCH_TRUSTED_REFERENCE_VIEWS_JSON"
REFERENCE_PATH = re.compile(
    r"/opt/safety-orchestrator/skills/safety-router-skill/"
    r"references/archetypes/[a-z0-9][a-z0-9-]*\.md"
)


def is_trusted_reference_view(event: dict) -> bool:
    """Trust exact pinned output, not a path, caller-supplied flag or filename."""
    # lib_common normalizes OpenHands file_editor to the Claude-style Edit name.
    if event.get("tool_name") not in {"file_editor", "Edit"}:
        return False
    action = event.get("tool_input")
    response = event.get("tool_response")
    if not isinstance(action, dict) or not isinstance(response, dict):
        return False
    path = action.get("path")
    if not isinstance(path, str) or not REFERENCE_PATH.fullmatch(path):
        return False
    if action.get("command") != "view" or action.get("view_range"):
        return False
    if (
        response.get("kind") != "FileEditorObservation"
        or response.get("command") != "view"
        or response.get("path") != path
        or response.get("is_error") is not False
        or response.get("old_content") is not None
        or response.get("new_content") is not None
    ):
        return False
    content = response.get("content")
    if not isinstance(content, list) or len(content) != 1:
        return False
    block = content[0]
    if not isinstance(block, dict) or block.get("type") != "text":
        return False
    text = block.get("text")
    if not isinstance(text, str):
        return False
    try:
        manifest = json.loads(os.environ.get(MANIFEST_ENV, "{}"))
    except (ValueError, TypeError):
        return False
    if not isinstance(manifest, dict):
        return False
    expected = manifest.get(path)
    return (
        isinstance(expected, str)
        and re.fullmatch(r"[0-9a-f]{64}", expected) is not None
        and hashlib.sha256(text.encode("utf-8")).hexdigest() == expected
    )
