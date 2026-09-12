#!/usr/bin/env python3
"""Configure, inspect and run API-only SABER/OAS/Terminal-Bench experiments."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlsplit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUNDLE = ROOT / "agent-safety-orchestrator" / "agent-safety-orchestrator"
REPORTS = ROOT / "reports" / "api_benchmarks"
BENCHMARKS = ("saber", "oas", "terminalbench")
MODES = ("none", "safety-orchestrator")


def environment(path: Path) -> dict[str, str]:
    """Read literal dotenv values without evaluating shell expressions."""
    values: dict[str, str] = {}
    if path.exists():
        for number, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                raise ValueError(f"Invalid dotenv assignment on line {number}")
            if value[:1] in ("'", '"'):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError(f"Unclosed quote on line {number}")
                value = value[1:-1]
            values[key] = value
    values.update(os.environ)
    return values


def require(env: dict[str, str], names: list[str]) -> None:
    """Reject incomplete configurations before contacting paid endpoints."""
    missing = [n for n in names if not env.get(n) or "REPLACE_" in env[n]]
    if missing:
        raise ValueError("Fill local .env: " + ", ".join(missing))


def validate_url(url: str) -> str:
    """Accept HTTP API bases without embedded credentials or query secrets."""
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("API base URL must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use API key variables, not credentials/query data in URLs")
    if parsed.path.rstrip("/").endswith(
        ("/responses", "/chat/completions", "/messages")
    ):
        raise ValueError("Configure the API base, without the operation suffix")
    return url.rstrip("/")


def role_config(env: dict[str, str], role: str, live: bool) -> dict[str, str]:
    """Resolve an independent agent, Responses, judge or NPC endpoint."""
    prefix = {
        "agent": "BENCH",
        "responses": "RESPONSES",
        "judge": "JUDGE",
        "npc": "NPC",
    }[role]
    names = [f"{prefix}_{name}" for name in ("MODEL", "BASE_URL", "API_KEY")]
    key_env = env.get(f"{prefix}_API_KEY_ENV", names[2])
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key_env):
        raise ValueError(f"{prefix}_API_KEY_ENV must name an environment variable")
    if live:
        require(env, names[:2] + [key_env])
    provider = (
        env.get("BENCH_PROVIDER", "openai")
        if role == "agent"
        else env.get("JUDGE_TYPE", "openai")
        if role == "judge"
        else "openai"
    )
    if provider not in ("openai", "anthropic"):
        raise ValueError("BENCH_PROVIDER/JUDGE_TYPE must be openai or anthropic")
    return {
        "id": env.get(names[0], "REPLACE_WITH_MODEL_ID"),
        "base_url": validate_url(env.get(names[1], "https://api.openai.com/v1")),
        "key": env.get(key_env, "") if live else "<runtime-only>",
        "type": provider,
    }


def python_for(name: str) -> str:
    """Use isolated benchmark dependencies, with no global package mutations."""
    paths = {
        "saber": HERE / ".venv-saber/bin/python",
        "oas": ROOT / "openagentsafety/.venv/bin/python",
        "terminalbench": HERE / ".venv-harbor/bin/python",
    }
    return str(paths[name])


def run_id(env: dict[str, str]) -> str:
    value = env.get("BENCH_RUN_ID", "api-smoke-001")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", value):
        raise ValueError("BENCH_RUN_ID must be a short filename-safe experiment ID")
    return value


def commands(
    name: str,
    mode: str,
    env: dict[str, str],
    limit: int,
    selection: Path | None,
    config: Path,
) -> tuple[Path, list[str]]:
    """Construct argv lists, never shell strings containing credentials."""
    output = REPORTS / run_id(env) / name / mode
    steps = int(env.get("BENCH_MAX_STEPS", "30"))
    if steps < 1 or limit < 1:
        raise ValueError("Step and task limits must be positive")
    if name == "saber":
        cmd = [
            python_for(name),
            "run_harness.py",
            "--harness",
            "codex-native",
            "--model",
            run_id(env),
            "--config",
            str(config),
            "--skill-mode",
            mode,
            "--safety-orchestrator",
            str(BUNDLE),
            "--limit",
            str(limit),
        ]
        if selection:
            cmd += ["--subset", str(selection)]
        return ROOT / "saber", cmd
    if name == "oas":
        cmd = [
            python_for(name),
            "-m",
            "benchmarks.openagentsafety.run_infer",
            str(config),
            "--dataset",
            env.get("OAS_DATASET", "mgulavani/openagentsafety_full_updated_v3"),
            "--split",
            "train",
            "--workspace",
            "docker",
            "--num-workers",
            "1",
            "--n-limit",
            str(limit),
            "--max-iterations",
            str(steps),
            "--critic",
            "pass",
            "--skill-mode",
            mode,
            "--safety-orchestrator-root",
            str(BUNDLE),
            "--output-dir",
            str(output),
        ]
        if selection:
            cmd += ["--select", str(selection)]
        return ROOT / "openagentsafety", cmd
    model = role_config(env, "responses", False)["id"]
    cmd = [
        python_for("terminalbench"),
        "-m",
        "harbor.cli.main",
        "run",
        "-d",
        env.get("TERMINALBENCH_DATASET", "terminal-bench/terminal-bench-2-1"),
        "--agent",
        "api_benchmarks.harbor_codex:SafetyCodex",
        "-m",
        model,
        "--n-concurrent",
        str(positive_setting(env, "TERMINALBENCH_CONCURRENCY", 1)),
        "--n-attempts",
        str(positive_setting(env, "TERMINALBENCH_ATTEMPTS", 1)),
        "--n-tasks",
        str(limit),
        "--jobs-dir",
        str(output),
        "--ak",
        f"skill_mode={mode}",
        "--ak",
        f"bundle_root={BUNDLE}",
        "--ak",
        "version=0.149.1",
    ]
    if selection:
        for task in selection.read_text().splitlines():
            if task.strip() and not task.lstrip().startswith("#"):
                cmd += ["--include-task-name", task.strip()]
    proxy = env.get("TERMINALBENCH_HTTP_PROXY")
    if proxy:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            cmd += ["--ae", f"{key}={proxy}", "--ve", f"{key}={proxy}"]
        for key in ("NO_PROXY", "no_proxy"):
            cmd += [
                "--ae",
                f"{key}=localhost,127.0.0.1",
                "--ve",
                f"{key}=localhost,127.0.0.1",
            ]
    if env.get("TERMINALBENCH_CODEX_ARCHIVE"):
        archive = Path(env["TERMINALBENCH_CODEX_ARCHIVE"]).expanduser().resolve()
        cmd += ["--ak", f"codex_archive={archive}"]
    return ROOT, cmd


def config_data(name: str, env: dict[str, str], live: bool) -> dict:
    """Produce the schema expected by each existing runner."""
    cfg = role_config(env, "responses" if name != "oas" else "agent", live)
    if name == "saber":
        cfg.pop("key")
        cfg.update(
            type="codex-native",
            key_env="RESPONSES_API_KEY",
            copy_codex_auth=False,
            preload_skill_references=False,
        )
        return {
            "max_steps": int(env.get("BENCH_MAX_STEPS", "30")),
            "models": {run_id(env): cfg},
        }
    if name == "terminalbench":
        return {
            "model": cfg["id"],
            "base_url": cfg["base_url"],
            "api_key": "<runtime-only>",
            "protocol": "responses-to-chat"
            if env.get("TERMINALBENCH_CHAT_BRIDGE") == "1"
            else "responses",
        }
    return {
        "model": f"{cfg['type']}/{cfg['id']}",
        "api_key": cfg["key"],
        "base_url": cfg["base_url"],
    }


def private_json(path: Path, data: dict) -> None:
    """Write configuration owner-readable, including at creation time."""
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def saber_judge_base_url(cfg: dict[str, str]) -> str:
    """Adapt SABER's legacy OpenAI judge, which appends /v1 itself."""
    url = cfg["base_url"].rstrip("/")
    return url[:-3] if cfg["type"] == "openai" and url.endswith("/v1") else url


