"""Skills image selection must reject missing, stale, or disabled adapters."""

import json
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from benchmarks.openagentsafety.safety_orchestrator import (
    HOOK_COMPAT_LABEL,
    hook_adapter_digest,
    select_safety_orchestrator_image,
)


@pytest.mark.parametrize("valid_hash", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_image_requires_current_code_and_opt_in(
    monkeypatch: pytest.MonkeyPatch, valid_hash: bool, enabled: bool
) -> None:
    monkeypatch.delenv("OPENAGENTSAFETY_SKILLS_IMAGE", raising=False)
    config = {
        "Labels": {HOOK_COMPAT_LABEL: hook_adapter_digest() if valid_hash else "old"},
        "Env": ["OPENHANDS_SAFETY_ORCHESTRATOR_COMPAT=1"] if enabled else [],
    }
    with patch(
        "benchmarks.openagentsafety.safety_orchestrator.subprocess.run",
        return_value=CompletedProcess([], 0, json.dumps([{"Config": config}])),
    ) as run:
        if valid_hash and enabled:
            assert (
                select_safety_orchestrator_image("base:tag") == "base:tag-oas-hooks-v1"
            )
        else:
            with pytest.raises(RuntimeError, match="missing/stale"):
                select_safety_orchestrator_image("base:tag")
        assert run.call_args.args[0] == [
            "docker",
            "image",
            "inspect",
            "base:tag-oas-hooks-v1",
        ]


def test_explicit_missing_image_never_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAGENTSAFETY_SKILLS_IMAGE", "skills:missing")
    with patch(
        "benchmarks.openagentsafety.safety_orchestrator.subprocess.run",
        return_value=CompletedProcess([], 1, ""),
    ) as run:
        with pytest.raises(RuntimeError, match="skills:missing"):
            select_safety_orchestrator_image("base:tag")
        assert run.call_args.args[0][-1] == "skills:missing"
