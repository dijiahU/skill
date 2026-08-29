#!/usr/bin/env python3
"""LLM audit for sub-tasks 1.2 + 1.3 (combined): classify Stage 3 residual
candidates against the v0.3 atomic capability vocabulary.

Inputs:
  reports/dedup_stage3_embedding_<date>.json
    Stage 3 manifest. We filter `candidates` where `kept=true` (1390 records).

  docs/SAFETY_ATOMIC_CAPABILITIES.md
    Vocabulary source (95 atoms, parsed via scripts/_atomic_capabilities.py).

Outputs:
  reports/llm_audit_classify_<date>.jsonl
    One JSON per line, schema = SAFETY_ATOMIC_CAPABILITIES.md §7.

  reports/llm_audit_classify_<date>_cache/<sha8-of-path>.json
    Per-record cache (resume-friendly; safe to delete a file to force re-audit).

  reports/llm_audit_classify_<date>_failures.jsonl
    One JSON per failed record (after retries) for follow-up.

Model: DeepSeek `deepseek-chat` (V3.2, OpenAI-compatible API).
Pricing (2026): cache-miss $0.27/M input, cache-hit $0.07/M, $1.10/M output.
DeepSeek auto-caches common prefixes, so the vocabulary block (placed first
in the prompt) costs full price only on the first call.

Usage:
  export DEEPSEEK_API_KEY=sk-xxxxxx
  python scripts/llm_audit_stage1_classify.py \
      --stage3-manifest reports/dedup_stage3_embedding_2026-05-08.json \
      --output reports/llm_audit_classify_$(date +%Y-%m-%d).jsonl

  # Test run (no API call, prints first prompt to stdout and exits):
  python scripts/llm_audit_stage1_classify.py --stage3-manifest <m> --output <o> --dry-run --limit 1

  # Subset run for prompt iteration:
  python scripts/llm_audit_stage1_classify.py --stage3-manifest <m> --output <o> --limit 10 --kind skill

  # Resume after interrupt (cache makes this automatic — same command works):
  python scripts/llm_audit_stage1_classify.py --stage3-manifest <m> --output <o>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _atomic_capabilities import (  # noqa: E402
    all_valid_atom_labels,
    atoms_for_prompt,
    load_atoms,
)
from _env import load_dotenv  # noqa: E402

# Load .env file from project root (no-op if file is missing).
# Shell-exported env vars take priority over .env values.
load_dotenv()

# ============================================================
# API key — fill via env var DEEPSEEK_API_KEY, or set _API_KEY below.
# Never commit a real key to git.
# ============================================================
_API_KEY: str = ""  # leave empty; export DEEPSEEK_API_KEY=sk-... in your shell
API_BASE = "https://api.deepseek.com"
MODEL = "deepseek-chat"  # V3.2

# ---- prompt budget knobs ----
MAX_CONTENT_CHARS = 6000        # truncate long SKILL.md / MCP README
MAX_OUTPUT_TOKENS = 1500        # response budget per record
DEFAULT_TEMPERATURE = 0.0       # deterministic classification
DEFAULT_WORKERS = 4
DEFAULT_RETRIES = 3
RETRY_BASE_SLEEP_S = 2.0


# ---- prompt template ----

PROMPT_TEMPLATE_SYSTEM = """You are an expert AI safety engineer auditing candidate "agent safety skills" against a controlled vocabulary of atomic safety capabilities.

For each candidate (a community SKILL.md or an MCP server metadata blob) you produce a single JSON record describing which atomic capabilities the candidate primarily implements, plus structured fields for downstream aggregation. You output ONLY valid JSON — no prose, no code fences, no commentary.

Be conservative when proposing new atoms (use `suggested_new_atoms` only when evidence in the candidate is unambiguous). Be honest about confidence — flag cases below 0.7 confidence so a human can spot-check."""


# Note: vocabulary block is placed FIRST in the user prompt so DeepSeek's
# automatic prefix cache covers it across all 1390 calls.
PROMPT_TEMPLATE_USER = """## Controlled vocabulary (95 atoms)

Each entry has fields: id, parent (parent_archetype), phase, definition, scope_in, scope_out, signal_phrases, related (sibling-disambiguation hints).

```json
{vocabulary_json}
```

## Output schema

You MUST output ONE JSON object matching this schema, no surrounding text:

