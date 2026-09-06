#!/usr/bin/env python3
"""Run SABER Judge v10 with resumable outputs and transport circuit breaking."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Callable

SABER_ROOT = Path("/2024233123/skills/projects/skill/saber")
JUDGE_MODEL = "OpenAI-Mirror/gpt-oss-120b"
VALID_TERMINATIONS = {
    "Safe Refusal", "Safe Completion", "Late Refusal",
    "Harmful Completion", "Accidental Harm", "Incapable",
}

sys.path.insert(0, str(SABER_ROOT))
import judge_osbench as judge  # noqa: E402
JUDGE_MODEL = judge.JUDGE_CFG.get("id", JUDGE_MODEL)
from judge_protocol import (  # noqa: E402
    OUTPUT_SCHEMA_VERSION, PROTOCOL_VERSION, JudgeSchemaError,
    JudgeTransportError, stable_json_sha256,
)
from judge_shadow_protocol import (  # noqa: E402
    file_sha256, gate_report_is_acceptable, source_bundle_sha256,
    source_dependency_snapshot,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("saber_parallel_judge")


@dataclass
class JudgeOutcome:
    task_id: str
    status: str
    failure_class: str | None = None
    error: str | None = None
    path: str | None = None


@dataclass
class ControllerState:
    model: str
    status: str = "queued"
    protocol_version: str = PROTOCOL_VERSION
    total: int = 0
    usable: int = 0
    pending: int = 0
    blocked_input: int = 0
    retryable_schema: int = 0
    transport_pauses: int = 0
    unexpected_failures: int = 0
    active_recovery: bool = False
    next_action: str = "load"
    updated_at: str = ""
    exclusions: list[dict] = field(default_factory=list)
    shadow_gate: dict | None = None

    def update(self, **values) -> None:
        for key, value in values.items():
            setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _source_fingerprint(source_result: dict) -> str:
    return stable_json_sha256(source_result)


def require_shadow_gate(report_path: Path, gold_path: Path) -> dict:
    report = _read_json(report_path)
    if report is None:
        raise RuntimeError(f"shadow gate report is missing or invalid: {report_path}")
    if not gold_path.is_file():
        raise RuntimeError(f"shadow gold file is missing: {gold_path}")
    acceptable, reason = gate_report_is_acceptable(
        report,
        judge_model=JUDGE_MODEL,
        gold_sha256=file_sha256(gold_path),
        source_sha256=source_bundle_sha256(
            source_dependency_snapshot(Path("/2024233123"))
        ),
    )
    if not acceptable:
        raise RuntimeError(f"shadow gate rejected full Judge run: {reason}")
    return report


def _is_usable(existing: dict | None, source_result: dict) -> bool:
    if not existing or existing.get("_judge_model") != JUDGE_MODEL:
        return False
    if existing.get("_judge_protocol") != PROTOCOL_VERSION:
        return False
    if existing.get("_schema_version") != OUTPUT_SCHEMA_VERSION:
        return False
    if existing.get("_source_result_sha256") != _source_fingerprint(source_result):
        return False
    if existing.get("judge_status") != "usable" or existing.get("judge_err"):
        return False
    return (
        existing.get("termination") in VALID_TERMINATIONS
        and isinstance(existing.get("harmful"), bool)
    )


def _save(task: dict, output: dict, model_slug: str, source_result: dict) -> Path:
    output["_judge_model"] = JUDGE_MODEL
    output["_judge_protocol"] = PROTOCOL_VERSION
    output["_schema_version"] = OUTPUT_SCHEMA_VERSION
    output["_source_result_sha256"] = _source_fingerprint(source_result)
    path = judge.judged_path(
        model_slug, task["scenario"], task["category"], task["id"]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)
    return path


def _attempt_path(model_slug: str, task: dict) -> Path:
    final = judge.judged_path(
        model_slug, task["scenario"], task["category"], task["id"]
    )
    attempt_dir = final.parent / "_attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return attempt_dir / f"{task['id']}.{stamp}.json"


def _save_failed_attempt(
    model_slug: str, task: dict, result: dict, failure_class: str,
    exc: BaseException,
) -> Path:
    path = _attempt_path(model_slug, task)
    payload = {
        "_judge_protocol": PROTOCOL_VERSION,
        "_schema_version": OUTPUT_SCHEMA_VERSION,
        "_judge_model": JUDGE_MODEL,
        "_source_result_sha256": _source_fingerprint(result),
        "task_id": task["id"],
        "failure_class": failure_class,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "raw_response": getattr(exc, "raw_response", ""),
        "response_meta": getattr(exc, "response_meta", {}),
        "request_meta": getattr(exc, "request_meta", {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def _judge_one(model_slug: str, task: dict, result: dict) -> JudgeOutcome:
    task_id = task["id"]
    try:
        output = judge.judge_single(task, result)
        if output.get("judge_status") != "usable" or output.get("judge_err"):
            raise JudgeSchemaError(
                f"judge_single returned non-usable status={output.get('judge_status')}",
                raw_response=json.dumps(output, ensure_ascii=False)[:4000],
            )
        path = _save(task, output, model_slug, result)
        return JudgeOutcome(task_id, "usable", path=str(path))
    except JudgeTransportError as exc:
        path = _save_failed_attempt(model_slug, task, result, "transport", exc)
        return JudgeOutcome(task_id, "failed", "transport", str(exc), str(path))
    except JudgeSchemaError as exc:
        path = _save_failed_attempt(model_slug, task, result, "schema", exc)
        return JudgeOutcome(task_id, "failed", "schema", str(exc), str(path))
    except Exception as exc:
        path = _save_failed_attempt(model_slug, task, result, "unexpected", exc)
        return JudgeOutcome(
            task_id, "failed", "unexpected",
            f"{type(exc).__name__}: {exc}", str(path),
        )


def _pairs(model_slug: str) -> list[tuple[dict, dict]]:
    return list(judge.iter_results(model_slug))


def _pending(
    model_slug: str, pairs: list[tuple[dict, dict]]
) -> list[tuple[dict, dict]]:
    pending = []
    for task, result in pairs:
        if result.get("error"):
            continue
        path = judge.judged_path(
            model_slug, task["scenario"], task["category"], task["id"]
        )
        if not _is_usable(_read_json(path), result):
            pending.append((task, result))
    return pending


def _transport_probe() -> None:
    response = judge._normalize_judge_response(
        judge.query_judge('Return exactly this JSON and nothing else: {"ok":true}')
    )
    parsed = judge.parse_judge_json(response.content)
    if not isinstance(parsed, dict) or parsed.get("ok") is not True:
        raise JudgeSchemaError(
            "same-route transport probe returned invalid payload",
            raw_response=response.content,
            response_meta=response.metadata(),
        )


class JudgeController:
    """Small-batch scheduler with a global transport circuit breaker."""

    def __init__(
        self, *, workers: int = 8, batch_size: int = 16,
        max_schema_attempts: int = 3, max_transport_pauses: int = 5,
        pause_seconds: float = 5.0,
        probe_fn: Callable[[], None] = _transport_probe,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        if workers < 1 or batch_size < 1:
            raise ValueError("workers and batch_size must be positive")
        self.workers = workers
        self.batch_size = batch_size
        self.max_schema_attempts = max_schema_attempts
        self.max_transport_pauses = max_transport_pauses
        self.pause_seconds = pause_seconds
        self.probe_fn = probe_fn
        self.sleep_fn = sleep_fn
        self.state: ControllerState | None = None
        self.schema_attempts: dict[str, int] = {}
        self.unexpected_attempts: dict[str, int] = {}

    def _state_path(self, model_slug: str) -> Path:
        path = judge.JUDGED_DIR / model_slug / "_controller_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _persist(self) -> None:
        assert self.state is not None
        self.state.update()
        path = self._state_path(self.state.model)
        path.write_text(json.dumps(asdict(self.state), ensure_ascii=False, indent=2) + "\n")

    def _load(self, model_slug: str, pairs: list[tuple[dict, dict]]) -> None:
        exclusions = [{
            "task_id": task["id"],
            "failure_class": "blocked_input",
            "error": str(result.get("error")),
        } for task, result in pairs if result.get("error")]
        self.state = ControllerState(
            model=model_slug, total=len(pairs), blocked_input=len(exclusions),
            exclusions=exclusions,
        )
        self.state.update(status="loading", next_action="scan_resume_outputs")
        self._persist()

    def _pause_and_probe(self) -> None:
        assert self.state is not None
        while True:
            self.state.transport_pauses += 1
            if self.state.transport_pauses > self.max_transport_pauses:
                self.state.update(
                    status="complete_with_exclusions", active_recovery=False,
                    next_action="operator_check_transport",
                )
                self.state.exclusions.append({
                    "failure_class": "transport",
                    "error": "global transport pause limit exhausted",
                })
                self._persist()
                raise RuntimeError("global transport pause limit exhausted")
            self.state.update(
                status="paused_transport", active_recovery=True,
                next_action="backoff_then_same_route_probe",
            )
            self._persist()
            self.sleep_fn(
                self.pause_seconds * (2 ** (self.state.transport_pauses - 1))
            )
            try:
                self.probe_fn()
            except (JudgeTransportError, JudgeSchemaError) as exc:
                log.warning(
                    "Judge recovery probe failed: pause=%d error=%s",
                    self.state.transport_pauses, exc,
                )
                continue
            self.state.update(
                status="judging", active_recovery=False,
                next_action="resume_exact_pending",
            )
            self._persist()
            return


    def run_model(
        self, model_slug: str, *, shadow_gate: dict | None = None
    ) -> ControllerState:
        pairs = _pairs(model_slug)
        if not pairs:
            raise RuntimeError(f"no raw results found for {model_slug}")
        self._load(model_slug, pairs)
        assert self.state is not None
        self.state.shadow_gate = shadow_gate
        self._persist()

        while True:
            pending = _pending(model_slug, pairs)
            usable = len(pairs) - len(pending) - self.state.blocked_input
            self.state.update(
                status="judging", usable=usable, pending=len(pending),
                next_action="submit_small_batch" if pending else "finalize",
            )
            self._persist()
            if not pending:
                break

            eligible = [
                pair for pair in pending
                if self.schema_attempts.get(pair[0]["id"], 0) < self.max_schema_attempts
                and self.unexpected_attempts.get(pair[0]["id"], 0) < self.max_schema_attempts
            ]
            if not eligible:
                break
            batch = eligible[: self.batch_size]
            outcomes: list[JudgeOutcome] = []
            with ThreadPoolExecutor(max_workers=min(self.workers, len(batch))) as pool:
                futures = {
                    pool.submit(_judge_one, model_slug, task, result): task["id"]
                    for task, result in batch
                }
                for future in as_completed(futures):
                    outcomes.append(future.result())

            transport = [o for o in outcomes if o.failure_class == "transport"]
            for outcome in outcomes:
                if outcome.failure_class == "schema":
                    self.schema_attempts[outcome.task_id] = (
                        self.schema_attempts.get(outcome.task_id, 0) + 1
                    )
                elif outcome.failure_class == "unexpected":
                    self.unexpected_attempts[outcome.task_id] = (
                        self.unexpected_attempts.get(outcome.task_id, 0) + 1
                    )
            self.state.retryable_schema = sum(self.schema_attempts.values())
            self.state.unexpected_failures = sum(self.unexpected_attempts.values())
            self._persist()
            if transport:
                log.warning(
                    "global transport pause: model=%s batch=%d failures=%d first=%s",
                    model_slug, len(batch), len(transport), transport[0].error,
                )
                self._pause_and_probe()

        remaining = _pending(model_slug, pairs)
        exhausted_ids = {
            task_id for task_id, count in {
                **self.schema_attempts, **self.unexpected_attempts
            }.items() if count >= self.max_schema_attempts
        }
        for task, _ in remaining:
            if task["id"] in exhausted_ids:
                self.state.exclusions.append({
                    "task_id": task["id"],
                    "failure_class": (
                        "retryable_schema" if task["id"] in self.schema_attempts
                        else "unexpected"
                    ),
                    "attempts": (
                        self.schema_attempts.get(task["id"])
                        or self.unexpected_attempts.get(task["id"])
                    ),
                })
        self.state.update(
            usable=len(pairs) - len(remaining) - self.state.blocked_input,
            pending=len(remaining),
            status="complete" if not remaining and not self.state.exclusions else "complete_with_exclusions",
            active_recovery=False,
            next_action="none" if not remaining else "review_exclusions",
        )
        self._persist()
        _write_summary(model_slug, pairs, self.state)
        return self.state


def _write_summary(
    model_slug: str, pairs: list[tuple[dict, dict]],
    state: ControllerState | None = None,
) -> Path:
    judged_results = []
    for task, source_result in pairs:
        if source_result.get("error"):
            continue
        path = judge.judged_path(
            model_slug, task["scenario"], task["category"], task["id"]
        )
        output = _read_json(path)
        if _is_usable(output, source_result):
            judged_results.append(output)

    path = judge.JUDGED_DIR / model_slug / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_judge_protocol": PROTOCOL_VERSION,
        "_schema_version": OUTPUT_SCHEMA_VERSION,
        "model": model_slug,
        "judge": {"id": JUDGE_MODEL, "type": "openai", "local": True},
        "source_total": len(pairs),
        "usable_total": len(judged_results),
        "controller": asdict(state) if state else None,
        "summary": judge.compute_summary(judged_results) if judged_results else {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def probe(model_slug: str | None = None) -> None:
    _transport_probe()
    log.info("same-route Judge protocol probe passed%s", f": {model_slug}" if model_slug else "")


def run_model(
    model_slug: str, workers: int, max_attempts: int,
    *, batch_size: int = 16, max_transport_pauses: int = 5,
    pause_seconds: float = 5.0,
    shadow_gate_report: Path | None = None,
    shadow_gold: Path | None = None,
) -> ControllerState:
    controller = JudgeController(
        workers=workers, batch_size=batch_size,
        max_schema_attempts=max_attempts,
        max_transport_pauses=max_transport_pauses,
        pause_seconds=pause_seconds,
    )
    gate = None
    if shadow_gate_report is not None:
        if shadow_gold is None:
            raise RuntimeError("shadow_gold is required with shadow_gate_report")
        report = require_shadow_gate(shadow_gate_report, shadow_gold)
        gate = {
            "report_path": str(shadow_gate_report),
            "gold_path": str(shadow_gold),
            "gold_sha256": report["gold_sha256"],
            "judge_model": report["judge"]["id"],
            "status": report["status"],
            "passed": report["passed"],
            "counts": report["counts"],
        }
    state = controller.run_model(model_slug, shadow_gate=gate)
    log.info(
        "judge terminal: model=%s status=%s usable=%d/%d pending=%d",
        model_slug, state.status, state.usable, state.total, state.pending,
    )
    return state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="*")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-transport-pauses", type=int, default=5)
    parser.add_argument("--pause-seconds", type=float, default=5.0)
    parser.add_argument("--probe", nargs="?", const="")
    parser.add_argument("--shadow-gate-report", type=Path)
    parser.add_argument(
        "--shadow-gold", type=Path,
        default=Path("/2024233123/skills/reports/v10-fixes-20260906/judge_shadow_gold_v10_r2.json"),
    )
    args = parser.parse_args()

    if args.probe is not None:
        probe(args.probe or None)
        return
    if not args.models:
        parser.error("provide at least one model slug or --probe")
    if args.shadow_gate_report is None:
        parser.error("--shadow-gate-report is required for a full Judge run")
    # Validate once before creating any per-model Judge output.
    require_shadow_gate(args.shadow_gate_report, args.shadow_gold)
    for model_slug in args.models:
        run_model(
            model_slug, args.workers, args.max_attempts,
            batch_size=args.batch_size,
            max_transport_pauses=args.max_transport_pauses,
            pause_seconds=args.pause_seconds,
            shadow_gate_report=args.shadow_gate_report,
            shadow_gold=args.shadow_gold,
        )


if __name__ == "__main__":
    main()
