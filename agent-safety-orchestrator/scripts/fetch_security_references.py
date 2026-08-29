#!/usr/bin/env python3

"""Fetch security taxonomy / standards / practice-guide reference material.

Source 5 in the project book is qualitatively different from sources 1-3:
each item is a hand-picked authoritative document, not a row in some
upstream catalog. So this script carries an internal **curated reference
list** (see REFERENCES below) instead of a search-and-paginate loop.

Each reference is downloaded into:

    data/raw/references/<source>/<category>/<doc-slug>/
        <files...>            (the upstream documents, byte-identical)
        metadata.json         (source URL, fetched_at, file count, etc.)

References do NOT enter the atomic skill library. They feed the
attack-surface taxonomy and risk dimensions used by Module 1.4 (semantic
alignment) and Module 3 (Safety Router phase mapping).

To add a new reference: append an entry to REFERENCES; the schema is
documented inline.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "references"
DEFAULT_CATEGORY = "security"
DEFAULT_REQUEST_DELAY = 0.5  # be polite to varied hosts


# ---------------------------------------------------------------------------
# Curated reference list
# ---------------------------------------------------------------------------
# Each entry has:
#   source     : directory under data/raw/references/ (lowercase, hyphens)
#   doc_slug   : directory under <source>/<category>/  (lowercase, hyphens)
#   title      : human-readable title
#   kind       : "standard" | "practice-guide" | "research" | "spec" — purely
#                informational, lands in metadata.json
#   why        : one-line rationale ("what taxonomy slot this fills")
#   license    : if knowable, else None
#   files      : list of {url, filename} pairs (filename relative to doc dir)
# Add new entries here; the rest of the script does not need changes.
REFERENCES: tuple[dict, ...] = (
    # --- Industry standards (taxonomy gold) ---
    {
        "source": "owasp",
        "doc_slug": "agentic-ai-threats",
        "title": "OWASP Agentic AI Threats and Mitigations",
        "kind": "standard",
        "why": "Reference taxonomy for agentic-AI threat surface; aligns with attack-surface dimensions in Module 1",
        "license": "CC BY-SA 4.0",
        "files": [
            {
                "url": "https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/",
                "filename": "agentic-ai-threats.html",
            },
        ],
    },
    {
        "source": "owasp",
        "doc_slug": "llm-top-10",
        "title": "OWASP Top 10 for LLM Applications (2025)",
        "kind": "standard",
        "why": "Canonical LLM-app risk list; risk taxonomy backbone",
        "license": "CC BY-SA 4.0",
        "files": [
            {
                "url": "https://genai.owasp.org/llm-top-10/",
                "filename": "llm-top-10.html",
            },
        ],
    },
    {
        "source": "nist",
        "doc_slug": "ai-rmf-genai-profile",
        "title": "NIST AI 600-1: GenAI Profile of the AI Risk Management Framework",
        "kind": "standard",
        "why": "US government AI risk taxonomy; useful for compliance-aware atomic skills",
        "license": "Public domain (US Government)",
        "files": [
            {
                "url": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf",
                "filename": "NIST.AI.600-1.pdf",
            },
        ],
    },
    {
        "source": "nist",
        "doc_slug": "ai-100-2-adversarial-ml",
        "title": "NIST AI 100-2: Adversarial Machine Learning Taxonomy",
        "kind": "standard",
        "why": "Adversarial ML attack taxonomy; closer to model-level threats but informs Sentinel risk axis",
        "license": "Public domain (US Government)",
        "files": [
            {
                "url": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-2e2025.pdf",
                "filename": "NIST.AI.100-2e2025.pdf",
            },
        ],
    },
    {
        "source": "mitre",
        "doc_slug": "atlas",
        "title": "MITRE ATLAS — Adversarial Threat Landscape for AI Systems",
        "kind": "standard",
        "why": "Tactic/technique taxonomy mirrored on ATT&CK; native YAML data is parseable for direct atomic alignment",
        "license": "Apache-2.0 (atlas-data repo)",
        "files": [
            {
                "url": "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/dist/ATLAS.yaml",
                "filename": "ATLAS.yaml",
            },
            {
                "url": "https://raw.githubusercontent.com/mitre-atlas/atlas-data/main/data/tactics.yaml",
                "filename": "tactics.yaml",
            },
        ],
    },
    {
        "source": "modelcontextprotocol",
        "doc_slug": "security-best-practices",
        "title": "MCP Spec — Security Best Practices (2025-06-18)",
        "kind": "spec",
        "why": "Official MCP threat model + best-practices; canonical reference for MCP-server-class atomic skills",
        "license": "MIT (modelcontextprotocol/modelcontextprotocol)",
        "files": [
            {
                "url": "https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices",
                "filename": "mcp-security-best-practices.html",
            },
        ],
    },
    # --- Vendor research / policy ---
    {
        "source": "anthropic",
        "doc_slug": "responsible-scaling-policy",
        "title": "Anthropic Responsible Scaling Policy",
        "kind": "research",
        "why": "Sentinel/threshold mechanism precedent; direct analog of Module 2 risk thresholding",
        "license": "Anthropic (informational use)",
        "files": [
            {
                "url": "https://www-cdn.anthropic.com/872c653b2d0501d6ab44cf87f43e1dc4853e4d37/Anthropic-Responsible-Scaling-Policy-2024-10-15.pdf",
                "filename": "Anthropic-RSP-2024-10-15.pdf",
            },
        ],
    },
    {
        "source": "lakera",
        "doc_slug": "guide-to-prompt-injection",
        "title": "Lakera — A Guide to Prompt Injection",
        "kind": "research",
        "why": "Prompt-injection taxonomy from a focused vendor; depth on a single attack-surface dimension",
        "license": "All rights reserved (informational use)",
        "files": [
            {
                "url": "https://www.lakera.ai/blog/guide-to-prompt-injection",
                "filename": "guide-to-prompt-injection.html",
            },
        ],
    },
    # --- GitHub practice guides (the source-4 examples that became source-5
    #     references after reclassification) ---
    {
        "source": "slowmist",
        "doc_slug": "openclaw-security-practice-guide",
        "title": "SlowMist — OpenClaw Security Practice Guide",
        "kind": "practice-guide",
        "why": "Agent-facing security practices (project book §1 example); 2.8k stars, high authority",
        "license": "see repo (typically MIT or CC variants)",
        "files": [
            {
                "url": "https://raw.githubusercontent.com/slowmist/openclaw-security-practice-guide/main/README.md",
                "filename": "README.md",
            },
        ],
    },
    {
        "source": "prompt-security",
        "doc_slug": "clawsec-overview",
        "title": "prompt-security/clawsec — Overview README",
        "kind": "practice-guide",
        "why": "Skill-suite-level taxonomy of OpenClaw protections (drift detection, audits, integrity)",
        "license": "see repo",
        "files": [
            {
                "url": "https://raw.githubusercontent.com/prompt-security/clawsec/main/README.md",
                "filename": "README.md",
            },
        ],
    },
    {
        "source": "useai-pro",
        "doc_slug": "openclaw-skills-security",
        "title": "UseAI-pro — Curated Security-First OpenClaw Skills (overview)",
        "kind": "practice-guide",
        "why": "Curated security skill set with stated coverage (prompt injection, supply chain, credential leaks)",
        "license": "see repo",
        "files": [
            {
                "url": "https://raw.githubusercontent.com/UseAI-pro/openclaw-skills-security/main/README.md",
                "filename": "README.md",
            },
        ],
    },
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Fetch a curated set of security taxonomy / standards / "
            "practice-guide references. The list lives in REFERENCES at the "
            "top of this script — edit it to add or remove items."
        )
    )
    p.add_argument("--dest", type=Path, default=DEFAULT_DEST_ROOT,
                   help="Destination root. Default: %(default)s")
    p.add_argument("--category", default=DEFAULT_CATEGORY,
                   help="Local category directory. Default: %(default)s")
    p.add_argument("--source", action="append", dest="sources", default=None,
                   help="Limit to specific source slug(s) (e.g. owasp, nist). Repeat as needed.")
    p.add_argument("--slug", action="append", dest="slugs", default=None,
                   help="Limit to specific doc_slug(s). Repeat as needed.")
    p.add_argument("--overwrite", action="store_true",
                   help="Replace existing destination directories.")
    p.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY,
                   help="Sleep between file downloads. Default: %(default)s")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be fetched without writing files.")
    p.add_argument("--list", action="store_true",
                   help="Print the curated reference list and exit.")
    return p.parse_args()


def urlopen_with_retries(request: urllib.request.Request) -> tuple[bytes, str]:
    """Return (body_bytes, content_type)."""
    last: BaseException | None = None
    for attempt in range(7):
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                return resp.read(), resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            last = e
            if attempt == 6 or e.code in {301, 302, 303, 307, 308, 400, 401, 404}:
                break
            ra = e.headers.get("Retry-After") if e.headers else None
            if e.code == 429:
                try:
                    delay = float(ra) if ra else 10.0 * (attempt + 1)
                except ValueError:
                    delay = 10.0 * (attempt + 1)
            else:
                delay = 1.5 * (attempt + 1)
            time.sleep(delay)
        except (TimeoutError, urllib.error.URLError) as e:
            last = e
            if attempt == 6:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {request.full_url}: {last}") from last


def fetch_url(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 distill-skill-fetcher",
    })
    return urlopen_with_retries(req)


def safe_name(value: str) -> str:
    """Ensure a single-segment safe filename."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    if not cleaned or cleaned == ".." or cleaned == ".":
        raise RuntimeError(f"Unsafe filename: {value!r}")
    return cleaned


