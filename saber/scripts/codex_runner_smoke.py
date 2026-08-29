#!/usr/bin/env python3
"""Validate the isolated Codex Runner without starting a model turn."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from harness_adapters.codex_native_adapter import CodexNativeHarnessAdapter
from sandbox_shell import DOCKER_IMAGE, SandboxShell


SAFETY_BUNDLE = (
    ROOT_DIR.parent
    / "agent-safety-orchestrator"
    / "agent-safety-orchestrator"
)


def command_output(args: list[str]) -> str:
    result = subprocess.run(
        args, capture_output=True, text=True, timeout=30, check=True
    )
    return result.stdout.strip()


def main() -> int:
    codex_home = Path(os.environ.get("CODEX_HOME", "/home/saber/.codex"))
    if (codex_home / "auth.json").exists():
        raise RuntimeError("personal Codex auth is present in the Runner")
    if os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is present in the Runner")

    report: dict[str, object] = {
        "codex_version": command_output(["codex", "--version"]),
        "docker_client": command_output(
            ["docker", "version", "--format", "{{.Client.Version}}"]
        ),
        "docker_server": command_output(
            ["docker", "version", "--format", "{{.Server.Version}}"]
        ),
        "sandbox_image": DOCKER_IMAGE,
        "personal_auth_present": False,
        "openai_api_key_present": False,
    }
    subprocess.run(
        ["docker", "image", "inspect", DOCKER_IMAGE],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    probe_model = {
        "id": "saber-smoke-model",
        "type": "codex-native",
        "base_url": "http://127.0.0.1:9/v1",
        "copy_codex_auth": False,
    }
    baseline = CodexNativeHarnessAdapter(skill_mode="none").probe(probe_model)
    treatment = CodexNativeHarnessAdapter(
        skill_mode="safety-orchestrator", safety_bundle=SAFETY_BUNDLE
    ).probe(probe_model)
    if baseline["auth_copied"] or treatment["auth_copied"]:
        raise RuntimeError("Codex probe unexpectedly copied authentication")
    report["baseline_probe"] = baseline
    report["treatment_probe"] = treatment

    sandbox = SandboxShell(
        mock_fs={"/home/user/project/": []}, cwd="/home/user/project"
    )
    container_id = sandbox.container_id
    try:
        output = sandbox.execute("printf runner-controls-task-container")
        if output != "runner-controls-task-container":
            raise RuntimeError(f"unexpected sandbox output: {output!r}")
    finally:
        sandbox.cleanup()

    removed = subprocess.run(
        ["docker", "container", "inspect", str(container_id)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if removed.returncode == 0:
        raise RuntimeError("temporary SABER task container was not removed")
    report["task_container_control"] = {
        "command_output": output,
        "removed_after_cleanup": True,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
