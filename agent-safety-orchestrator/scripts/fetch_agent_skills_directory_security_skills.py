#!/usr/bin/env python3

"""Fetch security-related skills from dmgrok/agent_skills_directory.

The directory is itself an aggregation index — it ships ready-made catalog
exports (``exports/claude-skills.json`` etc.) that list every skill with the
upstream GitHub repo, commit sha, and path. This script downloads the catalog,
filters security candidates by category + content keywords, then materializes
each skill's source folder via the GitHub raw API pinned to the catalog's sha.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from threading import Lock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "community_skills"
DEFAULT_MARKETPLACE = "agent-skills-directory"
DEFAULT_COLLECTION = "skills"
DEFAULT_CATEGORY = "security"
DEFAULT_REQUEST_DELAY = 0.0
DEFAULT_WORKERS = 4
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"

CATALOG_URLS = {
    "claude-skills.json": "https://raw.githubusercontent.com/dmgrok/agent_skills_directory/main/exports/claude-skills.json",
    "active-skills.json": "https://raw.githubusercontent.com/dmgrok/agent_skills_directory/main/exports/active-skills.json",
    "premium-skills.json": "https://raw.githubusercontent.com/dmgrok/agent_skills_directory/main/exports/premium-skills.json",
}

GITHUB_REPO_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")

# Security keyword set is intentionally aligned with
# fetch_skillsh_security_skills.py so security candidates are scoped consistently.
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

GITHUB_TREE_CACHE: dict[tuple[str, str], dict[str, object] | None] = {}
GITHUB_TREE_CACHE_LOCK = Lock()


@dataclass(frozen=True)
class SkillCandidate:
    catalog_id: str
    name: str
    provider: str
    description: str
    category: str
    tags: tuple[str, ...]
    repo_full_name: str   # e.g. "github/awesome-copilot"
    commit_sha: str
    skill_path: str       # e.g. "skills/acquire-codebase-knowledge"
    skill_md_url: str | None
    license_text: str | None
    quality_score: int | None
    maintenance_status: str | None
    discovered_via: str = "catalog"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch security-related skills aggregated by "
            "dmgrok/agent_skills_directory into the local community skill "
            "storage layout."
        )
    )
    parser.add_argument(
        "--catalog",
        choices=sorted(CATALOG_URLS),
        default="claude-skills.json",
        help="Which upstream export to use as the candidate set. Default: %(default)s",
    )
    parser.add_argument(
        "--catalog-url",
        default=None,
        help="Override the catalog URL. Useful for pinning to a tag or a fork.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST_ROOT,
        help=(
            "Destination root. Skills are stored as "
            "<dest>/agent-skills-directory/skills/security/<provider>__<name>. "
            "Default: %(default)s"
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
        default=None,
        help=(
            "If set, restrict candidates to this upstream category (e.g. "
            "'security' for the 25-skill native bucket). Default: keyword filter "
            "across all categories."
        ),
    )
    parser.add_argument(
        "--id",
        action="append",
        dest="ids",
        default=None,
        help="Explicit catalog id (provider/name) to fetch. Repeat as needed.",
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        default=0,
        help="Cap total candidates after dedup and filtering. 0 means no cap.",
    )
    parser.add_argument(
        "--no-content-filter",
        action="store_true",
        help="Save every catalog skill without keyword filtering.",
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
        help="Seconds to sleep between sequential GitHub requests. Default: %(default)s",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help="Concurrent skill download workers. Default: %(default)s",
    )
    parser.add_argument(
        "--github-token",
        default=None,
        help=(
            "GitHub token for tree+raw fetches. Defaults to GITHUB_TOKEN, "
            "GH_TOKEN, or `gh auth token`."
        ),
    )
    parser.add_argument(
        "--use-default-branch",
        action="store_true",
        help=(
            "Fetch the latest contents on the repo's default branch instead of "
            "pinning to the catalog's commit_sha. Off by default for reproducibility."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print discovered candidates without downloading files.",
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
        help="Stop immediately on the first failed download.",
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
            elif (
                error.code == 403
                and error.headers
                and error.headers.get("x-ratelimit-remaining") == "0"
            ):
                reset_at = error.headers.get("x-ratelimit-reset")
                if reset_at and reset_at.isdigit():
                    delay = max(10.0, int(reset_at) - int(time.time()) + 2.0)
                else:
                    delay = 60.0
            else:
                delay = 1.5 * (attempt + 1)
            time.sleep(delay)
        except (TimeoutError, urllib.error.URLError) as error:
            last_error = error
            if attempt == 6:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {request.full_url}: {last_error}") from last_error


def http_get_bytes(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "distill-skill-fetcher", **(headers or {})},
    )
    return urlopen_with_retries(request)


def http_get_json(url: str, headers: dict[str, str] | None = None) -> object:
    return json.loads(http_get_bytes(url, {"Accept": "application/json", **(headers or {})}).decode("utf-8"))


def resolve_github_token(explicit: str | None) -> str | None:
    if explicit:
        return explicit.strip()
    for env_name in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(env_name)
        if token:
            return token.strip()
    try:
        token = subprocess.check_output(
            ["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL, timeout=10,
        ).strip()
        return token or None
    except Exception:
        return None


def github_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "distill-skill-fetcher",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_repo_url(repo_url: str) -> tuple[str, str] | None:
    match = GITHUB_REPO_RE.match(repo_url.strip())
    if match is None:
        return None
    return match.group(1), match.group(2)


def repo_full_name(owner: str, repo: str) -> str:
    return f"{owner}/{repo}"


def to_candidate(item: dict[str, object]) -> SkillCandidate | None:
    catalog_id = item.get("id")
    if not isinstance(catalog_id, str):
        return None
    source = item.get("source") if isinstance(item.get("source"), dict) else None
    if not source:
        return None
    repo_url = source.get("repo")
    commit_sha = source.get("commit_sha")
    skill_path = source.get("path")
    if not isinstance(repo_url, str) or not isinstance(commit_sha, str) or not isinstance(skill_path, str):
        return None
    parsed = parse_repo_url(repo_url)
    if parsed is None:
        return None
    owner, repo = parsed
    tags_raw = item.get("tags") or []
    tags = tuple(str(tag) for tag in tags_raw if isinstance(tag, str))
    skill_md_url = source.get("skill_md_url") if isinstance(source.get("skill_md_url"), str) else None
    return SkillCandidate(
        catalog_id=catalog_id,
        name=str(item.get("name") or catalog_id.split("/", 1)[-1]),
        provider=str(item.get("provider") or catalog_id.split("/", 1)[0]),
        description=str(item.get("description") or ""),
        category=str(item.get("category") or ""),
        tags=tags,
        repo_full_name=repo_full_name(owner, repo),
        commit_sha=commit_sha,
        skill_path=skill_path.strip("/"),
        skill_md_url=skill_md_url,
        license_text=str(item.get("license")) if isinstance(item.get("license"), str) else None,
        quality_score=item.get("quality_score") if isinstance(item.get("quality_score"), int) else None,
        maintenance_status=item.get("maintenance_status") if isinstance(item.get("maintenance_status"), str) else None,
    )


def candidate_text_for_filter(candidate: SkillCandidate) -> str:
    return "\n".join([
        candidate.catalog_id,
        candidate.name,
        candidate.description,
        candidate.category,
        candidate.skill_path,
        " ".join(candidate.tags),
    ])


def is_security_related(candidate: SkillCandidate) -> bool:
    return any(p.search(candidate_text_for_filter(candidate)) for p in SECURITY_PATTERNS)


def fetch_catalog(args: argparse.Namespace) -> dict[str, object]:
    url = args.catalog_url or CATALOG_URLS[args.catalog]
    print(f"Fetching catalog: {url}", file=sys.stderr)
    raw = http_get_bytes(url)
    return json.loads(raw.decode("utf-8"))


def collect_candidates(args: argparse.Namespace, catalog: dict[str, object]) -> list[SkillCandidate]:
    skills = catalog.get("skills") if isinstance(catalog, dict) else None
    if not isinstance(skills, list):
        raise RuntimeError("Catalog payload missing 'skills' list.")

    explicit_ids = set(args.ids or [])
    candidates_by_id: dict[str, SkillCandidate] = {}

    for item in skills:
        if not isinstance(item, dict):
            continue
        candidate = to_candidate(item)
        if candidate is None:
            continue
        if explicit_ids and candidate.catalog_id not in explicit_ids:
            continue
        if args.upstream_category and candidate.category != args.upstream_category:
            continue
        candidates_by_id[candidate.catalog_id] = candidate

    if explicit_ids:
        missing = explicit_ids - candidates_by_id.keys()
        for missing_id in sorted(missing):
            print(f"Warning: explicit id {missing_id!r} not found in catalog.", file=sys.stderr)

    candidates = list(candidates_by_id.values())
    if not args.no_content_filter and not explicit_ids:
        candidates = [c for c in candidates if is_security_related(c)]
    candidates.sort(key=lambda c: c.catalog_id)
    if args.max_skills > 0:
        return candidates[: args.max_skills]
    return candidates


def fetch_repo_tree(repo_full: str, ref: str, token: str | None) -> dict[str, object]:
    cache_key = (repo_full, ref)
    with GITHUB_TREE_CACHE_LOCK:
        if cache_key in GITHUB_TREE_CACHE:
            cached = GITHUB_TREE_CACHE[cache_key]
            if cached is None:
                raise RuntimeError(f"Cached failure for {repo_full}@{ref}")
            return cached

    tree_url = (
        f"{GITHUB_API_BASE}/repos/{repo_full}/git/trees/"
        f"{urllib.parse.quote(ref, safe='')}?recursive=1"
    )
    tree_data = http_get_json(tree_url, github_headers(token))
    if not isinstance(tree_data, dict) or not isinstance(tree_data.get("tree"), list):
        with GITHUB_TREE_CACHE_LOCK:
            GITHUB_TREE_CACHE[cache_key] = None
        raise RuntimeError(f"Unexpected tree payload for {repo_full}@{ref}")

    payload: dict[str, object] = {
        "tree": tree_data["tree"],
        "sha": tree_data.get("sha"),
        "truncated": bool(tree_data.get("truncated")),
    }
    with GITHUB_TREE_CACHE_LOCK:
        GITHUB_TREE_CACHE[cache_key] = payload
    return payload


def resolve_default_branch(repo_full: str, token: str | None) -> str:
    repo_data = http_get_json(f"{GITHUB_API_BASE}/repos/{repo_full}", github_headers(token))
    if isinstance(repo_data, dict) and isinstance(repo_data.get("default_branch"), str):
        return repo_data["default_branch"]
    raise RuntimeError(f"Cannot determine default branch for {repo_full}")


def raw_url(repo_full: str, ref: str, path: str) -> str:
    return (
        f"{GITHUB_RAW_BASE}/{repo_full}/"
        f"{urllib.parse.quote(ref, safe='')}/"
        f"{urllib.parse.quote(path, safe='/')}"
    )


def file_under(path: str, folder: str) -> bool:
    if not folder:
        return True
    return path == folder or path.startswith(f"{folder}/")


def relative_to(path: str, folder: str) -> str:
    if not folder:
        return path
    if path == folder:
        return path.rsplit("/", 1)[-1] if "/" in path else path
    return path[len(folder) + 1:]


def safe_relative(name: str) -> PurePosixPath:
    p = PurePosixPath(name)
    if p.is_absolute() or any(part == ".." for part in p.parts) or not p.parts:
        raise RuntimeError(f"Unsafe path in repo tree: {name}")
    return p


def local_directory_name(catalog_id: str) -> str:
    raw = catalog_id.replace("/", "__")
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return normalized.lower() or "skill"


def destination_for_candidate(args: argparse.Namespace, candidate: SkillCandidate) -> Path:
    return (
        args.dest.expanduser().resolve()
        / args.marketplace
        / args.collection
        / args.category
        / local_directory_name(candidate.catalog_id)
    )


def candidate_to_record(candidate: SkillCandidate) -> dict[str, object]:
    return {
        "id": candidate.catalog_id,
        "provider": candidate.provider,
        "name": candidate.name,
        "category": candidate.category,
        "tags": list(candidate.tags),
        "repo": candidate.repo_full_name,
        "commitSha": candidate.commit_sha,
        "skillPath": candidate.skill_path,
        "skillMdUrl": candidate.skill_md_url,
        "license": candidate.license_text,
        "qualityScore": candidate.quality_score,
        "maintenanceStatus": candidate.maintenance_status,
    }


def fetch_and_store(args: argparse.Namespace, candidate: SkillCandidate) -> dict[str, object]:
    record = candidate_to_record(candidate)
    destination = destination_for_candidate(args, candidate)

    if destination.exists() and not args.overwrite:
        return {**record, "status": "skipped-existing", "path": str(destination)}

    if args.use_default_branch:
        ref = resolve_default_branch(candidate.repo_full_name, args.github_token)
    else:
        ref = candidate.commit_sha

    tree_info = fetch_repo_tree(candidate.repo_full_name, ref, args.github_token)
    tree_entries = tree_info.get("tree") or []
    skill_files = sorted(
        str(entry["path"])
        for entry in tree_entries
        if isinstance(entry, dict)
        and entry.get("type") == "blob"
        and isinstance(entry.get("path"), str)
        and file_under(str(entry["path"]), candidate.skill_path)
    )
    if not skill_files:
        raise RuntimeError(
            f"No files at {candidate.repo_full_name}@{ref}:{candidate.skill_path or '.'}"
        )

    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for source_path in skill_files:
        relative = safe_relative(relative_to(source_path, candidate.skill_path))
        target = destination.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        contents = http_get_bytes(raw_url(candidate.repo_full_name, ref, source_path))
        target.write_bytes(contents)
        written.append(str(relative))
        if args.request_delay > 0:
            time.sleep(args.request_delay)

    return {
        **record,
        "status": "fetched",
        "path": str(destination),
        "ref": ref,
        "fileCount": len(written),
        "files": written,
        "treeTruncated": tree_info.get("truncated"),
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
    args.github_token = resolve_github_token(args.github_token)
    if args.github_token:
        print("Using authenticated GitHub requests.", file=sys.stderr)
    else:
        print(
            "Warning: no GitHub token. Anonymous quota is 60 req/hr; large fetches "
            "will be throttled. Run `gh auth login` or set GITHUB_TOKEN.",
            file=sys.stderr,
        )

    catalog = fetch_catalog(args)
    catalog_meta = {
        "name": catalog.get("name") if isinstance(catalog, dict) else None,
        "version": catalog.get("version") if isinstance(catalog, dict) else None,
        "generatedAt": catalog.get("generated_at") if isinstance(catalog, dict) else None,
        "totalSkills": catalog.get("total_skills") if isinstance(catalog, dict) else None,
    }
    print(
        f"Catalog: {catalog_meta['name']!r} version={catalog_meta['version']} "
        f"total_skills={catalog_meta['totalSkills']}",
        file=sys.stderr,
    )

    candidates = collect_candidates(args, catalog)
    print(f"Discovered {len(candidates)} candidate(s) before filtering.", file=sys.stderr)

    if args.dry_run:
        for c in candidates:
            tag_text = ",".join(c.tags)
            print(
                f"{c.catalog_id} | cat={c.category} | repo={c.repo_full_name}@{c.commit_sha[:8]} "
                f"| path={c.skill_path} | tags={tag_text}"
            )
        if args.manifest:
            write_manifest(
                args.manifest,
                {
                    "source": "dmgrok/agent_skills_directory",
                    "catalog": args.catalog,
                    "catalogMeta": catalog_meta,
                    "marketplace": args.marketplace,
                    "collection": args.collection,
                    "category": args.category,
                    "upstreamCategory": args.upstream_category,
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
            return index, fetch_and_store(args, candidate)
        except Exception as error:
            if args.stop_on_error:
                raise
            return index, {**candidate_to_record(candidate), "status": "error", "error": str(error)}

    total = len(candidates)

    def progress_line(completed: int, result: dict[str, object]) -> str:
        status = str(result.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        elapsed = time.monotonic() - started_at
        eta = elapsed / completed * (total - completed) if completed else 0.0
        percent = completed / total * 100 if total else 100.0
        return (
            f"[{completed}/{total} {percent:5.1f}%] {status}: {result.get('id', '?')} | "
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
                print(f"Error fetching {candidate.catalog_id}: {result.get('error')}", file=sys.stderr)
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
                    print(f"Error fetching {candidate.catalog_id}: {result.get('error')}", file=sys.stderr)

    results = [r for _, r in sorted(indexed_results, key=lambda item: item[0])]

    payload = {
        "source": "dmgrok/agent_skills_directory",
        "catalog": args.catalog,
        "catalogMeta": catalog_meta,
        "destinationRoot": str(args.dest.expanduser().resolve()),
        "marketplace": args.marketplace,
        "collection": args.collection,
        "category": args.category,
        "upstreamCategory": args.upstream_category,
        "contentFilter": not args.no_content_filter,
        "useDefaultBranch": bool(args.use_default_branch),
        "candidateCount": len(candidates),
        "results": results,
    }
    if args.manifest:
        write_manifest(args.manifest, payload)

    summary = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
    print(f"Completed {len(results)} candidate(s): {summary}.")
    if args.print_results:
        for r in results:
            path = r.get("path", "")
            suffix = f" -> {path}" if path else ""
            print(f"{r.get('status')}: {r.get('id')}{suffix}")
    elif args.manifest:
        print(f"Detailed results written to {args.manifest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