def select_references(args: argparse.Namespace) -> list[dict]:
    items = list(REFERENCES)
    if args.sources:
        wanted_sources = {s.lower() for s in args.sources}
        items = [it for it in items if it["source"].lower() in wanted_sources]
    if args.slugs:
        wanted_slugs = {s.lower() for s in args.slugs}
        items = [it for it in items if it["doc_slug"].lower() in wanted_slugs]
    return items


def fetch_one(args: argparse.Namespace, ref: dict) -> dict:
    source = safe_name(ref["source"])
    doc_slug = safe_name(ref["doc_slug"])
    dest = args.dest.expanduser().resolve() / source / args.category / doc_slug

    if dest.exists() and not args.overwrite:
        return {
            "source": source, "doc_slug": doc_slug, "title": ref["title"],
            "status": "skipped-existing", "path": str(dest),
        }

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    saved_files: list[dict] = []
    for file_spec in ref["files"]:
        url = file_spec["url"]
        filename = safe_name(file_spec["filename"])
        body, content_type = fetch_url(url)
        (dest / filename).write_bytes(body)
        saved_files.append({
            "filename": filename,
            "url": url,
            "bytes": len(body),
            "contentType": content_type,
        })
        if args.request_delay > 0:
            time.sleep(args.request_delay)

    metadata = {
        "source": source,
        "docSlug": doc_slug,
        "title": ref["title"],
        "kind": ref.get("kind"),
        "why": ref.get("why"),
        "license": ref.get("license"),
        "fetchedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "files": saved_files,
    }
    (dest / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    return {
        "source": source, "doc_slug": doc_slug, "title": ref["title"],
        "status": "fetched", "path": str(dest), "fileCount": len(saved_files),
    }


def main() -> int:
    args = parse_args()

    if args.list:
        for ref in REFERENCES:
            print(
                f"[{ref['kind']:14s}] {ref['source']}/{ref['doc_slug']}\n"
                f"    {ref['title']}\n"
                f"    why: {ref.get('why', '')}"
            )
        return 0

    refs = select_references(args)
    if not refs:
        print("No references match the selection.", file=sys.stderr)
        return 0
    print(f"Selected {len(refs)} reference(s) to fetch.", file=sys.stderr)

    if args.dry_run:
        for ref in refs:
            files = ", ".join(f["filename"] for f in ref["files"])
            print(f"{ref['source']}/{ref['doc_slug']} | {ref['title']} | files=[{files}]")
        return 0

    saved = skipped = errored = 0
    for ref in refs:
        try:
            result = fetch_one(args, ref)
        except Exception as e:
            errored += 1
            print(f"[err] {ref['source']}/{ref['doc_slug']}: {e}", file=sys.stderr)
            continue
        status = result["status"]
        if status == "fetched":
            saved += 1
            print(f"[ok ] {result['source']}/{result['doc_slug']} "
                  f"({result['fileCount']} file(s)) -> {result['path']}", file=sys.stderr)
        elif status == "skipped-existing":
            skipped += 1
            print(f"[skip] {result['source']}/{result['doc_slug']} (already exists)",
                  file=sys.stderr)

    print(f"Done: saved={saved} skipped-existing={skipped} errors={errored} total={len(refs)}.")
    return 0 if errored == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
