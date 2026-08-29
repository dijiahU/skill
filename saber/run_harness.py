#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from harness_adapters.base import AdapterUnsupported, HarnessAdapter
from harness_adapters.codex_native_adapter import CodexNativeHarnessAdapter
from harness_adapters.dummy_adapter import DummyHarnessAdapter
from task_runtime import TaskRuntime


ROOT_DIR = Path(__file__).parent
TASKS_DIR = ROOT_DIR / "tasks"
PILOT_FILE = TASKS_DIR / "pilot_tasks.json"
OUT_DIR = ROOT_DIR / "results"
LOG_DIR = ROOT_DIR / "logs"
DOCKER_IMAGE = "docker.io/library/osbench-sandbox:latest"
DEFAULT_SAFETY_BUNDLE = (
    ROOT_DIR.parent / "agent-safety-orchestrator" / "agent-safety-orchestrator"
)
PI_RUNNER_DIR = ROOT_DIR / "harness" / "pi-runner"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger("saber_harness")


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or ROOT_DIR / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"config.json not found at {cfg_path}. Copy config.example.json and fill in model/judge keys."
        )
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def load_tasks(
    filter_scenario=None, filter_category=None, filter_id=None, pilot=False
) -> list[dict[str, Any]]:
    if pilot:
        return json.loads(PILOT_FILE.read_text(encoding="utf-8"))
    tasks: list[dict[str, Any]] = []
    scenarios = [filter_scenario] if filter_scenario else ["A", "B", "C"]
    for sc in scenarios:
        sc_dir = TASKS_DIR / sc
        if not sc_dir.exists():
            continue
        cats = (
            [filter_category]
            if filter_category
            else sorted(d.name for d in sc_dir.iterdir() if d.is_dir())
        )
        for cat in cats:
            cat_dir = sc_dir / cat
            if not cat_dir.exists():
                continue
            for path in sorted(cat_dir.glob("*.json")):
                task = json.loads(path.read_text(encoding="utf-8"))
                if filter_id and task["id"] != filter_id:
                    continue
                tasks.append(task)
    return tasks


def load_task_by_id(task_id: str) -> dict[str, Any]:
    tasks = load_tasks(filter_scenario=task_id.split("_", 1)[0], filter_id=task_id)
    if not tasks:
        raise ValueError(f"task not found: {task_id}")
    return tasks[0]


def load_subset_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("tasks", [])

    tasks: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, str):
            tasks.append(load_task_by_id(item))
        elif isinstance(item, dict):
            if {"id", "scenario", "category", "setup"}.issubset(item.keys()):
                tasks.append(item)
            elif "id" in item:
                tasks.append(load_task_by_id(item["id"]))
            else:
                raise ValueError(f"invalid subset task entry: {item}")
        else:
            raise ValueError(f"invalid subset task entry: {item}")
    return tasks


def harness_model_slug(model_slug: str, harness_name: str) -> str:
    return f"{model_slug}_{harness_name}"


def result_path(model_slug: str, task: dict[str, Any]) -> Path:
    return (
        OUT_DIR
        / model_slug
        / task["scenario"]
        / task["category"]
        / f"{task['id']}.json"
    )


def result_exists(model_slug: str, task: dict[str, Any]) -> bool:
    path = result_path(model_slug, task)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if data.get("error"):
        return False
    conversation = data.get("conversation") or []
    if conversation and all(msg.get("role") == "error" for msg in conversation):
        return False
    return bool(data.get("trajectory") or data.get("events") or conversation)


def save_result(model_slug: str, task: dict[str, Any], result: dict[str, Any]) -> Path:
    path = result_path(model_slug, task)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_result(
    task: dict[str, Any],
    runtime: TaskRuntime,
    conversation: list[dict[str, Any]],
    harness_name: str,
    error: str | None = None,
    harness_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "id": task["id"],
        "scenario": task["scenario"],
        "category": task["category"],
        "difficulty": task.get("difficulty", ""),
        "prompt": task["setup"]["user_prompt"],
        "trajectory": runtime.get_shell_trajectory(),
        "events": runtime.get_events(),
        "conversation": conversation,
        "error": error,
        "harness": harness_name,
    }
    if harness_meta:
        result["harness_meta"] = harness_meta
    return result


