"""Tests for the OpenAgentSafety Safety Orchestrator adapter."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from benchmarks.openagentsafety.run_infer import (
    _configure_npc_environment,
    _resolve_service_host_address,
    _workspace_forward_env,
    setup_host_mapping,
)
from benchmarks.openagentsafety.safety_orchestrator import (
    BUNDLE_CONTAINER_ROOT,
    bundle_volume,
    collect_archetype_reference_reads,
    load_openhands_hook_config,
    translate_to_docker_host,
)


def test_workspace_forward_env_isolates_agent_state(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("OPENAGENTSAFETY_AGENT_STATE_DIR", raising=False)
    for name in (
        "OH_PERSISTENCE_DIR",
        "OH_CONVERSATIONS_PATH",
        "OH_BASH_EVENTS_DIR",
    ):
        monkeypatch.delenv(name, raising=False)

    forwarded = _workspace_forward_env(["LMNR_SPAN_CONTEXT", "NPC_API_KEY"])

    assert forwarded == [
        "LMNR_SPAN_CONTEXT",
        "NPC_API_KEY",
        "OH_PERSISTENCE_DIR",
        "OH_CONVERSATIONS_PATH",
        "OH_BASH_EVENTS_DIR",
    ]
    assert os.environ["OH_PERSISTENCE_DIR"] == "/openhands-state/persistence"
    assert os.environ["OH_CONVERSATIONS_PATH"] == ("/openhands-state/conversations")
    assert os.environ["OH_BASH_EVENTS_DIR"] == "/openhands-state/bash_events"


def test_workspace_forward_env_rejects_state_under_task_root(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OPENAGENTSAFETY_AGENT_STATE_DIR", "/workspace/.openhands")

    with pytest.raises(ValueError, match="outside /workspace"):
        _workspace_forward_env([])


def test_configure_npc_environment_reuses_evaluation_llm(
    monkeypatch: pytest.MonkeyPatch,
):
    for name in ("NPC_API_KEY", "NPC_BASE_URL", "NPC_MODEL"):
        monkeypatch.delenv(name, raising=False)
    llm = SimpleNamespace(
        api_key=SecretStr("evaluation-secret"),
        base_url="https://api.deepseek.com",
        model="openai/deepseek-v4-pro",
    )

    _configure_npc_environment(llm)

    assert os.environ["NPC_API_KEY"] == "evaluation-secret"
    assert os.environ["NPC_BASE_URL"] == "https://api.deepseek.com"
    assert os.environ["NPC_MODEL"] == "deepseek-v4-pro"


def test_configure_npc_environment_preserves_explicit_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("NPC_API_KEY", "dedicated-secret")
    monkeypatch.setenv("NPC_BASE_URL", "https://npc.example/v1")
    monkeypatch.setenv("NPC_MODEL", "npc-model")
    llm = SimpleNamespace(
        api_key=SecretStr("evaluation-secret"),
        base_url="https://eval.example/v1",
        model="openai/eval-model",
    )

    _configure_npc_environment(llm)

    assert os.environ["NPC_API_KEY"] == "dedicated-secret"
    assert os.environ["NPC_BASE_URL"] == "https://npc.example/v1"
    assert os.environ["NPC_MODEL"] == "npc-model"


def test_configure_npc_environment_fails_without_any_key(
    monkeypatch: pytest.MonkeyPatch,
):
    for name in ("NPC_API_KEY", "NPC_BASE_URL", "NPC_MODEL"):
        monkeypatch.delenv(name, raising=False)
    llm = SimpleNamespace(
        api_key=None,
        base_url="https://eval.example/v1",
        model="openai/eval-model",
    )

    with pytest.raises(RuntimeError, match="evaluation LLM has no API key"):
        _configure_npc_environment(llm)


def test_resolve_service_host_address_uses_docker_bridge(monkeypatch):
    monkeypatch.delenv("OPENAGENTSAFETY_SERVICE_HOST_ADDR", raising=False)
    monkeypatch.setattr(
        "benchmarks.openagentsafety.run_infer.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="172.21.1.1\n"),
    )

    assert _resolve_service_host_address() == "172.21.1.1"


def test_resolve_service_host_address_prefers_explicit_setting(monkeypatch):
    monkeypatch.setenv("OPENAGENTSAFETY_SERVICE_HOST_ADDR", "192.0.2.10")
    monkeypatch.setattr(
        "benchmarks.openagentsafety.run_infer.subprocess.run",
        lambda *args, **kwargs: pytest.fail("Docker discovery should not run"),
    )

    assert _resolve_service_host_address() == "192.0.2.10"


def test_setup_host_mapping_uses_local_forwarder_address(monkeypatch):
    commands: list[str] = []

    class Workspace:
        def execute_command(self, command: str, timeout: int):
            commands.append(command)
            return SimpleNamespace(
                stdout="127.0.0.1 the-agent-company.com\n", exit_code=0, stderr=""
            )

    monkeypatch.setattr(
        "benchmarks.openagentsafety.run_infer._resolve_service_host_address",
        lambda: "172.21.1.1",
    )

    setup_host_mapping(Workspace())

    assert commands[0] == ("echo '127.0.0.1 the-agent-company.com' >> /etc/hosts")


def test_translate_to_docker_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pod_root = tmp_path / "pod"
    bundle = pod_root / "projects" / "bundle"
    bundle.mkdir(parents=True)
    monkeypatch.setenv("POD_USER_ROOT", str(pod_root))
    monkeypatch.setenv("HOST_USER_ROOT", "/host/user")

    assert translate_to_docker_host(bundle) == Path("/host/user/projects/bundle")
    assert bundle_volume(bundle) == (
        f"/host/user/projects/bundle:{BUNDLE_CONTAINER_ROOT}:ro"
    )


def test_translate_rejects_path_outside_pod_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    pod_root = tmp_path / "pod"
    outside = tmp_path / "outside"
    pod_root.mkdir()
    outside.mkdir()
    monkeypatch.setenv("POD_USER_ROOT", str(pod_root))
    monkeypatch.setenv("HOST_USER_ROOT", "/host/user")

    with pytest.raises(ValueError, match="outside POD_USER_ROOT"):
        translate_to_docker_host(outside)


def test_hook_config_rewrites_commands_and_matchers(tmp_path: Path):
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "hooks.json").write_text(
        """{
          "_comment": "manifest metadata is ignored by the adapter",
          "hooks": {
            "PreToolUse": [
              {"matcher": "Bash", "hooks": [
                {"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/x.py"}
              ]},
              {"matcher": "Write|Edit|MultiEdit", "hooks": [
                {"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/y.py"}
              ]}
            ]
          }
        }"""
    )

    config = load_openhands_hook_config(tmp_path)

    assert [matcher.matcher for matcher in config.pre_tool_use] == [
        "terminal",
        "file_editor|apply_patch",
    ]
    commands = [
        hook.command for matcher in config.pre_tool_use for hook in matcher.hooks
    ]
    assert all(BUNDLE_CONTAINER_ROOT in command for command in commands)
    assert all("CLAUDE_PLUGIN_ROOT" not in command for command in commands)


def test_collect_archetype_reference_reads_only_counts_tool_actions():
    history = [
        {
            "tool_name": "invoke_skill",
            "action": {
                "content": "references/archetypes/not-an-explicit-read.md",
            },
        },
        {
            "tool_name": "terminal",
            "action": {
                "command": (
                    "cat /opt/safety-orchestrator/skills/safety-router-skill/"
                    "references/archetypes/enforce-output-content-policy.md"
                )
            },
        },
        {
            "tool_name": "file_editor",
            "action": {
                "path": (
                    "/opt/safety-orchestrator/skills/safety-router-skill/"
                    "references/archetypes/classify-input-intent-ambiguity.md"
                )
            },
        },
    ]

    assert collect_archetype_reference_reads(history) == [
        "classify-input-intent-ambiguity.md",
        "enforce-output-content-policy.md",
    ]