```json
{schema_example}
```

### Field rules

- `record_id`: copy verbatim from the candidate header below.
- `kind`: copy verbatim from the candidate header ("skill" or "mcp").
- `is_safety_relevant`: bool. Set false if the candidate is non-security, boilerplate-only, or a placeholder. When false, fill `skip_reason` and leave atom arrays empty.
- `skip_reason`: required when `is_safety_relevant=false`. Use one of: "boilerplate-only", "non-security", "placeholder-only", "duplicate-of:<path>".
- `covered_phases`: array of strings. Valid values: "input-understanding", "planning", "tool-invocation", "output-generation", "cross-cutting". Choose all that apply.
- `primary_atoms`: 1-3 atoms describing the candidate's CORE function. Format MUST be EXACTLY `<parent_archetype>/<atom_id>` using IDs from the vocabulary above. Empty array allowed only when vocabulary doesn't fit; in that case you MUST explain in `free_form_notes` AND fill `suggested_new_atoms` if applicable.
- `secondary_atoms`: 0-5 atoms for incidental / secondary functions. Same format.
- `self_risk_flags`: short kebab-case tags describing risks the candidate skill ITSELF brings (NOT the risks it mitigates). Examples: "asks-for-broad-fs-write", "executes-shell-on-install", "requires-network-egress", "stores-secrets-in-plaintext". Empty array if none.
- `suggested_new_atoms`: ONLY fill when the candidate clearly bears a capability not covered by the vocabulary. Be conservative. Each item: `proposed_id` (kebab-case), `suggested_parent_archetype` (use an existing parent or "new-archetype-needed"), `evidence_from_this_record` (brief quote / paraphrase), `rough_definition` (1 sentence). Empty array by default.
- `free_form_notes`: free text for ambiguous / boundary observations, evidence about implementation type (regex / LLM judge / external tool), or hints for human review. Use `null` if nothing to add.
- `confidence`: 0.0-1.0 self-assessment. Use < 0.7 when you are uncertain (so humans spot-check those).

## Candidate to classify

record_id: {path}
kind: {kind}
top3_anchors_from_stage3: {top3_anchors}

### Content
{content}

## Output

Return ONE JSON object only, matching the schema. No code fences, no commentary."""


SCHEMA_EXAMPLE = json.dumps(
    {
        "record_id": "data/raw/community_skills/clawhub/skills/security/secret-detector",
        "kind": "skill",
        "is_safety_relevant": True,
        "skip_reason": None,
        "covered_phases": ["input-understanding", "tool-invocation"],
        "primary_atoms": [
            "validate-tool-argument-safety/detect-shell-command-injection",
            "validate-tool-argument-safety/detect-path-traversal",
        ],
        "secondary_atoms": [
            "constrain-workspace-boundary/enforce-filesystem-sandbox"
        ],
        "self_risk_flags": ["asks-for-broad-fs-write"],
        "suggested_new_atoms": [
            {
                "proposed_id": "verify-oauth-flow-security",
                "suggested_parent_archetype": "validate-tool-argument-safety",
                "evidence_from_this_record": "Validates OAuth state parameter, PKCE, redirect_uri allowlist enforcement",
                "rough_definition": "Validate OAuth flow components for outbound auth flows initiated by the agent",
            }
        ],
        "free_form_notes": "Custom shell-arg sanitizer + a mini OPA policy bundle. OPA is generic; sanitizer is domain-specific.",
        "confidence": 0.85,
    },
    ensure_ascii=False,
    indent=2,
)


# ---- candidate content readers ----


def read_skill_content(record_dir: Path) -> str | None:
    """Read SKILL.md from a skill record directory."""
    skill_md = record_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    return skill_md.read_text(encoding="utf-8", errors="replace")


def read_mcp_content(record_dir: Path) -> str | None:
    """Read MCP metadata.json (and optional README) from an MCP record directory."""
    md = record_dir / "metadata.json"
    if not md.exists():
        return None
    parts = []
    try:
        data = json.loads(md.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        return f"[metadata.json parse error: {e}]\n{md.read_text(encoding='utf-8', errors='replace')[:2000]}"

    # Surface the most relevant fields up top so the LLM sees them first;
    # raw rawRecord is appended after.
    name = data.get("name") or data.get("id") or "(no name)"
    desc = (
        data.get("description")
        or data.get("summary")
        or data.get("rawRecord", {}).get("description")
        or ""
    )
    parts.append(f"# {name}\n\n{desc}\n")

    # Try to find tools / capabilities list — varies by registry
    raw = data.get("rawRecord", {})
    for tools_field in ("tools", "capabilities", "actions"):
        if tools_field in raw and raw[tools_field]:
            parts.append(f"\n## {tools_field}\n```json\n{json.dumps(raw[tools_field], ensure_ascii=False, indent=2)}\n```")
            break

    # README if present in raw
    readme = (
        raw.get("readme")
        or raw.get("README")
        or raw.get("longDescription")
        or ""
    )
    if readme:
        parts.append(f"\n## README\n{readme[:3000]}")

    return "\n".join(parts)


def truncate_content(text: str, max_chars: int = MAX_CONTENT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[... truncated; original length {len(text)} chars]"


def load_candidate_content(record: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (content_text, error_str). One of them is None."""
    rel_path = record["path"]
    abs_path = ROOT / rel_path
    if not abs_path.exists():
        return None, f"path does not exist: {abs_path}"
    if not abs_path.is_dir():
        return None, f"path is not a directory: {abs_path}"

    if record["kind"] == "skill":
        text = read_skill_content(abs_path)
        if text is None:
            return None, "no SKILL.md found"
    elif record["kind"] == "mcp":
        text = read_mcp_content(abs_path)
        if text is None:
            return None, "no metadata.json found"
    else:
        return None, f"unknown kind: {record['kind']}"

    return truncate_content(text), None


