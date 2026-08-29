#!/usr/bin/env python3

"""Fetch security-related skills from skills.sh.

The script uses skills.sh only for candidate discovery. For normal GitHub-backed
skills it downloads raw files directly from the source GitHub repository, which
avoids the anonymous skills.sh download limit. Non-GitHub sources are skipped by
default unless --skills-api-fallback is enabled.
"""

from __future__ import annotations

import argparse
import hashlib
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
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from threading import Lock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "community_skills"
DEFAULT_API_BASE = "https://skills.sh"
DEFAULT_MARKETPLACE = "skillsh"
DEFAULT_COLLECTION = "skills"
DEFAULT_CATEGORY = "security"
DEFAULT_SEARCH_LIMIT = 50_000
DEFAULT_MAX_SKILLS = 0
DEFAULT_REQUEST_DELAY = 0.2
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"
GITHUB_TREE_CACHE: dict[str, dict[str, object] | None] = {}
GITHUB_TREE_CACHE_LOCK = Lock()
GITHUB_PRIORITY_PREFIXES = (
    "",
    "skills/",
    "skills/.curated/",
    "skills/.experimental/",
    "skills/.system/",
    ".agents/skills/",
    ".claude/skills/",
    ".cline/skills/",
    ".codebuddy/skills/",
    ".codex/skills/",
    ".commandcode/skills/",
    ".continue/skills/",
    ".github/skills/",
    ".goose/skills/",
    ".iflow/skills/",
    ".junie/skills/",
    ".kilocode/skills/",
    ".kiro/skills/",
    ".mux/skills/",
    ".neovate/skills/",
    ".opencode/skills/",
    ".openhands/skills/",
    ".pi/skills/",
    ".qoder/skills/",
    ".roo/skills/",
    ".trae/skills/",
    ".windsurf/skills/",
    ".zencoder/skills/",
)
DEFAULT_QUERIES = (
    "security",
    "cybersecurity",
    "secure coding",
    "secure",
    "hardening",
    "threat model",
    "threat modeling",
    "threat intelligence",
    "prompt injection",
    "jailbreak",
    "vulnerability",
    "vulnerability scanner",
    "malware",
    "exploit",
    "penetration testing",
    "pentest",
    "red team",
    "blue team",
    "secret scanning",
    "secret scanner",
    "secrets",
    "credential",
    "credentials",
    "authentication",
    "authorization",
    "access control",
    "oauth",
    "rbac",
    "compliance",
    "privacy",
    "audit",
    "forensics",
    "incident response",
    "siem",
    "security operations center",
    "owasp",
    "sast",
    "dast",
    "sbom",
    "supply chain security",
    "container security",
    "cloud security",
    "kubernetes security",
    "firewall",
    "waf",
    "tls",
    "encryption",
    "cryptography",
    "phishing",
    "ransomware",
    "yara",
    "ctf",
    "zero trust",
)
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
        r"\bsoc\b",
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
        r"\battack\b",
    )
)


