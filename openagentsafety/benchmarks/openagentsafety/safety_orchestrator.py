"""Safety Orchestrator integration helpers for OpenAgentSafety."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from openhands.sdk import AgentContext
from openhands.sdk.hooks import HookConfig, conversation_hooks, executor
from openhands.sdk.workspace import RemoteWorkspace


BUNDLE_CONTAINER_ROOT = "/opt/safety-orchestrator"
ROUTER_SKILL_NAME = "safety-router-skill"
ROUTER_WORKSPACE_PATH = f"/workspace/.agents/skills/{ROUTER_SKILL_NAME}"
WORKSPACE_LABEL = "skilldistill.openagentsafety.workspace"
HOOK_COMPAT_VERSION = "oas-hooks-v1"
HOOK_COMPAT_LABEL = "skilldistill.openagentsafety.hooks-sha256"


def hook_adapter_digest() -> str:
    """Hash the actual SDK modules used by this consumer."""
    digest = hashlib.sha256()
    for module in (executor, conversation_hooks):
        if module.__file__ is None:
            raise RuntimeError("Cannot locate Safety Orchestrator SDK modules")
        digest.update(Path(module.__file__).read_bytes())
    return digest.hexdigest()


def select_safety_orchestrator_image(base_image: str) -> str:
    """Fail before task execution if the skills image lacks the current adapter.

    Baseline never calls this function. No image is downloaded or built here.
    """
    image = os.getenv("OPENAGENTSAFETY_SKILLS_IMAGE") or (
        f"{base_image}-{HOOK_COMPAT_VERSION}"
    )
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Build the local {HOOK_COMPAT_VERSION} skills image: {image}"
        )
    config = json.loads(result.stdout)[0]["Config"]
    labels = config.get("Labels") or {}
    if labels.get(
        HOOK_COMPAT_LABEL
    ) != hook_adapter_digest() or "OPENHANDS_SAFETY_ORCHESTRATOR_COMPAT=1" not in (
        config.get("Env") or []
    ):
        raise RuntimeError(f"Skills image has a missing/stale hook adapter: {image}")
    return image


DEFAULT_BUNDLE_ROOT = (
    Path(__file__).resolve().parents[2].parent
    / "agent-safety-orchestrator"
    / "agent-safety-orchestrator"
)

_MATCHER_MAP = {
    "Bash": "terminal",
    "Write|Edit|MultiEdit": "file_editor|apply_patch",
    "WebFetch|WebSearch": "browser",
    "Task": "task",
}

_ARCHETYPE_REFERENCE_RE = re.compile(r"references/archetypes/([a-z0-9][a-z0-9-]*\.md)")


def resolve_bundle_root(explicit_root: str | Path | None = None) -> Path:
    """Resolve and validate the Safety Orchestrator bundle in the Pod."""
    root = Path(
        explicit_root
        or os.getenv("OPENAGENTSAFETY_SAFETY_ORCHESTRATOR_ROOT", "")
        or DEFAULT_BUNDLE_ROOT
    ).expanduser()
    root = root.resolve()
    required = (
        root / "skills" / ROUTER_SKILL_NAME / "SKILL.md",
        root / "hooks" / "hooks.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Safety Orchestrator bundle is incomplete; missing: " + ", ".join(missing)
        )
    return root


def translate_to_docker_host(path: str | Path) -> Path:
    """Translate an AIStation Pod path to the host daemon's bind-mount path."""
    resolved = Path(path).expanduser().resolve()
    pod_root_raw = os.getenv("POD_USER_ROOT")
    host_root_raw = os.getenv("HOST_USER_ROOT")
    if not pod_root_raw or not host_root_raw:
        return resolved

    pod_root = Path(pod_root_raw).expanduser().resolve()
    host_root = Path(host_root_raw).expanduser()
    try:
        relative = resolved.relative_to(pod_root)
    except ValueError as exc:
        raise ValueError(
            f"Path {resolved} is outside POD_USER_ROOT {pod_root}; "
            "cannot create a safe host bind mount"
        ) from exc
    return host_root / relative


def bundle_volume(bundle_root: str | Path) -> str:
    """Return the read-only Docker volume specification for the bundle."""
    return f"{translate_to_docker_host(bundle_root)}:{BUNDLE_CONTAINER_ROOT}:ro"