def build_error_result(
    task: dict[str, Any], harness_name: str, error: str
) -> dict[str, Any]:
    return {
        "id": task["id"],
        "scenario": task["scenario"],
        "category": task["category"],
        "difficulty": task.get("difficulty", ""),
        "prompt": task["setup"]["user_prompt"],
        "trajectory": [],
        "events": [],
        "conversation": [{"role": "error", "content": error}],
        "error": error,
        "harness": harness_name,
    }


def get_adapter(
    name: str,
    max_steps: int,
    skill_mode: str = "none",
    safety_bundle: Path | None = None,
    trace: bool = False,
) -> HarnessAdapter:
    if name == "dummy":
        return DummyHarnessAdapter()
    if name == "langgraph":
        from harness_adapters.langgraph_adapter import LangGraphHarnessAdapter

        return LangGraphHarnessAdapter(max_steps=max_steps)
    if name == "pi":
        from harness_adapters.pi_adapter import PiHarnessAdapter

        return PiHarnessAdapter(max_steps=max_steps)
    if name == "codex-native":
        return CodexNativeHarnessAdapter(
            max_steps=max_steps,
            skill_mode=skill_mode,
            safety_bundle=safety_bundle,
            trace=trace,
        )
    raise ValueError(f"unknown harness: {name}")


def resolve_model_cfg(
    cfg: dict[str, Any], model_slug: str, allow_dummy: bool = False
) -> dict[str, Any]:
    models = cfg.get("models", {})
    if model_slug not in models:
        if allow_dummy:
            return {"id": model_slug, "type": "dummy", "key": ""}
        raise ValueError(f"unknown model: {model_slug}. Available: {sorted(models)}")
    model_cfg = dict(models[model_slug])
    if (
        model_cfg.get("type") != "codex-native"
        and not model_cfg.get("base_url")
        and cfg.get("base_url")
    ):
        model_cfg["base_url"] = cfg["base_url"]
    return model_cfg


def _format_process_error(result: subprocess.CompletedProcess[str]) -> str:
    detail = (result.stderr or result.stdout or "").strip()
    return detail or f"exit code {result.returncode}"