@dataclass(frozen=True)
class SkillCandidate:
    id: str
    source: str
    skill_id: str
    name: str
    installs: int | None = None
    queries: tuple[str, ...] = field(default_factory=tuple)
    is_duplicate: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch security-related skills from skills.sh into the local "
            "community skill storage layout."
        )
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help="skills.sh base URL. Default: %(default)s",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST_ROOT,
        help=(
            "Destination root. Skills are stored as "
            "<dest>/skillsh/skills/security/<source>__<skill>. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--marketplace",
        default=DEFAULT_MARKETPLACE,
        help="Marketplace directory below the destination root. Default: %(default)s",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="Collection directory below the marketplace. Default: %(default)s",
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
            "Search query to run against skills.sh. Repeat for multiple queries. "
            "Defaults to a broad security-oriented query set."
        ),
    )
    parser.add_argument(
        "--skill",
        action="append",
        dest="skills",
        default=None,
        help=(
            "Explicit skill id to fetch, in source/skill form such as "
            "wshobson/agents/security-requirement-extraction. Repeat as needed."
        ),
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="Do not run keyword search; fetch only skills supplied with --skill.",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=DEFAULT_SEARCH_LIMIT,
        help=(
            "Maximum results to request per query. This is not a total cap. "
            "Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        default=DEFAULT_MAX_SKILLS,
        help=(
            "Maximum total candidates to download after deduplication. Use 0 for "
            "no total cap. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--no-content-filter",
        action="store_true",
        help=(
            "Save every discovered candidate without checking downloaded contents "
            "for security terms. This can include false positives for broad queries."
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
            "Seconds to sleep after each search or download request. Increase this "
            "if skills.sh returns 429. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "Number of concurrent download workers. Search is always serial. "
            "Use a small value to avoid skills.sh rate limits. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--github-token",
        default=None,
        help=(
            "GitHub token for repository tree lookups. Defaults to GITHUB_TOKEN, "
            "GH_TOKEN, or `gh auth token` when available."
        ),
    )
    parser.add_argument(
        "--skills-api-fallback",
        action="store_true",
        help=(
            "For non-GitHub sources, fall back to skills.sh/api/download. Disabled "
            "by default because that endpoint is anonymously limited to about "
            "60 requests per hour."
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
        help="Optional manifest path to write as JSON.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately if a skill fails to download or save.",
    )
    parser.add_argument(
        "--print-results",
        action="store_true",
        help="Print every result at the end. By default only a summary is printed.",
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
            retry_after = error.headers.get("Retry-After") if error.headers else None
            if error.code in {301, 302, 303, 307, 308, 400, 401, 404}:
                break
            if error.code == 429:
                try:
                    delay = float(retry_after) if retry_after else 10.0 * (attempt + 1)
                except ValueError:
                    delay = 10.0 * (attempt + 1)
            elif error.code == 403 and error.headers and error.headers.get("x-ratelimit-remaining") == "0":
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


def fetch_url_bytes(url: str, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {
        "User-Agent": "distill-skill-fetcher",
        **(headers or {}),
    }
    request = urllib.request.Request(url, headers=request_headers)
    return urlopen_with_retries(request)


def fetch_json(url: str, headers: dict[str, str] | None = None) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "distill-skill-fetcher",
            **(headers or {}),
        },
    )
    return json.loads(urlopen_with_retries(request).decode("utf-8"))


def api_url(api_base: str, endpoint_parts: tuple[str, ...], params: dict[str, object] | None = None) -> str:
    base = api_base.rstrip("/")
    endpoint = "/".join(urllib.parse.quote(part, safe="") for part in endpoint_parts)
    query = urllib.parse.urlencode(
        {key: str(value) for key, value in (params or {}).items() if value is not None}
    )
    return f"{base}/{endpoint}?{query}" if query else f"{base}/{endpoint}"


def to_skill_slug(value: str) -> str:
    return (
        value.lower()
        .replace("_", "-")
        .replace(" ", "-")
        .replace(":", "-")
    )


def normalized_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "", re.sub(r"[-\s_:]+", "-", value.lower())).strip("-")


def resolve_github_token(explicit_token: str | None) -> str | None:
    if explicit_token:
        return explicit_token.strip()
    for env_name in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(env_name)
        if token:
            return token.strip()
    try:
        token = subprocess.check_output(
            ["gh", "auth", "token"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
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


def github_owner_repo_from_source(source: str) -> str | None:
    parts = source.split("/")
    if len(parts) != 2:
        return None
    owner, repo = parts
    if "." in owner:
        return None
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", owner):
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        return None
    return source


def fetch_github_tree(owner_repo: str, token: str | None) -> dict[str, object] | None:
    with GITHUB_TREE_CACHE_LOCK:
        if owner_repo in GITHUB_TREE_CACHE:
            return GITHUB_TREE_CACHE[owner_repo]

    repo_url = f"{GITHUB_API_BASE}/repos/{owner_repo}"
    repo_data = fetch_json(repo_url, github_headers(token))
    if not isinstance(repo_data, dict):
        payload = None
    else:
        default_branch = repo_data.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            payload = None
        else:
            tree_url = (
                f"{GITHUB_API_BASE}/repos/{owner_repo}/git/trees/"
                f"{urllib.parse.quote(default_branch, safe='')}?recursive=1"
            )
            tree_data = fetch_json(tree_url, github_headers(token))
            if not isinstance(tree_data, dict) or not isinstance(tree_data.get("tree"), list):
                payload = None
            else:
                payload = {
                    "branch": default_branch,
                    "tree": tree_data["tree"],
                    "sha": tree_data.get("sha"),
                    "truncated": bool(tree_data.get("truncated")),
                }

    with GITHUB_TREE_CACHE_LOCK:
        if owner_repo not in GITHUB_TREE_CACHE:
            GITHUB_TREE_CACHE[owner_repo] = payload
        return GITHUB_TREE_CACHE[owner_repo]


def skill_md_priority(path: str) -> tuple[int, int, str]:
    for index, prefix in enumerate(GITHUB_PRIORITY_PREFIXES):
        if path.startswith(prefix):
            return (index, path.count("/"), path)
    return (len(GITHUB_PRIORITY_PREFIXES), path.count("/"), path)


def parent_folder_slug(skill_md_path: str, repo_name: str) -> str:
    parts = PurePosixPath(skill_md_path).parts
    if skill_md_path == "SKILL.md" or len(parts) == 1:
        return normalized_slug(repo_name)
    return normalized_slug(parts[-2])


def parse_frontmatter_name(markdown: str) -> str | None:
    if not markdown.startswith("---"):
        return None
    end = markdown.find("\n---", 3)
    if end == -1:
        return None
    frontmatter = markdown[3:end]
    for line in frontmatter.splitlines():
        if line.strip().lower().startswith("name:"):
            return line.split(":", 1)[1].strip().strip("'\"") or None
    return None


def raw_github_url(owner_repo: str, branch: str, path: str) -> str:
    return (
        f"{GITHUB_RAW_BASE}/{owner_repo}/"
        f"{urllib.parse.quote(branch, safe='')}/"
        f"{urllib.parse.quote(path, safe='/')}"
    )


def fetch_github_raw_file(owner_repo: str, branch: str, path: str) -> bytes:
    return fetch_url_bytes(raw_github_url(owner_repo, branch, path))


def find_github_skill_md_path(
    owner_repo: str,
    tree_info: dict[str, object],
    candidate: SkillCandidate,
) -> str | None:
    repo_name = owner_repo.split("/", 1)[1]
    tree = tree_info.get("tree")
    if not isinstance(tree, list):
        return None
    skill_md_paths = sorted(
        (
            str(entry["path"])
            for entry in tree
            if isinstance(entry, dict)
            and entry.get("type") == "blob"
            and isinstance(entry.get("path"), str)
            and str(entry["path"]).endswith("SKILL.md")
        ),
        key=skill_md_priority,
    )
    if not skill_md_paths:
        return None

    target_slugs = {
        normalized_slug(candidate.skill_id),
        normalized_slug(candidate.name),
    }
    exact_matches = [
        path
        for path in skill_md_paths
        if parent_folder_slug(path, repo_name) in target_slugs
    ]
    if exact_matches:
        return exact_matches[0]

    branch = str(tree_info.get("branch") or "")
    if not branch:
        return None
    for path in skill_md_paths[:200]:
        try:
            markdown = fetch_github_raw_file(owner_repo, branch, path).decode("utf-8", errors="ignore")
        except Exception:
            continue
        frontmatter_name = parse_frontmatter_name(markdown)
        if frontmatter_name and normalized_slug(frontmatter_name) in target_slugs:
            return path
    return None


def normalize_skill_id(raw: str) -> tuple[str, str, str]:
    value = raw.strip().strip("/")
    parts = [part for part in value.split("/") if part]
    if len(parts) == 2 and "." in parts[0]:
        return value, parts[0], parts[1]
    if len(parts) < 3:
        raise ValueError(f"Expected source/skill id with at least 3 segments: {raw}")
    source = "/".join(parts[:-1])
    skill_id = parts[-1]
    return value, source, skill_id


def search_skills(api_base: str, query: str, limit: int) -> list[SkillCandidate]:
    url = api_url(api_base, ("api", "search"), {"q": query, "limit": limit})
    data = fetch_json(url)
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected skills.sh search response for query: {query}")

    candidates = []
    for item in data.get("skills", []):
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        skill_id = item.get("skillId")
        candidate_id = item.get("id")
        if not isinstance(source, str) or not isinstance(skill_id, str):
            continue
        if not isinstance(candidate_id, str):
            candidate_id = f"{source}/{skill_id}"
        installs = item.get("installs")
        candidates.append(
            SkillCandidate(
                id=candidate_id,
                source=source,
                skill_id=skill_id,
                name=str(item.get("name") or skill_id),
                installs=installs if isinstance(installs, int) else None,
                queries=(query,),
                is_duplicate=bool(item.get("isDuplicate")),
            )
        )
    return candidates


def explicit_candidate(raw_skill_id: str) -> SkillCandidate:
    candidate_id, source, skill_id = normalize_skill_id(raw_skill_id)
    return SkillCandidate(
        id=candidate_id,
        source=source,
        skill_id=skill_id,
        name=skill_id,
        queries=("explicit",),
    )


def merge_candidate(existing: SkillCandidate, new: SkillCandidate) -> SkillCandidate:
    queries = tuple(dict.fromkeys((*existing.queries, *new.queries)))
    installs = existing.installs if existing.installs is not None else new.installs
    return SkillCandidate(
        id=existing.id,
        source=existing.source,
        skill_id=existing.skill_id,
        name=existing.name or new.name,
        installs=installs,
        queries=queries,
        is_duplicate=existing.is_duplicate or new.is_duplicate,
    )


def collect_candidates(args: argparse.Namespace) -> list[SkillCandidate]:
    candidates_by_id: dict[str, SkillCandidate] = {}

    for raw_skill_id in args.skills or []:
        candidate = explicit_candidate(raw_skill_id)
        candidates_by_id[candidate.id] = candidate

    if not args.no_search:
        for query in tuple(args.queries or DEFAULT_QUERIES):
            print(f"Searching skills.sh for {query!r}", file=sys.stderr)
            for candidate in search_skills(args.api_base, query, args.search_limit):
                existing = candidates_by_id.get(candidate.id)
                candidates_by_id[candidate.id] = (
                    merge_candidate(existing, candidate) if existing else candidate
                )
            if args.request_delay > 0:
                time.sleep(args.request_delay)

    candidates = list(candidates_by_id.values())
    candidates.sort(key=lambda item: (-(item.installs or 0), item.source, item.skill_id))
    if args.max_skills == 0:
        return candidates
    return candidates[: args.max_skills]


def local_directory_name(candidate: SkillCandidate) -> str:
    raw = f"{candidate.source.replace('/', '__')}__{candidate.skill_id}"
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return normalized.lower() or "skill"


def destination_for_skill(args: argparse.Namespace, candidate: SkillCandidate) -> Path:
    return (
        args.dest.expanduser().resolve()
        / args.marketplace
        / args.collection
        / args.category
        / local_directory_name(candidate)
    )


def download_url_for_skill(api_base: str, candidate: SkillCandidate) -> str:
    return api_url(api_base, ("api", "download", *candidate.source.split("/"), candidate.skill_id))


def download_skill(api_base: str, candidate: SkillCandidate) -> dict[str, object]:
    url = download_url_for_skill(api_base, candidate)
    data = fetch_json(url)
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise RuntimeError(f"Unexpected skills.sh download response for {candidate.id}")
    data["downloadMethod"] = "skills.sh-api"
    return data


def file_is_under_skill_folder(path: str, skill_folder: str) -> bool:
    if not skill_folder:
        return path == "SKILL.md"
    return path.startswith(f"{skill_folder}/")


def relative_skill_file_path(path: str, skill_folder: str) -> str:
    if not skill_folder:
        return path
    return path[len(skill_folder) + 1 :]


def hash_download_files(files: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for file_item in sorted(files, key=lambda item: str(item.get("path", ""))):
        path = str(file_item.get("path", ""))
        digest.update(path.encode("utf-8"))
        contents_bytes = file_item.get("contentsBytes")
        if isinstance(contents_bytes, bytes):
            digest.update(contents_bytes)
        elif isinstance(file_item.get("contents"), str):
            digest.update(str(file_item["contents"]).encode("utf-8"))
    return digest.hexdigest()


def download_github_skill(args: argparse.Namespace, candidate: SkillCandidate) -> dict[str, object] | None:
    owner_repo = github_owner_repo_from_source(candidate.source)
    if owner_repo is None:
        return None

    tree_info = fetch_github_tree(owner_repo, args.github_token)
    if tree_info is None:
        raise RuntimeError(f"Could not fetch GitHub repository tree for {owner_repo}")

    branch = tree_info.get("branch")
    if not isinstance(branch, str) or not branch:
        raise RuntimeError(f"Could not determine default branch for {owner_repo}")

    skill_md_path = find_github_skill_md_path(owner_repo, tree_info, candidate)
    if not skill_md_path:
        raise RuntimeError(f"No matching SKILL.md found in GitHub repository {owner_repo}")

    skill_folder = skill_md_path.removesuffix("/SKILL.md")
    if skill_md_path == "SKILL.md":
        skill_folder = ""

    tree = tree_info.get("tree")
    if not isinstance(tree, list):
        raise RuntimeError(f"Unexpected GitHub tree payload for {owner_repo}")

    source_paths = sorted(
        str(entry["path"])
        for entry in tree
        if isinstance(entry, dict)
        and entry.get("type") == "blob"
        and isinstance(entry.get("path"), str)
        and file_is_under_skill_folder(str(entry["path"]), skill_folder)
    )
    if not source_paths:
        raise RuntimeError(f"No files found for GitHub skill folder {owner_repo}:{skill_folder or '.'}")

    files: list[dict[str, object]] = []
    for source_path in source_paths:
        contents = fetch_github_raw_file(owner_repo, branch, source_path)
        files.append(
            {
                "path": relative_skill_file_path(source_path, skill_folder),
                "sourcePath": source_path,
                "contentsBytes": contents,
            }
        )

    return {
        "files": files,
        "hash": hash_download_files(files),
        "downloadMethod": "github-raw",
        "sourceRepository": owner_repo,
        "sourceBranch": branch,
        "sourceSkillPath": skill_folder or ".",
        "sourceSkillMdPath": skill_md_path,
        "treeSha": tree_info.get("sha"),
        "treeTruncated": tree_info.get("truncated"),
    }


def download_candidate(args: argparse.Namespace, candidate: SkillCandidate) -> dict[str, object] | None:
    if github_owner_repo_from_source(candidate.source) is not None:
        try:
            return download_github_skill(args, candidate)
        except Exception as github_error:
            if not args.skills_api_fallback:
                raise
            fallback = download_skill(args.api_base, candidate)
            fallback["githubDirectError"] = str(github_error)
            return fallback

    if not args.skills_api_fallback:
        return None

    return download_skill(args.api_base, candidate)


def combined_download_text(candidate: SkillCandidate, download: dict[str, object]) -> str:
    parts = [
        candidate.id,
        candidate.source,
        candidate.skill_id,
        candidate.name,
    ]
    for file_item in download.get("files", []):
        if not isinstance(file_item, dict):
            continue
        path = file_item.get("path")
        contents = file_item.get("contents")
        if isinstance(path, str):
            parts.append(path)
        if isinstance(contents, str):
            parts.append(contents)
        contents_bytes = file_item.get("contentsBytes")
        if isinstance(contents_bytes, bytes):
            parts.append(contents_bytes.decode("utf-8", errors="ignore"))
    return "\n".join(parts)


def is_security_related(candidate: SkillCandidate, download: dict[str, object]) -> bool:
    text = combined_download_text(candidate, download)
    return any(pattern.search(text) for pattern in SECURITY_PATTERNS)


def ensure_safe_file_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise RuntimeError(f"Unsafe file path in download payload: {name}")
    return path


def write_downloaded_files(download: dict[str, object], destination: Path) -> int:
    file_count = 0
    for file_item in download.get("files", []):
        if not isinstance(file_item, dict):
            continue
        raw_path = file_item.get("path")
        contents = file_item.get("contents")
        contents_bytes = file_item.get("contentsBytes")
        if not isinstance(raw_path, str):
            continue
        relative_path = ensure_safe_file_path(raw_path)
        target = destination.joinpath(*relative_path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contents_bytes, bytes):
            target.write_bytes(contents_bytes)
        elif isinstance(contents, str):
            target.write_text(contents, encoding="utf-8")
        else:
            continue
        file_count += 1
    return file_count


def fetch_and_store(args: argparse.Namespace, candidate: SkillCandidate) -> dict[str, object]:
    destination = destination_for_skill(args, candidate)
    if destination.exists() and not args.overwrite:
        return {
            "id": candidate.id,
            "source": candidate.source,
            "skillId": candidate.skill_id,
            "name": candidate.name,
            "status": "skipped-existing",
            "path": str(destination),
            "queries": list(candidate.queries),
            "installs": candidate.installs,
            "isDuplicate": candidate.is_duplicate,
        }

    download = download_candidate(args, candidate)
    if download is None:
        if destination.exists() and args.overwrite:
            shutil.rmtree(destination)
        return {
            "id": candidate.id,
            "source": candidate.source,
            "skillId": candidate.skill_id,
            "name": candidate.name,
            "status": "skipped-non-github",
            "queries": list(candidate.queries),
            "installs": candidate.installs,
            "isDuplicate": candidate.is_duplicate,
            "reason": "Source is not a GitHub owner/repo and --skills-api-fallback is disabled.",
        }

    if not args.no_content_filter and not is_security_related(candidate, download):
        if destination.exists() and args.overwrite:
            shutil.rmtree(destination)
        return {
            "id": candidate.id,
            "source": candidate.source,
            "skillId": candidate.skill_id,
            "name": candidate.name,
            "status": "skipped-filtered",
            "queries": list(candidate.queries),
            "installs": candidate.installs,
            "isDuplicate": candidate.is_duplicate,
            "downloadUrl": download_url_for_skill(args.api_base, candidate),
            "downloadMethod": download.get("downloadMethod"),
        }

    if destination.exists():
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    file_count = write_downloaded_files(download, destination)
    return {
        "id": candidate.id,
        "source": candidate.source,
        "skillId": candidate.skill_id,
        "name": candidate.name,
        "status": "fetched",
        "path": str(destination),
        "fileCount": file_count,
        "hash": download.get("hash"),
        "queries": list(candidate.queries),
        "installs": candidate.installs,
        "isDuplicate": candidate.is_duplicate,
        "downloadUrl": download_url_for_skill(args.api_base, candidate),
        "downloadMethod": download.get("downloadMethod"),
        "sourceRepository": download.get("sourceRepository"),
        "sourceBranch": download.get("sourceBranch"),
        "sourceSkillPath": download.get("sourceSkillPath"),
        "sourceSkillMdPath": download.get("sourceSkillMdPath"),
        "treeSha": download.get("treeSha"),
        "treeTruncated": download.get("treeTruncated"),
    }


def write_manifest(path: Path, payload: object) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def candidate_to_manifest(candidate: SkillCandidate) -> dict[str, object]:
    github_owner_repo = github_owner_repo_from_source(candidate.source)
    return {
        "id": candidate.id,
        "source": candidate.source,
        "skillId": candidate.skill_id,
        "name": candidate.name,
        "installs": candidate.installs,
        "queries": list(candidate.queries),
        "isDuplicate": candidate.is_duplicate,
        "githubRawEligible": github_owner_repo is not None,
        "sourceRepository": github_owner_repo,
        "skillsApiDownloadUrl": download_url_for_skill(DEFAULT_API_BASE, candidate),
    }


def main() -> int:
    args = parse_args()
    if args.search_limit < 1:
        raise ValueError("--search-limit must be >= 1")
    if args.max_skills < 0:
        raise ValueError("--max-skills must be >= 0")
    if args.workers < 1:
        raise ValueError("--workers must be >= 1")
    args.github_token = resolve_github_token(args.github_token)
    if args.github_token:
        print("Using authenticated GitHub requests for repository tree lookups.", file=sys.stderr)
    else:
        print(
            "Warning: no GitHub token found. GitHub API tree lookups may hit the "
            "anonymous 60 requests/hour limit. Run `gh auth login` or set GITHUB_TOKEN "
            "for full-scale fetches.",
            file=sys.stderr,
        )
    if args.skills_api_fallback:
        print(
            "skills.sh API fallback is enabled for non-GitHub or failed GitHub downloads; "
            "that endpoint is rate-limited.",
            file=sys.stderr,
        )

    candidates = collect_candidates(args)
    if args.dry_run:
        print(f"Discovered {len(candidates)} candidate skill(s); dry run only.")
        for candidate in candidates:
            installs = "" if candidate.installs is None else f" installs={candidate.installs}"
            query_text = ",".join(candidate.queries)
            print(f"{candidate.id}{installs} queries={query_text}")
        if args.manifest:
            write_manifest(
                args.manifest,
                {
                    "source": "skills.sh",
                    "destinationRoot": str(args.dest.expanduser().resolve()),
                    "marketplace": args.marketplace,
                    "collection": args.collection,
                    "category": args.category,
                    "queries": list(args.queries or DEFAULT_QUERIES),
                    "searchLimit": args.search_limit,
                    "maxSkills": args.max_skills,
                    "dryRun": True,
                    "candidates": [candidate_to_manifest(candidate) for candidate in candidates],
                },
            )
        return 0

    def fetch_one(index: int, candidate: SkillCandidate) -> tuple[int, dict[str, object]]:
        try:
            result = fetch_and_store(args, candidate)
            if args.request_delay > 0:
                time.sleep(args.request_delay)
            return index, result
        except Exception as error:
            if args.stop_on_error:
                raise
            return index, (
                {
                    "id": candidate.id,
                    "source": candidate.source,
                    "skillId": candidate.skill_id,
                    "name": candidate.name,
                    "status": "error",
                    "error": str(error),
                    "queries": list(candidate.queries),
                    "installs": candidate.installs,
                    "isDuplicate": candidate.is_duplicate,
                }
            )

    indexed_results: list[tuple[int, dict[str, object]]] = []
    total = len(candidates)
    started_at = time.monotonic()
    status_counts = {
        "fetched": 0,
        "skipped-existing": 0,
        "skipped-filtered": 0,
        "skipped-non-github": 0,
        "error": 0,
    }

    def format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h{minutes:02d}m{sec:02d}s"
        if minutes:
            return f"{minutes}m{sec:02d}s"
        return f"{sec}s"

    def progress_message(completed: int, result: dict[str, object], candidate_id: str) -> str:
        status = str(result["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
        elapsed = time.monotonic() - started_at
        eta = elapsed / completed * (total - completed) if completed else 0
        percent = completed / total * 100 if total else 100
        return (
            f"[{completed}/{total} {percent:5.1f}%] {status}: {candidate_id} | "
            f"saved={status_counts.get('fetched', 0)} "
            f"filtered={status_counts.get('skipped-filtered', 0)} "
            f"non_github={status_counts.get('skipped-non-github', 0)} "
            f"existing={status_counts.get('skipped-existing', 0)} "
            f"errors={status_counts.get('error', 0)} "
            f"elapsed={format_duration(elapsed)} eta={format_duration(eta)}"
        )

    if args.workers == 1:
        completed = 0
        for index, candidate in enumerate(candidates, start=1):
            print(f"[{index}/{total}] Fetching {candidate.id}", file=sys.stderr)
            result_index, result = fetch_one(index, candidate)
            completed += 1
            indexed_results.append((result_index, result))
            print(progress_message(completed, result, candidate.id), file=sys.stderr)
            if result["status"] == "error":
                print(f"Error fetching {candidate.id}: {result.get('error')}", file=sys.stderr)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(fetch_one, index, candidate): (index, candidate)
                for index, candidate in enumerate(candidates, start=1)
            }
            completed = 0
            for future in as_completed(futures):
                index, candidate = futures[future]
                result_index, result = future.result()
                completed += 1
                indexed_results.append((result_index, result))
                status = result["status"]
                print(progress_message(completed, result, candidate.id), file=sys.stderr)
                if status == "error":
                    print(f"Error fetching {candidate.id}: {result.get('error')}", file=sys.stderr)

    results = [result for _, result in sorted(indexed_results, key=lambda item: item[0])]

    payload = {
        "source": "skills.sh",
        "note": "The user requested skill.sh; that domain is parked, so the fetch used skills.sh, the active Agent Skills Directory.",
        "apiBase": args.api_base,
        "destinationRoot": str(args.dest.expanduser().resolve()),
        "marketplace": args.marketplace,
        "collection": args.collection,
        "category": args.category,
        "queries": list(args.queries or DEFAULT_QUERIES),
        "searchLimit": args.search_limit,
        "maxSkills": args.max_skills,
        "contentFilter": not args.no_content_filter,
        "downloadStrategy": "github-raw-first",
        "skillsApiFallback": bool(args.skills_api_fallback),
        "candidateCount": len(candidates),
        "results": results,
    }
    if args.manifest:
        write_manifest(args.manifest, payload)

    final_status_counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        final_status_counts[status] = final_status_counts.get(status, 0) + 1
    status_summary = ", ".join(
        f"{status}={count}" for status, count in sorted(final_status_counts.items())
    )
    print(f"Completed {len(results)} candidate(s): {status_summary}.")
    if args.print_results:
        for result in results:
            path = result.get("path", "")
            suffix = f" -> {path}" if path else ""
            print(f"{result['status']}: {result['id']}{suffix}")
    elif args.manifest:
        print(f"Detailed results written to {args.manifest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