def fingerprint(
    env: dict[str, str], name: str, limit: int, selection: Path | None
) -> dict:
    """Record non-secret inputs so reusing an experiment ID cannot mix models."""
    files = sorted(
        p
        for d in ("skills", "hooks", "helpers", "adapters")
        for p in (BUNDLE / d).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(BUNDLE)).encode())
        digest.update(path.read_bytes())
    cfg = config_data(name, env, False)
    result = {
        "benchmark": name,
        "config": cfg,
        "limit": limit,
        "selection_sha256": hashlib.sha256(selection.read_bytes()).hexdigest()
        if selection
        else None,
        "bundle_sha256": digest.hexdigest(),
        "max_steps": env.get("BENCH_MAX_STEPS", "30"),
    }
    if name == "oas":
        result["npc"] = role_config(env, "npc", False)
        result["dataset"] = env.get(
            "OAS_DATASET", "mgulavani/openagentsafety_full_updated_v3"
        )
    if name == "terminalbench":
        result["dataset"] = env.get(
            "TERMINALBENCH_DATASET", "terminal-bench/terminal-bench-2-1"
        )
        result["harbor_version"] = "0.22.0"
        result["codex_version"] = "0.149.1"
        result["concurrency"] = positive_setting(env, "TERMINALBENCH_CONCURRENCY", 1)
        result["attempts"] = positive_setting(env, "TERMINALBENCH_ATTEMPTS", 1)
        if env.get("TERMINALBENCH_CHAT_BRIDGE") == "1":
            result["bridge"] = {
                "implementation": "litellm-responses-to-chat",
                "source_sha256": hashlib.sha256(
                    (HERE / "responses_bridge.py").read_bytes()
                ).hexdigest(),
                "dependency_lock_sha256": hashlib.sha256(
                    (HERE / "requirements-harbor.lock.txt").read_bytes()
                ).hexdigest(),
                "enable_thinking": False,
                "max_output_tokens": positive_setting(
                    env, "BRIDGE_MAX_OUTPUT_TOKENS", 8192
                ),
            }
        result["http_proxy"] = env.get("TERMINALBENCH_HTTP_PROXY")
        if env.get("TERMINALBENCH_CODEX_ARCHIVE"):
            archive = Path(env["TERMINALBENCH_CODEX_ARCHIVE"]).expanduser()
            result["codex_archive_sha256"] = hashlib.sha256(
                archive.read_bytes()
            ).hexdigest()
    return result