def install_router_skill_link(workspace: RemoteWorkspace) -> None:
    """Expose only the router skill through the standard project-skill path."""
    command = (
        "mkdir -p /workspace/.agents/skills && "
        f"ln -s {BUNDLE_CONTAINER_ROOT}/skills/{ROUTER_SKILL_NAME} "
        f"{ROUTER_WORKSPACE_PATH}"
    )
    result = workspace.execute_command(command, timeout=30)
    if result.exit_code != 0:
        raise RuntimeError(f"Failed to install router skill link: {result.stderr}")


def load_router_context(
    workspace: RemoteWorkspace,
) -> tuple[list[str], AgentContext]:
    """Load exactly the Safety Orchestrator router and no public/user skills."""
    skills, agent_context = workspace.load_skills_from_agent_server(
        project_dirs=["/workspace"],
        load_public=False,
        load_user=False,
        load_project=True,
        load_org=False,
    )
    names = [skill.name for skill in skills]
    if names != [ROUTER_SKILL_NAME]:
        raise RuntimeError(f"Expected exactly {ROUTER_SKILL_NAME!r}, loaded {names!r}")
    return names, agent_context


def load_openhands_hook_config(bundle_root: str | Path) -> HookConfig:
    """Load Claude-style hooks and adapt commands/matchers for OpenHands."""
    hook_path = Path(bundle_root) / "hooks" / "hooks.json"
    raw_config = json.loads(hook_path.read_text())
    if not isinstance(raw_config, dict):
        raise ValueError(f"Hook configuration must be an object: {hook_path}")
    # The bundle includes manifest-only metadata beside the Claude-compatible
    # hooks wrapper. Pass only runtime hooks to OpenHands so it does not warn
    # about (or accidentally interpret) those informational fields.
    wrapped_hooks = raw_config.get("hooks")
    if isinstance(wrapped_hooks, dict):
        raw_config = {"hooks": wrapped_hooks}
    config = HookConfig.model_validate(raw_config)
    config = config.model_copy(deep=True)

    for event_name in (
        "user_prompt_submit",
        "pre_tool_use",
        "post_tool_use",
        "session_start",
        "session_end",
        "stop",
    ):
        for matcher in getattr(config, event_name):
            matcher.matcher = _MATCHER_MAP.get(matcher.matcher, matcher.matcher)
            for hook in matcher.hooks:
                hook.command = hook.command.replace(
                    "${CLAUDE_PLUGIN_ROOT}", BUNDLE_CONTAINER_ROOT
                )

    if config.is_empty():
        raise RuntimeError("Safety Orchestrator hook configuration is empty")
    return config


def collect_audit_counts(workspace: RemoteWorkspace) -> dict[str, Any]:
    """Collect audit-file line counts without exposing prompt or tool contents."""
    command = r"""python3 - <<'PY'
import json
from pathlib import Path

root = Path.home() / ".safety-orch"
counts = {}
if root.is_dir():
    for path in sorted(root.glob("*.jsonl")):
        try:
            with path.open(errors="replace") as stream:
                counts[path.name] = sum(1 for _ in stream)
        except OSError:
            counts[path.name] = -1
print(json.dumps({"jsonl_files": len(counts), "jsonl_lines": counts}))
PY"""
    result = workspace.execute_command(command, timeout=30)
    if result.exit_code != 0:
        return {"error": result.stderr.strip() or "audit count command failed"}
    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"error": "audit count output was not valid JSON"}
    return (
        data if isinstance(data, dict) else {"error": "unexpected audit count output"}
    )


def collect_archetype_reference_reads(history: list[dict[str, Any]]) -> list[str]:
    """Return archetype files explicitly referenced by agent file/tool actions."""
    names: set[str] = set()
    for event in history:
        if event.get("tool_name") not in {"terminal", "file_editor", "apply_patch"}:
            continue
        action = event.get("action")
        if not isinstance(action, dict):
            continue
        action_text = json.dumps(action, sort_keys=True)
        names.update(_ARCHETYPE_REFERENCE_RE.findall(action_text))
    return sorted(names)