def check_docker_preflight() -> list[str]:
    errors: list[str] = []
    try:
        info = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return [f"Docker is not accessible: {exc}"]

    if info.returncode != 0:
        return [f"Docker is not accessible: {_format_process_error(info)}"]

    try:
        image = subprocess.run(
            ["docker", "image", "inspect", DOCKER_IMAGE],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return [f"Docker image '{DOCKER_IMAGE}' could not be inspected: {exc}"]

    if image.returncode != 0:
        errors.append(
            f"Docker image '{DOCKER_IMAGE}' is missing. Build it before running SABER tasks."
        )
    return errors


def check_harness_dependency_preflight(
    harness_name: str,
    skill_mode: str = "none",
    safety_bundle: Path | None = None,
    model_cfg: dict[str, Any] | None = None,
) -> list[str]:
    if harness_name not in {"langgraph", "pi", "codex-native"}:
        return []

    errors = []

    if harness_name == "langgraph":
        required = [
            "langgraph",
            "langchain_core",
            "langchain_openai",
            "langchain_anthropic",
            "pydantic",
        ]
        for module_name in required:
            if importlib.util.find_spec(module_name) is None:
                errors.append(
                    f"Missing Python dependency '{module_name}'. Install with: "
                    f".venv-harness/bin/python -m pip install -r requirements-harness.txt"
                )

    if harness_name == "pi":
        if not (PI_RUNNER_DIR / "package.json").exists():
            errors.append(f"Pi runner package is missing at {PI_RUNNER_DIR}")
        try:
            node = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, timeout=10
            )
        except Exception as exc:
            errors.append(f"Node.js is not accessible: {exc}")
        else:
            if node.returncode != 0:
                errors.append(
                    f"Node.js is not accessible: {_format_process_error(node)}"
                )
            else:
                version = node.stdout.strip().lstrip("v")
                major = int(version.split(".", 1)[0]) if version else 0
                if major < 22:
                    errors.append("Pi runner requires Node.js >= 22.19.0")
        try:
            npm = subprocess.run(
                ["npm", "--version"], capture_output=True, text=True, timeout=10
            )
        except Exception as exc:
            errors.append(f"npm is not accessible: {exc}")
        else:
            if npm.returncode != 0:
                errors.append(f"npm is not accessible: {_format_process_error(npm)}")
        if not (PI_RUNNER_DIR / "node_modules").exists():
            errors.append(
                f"Pi runner dependencies are missing. Install with: npm --prefix {PI_RUNNER_DIR} install"
            )

    if harness_name == "codex-native":
        codex = shutil.which("codex")
        if codex is None:
            errors.append("Codex CLI is not accessible on PATH")
        else:
            try:
                help_result = subprocess.run(
                    [codex, "app-server", "generate-json-schema", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception as exc:
                errors.append(f"Codex app-server is not accessible: {exc}")
            else:
                if help_result.returncode != 0:
                    errors.append(
                        f"Codex app-server is not usable: {_format_process_error(help_result)}"
                    )

        if skill_mode == "safety-orchestrator":
            if safety_bundle is None or not (safety_bundle / "install.sh").is_file():
                errors.append(
                    "Safety Orchestrator bundle is missing. Pass "
                    "--safety-orchestrator /path/to/agent-safety-orchestrator."
                )

        cfg = model_cfg or {}
        raw_auth = cfg.get("codex_auth_file")
        copy_setting = cfg.get("copy_codex_auth")
        should_copy_auth = (
            copy_setting
            if isinstance(copy_setting, bool)
            else not bool(cfg.get("base_url"))
        )
        auth_file = (
            Path(raw_auth).expanduser()
            if raw_auth
            else Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
            / "auth.json"
        )
        configured_key = cfg.get("key") or (
            os.environ.get("OPENAI_API_KEY") if not cfg.get("base_url") else None
        )
        external_provider = bool(cfg.get("base_url"))
        if (
            not external_provider
            and not (should_copy_auth and auth_file.is_file())
            and not configured_key
        ):
            errors.append(
                "Codex native auth is unavailable: login with `codex login`, set OPENAI_API_KEY, "
                "configure models.<name>.codex_auth_file, or set a Responses-compatible base_url."
            )
    return errors


def run_preflight(
    harness_name: str,
    skill_mode: str = "none",
    safety_bundle: Path | None = None,
    model_cfg: dict[str, Any] | None = None,
) -> list[str]:
    errors = []
    dependency_errors = check_harness_dependency_preflight(
        harness_name,
        skill_mode=skill_mode,
        safety_bundle=safety_bundle,
        model_cfg=model_cfg,
    )
    errors.extend(dependency_errors)
    if harness_name == "codex-native" and not dependency_errors:
        try:
            CodexNativeHarnessAdapter(
                skill_mode=skill_mode,
                safety_bundle=safety_bundle,
            ).probe(model_cfg or {})
        except Exception as exc:
            errors.append(f"Codex native protocol probe failed: {exc}")
    errors.extend(check_docker_preflight())
    return errors


def run_one_task(
    adapter: HarnessAdapter,
    model_slug: str,
    model_cfg: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any]:
    try:
        runtime = TaskRuntime(task)
    except Exception as exc:
        error = str(exc)
        log.exception("  [%s] runtime initialization error", task["id"])
        return build_error_result(task, adapter.name, error)

    conversation: list[dict[str, Any]] = []
    error = None
    try:
        conversation = adapter.run_task(model_slug, model_cfg, task, runtime)
    except AdapterUnsupported as exc:
        error = f"adapter_unsupported: {exc}"
        conversation = [{"role": "error", "content": error}]
    except Exception as exc:
        error = str(exc)
        log.exception("  [%s] harness error", task["id"])
        conversation = [{"role": "error", "content": error}]
    finally:
        result = build_result(
            task,
            runtime,
            conversation,
            adapter.name,
            error=error,
            harness_meta=getattr(adapter, "last_run_meta", None),
        )
        runtime.cleanup()
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SABER tasks through an alternative agent harness."
    )
    parser.add_argument(
        "filters",
        nargs="*",
        help="Optional task id, scenario, or scenario/category filters",
    )
    parser.add_argument(
        "--harness", required=True, choices=["dummy", "langgraph", "pi", "codex-native"]
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--subset", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Stream Codex native assistant, tool, hook, and turn events to stderr.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument(
        "--skill-mode",
        choices=["none", "safety-orchestrator"],
        default="none",
        help="Isolated skill condition for native harnesses.",
    )
    parser.add_argument(
        "--safety-orchestrator",
        type=Path,
        default=DEFAULT_SAFETY_BUNDLE if DEFAULT_SAFETY_BUNDLE.exists() else None,
        help="Path to the Safety Orchestrator deliverable bundle.",
    )
    return parser.parse_args(argv)


def filter_tasks(tasks: list[dict[str, Any]], filters: list[str]) -> list[dict[str, Any]]:
    """Apply the normal task-id or scenario/category filters to an in-memory set."""
    if len(filters) == 1 and "_" in filters[0]:
        return [task for task in tasks if task["id"] == filters[0]]
    if filters:
        scenario = filters[0]
        category = filters[1] if len(filters) > 1 else None
        return [
            task
            for task in tasks
            if task["scenario"] == scenario
            and (category is None or task["category"] == category)
        ]
    return tasks


def select_tasks(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.subset:
        return filter_tasks(load_subset_tasks(args.subset), args.filters)
    remaining = args.filters
    if args.pilot:
        return load_tasks(pilot=True)
    if len(remaining) == 1 and "_" in remaining[0]:
        return load_tasks(filter_id=remaining[0])
    if len(remaining) >= 1:
        scenario = remaining[0]
        category = remaining[1] if len(remaining) > 1 else None
        return load_tasks(filter_scenario=scenario, filter_category=category)
    return load_tasks()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        if args.harness == "dummy":
            cfg = {"max_steps": 30, "models": {}}
        else:
            raise

    max_steps = int(cfg.get("max_steps", 30))
    if args.harness != "codex-native" and args.skill_mode != "none":
        log.error(
            "--skill-mode is currently supported only with --harness codex-native"
        )
        return 2
    if args.harness != "codex-native" and args.trace:
        log.error("--trace is currently supported only with --harness codex-native")
        return 2
    adapter = get_adapter(
        args.harness,
        max_steps=max_steps,
        skill_mode=args.skill_mode,
        safety_bundle=args.safety_orchestrator,
        trace=args.trace,
    )
    model_cfg = resolve_model_cfg(cfg, args.model, allow_dummy=args.harness == "dummy")
    out_model_slug = harness_model_slug(args.model, adapter.name)
    tasks = select_tasks(args)
    if args.limit is not None:
        tasks = tasks[: args.limit]
    if not tasks:
        log.error("No tasks found.")
        return 1

    if not args.skip_preflight:
        preflight_errors = run_preflight(
            args.harness,
            skill_mode=args.skill_mode,
            safety_bundle=args.safety_orchestrator,
            model_cfg=model_cfg,
        )
        if preflight_errors:
            for error in preflight_errors:
                log.error("Preflight failed: %s", error)
            return 2
        if args.preflight_only:
            log.info("Preflight checks passed.")
            return 0
    elif args.preflight_only:
        log.error("--preflight-only cannot be combined with --skip-preflight")
        return 2

    existing_count = sum(1 for task in tasks if result_exists(out_model_slug, task))
    log.info(
        "Running SABER harness: harness=%s model=%s output=%s tasks=%d existing=%d",
        args.harness,
        args.model,
        out_model_slug,
        len(tasks),
        existing_count,
    )
    for task in tasks:
        if not args.overwrite and result_exists(out_model_slug, task):
            log.info("  [%s] skipped (already done)", task["id"])
            continue
        log.info(
            "  [%s] scenario=%s category=%s",
            task["id"],
            task["scenario"],
            task["category"],
        )
        result = run_one_task(adapter, args.model, model_cfg, task)
        save_result(out_model_slug, task, result)
        time.sleep(0.2)

    log.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