def launch(
    name: str,
    modes: tuple[str, ...],
    env: dict[str, str],
    limit: int,
    selection: Path | None,
) -> None:
    """Launch a bounded experiment, clearing temporary secret files on exit."""
    data = config_data(name, env, True)
    child_env = env.copy()
    if name == "saber":
        child_env["RESPONSES_API_KEY"] = role_config(env, "responses", True)["key"]
    if name == "oas":
        child_env["NPC_API_KEY"] = role_config(env, "npc", True)["key"]
        child_env.setdefault(
            "OPENAGENTSAFETY_ASSET_CACHE", str(HERE / ".cache/oas-assets")
        )
        child_env.setdefault(
            "OPENAGENTSAFETY_WHEELHOUSE", str(HERE / ".cache/oas-wheels")
        )
        child_env.setdefault("OPENAGENTSAFETY_IMAGE_TAG_PREFIX", "api")
    elif name == "terminalbench":
        child_env["OPENAI_API_KEY"] = role_config(env, "responses", True)["key"]
        child_env["OPENAI_BASE_URL"] = env["RESPONSES_BASE_URL"]
        child_env.pop("CODEX_AUTH_JSON_PATH", None)
        child_env.pop("CODEX_FORCE_AUTH_JSON", None)
    expected = fingerprint(env, name, limit, selection)
    manifest = REPORTS / run_id(env) / name / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if manifest.exists() and json.loads(manifest.read_text()) != expected:
        raise ValueError("Run configuration changed; choose a new BENCH_RUN_ID")
    if not manifest.exists():
        private_json(manifest, expected)
    with ExitStack() as stack:
        if name == "terminalbench" and env.get("TERMINALBENCH_CHAT_BRIDGE") == "1":
            # bench.py also works as a direct script, with HERE on the import path.
            if __package__:
                from .bridge_process import chat_bridge
            else:
                from bridge_process import chat_bridge

            child_env.update(
                stack.enter_context(
                    chat_bridge(
                        env,
                        role_config(env, "responses", True),
                        python_for(name),
                        ROOT,
                        manifest.parent,
                    )
                )
            )
        temp = stack.enter_context(tempfile.TemporaryDirectory(prefix="api-benchmark-"))
        config = Path(temp) / "model.json"
        private_json(config, data)
        for mode in modes:
            cwd, command = commands(name, mode, env, limit, selection, config)
            output = REPORTS / run_id(env) / name / mode
            previous = (
                set(output.glob("*/result.json")) if name == "terminalbench" else set()
            )
            subprocess.run(command, cwd=cwd, env=child_env, check=True)
            if name == "terminalbench":
                check_harbor_results(set(output.glob("*/result.json")) - previous)
            elif name == "oas":
                check_oas_results(list(output.rglob("output.jsonl")))


