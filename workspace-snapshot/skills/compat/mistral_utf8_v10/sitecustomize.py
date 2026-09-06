"""SABER v10 Mistral service compatibility entry point."""
from __future__ import annotations

import os
import runpy
from pathlib import Path

_TRUE = {"1", "true", "yes", "on"}
if os.environ.get("SABER_MISTRAL_DEVELOPER_ROLE_COMPAT", "").strip().lower() in _TRUE:
    old_sitecustomize = (
        Path(__file__).resolve().parent.parent
        / "mistral_developer_role"
        / "sitecustomize.py"
    )
    if not old_sitecustomize.is_file():
        raise FileNotFoundError(
            "SABER_MISTRAL_DEVELOPER_ROLE_COMPAT=1 but compatibility shim is missing: "
            + str(old_sitecustomize)
        )
    runpy.run_path(str(old_sitecustomize), run_name="_saber_mistral_developer_role")

if os.environ.get("SABER_MISTRAL_UTF8_COMPAT_V10", "").strip().lower() in _TRUE:
    from mistral_utf8_compat import install

    install()

if os.environ.get("SABER_MISTRAL_TOOL_STRICT_COMPAT_V10", "").strip().lower() in _TRUE:
    from mistral_tool_strict_compat import install as install_tool_strict_compat

    install_tool_strict_compat()
