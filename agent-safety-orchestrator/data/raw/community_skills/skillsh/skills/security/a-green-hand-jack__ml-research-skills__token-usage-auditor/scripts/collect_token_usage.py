#!/usr/bin/env python3
"""Collect project token usage from local Codex and Claude Code logs.

The script intentionally stores no prompt/message content. It reads local JSONL
session logs, aggregates provider-reported usage fields, and prints Markdown or
JSON session summaries.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable


USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


@dataclass
class SessionSummary:
    agent: str
    source_file: str
    project_root: str
    session_id: str | None = None
    cwd: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    model_provider: str | None = None
    model: str | None = None
    git_branch: str | None = None
    usage: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    usage_events: int = 0

    def add_usage(self, usage: dict[str, Any]) -> None:
        for key in USAGE_FIELDS:
            value = usage.get(key)
            if isinstance(value, int):
                self.usage[key] += value
        self.usage_events += 1

    def finalize_usage(self) -> dict[str, int]:
        usage = {key: int(self.usage.get(key, 0)) for key in USAGE_FIELDS}

        if self.agent.startswith("codex"):
            total_context = usage["total_tokens"]
            if total_context == 0:
                total_context = usage["input_tokens"] + usage["output_tokens"]
            cached = usage["cached_input_tokens"]
            fresh = max(usage["input_tokens"] - cached, 0) + usage["output_tokens"]
        else:
            total_context = (
                usage["input_tokens"]
                + usage["cache_creation_input_tokens"]
                + usage["cache_read_input_tokens"]
                + usage["output_tokens"]
            )
            cached = usage["cache_read_input_tokens"]
            fresh = (
                usage["input_tokens"]
                + usage["cache_creation_input_tokens"]
                + usage["output_tokens"]
            )

        usage["total_context_tokens"] = total_context
        usage["fresh_tokens"] = fresh
        usage["cached_tokens"] = cached
        return usage

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "source_file": self.source_file,
            "project_root": self.project_root,
            "session_id": self.session_id,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "model_provider": self.model_provider,
            "model": self.model,
            "git_branch": self.git_branch,
            "usage_events": self.usage_events,
            "usage": self.finalize_usage(),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="Project root to match against cwd fields.")
    parser.add_argument("--since", help="Inclusive start date or timestamp, e.g. 2026-05-01.")
    parser.add_argument("--until", help="Inclusive end date or timestamp, e.g. 2026-05-31.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Write output to this file instead of stdout.")
    parser.add_argument("--codex-root", default="~/.codex/sessions", help="Codex sessions root.")
    parser.add_argument("--claude-root", default="~/.claude/projects", help="Claude Code projects root.")
    parser.add_argument("--no-codex", action="store_true", help="Skip Codex logs.")
    parser.add_argument("--no-claude", action="store_true", help="Skip Claude Code logs.")
    parser.add_argument("--no-sidecars", action="store_true", help="Skip repo-local .agent/sidecars model metadata.")
    return parser.parse_args()


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    try:
        if len(text) == 10:
            return datetime.combine(date.fromisoformat(text), time.min, tzinfo=timezone.utc)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def parse_until(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if len(text) == 10:
        try:
            return datetime.combine(date.fromisoformat(text), time.max, tzinfo=timezone.utc)
        except ValueError:
            return None
    return parse_timestamp(text)


def in_window(timestamp: str | None, since: datetime | None, until: datetime | None) -> bool:
    parsed = parse_timestamp(timestamp)
    if parsed is None:
        return since is None and until is None
    if since is not None and parsed < since:
        return False
    if until is not None and parsed > until:
        return False
    return True


def safe_json_lines(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    yield parsed
    except OSError:
        return


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def path_is_within(path_value: str | None, root: Path) -> bool:
    if not path_value:
        return False
    path = resolve_path(path_value)
    return path == root or root in path.parents


def update_time_bounds(summary: SessionSummary, timestamp: str | None) -> None:
    if not timestamp:
        return
    if summary.started_at is None or timestamp < summary.started_at:
        summary.started_at = timestamp
    if summary.ended_at is None or timestamp > summary.ended_at:
        summary.ended_at = timestamp


def collect_codex_file(path: Path, project_root: Path, since: datetime | None, until: datetime | None) -> SessionSummary | None:
    summary = SessionSummary(agent="codex", source_file=str(path), project_root=str(project_root))
    matched_project = False

    for record in safe_json_lines(path):
        timestamp = record.get("timestamp")

        if record.get("type") == "session_meta":
            payload = record.get("payload") or {}
            if isinstance(payload, dict):
                summary.session_id = summary.session_id or payload.get("id")
                summary.cwd = summary.cwd or payload.get("cwd")
                summary.model_provider = summary.model_provider or payload.get("model_provider")
                summary.model = summary.model or payload.get("model")
                matched_project = matched_project or path_is_within(payload.get("cwd"), project_root)

        payload = record.get("payload") or {}
        if isinstance(payload, dict):
            cwd = payload.get("cwd")
            matched_project = matched_project or path_is_within(cwd, project_root)
            if summary.cwd is None and isinstance(cwd, str):
                summary.cwd = cwd

        if not in_window(timestamp, since, until):
            continue

        if record.get("type") == "event_msg" and isinstance(payload, dict) and payload.get("type") == "token_count":
            info = payload.get("info") or {}
            if isinstance(info, dict):
                usage = info.get("last_token_usage") or {}
                if isinstance(usage, dict):
                    summary.add_usage(usage)
                    update_time_bounds(summary, timestamp)

    if not matched_project or summary.usage_events == 0:
        return None
    return summary


def collect_claude_file(path: Path, project_root: Path, since: datetime | None, until: datetime | None) -> SessionSummary | None:
    summary = SessionSummary(agent="claude-code", source_file=str(path), project_root=str(project_root))
    matched_project = False
    seen_usage_keys: set[str] = set()

    for record in safe_json_lines(path):
        timestamp = record.get("timestamp")
        cwd = record.get("cwd")
        matched_project = matched_project or path_is_within(cwd, project_root)
        if summary.cwd is None and isinstance(cwd, str):
            summary.cwd = cwd
        if summary.session_id is None and isinstance(record.get("sessionId"), str):
            summary.session_id = record["sessionId"]
        if summary.git_branch is None and isinstance(record.get("gitBranch"), str):
            summary.git_branch = record["gitBranch"]

        if not in_window(timestamp, since, until):
            continue

        message = record.get("message") or {}
        if not isinstance(message, dict):
            continue
        usage = message.get("usage") or {}
        if not isinstance(usage, dict):
            continue

        usage_key = record.get("requestId") or message.get("id") or record.get("uuid")
        if isinstance(usage_key, str) and usage_key in seen_usage_keys:
            continue
        if isinstance(usage_key, str):
            seen_usage_keys.add(usage_key)

        if summary.model is None and isinstance(message.get("model"), str):
            summary.model = message["model"]
        summary.model_provider = summary.model_provider or "anthropic"
        summary.add_usage(usage)
        update_time_bounds(summary, timestamp)

    if not matched_project or summary.usage_events == 0:
        return None
    return summary


def collect_sidecar_model_file(path: Path, project_root: Path, since: datetime | None, until: datetime | None) -> SessionSummary | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    created_at = payload.get("created_at")
    if isinstance(created_at, str) and not in_window(created_at, since, until):
        return None

    repo = payload.get("repo")
    cwd = repo if isinstance(repo, str) else str(project_root)
    summary = SessionSummary(
        agent="codex-sidecar",
        source_file=str(path),
        project_root=str(project_root),
        session_id=f"sidecar:{payload.get('task_id')}" if payload.get("task_id") else None,
        cwd=cwd,
        started_at=created_at if isinstance(created_at, str) else None,
        ended_at=created_at if isinstance(created_at, str) else None,
        model_provider=payload.get("model_provider") if isinstance(payload.get("model_provider"), str) else "openai",
        model=payload.get("model") if isinstance(payload.get("model"), str) else None,
    )

    usage = payload.get("usage") or {}
    if isinstance(usage, dict) and any(isinstance(usage.get(key), int) for key in USAGE_FIELDS):
        summary.add_usage(usage)

    return summary


def collect_sessions(args: argparse.Namespace) -> list[SessionSummary]:
    project_root = resolve_path(args.project_root)
    since = parse_timestamp(args.since)
    until = parse_until(args.until)
    sessions: list[SessionSummary] = []

    if not args.no_sidecars:
        sidecar_root = project_root / ".agent" / "sidecars"
        if sidecar_root.exists():
            for path in sorted(sidecar_root.glob("*/model.json")):
                summary = collect_sidecar_model_file(path, project_root, since, until)
                if summary is not None:
                    sessions.append(summary)

    if not args.no_codex:
        codex_root = resolve_path(args.codex_root)
        if codex_root.exists():
            for path in sorted(codex_root.rglob("*.jsonl")):
                summary = collect_codex_file(path, project_root, since, until)
                if summary is not None:
                    sessions.append(summary)

    if not args.no_claude:
        claude_root = resolve_path(args.claude_root)
        if claude_root.exists():
            for path in sorted(claude_root.rglob("*.jsonl")):
                summary = collect_claude_file(path, project_root, since, until)
                if summary is not None:
                    sessions.append(summary)

    return sorted(sessions, key=lambda item: (item.started_at or "", item.agent, item.source_file))


def aggregate_by_agent(sessions: list[SessionSummary]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for session in sessions:
        agent_totals = totals.setdefault(session.agent, defaultdict(int))
        agent_totals["session_count"] += 1
        agent_totals["usage_events"] += session.usage_events
        for key, value in session.finalize_usage().items():
            agent_totals[key] += value
    return {agent: dict(values) for agent, values in totals.items()}


def fmt_int(value: int) -> str:
    return f"{value:,}"


def render_markdown(sessions: list[SessionSummary], args: argparse.Namespace) -> str:
    project_root = str(resolve_path(args.project_root))
    totals = aggregate_by_agent(sessions)
    lines = [
        "# Token Usage Report",
        "",
        f"- Project root: `{project_root}`",
        f"- Since: `{args.since or 'beginning'}`",
        f"- Until: `{args.until or 'now'}`",
        f"- Sessions matched: {len(sessions)}",
        "",
        "## Summary By Agent",
        "",
        "| Agent | Sessions | Usage events | Total context | Fresh tokens | Cached tokens | Output | Reasoning |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    if not totals:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
    else:
        for agent, usage in sorted(totals.items()):
            lines.append(
                "| {agent} | {sessions} | {events} | {total} | {fresh} | {cached} | {output} | {reasoning} |".format(
                    agent=agent,
                    sessions=fmt_int(usage.get("session_count", 0)),
                    events=fmt_int(usage.get("usage_events", 0)),
                    total=fmt_int(usage.get("total_context_tokens", 0)),
                    fresh=fmt_int(usage.get("fresh_tokens", 0)),
                    cached=fmt_int(usage.get("cached_tokens", 0)),
                    output=fmt_int(usage.get("output_tokens", 0)),
                    reasoning=fmt_int(usage.get("reasoning_output_tokens", 0)),
                )
            )

    lines.extend(
        [
            "",
            "## Session Details",
            "",
            "| Agent | Start | End | Model | Branch | Fresh | Total context | Cached | Source |",
            "|---|---|---|---|---|---:|---:|---:|---|",
        ]
    )

    for session in sessions:
        usage = session.finalize_usage()
        source = Path(session.source_file).name
        lines.append(
            "| {agent} | {start} | {end} | {model} | {branch} | {fresh} | {total} | {cached} | `{source}` |".format(
                agent=session.agent,
                start=session.started_at or "",
                end=session.ended_at or "",
                model=session.model or "",
                branch=session.git_branch or "",
                fresh=fmt_int(usage["fresh_tokens"]),
                total=fmt_int(usage["total_context_tokens"]),
                cached=fmt_int(usage["cached_tokens"]),
                source=source,
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            "- `total_context_tokens` includes cached context when reported.",
            "- `fresh_tokens` excludes cache reads and cached Codex input where possible.",
            "- This report does not store raw prompts or message content.",
            "- High token burn should be interpreted with artifacts, outcomes, and friction signals.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_json(sessions: list[SessionSummary], args: argparse.Namespace) -> str:
    payload = {
        "project_root": str(resolve_path(args.project_root)),
        "since": args.since,
        "until": args.until,
        "summary_by_agent": aggregate_by_agent(sessions),
        "sessions": [session.to_dict() for session in sessions],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    args = parse_args()
    sessions = collect_sessions(args)
    rendered = render_json(sessions, args) if args.format == "json" else render_markdown(sessions, args)

    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
