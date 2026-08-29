#!/usr/bin/env python3

"""Fetch security-related skills from skillsdirectory.com.

Discovery uses the public /api/skills endpoint (no auth required). The
"testing-security" category (1200+ skills) is fetched by default; --scan-all
walks the full catalog (~34k skills) so security-themed skills filed under
other categories (e.g. tools, devops) are not missed. Each candidate is then
keyword-filtered against name/description/tags/content/slug. Bundles are
downloaded as zip archives via /api/skills/<slug>/download and extracted into
the community skill storage layout.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "community_skills"
DEFAULT_API_BASE = "https://www.skillsdirectory.com"
DEFAULT_MARKETPLACE = "skillsdirectory"
DEFAULT_COLLECTION = "skills"
DEFAULT_CATEGORY = "security"
DEFAULT_UPSTREAM_CATEGORY = "testing-security"
DEFAULT_PAGE_SIZE = 20  # API caps limit at 20 regardless of request
DEFAULT_REQUEST_DELAY = 0.25
DEFAULT_MAX_SKILLS = 0
DEFAULT_WORKERS = 4

SECURITY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsecurity\b",
        r"\bsecure\b",
        r"\bcyber(?:security)?\b",
        r"\bvulnerab",
        r"\bcve(?:-\d{4}-\d+)?\b",
        r"\bthreat",
        r"\bmalware\b",
        r"\bmalicious\b",
        r"\bexploit",
        r"\bpentest",
        r"penetration test",
        r"\bred team\b",
        r"\bblue team\b",
        r"prompt injection",
        r"\bjailbreak",
        r"\bsecret(?:s)?\b",
        r"\bcredential",
        r"\bpassword",
        r"\bauthentication\b",
        r"\bauthorization\b",
        r"\bauthn\b",
        r"\bauthz\b",
        r"\boauth\b",
        r"\boidc\b",
        r"\bsaml\b",
        r"\brbac\b",
        r"access control",
        r"\bcompliance\b",
        r"\bprivacy\b",
        r"data protection",
        r"security audit",
        r"code audit",
        r"dependency audit",
        r"smart contract audit",
        r"\baudit log",
        r"\baudit trail",
        r"\bforensic",
        r"incident response",
        r"\bsiem\b",
        r"\bowasp\b",
        r"\bsast\b",
        r"\bdast\b",
        r"\bsbom\b",
        r"supply chain",
        r"container security",
        r"kubernetes security",
        r"cloud security",
        r"\bfirewall\b",
        r"\bwaf\b",
        r"\btls\b",
        r"\bencrypt",
        r"\bcryptograph",
        r"crypto protocol",
        r"\bphishing\b",
        r"\bransomware\b",
        r"\byara\b",
        r"\bctf\b",
        r"zero trust",
        r"least privilege",
        r"policy-as-code",
        r"secrets? scanning",
        r"token leakage",
        r"data loss prevention",
        r"\bdlp\b",
        r"\bmitre\b",
    )
)


@dataclass(frozen=True)
class SkillCandidate:
    slug: str
    name: str
    description: str
    upstream_category: str
    tags: tuple[str, ...]
    content: str
    bundle_files: tuple[dict[str, object], ...]
    source_url: str | None
    github_repo: str | None
    github_branch: str | None
    skill_file_path: str | None
    security_grade: str | None
    security_score: int | None
    discovered_via: str = "category"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch security-related skills from skillsdirectory.com into the "
            "local community skill storage layout."
        )
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help="skillsdirectory.com base URL. Default: %(default)s",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST_ROOT,
        help=(
            "Destination root. Skills are stored as "
            "<dest>/skillsdirectory/skills/security/<slug>. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--marketplace",
        default=DEFAULT_MARKETPLACE,
        help="Marketplace directory under destination root. Default: %(default)s",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="Collection directory under marketplace. Default: %(default)s",
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help="Local category directory under collection. Default: %(default)s",
    )
    parser.add_argument(
        "--upstream-category",
        default=DEFAULT_UPSTREAM_CATEGORY,
        help=(
            "Upstream category slug used for primary discovery. The site groups "
            "testing and security together under 'testing-security'. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--scan-all",
        action="store_true",
        help=(
            "Walk the entire skillsdirectory.com catalog (~34k skills) and let "
            "the keyword filter pick out security candidates from every category. "
            "Slow but catches security skills filed under tools, devops, etc."
        ),
    )
    parser.add_argument(
        "--slug",
        action="append",
        dest="slugs",
        default=None,
        help="Explicit skill slug to fetch. Repeat as needed.",
    )
    parser.add_argument(
        "--no-listing",
        action="store_true",
        help="Skip listing-based discovery and only fetch slugs supplied with --slug.",
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        default=DEFAULT_MAX_SKILLS,
        help="Cap total candidates after dedup and filtering. 0 means no cap.",
    )
    parser.add_argument(
        "--no-content-filter",
        action="store_true",
        help=(
            "Save every discovered candidate without keyword filtering. The "
            "testing-security category includes pure testing skills, so the "
            "default keyword filter is recommended."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing destination skill directories.",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY,
        help=(
            "Seconds to sleep after each listing or zip request. Increase if "
            "the API returns 429. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Concurrent download workers. Listing is serial. Default: %(default)s",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print discovered candidates without downloading zips.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional manifest path (JSON).",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately if a skill fails to download or save.",
    )
    parser.add_argument(
        "--print-results",
        action="store_true",
        help="Print every result line at the end (default prints only a summary).",
    )
    return parser.parse_args()


def urlopen_with_retries(request: urllib.request.Request) -> bytes:
    last_error: BaseException | None = None
    for attempt in range(7):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            last_error = error
            if attempt == 6:
                break
            if error.code in {301, 302, 303, 307, 308, 400, 401, 404}:
                break
            retry_after = error.headers.get("Retry-After") if error.headers else None
            if error.code == 429:
                try:
                    delay = float(retry_after) if retry_after else 10.0 * (attempt + 1)
                except ValueError:
                    delay = 10.0 * (attempt + 1)
            else:
                delay = 1.5 * (attempt + 1)
            time.sleep(delay)
        except (TimeoutError, urllib.error.URLError) as error:
            last_error = error
            if attempt == 6:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {request.full_url}: {last_error}") from last_error


def http_get_bytes(url: str, accept: str | None = None) -> bytes:
    headers = {
        "User-Agent": "distill-skill-fetcher",
    }
    if accept:
        headers["Accept"] = accept
    return urlopen_with_retries(urllib.request.Request(url, headers=headers))


def http_get_json(url: str) -> object:
    return json.loads(http_get_bytes(url, accept="application/json").decode("utf-8"))


def listing_url(api_base: str, params: dict[str, object]) -> str:
    base = api_base.rstrip("/")
    query = urllib.parse.urlencode(
        {key: str(value) for key, value in params.items() if value is not None}
    )
    return f"{base}/api/skills?{query}"


def download_url_for_slug(api_base: str, slug: str) -> str:
    base = api_base.rstrip("/")
    encoded = urllib.parse.quote(slug, safe="")
    return f"{base}/api/skills/{encoded}/download"


def to_candidate(item: dict[str, object], discovered_via: str) -> SkillCandidate | None:
    slug = item.get("slug")
    if not isinstance(slug, str) or not slug:
        return None
    tags_raw = item.get("tags") or []
    tags = tuple(str(tag) for tag in tags_raw if isinstance(tag, str))
    bundle = item.get("bundleFiles") or []
    bundle_files = tuple(b for b in bundle if isinstance(b, dict))
    return SkillCandidate(
        slug=slug,
        name=str(item.get("name") or slug),
        description=str(item.get("description") or ""),
        upstream_category=str(item.get("category") or ""),
        tags=tags,
        content=str(item.get("content") or ""),
        bundle_files=bundle_files,
        source_url=item.get("sourceUrl") if isinstance(item.get("sourceUrl"), str) else None,
        github_repo=item.get("githubRepoFullName") if isinstance(item.get("githubRepoFullName"), str) else None,
        github_branch=item.get("githubDefaultBranch") if isinstance(item.get("githubDefaultBranch"), str) else None,
        skill_file_path=item.get("skillFilePath") if isinstance(item.get("skillFilePath"), str) else None,
        security_grade=item.get("securityGrade") if isinstance(item.get("securityGrade"), str) else None,
        security_score=item.get("securityScore") if isinstance(item.get("securityScore"), int) else None,
        discovered_via=discovered_via,
    )


def fetch_listing_pages(
    api_base: str,
    params: dict[str, object],
    request_delay: float,
    discovered_via: str,
    label: str,
    max_candidates: int = 0,
) -> list[SkillCandidate]:
    page = 1
    candidates: list[SkillCandidate] = []
    while True:
        page_params = dict(params)
        page_params["page"] = page
        page_params.setdefault("limit", DEFAULT_PAGE_SIZE)
        url = listing_url(api_base, page_params)
        data = http_get_json(url)
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected listing response from {url}")
        items = data.get("skills") or []
        pagination = data.get("pagination") or {}
        total = pagination.get("totalCount") if isinstance(pagination, dict) else None
        total_pages = pagination.get("totalPages") if isinstance(pagination, dict) else None
        for item in items:
            if not isinstance(item, dict):
                continue
            candidate = to_candidate(item, discovered_via)
            if candidate is not None:
                candidates.append(candidate)
        print(
            f"[{label}] page={page} got={len(items)} running_total={len(candidates)}"
            f" upstream_total={total}",
            file=sys.stderr,
        )
        if not isinstance(items, list) or not items:
            break
        if isinstance(total_pages, int) and page >= total_pages:
            break
        if max_candidates and len(candidates) >= max_candidates:
            break
        page += 1
        if request_delay > 0:
            time.sleep(request_delay)
    return candidates


def fetch_explicit_candidate(slug: str) -> SkillCandidate:
    """Skillsdirectory has no public skill-detail endpoint, so explicit slugs
    bypass metadata discovery and rely on the zip download endpoint."""
    return SkillCandidate(
        slug=slug,
        name=slug,
        description="",
        upstream_category="",
        tags=(),
        content="",
        bundle_files=(),
        source_url=None,
        github_repo=None,
        github_branch=None,
        skill_file_path=None,
        security_grade=None,
        security_score=None,
        discovered_via="explicit",
    )


def collect_candidates(args: argparse.Namespace) -> list[SkillCandidate]:
    candidates_by_slug: dict[str, SkillCandidate] = {}

    for slug in args.slugs or []:
        candidate = fetch_explicit_candidate(slug)
        candidates_by_slug[candidate.slug] = candidate

    if args.no_listing:
        candidates = list(candidates_by_slug.values())
        candidates.sort(key=lambda item: item.slug)
        if args.max_skills > 0:
            return candidates[: args.max_skills]
        return candidates

    listing_max = args.max_skills if (args.max_skills and args.no_content_filter) else 0

    if args.scan_all:
        listing_candidates = fetch_listing_pages(
            args.api_base,
            {},
            args.request_delay,
            discovered_via="scan-all",
            label="scan-all",
            max_candidates=listing_max,
        )
    else:
        listing_candidates = fetch_listing_pages(
            args.api_base,
            {"category": args.upstream_category},
            args.request_delay,
            discovered_via=f"category:{args.upstream_category}",
            label=f"category={args.upstream_category}",
            max_candidates=listing_max,
        )

    for candidate in listing_candidates:
        existing = candidates_by_slug.get(candidate.slug)
        if existing is None:
            candidates_by_slug[candidate.slug] = candidate

    candidates = list(candidates_by_slug.values())
    candidates.sort(key=lambda item: item.slug)
    if args.max_skills > 0:
        return candidates[: args.max_skills]
    return candidates


def candidate_text_for_filter(candidate: SkillCandidate) -> str:
    parts = [
        candidate.slug,
        candidate.name,
        candidate.description,
        candidate.upstream_category,
        candidate.skill_file_path or "",
        candidate.content,
        " ".join(candidate.tags),
    ]
    return "\n".join(parts)


def is_security_related(candidate: SkillCandidate) -> bool:
    text = candidate_text_for_filter(candidate)
    return any(pattern.search(text) for pattern in SECURITY_PATTERNS)


def local_directory_name(slug: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-._")
    return normalized.lower() or "skill"


def destination_for_slug(args: argparse.Namespace, slug: str) -> Path:
    return (
        args.dest.expanduser().resolve()
        / args.marketplace
        / args.collection
        / args.category
        / local_directory_name(slug)
    )


def ensure_safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or any(part == ".." for part in path.parts) or not path.parts:
        raise RuntimeError(f"Unsafe zip member: {name}")
    return path


def extract_zip(zip_bytes: bytes, destination: Path) -> tuple[int, list[str]]:
    file_count = 0
    written: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            relative = ensure_safe_member(member.filename)
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            file_count += 1
            written.append(str(relative))
    return file_count, written


def candidate_to_record(candidate: SkillCandidate) -> dict[str, object]:
    return {
        "slug": candidate.slug,
        "name": candidate.name,
        "description": candidate.description,
        "upstreamCategory": candidate.upstream_category,
        "tags": list(candidate.tags),
        "sourceUrl": candidate.source_url,
        "githubRepo": candidate.github_repo,
        "githubBranch": candidate.github_branch,
        "skillFilePath": candidate.skill_file_path,
        "securityGrade": candidate.security_grade,
        "securityScore": candidate.security_score,
        "discoveredVia": candidate.discovered_via,
        "bundleFileCount": len(candidate.bundle_files),
    }


def fetch_and_store(args: argparse.Namespace, candidate: SkillCandidate) -> dict[str, object]:
    record = candidate_to_record(candidate)
    destination = destination_for_slug(args, candidate.slug)

    if not args.no_content_filter and not is_security_related(candidate):
        return {**record, "status": "skipped-filtered", "reason": "no security keyword match"}

    if destination.exists() and not args.overwrite:
        return {**record, "status": "skipped-existing", "path": str(destination)}

    zip_url = download_url_for_slug(args.api_base, candidate.slug)
    zip_bytes = http_get_bytes(zip_url, accept="application/zip")

    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_count, written = extract_zip(zip_bytes, destination)

    return {
        **record,
        "status": "fetched",
        "path": str(destination),
        "fileCount": file_count,
        "files": written,
        "downloadUrl": zip_url,
    }


def write_manifest(path: Path, payload: object) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{sec:02d}s"
    if minutes:
        return f"{minutes}m{sec:02d}s"
    return f"{sec}s"


def main() -> int:
    args = parse_args()
    if args.max_skills < 0:
        raise ValueError("--max-skills must be >= 0")
    if args.workers < 1:
        raise ValueError("--workers must be >= 1")

    candidates = collect_candidates(args)
    print(f"Discovered {len(candidates)} candidate(s) before filtering.", file=sys.stderr)

    if args.dry_run:
        for candidate in candidates:
            tag_text = ",".join(candidate.tags)
            print(
                f"{candidate.slug} | grade={candidate.security_grade} | "
                f"upstream={candidate.upstream_category} | tags={tag_text} | "
                f"name={candidate.name}"
            )
        if args.manifest:
            write_manifest(
                args.manifest,
                {
                    "source": "skillsdirectory.com",
                    "apiBase": args.api_base,
                    "marketplace": args.marketplace,
                    "collection": args.collection,
                    "category": args.category,
                    "upstreamCategory": args.upstream_category,
                    "scanAll": bool(args.scan_all),
                    "dryRun": True,
                    "candidateCount": len(candidates),
                    "candidates": [candidate_to_record(c) for c in candidates],
                },
            )
        return 0

    started_at = time.monotonic()
    indexed_results: list[tuple[int, dict[str, object]]] = []
    status_counts: dict[str, int] = {}

    def fetch_one(index: int, candidate: SkillCandidate) -> tuple[int, dict[str, object]]:
        try:
            result = fetch_and_store(args, candidate)
            if args.request_delay > 0:
                time.sleep(args.request_delay)
            return index, result
        except Exception as error:
            if args.stop_on_error:
                raise
            return index, {
                **candidate_to_record(candidate),
                "status": "error",
                "error": str(error),
            }

    total = len(candidates)

    def progress_line(completed: int, result: dict[str, object]) -> str:
        status = str(result.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        elapsed = time.monotonic() - started_at
        eta = elapsed / completed * (total - completed) if completed else 0.0
        percent = completed / total * 100 if total else 100.0
        return (
            f"[{completed}/{total} {percent:5.1f}%] {status}: {result.get('slug', '?')} | "
            f"saved={status_counts.get('fetched', 0)} "
            f"filtered={status_counts.get('skipped-filtered', 0)} "
            f"existing={status_counts.get('skipped-existing', 0)} "
            f"errors={status_counts.get('error', 0)} "
            f"elapsed={format_duration(elapsed)} eta={format_duration(eta)}"
        )

    if args.workers == 1:
        completed = 0
        for index, candidate in enumerate(candidates, start=1):
            _, result = fetch_one(index, candidate)
            completed += 1
            indexed_results.append((index, result))
            print(progress_line(completed, result), file=sys.stderr)
            if result.get("status") == "error":
                print(f"Error fetching {candidate.slug}: {result.get('error')}", file=sys.stderr)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(fetch_one, index, candidate): (index, candidate)
                for index, candidate in enumerate(candidates, start=1)
            }
            completed = 0
            for future in as_completed(futures):
                index, candidate = futures[future]
                _, result = future.result()
                completed += 1
                indexed_results.append((index, result))
                print(progress_line(completed, result), file=sys.stderr)
                if result.get("status") == "error":
                    print(f"Error fetching {candidate.slug}: {result.get('error')}", file=sys.stderr)

    results = [result for _, result in sorted(indexed_results, key=lambda item: item[0])]

    payload = {
        "source": "skillsdirectory.com",
        "apiBase": args.api_base,
        "destinationRoot": str(args.dest.expanduser().resolve()),
        "marketplace": args.marketplace,
        "collection": args.collection,
        "category": args.category,
        "upstreamCategory": args.upstream_category,
        "scanAll": bool(args.scan_all),
        "contentFilter": not args.no_content_filter,
        "candidateCount": len(candidates),
        "results": results,
    }
    if args.manifest:
        write_manifest(args.manifest, payload)

    summary = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
    print(f"Completed {len(results)} candidate(s): {summary}.")
    if args.print_results:
        for result in results:
            path = result.get("path", "")
            suffix = f" -> {path}" if path else ""
            print(f"{result.get('status')}: {result.get('slug')}{suffix}")
    elif args.manifest:
        print(f"Detailed results written to {args.manifest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
