#!/usr/bin/env python3

"""Fetch security-related skills from ClawHub.

ClawHub is a large community marketplace. This script queries security-oriented
terms, deduplicates results, optionally caps the number of downloaded skills,
and extracts each zip package into the project's community skill storage layout.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "community_skills"
DEFAULT_API_BASE = "https://clawhub.ai/api/v1"
DEFAULT_PROVIDER = "clawhub"
DEFAULT_COLLECTION = "skills"
DEFAULT_CATEGORY = "security"
DEFAULT_PER_QUERY_LIMIT = 1000
DEFAULT_MAX_SKILLS = 0
DEFAULT_QUERIES = (
    "security",
    "security audit",
    "threat model",
    "prompt injection",
    "vulnerability scanner",
    "secret scanner",
    "credential scanner",
    "privacy",
    "compliance",
    "malware scanner",
    "safe install",
    "hardening",
)
SECURITY_FILTER_TERMS = (
    "security",
    "secure",
    "hardening",
    "audit",
    "threat",
    "prompt injection",
    "injection",
    "vulnerability",
    "vulnerabilities",
    "scanner",
    "scan",
    "secret",
    "credential",
    "privacy",
    "compliance",
    "malware",
    "exfiltration",
    "guard",
    "safe install",
)


@dataclass(frozen=True)
class SkillCandidate:
    slug: str
    display_name: str
    summary: str
    score: float | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch security-related community skills from ClawHub with a bounded, "
            "repeatable search-and-download workflow."
        )
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help="ClawHub API base URL. Default: %(default)s",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST_ROOT,
        help=(
            "Destination root. Skills are stored as "
            "<dest>/clawhub/skills/security/<slug>. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        help="Provider directory below the destination root. Default: %(default)s",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="Collection directory below the provider. Default: %(default)s",
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help="Category directory below the collection. Default: %(default)s",
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        default=None,
        help=(
            "Search query to run against ClawHub. Repeat for multiple queries. "
            "Defaults to a security-oriented query set."
        ),
    )
    parser.add_argument(
        "--slug",
        action="append",
        dest="slugs",
        default=None,
        help=(
            "Explicit ClawHub skill slug to fetch. Repeat for multiple slugs. "
            "Explicit slugs are included in addition to search results."
        ),
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="Do not run keyword search; fetch only slugs supplied with --slug.",
    )
    parser.add_argument(
        "--per-query-limit",
        type=int,
        default=DEFAULT_PER_QUERY_LIMIT,
        help="Maximum search results to request per query. Default: %(default)s",
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        default=DEFAULT_MAX_SKILLS,
        help=(
            "Maximum total skills to download after deduplication. Use 0 for no "
            "total cap. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--no-post-filter",
        action="store_true",
        help=(
            "Disable local keyword filtering of search results. This can increase "
            "false positives for broad semantic searches."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing destination skill directories.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected skills without downloading zip files.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=(
            "Optional manifest path to write as JSON. Defaults to no manifest. "
            "Use a path outside individual skill directories."
        ),
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately if a skill fails to download or extract.",
    )
    return parser.parse_args()


def urlopen_with_retries(request: urllib.request.Request) -> bytes:
    last_error: BaseException | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (TimeoutError, urllib.error.URLError) as error:
            last_error = error
            if attempt == 2:
                break
            time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Failed to fetch {request.full_url}: {last_error}") from last_error


def fetch_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "distill-skill-fetcher",
        },
    )
    return json.loads(urlopen_with_retries(request).decode("utf-8"))


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "distill-skill-fetcher"},
    )
    return urlopen_with_retries(request)


def api_url(api_base: str, endpoint: str, params: dict[str, object]) -> str:
    base = api_base.rstrip("/")
    query = urllib.parse.urlencode(
        {key: str(value) for key, value in params.items() if value is not None}
    )
    return f"{base}/{endpoint.lstrip('/')}?{query}" if query else f"{base}/{endpoint.lstrip('/')}"


def normalize_slug(slug: str) -> str:
    normalized = slug.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", normalized):
        raise ValueError(f"Invalid ClawHub slug: {slug}")
    return normalized


def search_skills(
    api_base: str,
    query: str,
    limit: int,
) -> list[SkillCandidate]:
    url = api_url(
        api_base,
        "search",
        {"type": "skills", "q": query, "limit": limit},
    )
    data = fetch_json(url)
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected ClawHub search response for query: {query}")

    candidates = []
    for item in data.get("results", []):
        if not isinstance(item, dict) or not isinstance(item.get("slug"), str):
            continue
        candidates.append(
            SkillCandidate(
                slug=normalize_slug(item["slug"]),
                display_name=str(item.get("displayName") or item["slug"]),
                summary=str(item.get("summary") or ""),
                score=float(item["score"]) if isinstance(item.get("score"), (int, float)) else None,
            )
        )
    return candidates


def is_security_related(candidate: SkillCandidate) -> bool:
    text = f"{candidate.slug}\n{candidate.display_name}\n{candidate.summary}".lower()
    return any(term in text for term in SECURITY_FILTER_TERMS)


def collect_candidates(args: argparse.Namespace) -> list[SkillCandidate]:
    queries = tuple(args.queries or DEFAULT_QUERIES)
    seen: set[str] = set()
    candidates: list[SkillCandidate] = []

    for slug in args.slugs or []:
        normalized = normalize_slug(slug)
        if normalized not in seen:
            seen.add(normalized)
            candidates.append(
                SkillCandidate(
                    slug=normalized,
                    display_name=normalized,
                    summary="Explicitly requested by slug.",
                    score=None,
                )
            )

    if not args.no_search:
        for query in queries:
            print(f"Searching ClawHub for {query!r}", file=sys.stderr)
            for candidate in search_skills(args.api_base, query, args.per_query_limit):
                if candidate.slug in seen:
                    continue
                if not args.no_post_filter and not is_security_related(candidate):
                    continue
                seen.add(candidate.slug)
                candidates.append(candidate)

    if args.max_skills == 0:
        return candidates
    return candidates[: args.max_skills]


def destination_for_skill(
    dest_root: Path,
    provider: str,
    collection: str,
    category: str,
    slug: str,
) -> Path:
    return dest_root / provider / collection / category / slug


def ensure_safe_zip_member(name: str) -> PurePosixPath | None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unsafe path in zip: {name}")
    if not path.parts:
        return None
    return path


def extract_zip_bytes(zip_bytes: bytes, destination: Path) -> int:
    extracted_files = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for member in archive.infolist():
            relative_path = ensure_safe_zip_member(member.filename)
            if relative_path is None or member.is_dir():
                continue

            target = destination.joinpath(*relative_path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))
            extracted_files += 1
    return extracted_files


def download_skill(args: argparse.Namespace, candidate: SkillCandidate) -> dict[str, object]:
    destination = destination_for_skill(
        args.dest.expanduser().resolve(),
        args.provider,
        args.collection,
        args.category,
        candidate.slug,
    )
    if destination.exists():
        if not args.overwrite:
            return {
                "slug": candidate.slug,
                "displayName": candidate.display_name,
                "status": "skipped-existing",
                "path": str(destination),
            }
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    download_url = api_url(args.api_base, "download", {"slug": candidate.slug})
    zip_bytes = fetch_bytes(download_url)

    try:
        file_count = extract_zip_bytes(zip_bytes, destination)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise

    return {
        "slug": candidate.slug,
        "displayName": candidate.display_name,
        "status": "fetched",
        "path": str(destination),
        "fileCount": file_count,
        "downloadUrl": download_url,
    }


def write_manifest(path: Path, payload: object) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.per_query_limit < 1:
        raise ValueError("--per-query-limit must be >= 1")
    if args.max_skills < 0:
        raise ValueError("--max-skills must be >= 0")

    candidates = collect_candidates(args)
    if args.dry_run:
        print(f"Selected {len(candidates)} skill(s); dry run only.")
        for candidate in candidates:
            score = "" if candidate.score is None else f" score={candidate.score:.3f}"
            print(f"{candidate.slug}{score} - {candidate.display_name}")
        return 0

    results = []
    for index, candidate in enumerate(candidates, start=1):
        print(f"[{index}/{len(candidates)}] Fetching {candidate.slug}", file=sys.stderr)
        try:
            results.append(download_skill(args, candidate))
        except Exception as error:
            if args.stop_on_error:
                raise
            results.append(
                {
                    "slug": candidate.slug,
                    "displayName": candidate.display_name,
                    "status": "error",
                    "error": str(error),
                }
            )
            print(f"Error fetching {candidate.slug}: {error}", file=sys.stderr)

    payload = {
        "source": "clawhub",
        "apiBase": args.api_base,
        "destinationRoot": str(args.dest.expanduser().resolve()),
        "provider": args.provider,
        "collection": args.collection,
        "category": args.category,
        "queries": list(args.queries or DEFAULT_QUERIES),
        "perQueryLimit": args.per_query_limit,
        "maxSkills": args.max_skills,
        "results": results,
    }
    if args.manifest:
        write_manifest(args.manifest, payload)

    fetched = sum(1 for result in results if result["status"] == "fetched")
    skipped = sum(1 for result in results if result["status"] == "skipped-existing")
    errors = sum(1 for result in results if result["status"] == "error")
    print(f"Fetched {fetched} skill(s); skipped {skipped} existing skill(s); errors {errors}.")
    for result in results:
        path = result.get("path", "")
        suffix = f" -> {path}" if path else ""
        print(f"{result['status']}: {result['slug']}{suffix}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
