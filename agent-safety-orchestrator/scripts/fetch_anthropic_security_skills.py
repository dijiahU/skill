#!/usr/bin/env python3

"""Fetch security-related skills from Anthropic's official skills repository.

The script discovers skill directories in `anthropics/skills`, matches them
against security-oriented keywords, and downloads matched skill directories
without rewriting their file contents.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "official_skills"
DEFAULT_REPO = "anthropics/skills"
DEFAULT_PROVIDER = "anthropic"
DEFAULT_CATEGORY = "security"
DEFAULT_KEYWORDS = (
    "security",
    "secure",
    "safety",
    "safe",
    "threat",
    "audit",
    "vulnerability",
    "vulnerabilities",
    "privacy",
    "risk",
    "compliance",
    "red team",
    "red-team",
    "prompt injection",
    "prompt-injection",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch security-related skills from Anthropic's official "
            "anthropics/skills repository."
        )
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="GitHub repository in owner/name form. Default: %(default)s",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref to read from (branch, tag, or commit SHA). Default: %(default)s",
    )
    parser.add_argument(
        "--provider",
        default=DEFAULT_PROVIDER,
        help="Provider directory below the destination root. Default: %(default)s",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST_ROOT,
        help=(
            "Destination root. Skills are stored by provider, collection, "
            "category, and skill name under this directory. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help="Category directory to use below the collection. Default: %(default)s",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        default=None,
        help=(
            "Keyword used for automatic discovery. Repeat for multiple keywords. "
            "Defaults to a security-oriented keyword set."
        ),
    )
    parser.add_argument(
        "--skill-path",
        action="append",
        dest="skill_paths",
        default=None,
        help=(
            "Repo-relative skill directory to copy, for example "
            "`skills/skill-creator`. Repeat to fetch multiple skills. Supplied "
            "paths are fetched in addition to keyword-discovered matches."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing destination skill directory.",
    )
    parser.add_argument(
        "--search-body",
        action="store_true",
        help=(
            "Include the full SKILL.md body in keyword discovery. By default, "
            "only the skill path and frontmatter metadata are searched."
        ),
    )
    parser.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="Return a non-zero exit code when no matching skills are found.",
    )
    return parser.parse_args()


def urlopen_with_retries(request: urllib.request.Request) -> bytes:
    last_error: BaseException | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            if attempt == 2:
                break
            time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Failed to fetch {request.full_url}: {last_error}") from last_error


def github_json(url: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
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


def get_tree(repo: str, ref: str) -> list[dict[str, object]]:
    url = f"https://api.github.com/repos/{repo}/git/trees/{ref}?recursive=1"
    data = github_json(url)
    if not isinstance(data, dict) or "tree" not in data:
        raise RuntimeError(f"Unexpected GitHub tree response for {repo}@{ref}")
    tree = data["tree"]
    if not isinstance(tree, list):
        raise RuntimeError(f"Unexpected GitHub tree payload for {repo}@{ref}")
    return tree


def normalize_skill_path(path: str) -> PurePosixPath:
    normalized = PurePosixPath(path)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"Invalid skill path: {path}")
    if not normalized.parts or normalized.parts[0] != "skills":
        raise ValueError(f"Expected a skill path under skills/: {path}")
    return normalized


def discover_skill_paths(tree: list[dict[str, object]]) -> list[PurePosixPath]:
    skill_paths = []
    for item in tree:
        path = item.get("path")
        item_type = item.get("type")
        if not isinstance(path, str) or item_type != "blob":
            continue

        parts = PurePosixPath(path).parts
        if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
            skill_paths.append(PurePosixPath(*parts[:2]))

    return sorted(set(skill_paths), key=str)


def raw_url(repo: str, ref: str, path: PurePosixPath) -> str:
    quoted_path = urllib.parse.quote(str(path), safe="/")
    quoted_ref = urllib.parse.quote(ref, safe="")
    return f"https://raw.githubusercontent.com/{repo}/{quoted_ref}/{quoted_path}"


def read_skill_md(repo: str, ref: str, skill_path: PurePosixPath) -> str:
    skill_md_path = skill_path / "SKILL.md"
    return fetch_bytes(raw_url(repo, ref, skill_md_path)).decode(
        "utf-8", errors="replace"
    )


def frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""

    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""

    return parts[1]


def matches_keywords(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def discover_security_skills(
    repo: str,
    ref: str,
    tree: list[dict[str, object]],
    keywords: tuple[str, ...],
    search_body: bool,
) -> list[PurePosixPath]:
    matches = []
    for skill_path in discover_skill_paths(tree):
        skill_md = read_skill_md(repo, ref, skill_path)
        metadata = frontmatter(skill_md)
        haystack = f"{skill_path}\n{metadata}"
        if search_body:
            haystack = f"{haystack}\n{skill_md}"
        if matches_keywords(haystack, keywords):
            matches.append(skill_path)
    return matches


def destination_for_skill(
    dest_root: Path,
    provider: str,
    category: str,
    source_path: PurePosixPath,
) -> Path:
    parts = source_path.parts
    if len(parts) >= 3 and parts[1].startswith("."):
        collection = parts[1].lstrip(".")
        skill_name = parts[2]
    elif len(parts) >= 2:
        collection = parts[0]
        skill_name = parts[1]
    else:
        raise ValueError(f"Expected a skill path under skills/: {source_path}")

    return dest_root / provider / collection / category / skill_name


def blobs_under_skill(
    tree: list[dict[str, object]],
    skill_path: PurePosixPath,
) -> list[PurePosixPath]:
    prefix = f"{skill_path}/"
    blobs = []
    for item in tree:
        path = item.get("path")
        item_type = item.get("type")
        if isinstance(path, str) and item_type == "blob" and path.startswith(prefix):
            blobs.append(PurePosixPath(path))
    return sorted(blobs, key=str)


def copy_skill(
    repo: str,
    ref: str,
    tree: list[dict[str, object]],
    source_path: PurePosixPath,
    dest_root: Path,
    provider: str,
    category: str,
    overwrite: bool,
) -> Path:
    blobs = blobs_under_skill(tree, source_path)
    if not blobs:
        raise FileNotFoundError(f"No files found for skill path: {source_path}")

    dst = destination_for_skill(dest_root, provider, category, source_path)
    if dst.exists():
        if not overwrite:
            raise FileExistsError(
                f"Destination already exists: {dst}. Use --overwrite to replace it."
            )
        shutil.rmtree(dst)

    try:
        for blob_path in blobs:
            relative_path = blob_path.relative_to(source_path)
            target = dst.joinpath(*relative_path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fetch_bytes(raw_url(repo, ref, blob_path)))
    except Exception:
        if dst.exists():
            shutil.rmtree(dst)
        raise

    return dst


def main() -> int:
    args = parse_args()
    dest_root = args.dest.expanduser().resolve()
    keywords = tuple(args.keywords or DEFAULT_KEYWORDS)

    print(f"Reading tree for {args.repo}@{args.ref}", file=sys.stderr)
    tree = get_tree(args.repo, args.ref)

    discovered = discover_security_skills(
        args.repo,
        args.ref,
        tree,
        keywords,
        args.search_body,
    )
    requested = [
        normalize_skill_path(path)
        for path in (args.skill_paths or [])
    ]
    skill_paths = sorted(set(discovered + requested), key=str)

    if not skill_paths:
        print("No matching security-related skills found.")
        if args.fail_on_empty:
            return 1
        return 0

    copied_paths = []
    for skill_path in skill_paths:
        copied_paths.append(
            copy_skill(
                args.repo,
                args.ref,
                tree,
                skill_path,
                dest_root,
                args.provider,
                args.category,
                args.overwrite,
            )
        )

    print(f"Fetched {len(copied_paths)} skill(s) into {dest_root}")
    for path in copied_paths:
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
