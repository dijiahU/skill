#!/usr/bin/env python3

"""Stage 3 — embedding-based safety relevance ranking.

Reads the Stage 2 manifest, embeds each surviving candidate's relevance text
plus the 20 v2 archetypes via Zhipu embedding-3, computes per-anchor cosine
similarity, and applies the selection rules from
docs/SAFETY_ATOMIC_ARCHETYPES.md §1.4:

    per_anchor_kept = ⋃_a { top-N from {c : cosine(c, a) >= anchor_min_threshold} }
    global_kept     = { c : max-cosine(c, *) >= global_threshold }
    Stage 3 残量    = per_anchor_kept ∪ global_kept

Default thresholds (must be calibrated after first run; see §1.4.1):
    per_anchor_cap        N  = 150
    anchor_min_threshold     = 0.55
    global_threshold      τ  = 0.65

Outputs:
- reports/dedup_stage3_embedding_<date>.json    full manifest (per-candidate
                                                 entries, kept lists, sampling
                                                 buckets for calibration)
- data/cache/embeddings/zhipu_embedding3.pkl    persistent vector cache,
                                                 keyed by sha256 of the
                                                 actual text sent to API

API key is read from the ZHIPU_API_KEY environment variable. NEVER stored
or echoed to disk.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pickle
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

import numpy as np

# Local config — keep import last so module-load failures surface cleanly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _archetypes import ARCHETYPES, anchor_text_for_embedding, ARCHETYPE_LIST_VERSION  # noqa: E402
from _env import load_dotenv  # noqa: E402

# Load .env from project root if present. Shell-exported env vars win.
load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE2_MANIFEST = PROJECT_ROOT / "reports" / "dedup_stage2_filter_2026-05-08.json"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "embeddings" / "zhipu_embedding3.pkl"

DEFAULT_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/embeddings"
DEFAULT_MODEL = "embedding-3"
DEFAULT_BATCH_SIZE = 16
# Zhipu embedding-3 per-input token cap is ~3000. Char-to-token ratio varies:
# English prose ~0.25 tok/char; dense Chinese ~0.6; mixed markdown with tables /
# json / heavy punctuation can spike to ~0.85. We default to 3500 chars (≈2900
# tokens upper bound on dense CJK) and handle the long-tail edge cases with the
# 1210-fallback in call_embedding_api (truncate-and-retry on per-input failure).
DEFAULT_MAX_TEXT_CHARS_SKILL = 3500
DEFAULT_MAX_README_CHARS_MCP = 1200
DEFAULT_PER_ANCHOR_CAP = 150
DEFAULT_ANCHOR_MIN_THRESHOLD = 0.55
DEFAULT_GLOBAL_THRESHOLD = 0.65
EMBEDDING_DIM = 2048

# Section headers we strip from SKILL.md / MCP readme as boilerplate.
# The match is case-insensitive on the first non-whitespace word(s) of a
# markdown header. The matched section spans until the next header of equal
# or shallower depth.
BOILERPLATE_HEADER_RE = re.compile(
    r"^(#{1,6})\s+("
    r"license|licensing"
    r"|installation|install|setup|getting\s+started|quick\s*start"
    r"|contributors?|contributing"
    r"|changelog|change\s*log|release\s+notes|history"
    r"|build\s*status|ci\s+status"
    r"|sponsors?|acknowledg(?:e?ments?)|credits"
    r"|badges?"
    r"|prerequisites"
    r"|examples?"
    r"|faq|frequently\s+asked"
    r"|see\s+also|related"
    r")\b",
    re.IGNORECASE,
)
BADGE_LINE_RE = re.compile(
    r"^\s*\[?!\[[^\]]*\]\([^)]*\)\]?(\([^)]*\))?\s*$"
)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage 3 — embedding-based safety relevance ranking via "
                    "Zhipu embedding-3. Reads the Stage 2 manifest and applies "
                    "per-anchor cap + global threshold selection rules."
    )
    p.add_argument("--stage2-manifest", type=Path, default=DEFAULT_STAGE2_MANIFEST,
                   help="Path to Stage 2 manifest. Default: %(default)s")
    p.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    p.add_argument("--manifest-name", default=None,
                   help="Output filename. Default: dedup_stage3_embedding_<YYYY-MM-DD>.json")
    p.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH,
                   help="Persistent embedding cache. Default: %(default)s")
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p.add_argument("--per-anchor-cap", type=int, default=DEFAULT_PER_ANCHOR_CAP,
                   help="N in §1.4. Default: %(default)s")
    p.add_argument("--anchor-min-threshold", type=float,
                   default=DEFAULT_ANCHOR_MIN_THRESHOLD,
                   help="Per-anchor floor. Default: %(default)s")
    p.add_argument("--global-threshold", type=float, default=DEFAULT_GLOBAL_THRESHOLD,
                   help="Global τ. Default: %(default)s")
    p.add_argument("--max-skill-chars", type=int, default=DEFAULT_MAX_TEXT_CHARS_SKILL)
    p.add_argument("--max-mcp-readme-chars", type=int, default=DEFAULT_MAX_README_CHARS_MCP)
    p.add_argument("--limit", type=int, default=0,
                   help="Cap candidate count for testing (0 = no cap)")
    p.add_argument("--reselect-only", action="store_true",
                   help="Skip embedding API calls; require full cache hit; only re-run selection. "
                        "Use this to retune thresholds without re-paying API cost.")
    p.add_argument("--dry-run-embedding", action="store_true",
                   help="Build texts and check cache, but skip API calls "
                        "(also skip selection). Useful to estimate API spend.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Boilerplate stripping
# ---------------------------------------------------------------------------

def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n") or text.startswith("---\r\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4 :].lstrip("\r\n")
    return text


def strip_html_comments(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


def strip_badge_lines(text: str) -> str:
    out: list[str] = []
    for line in text.split("\n"):
        if BADGE_LINE_RE.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def strip_boilerplate_sections(text: str) -> str:
    """Remove sections whose header matches BOILERPLATE_HEADER_RE.
    A section spans from its header to the next header of equal or shallower depth."""
    lines = text.split("\n")
    out: list[str] = []
    skip_until_level: int | None = None
    for line in lines:
        m = re.match(r"^(#+)\s+(.+?)\s*$", line)
        if m:
            level = len(m.group(1))
            is_boilerplate = bool(BOILERPLATE_HEADER_RE.match(line))
            if skip_until_level is not None and level <= skip_until_level:
                # this header ends or peers a skipped section
                if is_boilerplate:
                    skip_until_level = level
                    continue
                skip_until_level = None
                out.append(line)
            elif is_boilerplate:
                skip_until_level = level
                continue  # drop the header itself
            elif skip_until_level is None:
                out.append(line)
            else:
                continue  # nested header inside skipped section
        else:
            if skip_until_level is None:
                out.append(line)
    # trim leading/trailing whitespace runs
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def normalize_for_embedding(text: str) -> str:
    text = strip_html_comments(text)
    text = strip_badge_lines(text)
    text = strip_boilerplate_sections(text)
    return text


# ---------------------------------------------------------------------------
# Candidate text construction
# ---------------------------------------------------------------------------

def build_skill_relevance_text(skill_dir: Path, max_chars: int) -> str:
    md_path = skill_dir / "SKILL.md"
    if not md_path.is_file():
        return ""
    raw = md_path.read_text(encoding="utf-8", errors="ignore")
    body = strip_frontmatter(raw)
    cleaned = normalize_for_embedding(body)
    return cleaned[:max_chars]


def build_mcp_relevance_text(mcp_dir: Path, max_readme_chars: int, max_chars: int) -> str:
    meta_path = mcp_dir / "metadata.json"
    if not meta_path.is_file():
        return ""
    try:
        d = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    name = str(d.get("name") or d.get("displayName") or d.get("title") or d.get("slug") or "")
    description = str(d.get("description") or d.get("shortDescription") or "")
    readme = str(d.get("readme") or "")
    readme_clean = normalize_for_embedding(readme)[:max_readme_chars] if readme else ""
    parts = [p for p in (name.strip(), description.strip(), readme_clean.strip()) if p]
    text = "\n\n".join(parts)
    return text[:max_chars]


# ---------------------------------------------------------------------------
# Embedding cache
# ---------------------------------------------------------------------------

def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cache(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as f:
            data = pickle.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as e:
        print(f"[cache] failed to load {path}: {e}; starting empty", file=sys.stderr)
        return {}


def save_cache(path: Path, cache: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Zhipu embedding-3 API
# ---------------------------------------------------------------------------

def call_embedding_api(endpoint: str, model: str, api_key: str,
                        inputs: list[str], timeout: int = 60) -> list[np.ndarray]:
    body = json.dumps({"model": model, "input": inputs}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    last_err: BaseException | None = None
    for attempt in range(7):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data") or []
            if len(data) != len(inputs):
                raise RuntimeError(f"API returned {len(data)} embeddings for {len(inputs)} inputs")
            data_sorted = sorted(data, key=lambda d: d.get("index", 0))
            vecs: list[np.ndarray] = []
            for item in data_sorted:
                emb = item.get("embedding")
                if not isinstance(emb, list):
                    raise RuntimeError("Malformed embedding entry")
                vecs.append(np.asarray(emb, dtype=np.float32))
            return vecs
        except urllib.error.HTTPError as e:
            last_err = e
            if attempt == 6 or e.code in {400, 401, 403, 404}:
                msg_body = ""
                try:
                    msg_body = e.read().decode("utf-8", errors="ignore")[:400]
                except Exception:
                    pass
                raise RuntimeError(f"HTTP {e.code} {e.reason}: {msg_body}") from e
            ra = e.headers.get("Retry-After") if e.headers else None
            if e.code == 429:
                try:
                    delay = float(ra) if ra else 5.0 * (attempt + 1)
                except ValueError:
                    delay = 5.0 * (attempt + 1)
            else:
                delay = 1.5 * (attempt + 1)
            print(f"[api] HTTP {e.code}; sleeping {delay:.1f}s and retrying", file=sys.stderr)
            time.sleep(delay)
        except (TimeoutError, urllib.error.URLError) as e:
            last_err = e
            if attempt == 6:
                break
            delay = 1.5 * (attempt + 1)
            print(f"[api] {e}; sleeping {delay:.1f}s and retrying", file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError(f"Embedding API failed: {last_err}") from last_err


def _embed_single_with_truncation(endpoint: str, model: str, api_key: str,
                                    text: str, max_halvings: int = 4) -> np.ndarray:
    """Fallback for per-input 1210 (token cap exceeded): halve the text and
    retry, up to max_halvings times. Returns the embedding of the
    successfully-embedded prefix."""
    current = text
    for attempt in range(max_halvings + 1):
        try:
            return call_embedding_api(endpoint, model, api_key, [current])[0]
        except RuntimeError as e:
            msg = str(e)
            is_token_cap = "1210" in msg or "400 Bad Request" in msg
            if not is_token_cap or attempt == max_halvings:
                raise
            new_len = max(400, len(current) // 2)
            print(f"  [embed-fallback] over-length single text "
                  f"({len(current)} chars → {new_len}); retrying",
                  file=sys.stderr)
            current = current[:new_len]
    raise RuntimeError("unreachable")


def embed_texts(texts: list[str], cache: dict[str, np.ndarray],
                 endpoint: str, model: str, api_key: str,
                 batch_size: int, cache_path: Path | None = None,
                 cache_save_every: int = 5) -> list[np.ndarray]:
    """Embed a list of texts, using cache, batching missing ones to the API.
    Cache mutated in-place. The cache is persisted to disk every
    `cache_save_every` batches so a crash mid-run doesn't lose progress.
    On per-batch 1210 failure, falls back to per-text processing with
    halving-on-overlength for each text in the failing batch."""
    keys = [text_key(t) for t in texts]
    missing_indices = [i for i, k in enumerate(keys) if k not in cache]
    if missing_indices:
        missing_texts = [texts[i] for i in missing_indices]
        print(f"[embed] cache miss: {len(missing_indices)}/{len(texts)} texts; "
              f"calling API in batches of {batch_size}", file=sys.stderr)
        batches_since_save = 0
        for batch_start in range(0, len(missing_texts), batch_size):
            batch = missing_texts[batch_start:batch_start + batch_size]
            batch_idx = missing_indices[batch_start:batch_start + batch_size]
            try:
                vecs = call_embedding_api(endpoint, model, api_key, batch)
            except RuntimeError as e:
                msg = str(e)
                if "1210" in msg or "400 Bad Request" in msg:
                    print(f"  [embed-fallback] batch failed with 1210; "
                          f"processing per-text with truncation", file=sys.stderr)
                    vecs = []
                    for t in batch:
                        vecs.append(_embed_single_with_truncation(
                            endpoint, model, api_key, t))
                else:
                    raise
            for i, vec in zip(batch_idx, vecs):
                cache[keys[i]] = vec
            done = min(batch_start + batch_size, len(missing_texts))
            print(f"  [embed] {done}/{len(missing_texts)} done", file=sys.stderr)
            batches_since_save += 1
            if cache_path is not None and batches_since_save >= cache_save_every:
                save_cache(cache_path, cache)
                batches_since_save = 0
        if cache_path is not None and batches_since_save > 0:
            save_cache(cache_path, cache)
    else:
        print(f"[embed] all {len(texts)} texts cached; no API calls", file=sys.stderr)
    return [cache[k] for k in keys]


# ---------------------------------------------------------------------------
# Cosine + selection
# ---------------------------------------------------------------------------

def cosine_matrix(candidate_vecs: np.ndarray, anchor_vecs: np.ndarray) -> np.ndarray:
    """Return (M, K) array of cosine similarity for M candidates vs K anchors."""
    cand_norms = np.linalg.norm(candidate_vecs, axis=1, keepdims=True)
    anc_norms = np.linalg.norm(anchor_vecs, axis=1, keepdims=True)
    cand_normalized = candidate_vecs / np.where(cand_norms == 0, 1.0, cand_norms)
    anc_normalized = anchor_vecs / np.where(anc_norms == 0, 1.0, anc_norms)
    return cand_normalized @ anc_normalized.T


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    api_key = os.environ.get("ZHIPU_API_KEY", "").strip()
    if not args.dry_run_embedding and not args.reselect_only and not api_key:
        print("ZHIPU_API_KEY env var not set. Export it first.", file=sys.stderr)
        return 2

    if not args.stage2_manifest.is_file():
        print(f"Stage 2 manifest not found: {args.stage2_manifest}", file=sys.stderr)
        return 2

    stage2 = json.loads(args.stage2_manifest.read_text(encoding="utf-8"))
    skill_paths: list[str] = list(stage2["skill"]["kept"])
    mcp_paths: list[str] = list(stage2["mcp"]["kept"])
    if args.limit > 0:
        skill_paths = skill_paths[: args.limit]
        mcp_paths = mcp_paths[: args.limit]
    print(f"Stage 2 → Stage 3 input: {len(skill_paths)} skill + {len(mcp_paths)} mcp",
          file=sys.stderr)

    # ---------- Build relevance texts ----------
    candidates: list[dict] = []
    for path in skill_paths:
        text = build_skill_relevance_text(PROJECT_ROOT / path, args.max_skill_chars)
        if not text:
            continue
        candidates.append({"path": path, "kind": "skill", "text": text})
    for path in mcp_paths:
        text = build_mcp_relevance_text(
            PROJECT_ROOT / path, args.max_mcp_readme_chars, args.max_skill_chars)
        if not text:
            continue
        candidates.append({"path": path, "kind": "mcp", "text": text})
    print(f"Constructed relevance_text for {len(candidates)} candidates "
          f"(empty texts skipped)", file=sys.stderr)

    # ---------- Anchor texts ----------
    anchor_texts = [anchor_text_for_embedding(arc) for arc in ARCHETYPES]
    anchor_ids = [arc["id"] for arc in ARCHETYPES]

    # ---------- Cache ----------
    cache = load_cache(args.cache_path)
    print(f"[cache] {len(cache)} vectors loaded from {args.cache_path}", file=sys.stderr)

    # ---------- Estimate API spend ----------
    all_texts_for_embed = anchor_texts + [c["text"] for c in candidates]
    keys_needed = [text_key(t) for t in all_texts_for_embed]
    cache_misses = sum(1 for k in keys_needed if k not in cache)
    print(f"[plan] total texts to embed: {len(all_texts_for_embed)} "
          f"(cache hit: {len(all_texts_for_embed) - cache_misses}, "
          f"miss: {cache_misses})", file=sys.stderr)

    if args.dry_run_embedding:
        approx_tokens = sum(len(t) for t in all_texts_for_embed if text_key(t) not in cache) // 3
        print(f"[dry-run] would call API for {cache_misses} texts "
              f"(~{approx_tokens:,} tokens, est. cost ¥{approx_tokens / 1_000_000 * 0.5:.2f} "
              f"@ assumed ¥0.5/M tok)", file=sys.stderr)
        return 0

    if args.reselect_only and cache_misses > 0:
        print(f"[reselect-only] {cache_misses} cache miss(es); cannot reselect "
              f"without re-embedding. Run without --reselect-only first.",
              file=sys.stderr)
        return 2

    # ---------- Embed ----------
    print("[embed] embedding anchors...", file=sys.stderr)
    anchor_vecs_list = embed_texts(
        anchor_texts, cache, args.endpoint, args.model, api_key,
        args.batch_size, cache_path=args.cache_path)
    print("[embed] embedding candidates...", file=sys.stderr)
    cand_vecs_list = embed_texts(
        [c["text"] for c in candidates], cache,
        args.endpoint, args.model, api_key, args.batch_size,
        cache_path=args.cache_path)

    anchor_vecs = np.stack(anchor_vecs_list).astype(np.float32)
    cand_vecs = np.stack(cand_vecs_list).astype(np.float32)
    print(f"[embed] anchor matrix {anchor_vecs.shape}, candidate matrix {cand_vecs.shape}",
          file=sys.stderr)

    # ---------- Cosine ----------
    sim = cosine_matrix(cand_vecs, anchor_vecs)  # (M, K)
    print(f"[score] cosine matrix computed, shape {sim.shape}", file=sys.stderr)

    # ---------- Selection ----------
    M, K = sim.shape
    max_score = sim.max(axis=1)
    top1_idx = sim.argmax(axis=1)

    # per-anchor top-N (with floor)
    per_anchor_keep: dict[int, set[int]] = {a: set() for a in range(K)}
    for a in range(K):
        col = sim[:, a]
        eligible = np.where(col >= args.anchor_min_threshold)[0]
        if len(eligible) == 0:
            continue
        eligible_scores = col[eligible]
        order = np.argsort(-eligible_scores)
        keep_local = eligible[order[: args.per_anchor_cap]]
        per_anchor_keep[a] = set(int(i) for i in keep_local)
    per_anchor_kept_indices = set().union(*per_anchor_keep.values())
    global_kept_indices = set(int(i) for i in np.where(max_score >= args.global_threshold)[0])
    kept_indices = per_anchor_kept_indices | global_kept_indices
    print(f"[select] per_anchor_kept={len(per_anchor_kept_indices)} "
          f"global_kept={len(global_kept_indices)} "
          f"union={len(kept_indices)}", file=sys.stderr)

    # ---------- Per-candidate manifest entries ----------
    candidate_entries: list[dict] = []
    for i, c in enumerate(candidates):
        scores = sim[i]
        order = np.argsort(-scores)[:3]
        top3 = [(anchor_ids[j], float(scores[j])) for j in order]
        all_scores = {anchor_ids[j]: float(scores[j]) for j in range(K)}
        kept_by: list[str] = []
        if i in per_anchor_kept_indices:
            kept_by.append("per_anchor")
        if i in global_kept_indices:
            kept_by.append("global_threshold")
        candidate_entries.append({
            "path": c["path"],
            "kind": c["kind"],
            "max_score": float(max_score[i]),
            "top1_anchor": anchor_ids[int(top1_idx[i])],
            "top1_score": float(scores[int(top1_idx[i])]),
            "top3_anchors": top3,
            "all_scores": all_scores,
            "kept": i in kept_indices,
            "kept_by": kept_by,
        })

    # ---------- Calibration sampling buckets (for §1.4.1) ----------
    calibration: dict[str, dict] = {}
    for a, arc_id in enumerate(anchor_ids):
        col = sim[:, a]
        order = np.argsort(-col)
        ranked = [(int(i), float(col[i])) for i in order]
        # top 30
        top30 = ranked[:30]
        # candidates with score in [0.63, 0.67] (around τ=0.65) — take 30
        near_global = [(i, s) for i, s in ranked if 0.63 <= s <= 0.67][:30]
        # candidates with score in [0.55, 0.65) — take 30
        in_band = [(i, s) for i, s in ranked if 0.55 <= s < 0.65][:30]
        calibration[arc_id] = {
            "top30": [{"path": candidates[i]["path"], "score": s} for i, s in top30],
            "near_global_threshold": [
                {"path": candidates[i]["path"], "score": s} for i, s in near_global
            ],
            "in_anchor_min_band": [
                {"path": candidates[i]["path"], "score": s} for i, s in in_band
            ],
            "raw_score_distribution": {
                "p50": float(np.percentile(col, 50)),
                "p90": float(np.percentile(col, 90)),
                "p95": float(np.percentile(col, 95)),
                "p99": float(np.percentile(col, 99)),
                "max": float(col.max()),
                "count_ge_055": int((col >= 0.55).sum()),
                "count_ge_065": int((col >= 0.65).sum()),
                "count_ge_075": int((col >= 0.75).sum()),
            },
        }

    # ---------- Per-anchor + per-kind summary ----------
    per_anchor_summary: list[dict] = []
    for a, arc_id in enumerate(anchor_ids):
        kept_idx = per_anchor_keep.get(a, set())
        skill_count = sum(1 for i in kept_idx if candidates[i]["kind"] == "skill")
        mcp_count = sum(1 for i in kept_idx if candidates[i]["kind"] == "mcp")
        per_anchor_summary.append({
            "anchor": arc_id,
            "phase": ARCHETYPES[a]["phase"],
            "kept_total": len(kept_idx),
            "kept_skill": skill_count,
            "kept_mcp": mcp_count,
            "score_p99": calibration[arc_id]["raw_score_distribution"]["p99"],
            "score_max": calibration[arc_id]["raw_score_distribution"]["max"],
        })

    skill_kept = sorted([candidates[i]["path"] for i in kept_indices if candidates[i]["kind"] == "skill"])
    mcp_kept = sorted([candidates[i]["path"] for i in kept_indices if candidates[i]["kind"] == "mcp"])

    # ---------- Print summary ----------
    print()
    print(f"=== Stage 3 result ===")
    print(f"Input candidates  : {len(candidates)} ({sum(1 for c in candidates if c['kind']=='skill')} skill + "
          f"{sum(1 for c in candidates if c['kind']=='mcp')} mcp)")
    print(f"Per-anchor kept   : {len(per_anchor_kept_indices)} (cap={args.per_anchor_cap}, "
          f"min_thr={args.anchor_min_threshold})")
    print(f"Global threshold  : {len(global_kept_indices)} (τ={args.global_threshold})")
    print(f"Union (residual)  : {len(kept_indices)} ({len(skill_kept)} skill + {len(mcp_kept)} mcp)")
    print(f"\nPer-anchor breakdown (sorted by kept count):")
    for s in sorted(per_anchor_summary, key=lambda x: -x["kept_total"]):
        print(f"  {s['anchor']:42s} kept={s['kept_total']:3d} "
              f"(skill={s['kept_skill']:3d} mcp={s['kept_mcp']:3d})  "
              f"p99={s['score_p99']:.3f} max={s['score_max']:.3f}")

    # ---------- Write manifest ----------
    today = datetime.date.today().isoformat()
    manifest_name = args.manifest_name or f"dedup_stage3_embedding_{today}.json"
    manifest_path = args.reports_dir.expanduser().resolve() / manifest_name
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "stage3-embedding",
        "ranAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "stage2Manifest": str(args.stage2_manifest.resolve().relative_to(PROJECT_ROOT.resolve())),
        "archetypeListVersion": ARCHETYPE_LIST_VERSION,
        "model": args.model,
        "embeddingDim": EMBEDDING_DIM,
        "thresholds": {
            "perAnchorCap": args.per_anchor_cap,
            "anchorMinThreshold": args.anchor_min_threshold,
            "globalThreshold": args.global_threshold,
            "maxSkillChars": args.max_skill_chars,
            "maxMcpReadmeChars": args.max_mcp_readme_chars,
        },
        "summary": {
            "inputCandidates": len(candidates),
            "perAnchorKept": len(per_anchor_kept_indices),
            "globalKept": len(global_kept_indices),
            "unionKept": len(kept_indices),
            "skillKept": len(skill_kept),
            "mcpKept": len(mcp_kept),
        },
        "perAnchorSummary": per_anchor_summary,
        "kept": {
            "skill": skill_kept,
            "mcp": mcp_kept,
        },
        "candidates": candidate_entries,
        "calibrationSamples": calibration,
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nManifest written: {manifest_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