def positive_setting(env: dict[str, str], name: str, default: int) -> int:
    """Validate explicit parallelism and repeat counts before starting jobs."""
    value = int(env.get(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def check_oas_results(paths: list[Path]) -> None:
    """Require scored OAS conversations, including errors hidden by exit zero."""
    rows = [
        json.loads(line)
        for path in paths
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("OAS produced no task results")
    for row in rows:
        result = row.get("test_result") or {}
        condition = result.get("skilldistill") or {}
        score = result.get("final_score") or {}
        if (
            row.get("error")
            or result.get("error")
            or condition.get("conversation_error")
            or condition.get("graded_from_partial_trajectory")
            or score.get("total", 0) <= 0
            or not isinstance(score.get("result"), (int, float))
        ):
            raise ValueError(
                f"OAS task failed or lacks a valid score: {row.get('instance_id')}"
            )


def check_harbor_results(paths: set[Path]) -> None:
    """Harbor can exit zero when every trial failed; require finished trials."""
    if not paths:
        raise ValueError("Harbor produced no new job result")
    for path in sorted(paths):
        stats = json.loads(path.read_text()).get("stats", {})
        if (
            stats.get("n_completed_trials", 0) < 1
            or stats.get("n_errored_trials", 0)
            or any(
                stats.get(f"n_{state}_trials", 0)
                for state in ("pending", "running", "cancelled")
            )
        ):
            raise ValueError(
                f"Harbor job has failed or unfinished trials; inspect {path}"
            )


def check_responses_stream(response) -> None:
    """Require a completed SSE event without waiting for the gateway to close."""
    remaining = 2_000_000
    while remaining > 0:
        line = response.readline(remaining + 1)
        remaining -= len(line)
        if remaining < 0:
            raise ValueError("Responses probe exceeded its stream size limit")
        if not line:
            break
        if not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            break
        event = json.loads(data)
        if event.get("type") in ("response.failed", "response.incomplete", "error"):
            raise ValueError("Responses provider reported a failed/incomplete stream")
        if event.get("type") == "response.completed":
            if event.get("response", {}).get("status") != "completed":
                raise ValueError("Responses completion event has no completed status")
            return
    raise ValueError("Responses stream ended before response.completed")


def probe(env: dict[str, str], role: str) -> None:
    """Make one small API request; never print credentials or response content."""
    cfg = role_config(env, role, True)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['key']}",
    }
    if role == "responses":
        suffix = "/responses"
        body = {
            "model": cfg["id"],
            "instructions": "This is a minimal API connectivity test.",
            "input": [{"role": "user", "content": "Reply OK."}],
            "max_output_tokens": 128,
            "stream": True,
            "store": False,
            "tools": [
                {
                    "type": "function",
                    "name": "api_probe",
                    "description": "Connectivity probe only; no execution",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
        }
    elif cfg["type"] == "anthropic":
        suffix = "/v1/messages" if not cfg["base_url"].endswith("/v1") else "/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": cfg["key"],
            "anthropic-version": "2023-06-01",
        }
        body = {
            "model": cfg["id"],
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Reply OK."}],
        }
    else:
        suffix = "/chat/completions"
        body = {
            "model": cfg["id"],
            "max_tokens": 64,
            "messages": [{"role": "user", "content": "Reply OK."}],
        }
    request = urllib.request.Request(
        cfg["base_url"] + suffix, data=json.dumps(body).encode(), headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if role == "responses":
                check_responses_stream(response)
            else:
                parsed = json.loads(response.read(2_000_000))
                if not parsed.get("choices", parsed.get("content")):
                    raise ValueError("Provider returned no completion")
    except urllib.error.HTTPError as exc:
        raise ValueError(
            f"{role} API returned HTTP {exc.code}; response body hidden"
        ) from None
    except urllib.error.URLError:
        raise ValueError(
            f"{role} API connection failed; check endpoint/network"
        ) from None
    except http.client.HTTPException:
        raise ValueError(f"{role} API stream disconnected before completion") from None
    print(
        f"PASS {role}: API request completed (full tool execution needs a benchmark smoke run)"
    )


def doctor(env: dict[str, str]) -> int:
    """Check local prerequisites without making model requests."""
    failures = 0
    for name, path in [
        ("bundle", BUNDLE / "atoms.json"),
        *[(b + " Python", Path(python_for(b))) for b in BENCHMARKS],
    ]:
        ok = path.exists()
        print(f"{'PASS' if ok else 'MISSING'} {name}: {path}")
        failures += not ok
    imports = {
        "saber": "httpx, openai, anthropic",
        "oas": "openhands.sdk, benchmarks.openagentsafety.run_infer",
        "terminalbench": "harbor, api_benchmarks.harbor_codex",
    }
    for name, modules in imports.items():
        if not Path(python_for(name)).exists():
            continue
        result = subprocess.run(
            [python_for(name), "-c", f"import {modules}"],
            cwd=ROOT / "openagentsafety" if name == "oas" else ROOT,
            capture_output=True,
            text=True,
            timeout=45,
            env={**env, "LITELLM_LOCAL_MODEL_COST_MAP": "True"},
        )
        print(
            f"{'PASS' if result.returncode == 0 else 'MISSING'} {name} Python imports"
        )
        failures += result.returncode != 0
    for binary in ("docker", "codex"):
        ok = shutil.which(binary) is not None
        print(f"{'PASS' if ok else 'MISSING'} {binary}")
        failures += not ok
    if shutil.which("docker"):
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        print(
            "PASS Docker daemon"
            if result.returncode == 0
            else "MISSING Docker daemon access"
        )
        failures += result.returncode != 0
    for role in ("agent", "responses", "judge", "npc"):
        try:
            role_config(env, role, True)
            print(f"PASS {role} API fields configured (not connectivity-tested)")
        except ValueError as exc:
            print(f"MISSING {role}: {exc}")
            failures += 1
    print(
        "OAS service stack and task images are checked by the OAS runner before execution."
    )
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("init", "doctor", "plan", "preflight", "probe", "run", "judge"),
    )
    parser.add_argument(
        "benchmark", nargs="?", choices=(*BENCHMARKS, "all"), default="all"
    )
    parser.add_argument("--env-file", type=Path, default=HERE / ".env")
    parser.add_argument("--mode", choices=(*MODES, "both"), default="both")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument(
        "--select", type=Path, help="SABER subset JSON; OAS/TB task-ID text file"
    )
    parser.add_argument(
        "--role", choices=("agent", "responses", "judge", "npc"), default="responses"
    )
    parser.add_argument("--output", type=Path, help="OAS/TB output.jsonl to summarize")
    args = parser.parse_args()
    if args.action == "judge" and args.benchmark == "all":
        parser.error(
            "Judge each benchmark separately: SABER uses an API, OAS/TB summarize task scores"
        )
    if args.action == "init":
        try:
            with args.env_file.open("x") as stream:
                os.chmod(args.env_file, 0o600)
                stream.write((HERE / ".env.example").read_text())
            print(f"Created {args.env_file}; fill model IDs and keys locally")
        except FileExistsError:
            print(f"Kept existing {args.env_file}")
        return 0
    env = environment(args.env_file)
    if args.action == "doctor":
        return doctor(env)
    if args.action == "probe":
        probe(env, args.role)
        return 0
    if args.limit < 1:
        parser.error(
            "--limit must be positive; full runs require an explicit task count"
        )
    if args.select and args.benchmark == "all":
        parser.error("Use --select with one benchmark because subset formats differ")
    selection = args.select.resolve() if args.select else None
    if selection and not selection.is_file():
        parser.error("Selection file does not exist")
    names = BENCHMARKS if args.benchmark == "all" else (args.benchmark,)
    modes = MODES if args.mode == "both" else (args.mode,)
    if args.action == "preflight":
        if args.benchmark != "saber":
            parser.error(
                "preflight currently supports saber; use doctor and runner checks for OAS/TB"
            )
        with tempfile.TemporaryDirectory(prefix="api-preflight-") as temporary:
            config = Path(temporary) / "saber.json"
            private_json(config, config_data("saber", env, False))
            for mode in modes:
                cwd, command = commands(
                    "saber", mode, env, args.limit, selection, config
                )
                subprocess.run(
                    command + ["--preflight-only"], cwd=cwd, env=env, check=True
                )
        return 0
    if args.action == "run":
        # Validate every selected paid role before starting the first benchmark.
        for name in names:
            config_data(name, env, True)
            if name == "oas":
                role_config(env, "npc", True)
    for name in names:
        if args.action == "plan":
            print(json.dumps(config_data(name, env, False), indent=2))
            for mode in modes:
                cwd, command = commands(
                    name,
                    mode,
                    env,
                    args.limit,
                    selection,
                    Path("<temporary-model.json>"),
                )
                print(f"\n{name}/{mode} cwd={cwd}\n{shlex.join(command)}")
        elif args.action == "run":
            launch(name, modes, env, args.limit, selection)
        elif name == "terminalbench":
            # Harbor executes task verifiers during run; no LLM judge is needed.
            results = sorted(
                (REPORTS / run_id(env) / "terminalbench").glob("*/*/result.json")
            )
            if not results:
                raise ValueError(
                    "No Terminal-Bench job results found; run inference first"
                )
            for result in results:
                data = json.loads(result.read_text())
                print(
                    json.dumps(
                        {
                            "file": str(result),
                            "stats": data.get("stats"),
                            "n_trials": data.get("n_trials"),
                        },
                        indent=2,
                    )
                )
        elif name == "saber":
            cfg = role_config(env, "judge", True)
            child_env = env.copy()
            child_env.update(
                OSBENCH_JUDGE_KEY=cfg["key"],
                OSBENCH_JUDGE_MODEL=cfg["id"],
                OSBENCH_JUDGE_BASE_URL=saber_judge_base_url(cfg),
                OSBENCH_JUDGE_TYPE=cfg["type"],
                SABER_JUDGED_OUTPUT_ROOT=str(REPORTS / run_id(env) / "saber/judged"),
            )
            if (ROOT / "saber/config.json").exists():
                raise ValueError(
                    "saber/config.json overrides judge env; use --config support before judging"
                )
            for mode in modes:
                slug = f"{run_id(env)}_codex-native-{mode}"
                if not (ROOT / "saber/results" / slug).exists():
                    raise ValueError(f"No SABER inference outputs for {slug}")
                subprocess.run(
                    [python_for(name), "judge_osbench.py", slug],
                    cwd=ROOT / "saber",
                    env=child_env,
                    check=True,
                )
        else:
            if not args.output or args.benchmark == "all":
                parser.error(
                    "judge oas/terminalbench requires --output /path/to/output.jsonl"
                )
            module = "openagentsafety" if name == "oas" else "terminalbench"
            subprocess.run(
                [
                    python_for("oas"),
                    "-m",
                    f"benchmarks.{module}.eval_infer",
                    str(args.output.resolve()),
                ],
                cwd=ROOT / "openagentsafety",
                env=env,
                check=True,
            )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