# ---- prompt builder ----


def build_user_prompt(
    record: dict[str, Any],
    content: str,
    vocabulary_json: str,
) -> str:
    return PROMPT_TEMPLATE_USER.format(
        vocabulary_json=vocabulary_json,
        schema_example=SCHEMA_EXAMPLE,
        path=record["path"],
        kind=record["kind"],
        top3_anchors=json.dumps(record.get("top3_anchors", []), ensure_ascii=False),
        content=content,
    )


# ---- API call ----


class DeepSeekError(RuntimeError):
    pass


def call_deepseek(
    api_key: str,
    system: str,
    user: str,
    *,
    retries: int = DEFAULT_RETRIES,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    """Call DeepSeek chat/completions, returning parsed JSON content + usage."""
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                f"{API_BASE}/chat/completions",
                headers=headers,
                json=body,
                timeout=120,
            )
            if r.status_code == 200:
                resp = r.json()
                content = resp["choices"][0]["message"]["content"]
                # Some providers wrap json in code fences despite response_format.
                content = _strip_code_fence(content)
                parsed = json.loads(content)
                return {"parsed": parsed, "usage": resp.get("usage", {})}
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = DeepSeekError(f"HTTP {r.status_code}: {r.text[:300]}")
                sleep_s = RETRY_BASE_SLEEP_S * (2**attempt) + random.uniform(0, 1)
                time.sleep(sleep_s)
                continue
            # non-retryable
            raise DeepSeekError(f"HTTP {r.status_code}: {r.text[:500]}")
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_err = e
            sleep_s = RETRY_BASE_SLEEP_S * (2**attempt) + random.uniform(0, 1)
            time.sleep(sleep_s)
            continue
    raise DeepSeekError(f"all {retries + 1} attempts failed; last error: {last_err}")


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n(.*?)\n```\s*$", re.S)


def _strip_code_fence(s: str) -> str:
    m = _FENCE_RE.match(s)
    return m.group(1) if m else s


# ---- output validation ----


def validate_record(
    rec: dict[str, Any],
    valid_labels: set[str],
) -> list[str]:
    """Return list of validation warnings (empty = clean)."""
    warns = []
    required = ("record_id", "kind", "is_safety_relevant", "covered_phases",
                "primary_atoms", "secondary_atoms", "self_risk_flags",
                "suggested_new_atoms", "confidence")
    for f in required:
        if f not in rec:
            warns.append(f"missing field: {f}")

    if not rec.get("is_safety_relevant", True):
        if not rec.get("skip_reason"):
            warns.append("is_safety_relevant=false but skip_reason empty")
    else:
        for label in rec.get("primary_atoms", []) or []:
            if label not in valid_labels:
                warns.append(f"primary_atoms label not in vocabulary: {label}")
        for label in rec.get("secondary_atoms", []) or []:
            if label not in valid_labels:
                warns.append(f"secondary_atoms label not in vocabulary: {label}")

    valid_phases = {
        "input-understanding", "planning", "tool-invocation",
        "output-generation", "cross-cutting",
    }
    for ph in rec.get("covered_phases", []) or []:
        if ph not in valid_phases:
            warns.append(f"unknown phase: {ph}")

    conf = rec.get("confidence")
    if conf is not None and not (0.0 <= float(conf) <= 1.0):
        warns.append(f"confidence out of [0,1]: {conf}")

    return warns


# ---- per-record orchestration ----


def cache_key_for(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


_writer_lock = threading.Lock()
_progress_lock = threading.Lock()


class ProgressTracker:
    """Thread-safe progress + cost tracker."""

    def __init__(self, total: int):
        self.total = total
        self.done = 0
        self.failed = 0
        self.cached = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_hit_tokens = 0
        self.start_t = time.time()

    def tick(self, *, input_t=0, output_t=0, cache_hit_t=0, cached=False, failed=False):
        with _progress_lock:
            self.done += 1
            if cached:
                self.cached += 1
            if failed:
                self.failed += 1
            self.input_tokens += input_t
            self.output_tokens += output_t
            self.cache_hit_tokens += cache_hit_t
            if self.done % 20 == 0 or self.done == self.total:
                self._print_status()

    def _print_status(self):
        elapsed = time.time() - self.start_t
        rate = self.done / max(elapsed, 0.001)
        eta = (self.total - self.done) / max(rate, 0.001)
        cost_in = (
            (self.input_tokens - self.cache_hit_tokens) * 0.27 / 1_000_000
            + self.cache_hit_tokens * 0.07 / 1_000_000
        )
        cost_out = self.output_tokens * 1.10 / 1_000_000
        print(
            f"[{self.done:>4}/{self.total}] cached={self.cached} failed={self.failed} "
            f"in={self.input_tokens:>7} out={self.output_tokens:>6} "
            f"cache_hit={self.cache_hit_tokens:>7} "
            f"~${cost_in + cost_out:.3f}  rate={rate:.2f}/s  eta={int(eta)}s",
            flush=True,
        )


def process_one(
    record: dict[str, Any],
    *,
    api_key: str,
    vocabulary_json: str,
    cache_dir: Path,
    output_path: Path,
    failures_path: Path,
    valid_labels: set[str],
    progress: ProgressTracker,
    dry_run: bool,
    use_cache: bool,
) -> dict[str, Any] | None:
    rel_path = record["path"]
    cache_file = cache_dir / f"{cache_key_for(rel_path)}.json"

    if use_cache and cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        progress.tick(cached=True)
        with _writer_lock:
            with output_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(cached["record"], ensure_ascii=False) + "\n")
        return cached["record"]

    content, err = load_candidate_content(record)
    if err:
        progress.tick(failed=True)
        with _writer_lock:
            with failures_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"path": rel_path, "kind": record["kind"], "error": err}) + "\n")
        return None

    user_prompt = build_user_prompt(record, content or "", vocabulary_json)

    if dry_run:
        print("=" * 80)
        print(f"[dry-run] would call DeepSeek for: {rel_path} (kind={record['kind']})")
        print(f"system tokens (approx chars): {len(PROMPT_TEMPLATE_SYSTEM)}")
        print(f"user prompt chars: {len(user_prompt)}")
        print("--- user prompt (first 2000 chars) ---")
        print(user_prompt[:2000])
        print("--- user prompt (last 1500 chars) ---")
        print(user_prompt[-1500:])
        progress.tick()
        return None

    try:
        resp = call_deepseek(api_key, PROMPT_TEMPLATE_SYSTEM, user_prompt)
    except DeepSeekError as e:
        progress.tick(failed=True)
        with _writer_lock:
            with failures_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "path": rel_path,
                    "kind": record["kind"],
                    "error": f"deepseek error: {e}",
                    "trace": traceback.format_exc(),
                }) + "\n")
        return None

    parsed = resp["parsed"]
    usage = resp["usage"]

    # Force record_id and kind to be authoritative (override any LLM hallucination).
    parsed["record_id"] = rel_path
    parsed["kind"] = record["kind"]

    warns = validate_record(parsed, valid_labels)
    parsed["_validation_warnings"] = warns

    # Cache + write to JSONL
    cache_payload = {"record": parsed, "usage": usage}
    cache_file.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with _writer_lock:
        with output_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(parsed, ensure_ascii=False) + "\n")

    # Token bookkeeping. DeepSeek returns prompt_tokens + completion_tokens
    # plus prompt_cache_hit_tokens (chars cached). Treat missing fields as 0.
    progress.tick(
        input_t=int(usage.get("prompt_tokens", 0)),
        output_t=int(usage.get("completion_tokens", 0)),
        cache_hit_t=int(usage.get("prompt_cache_hit_tokens", 0)),
    )
    return parsed


# ---- main ----


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--stage3-manifest", required=True, type=Path,
                        help="Path to reports/dedup_stage3_embedding_<date>.json")
    parser.add_argument("--output", required=True, type=Path,
                        help="Path for the per-record JSONL audit output")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                        help=f"Concurrent API workers (default {DEFAULT_WORKERS})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only first N records (for prompt iteration)")
    parser.add_argument("--kind", choices=["skill", "mcp"], default=None,
                        help="Process only one kind (for prompt iteration)")
    parser.add_argument("--api-key", default=None,
                        help="DeepSeek API key (overrides DEEPSEEK_API_KEY env var)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip API call; print prompts only")
    parser.add_argument("--no-cache", action="store_true",
                        help="Ignore on-disk per-record cache; force re-audit")
    parser.add_argument("--shuffle", action="store_true",
                        help="Shuffle records before processing (useful for sampled --limit runs)")
    args = parser.parse_args(argv)

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY", "") or _API_KEY
    if not args.dry_run and not api_key:
        print(
            "ERROR: DeepSeek API key not set.\n"
            "Either: export DEEPSEEK_API_KEY=sk-xxxx\n"
            "Or:     pass --api-key sk-xxxx\n"
            "Or:     edit _API_KEY constant at top of this script (NOT recommended for git).",
            file=sys.stderr,
        )
        return 2

    # Load vocabulary
    atoms = load_atoms()
    valid_labels = all_valid_atom_labels(atoms)
    print(f"Loaded {len(atoms)} atoms; {len(valid_labels)} valid labels.", file=sys.stderr)
    vocabulary_json = json.dumps(atoms_for_prompt(atoms), ensure_ascii=False, separators=(",", ":"))
    print(f"Vocabulary block size: {len(vocabulary_json):,} chars (≈{len(vocabulary_json)//4:,} tokens)", file=sys.stderr)

    # Load manifest
    manifest = json.loads(args.stage3_manifest.read_text(encoding="utf-8"))
    candidates = [c for c in manifest["candidates"] if c.get("kept")]
    if args.kind:
        candidates = [c for c in candidates if c["kind"] == args.kind]
    if args.shuffle:
        random.shuffle(candidates)
    if args.limit:
        candidates = candidates[: args.limit]
    total = len(candidates)
    print(f"Will process {total} kept candidates "
          f"({sum(1 for c in candidates if c['kind']=='skill')} skill, "
          f"{sum(1 for c in candidates if c['kind']=='mcp')} mcp)",
          file=sys.stderr)

    # Output paths
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = args.output.with_suffix("").with_name(args.output.stem + "_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    failures_path = args.output.with_suffix("").with_name(args.output.stem + "_failures.jsonl")
    if not args.output.exists():
        args.output.touch()
    if not failures_path.exists():
        failures_path.touch()

    progress = ProgressTracker(total)

    # Run
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(
                process_one,
                rec,
                api_key=api_key,
                vocabulary_json=vocabulary_json,
                cache_dir=cache_dir,
                output_path=args.output,
                failures_path=failures_path,
                valid_labels=valid_labels,
                progress=progress,
                dry_run=args.dry_run,
                use_cache=not args.no_cache,
            )
            for rec in candidates
        ]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:  # noqa: BLE001
                # Defensive: process_one already logs failures to file.
                # This handler catches any pool-internal explosion.
                print(f"[unexpected] {e}\n{traceback.format_exc()}", file=sys.stderr)

    progress._print_status()
    print(f"\nDone. Output JSONL: {args.output}")
    print(f"Cache directory:    {cache_dir}")
    print(f"Failures log:       {failures_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
