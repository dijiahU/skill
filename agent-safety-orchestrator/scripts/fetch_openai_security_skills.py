#!/usr/bin/env python3

"""Fetch security-related skills from the official openai/skills repository.

The script downloads a tarball for a given ref and copies the selected skill
directories without modifying file contents. By default it fetches the security
skills currently present under `skills/.curated/` in `openai/skills`.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "official_skills"
DEFAULT_CATEGORY = "security"


DEFAULT_SKILL_PATHS = (
    "skills/.curated/security-best-practices",
    "skills/.curated/security-ownership-map",
    "skills/.curated/security-threat-model",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch security-related skills from the official openai/skills "
            "repository without rewriting their contents."
        )
    )
    parser.add_argument(
        "--repo",
        default="openai/skills",
        help="GitHub repository in owner/name form. Default: %(default)s",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref to download (branch, tag, or commit SHA). Default: %(default)s",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST_ROOT,
        help=(
            "Destination root. Skills are stored by vendor, collection, category, "
            "and skill name under this directory. Default: %(default)s"
        ),
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help="Category directory to use below the collection. Default: %(default)s",
    )
    parser.add_argument(
        "--skill-path",
        action="append",
        dest="skill_paths",
        default=None,
        help=(
            "Repo-relative skill directory to copy. Repeat to fetch multiple "
            "skills. If omitted, the current official security skills are used."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing destination skill directory.",
    )
    return parser.parse_args()


def build_tarball_url(repo: str, ref: str) -> str:
    return f"https://codeload.github.com/{repo}/tar.gz/{ref}"


def ensure_safe_members(tar: tarfile.TarFile) -> None:
    for member in tar.getmembers():
        member_path = PurePosixPath(member.name)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise RuntimeError(f"Unsafe path in tarball: {member.name}")


def extract_tarball(tarball_path: Path, extract_dir: Path) -> Path:
    with tarfile.open(tarball_path, "r:gz") as tar:
        ensure_safe_members(tar)
        tar.extractall(extract_dir)

    roots = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(
            f"Expected exactly one extracted root directory, found {len(roots)}"
        )
    return roots[0]


def repo_owner(repo: str) -> str:
    parts = repo.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"Repository must be in owner/name form: {repo}")
    return parts[0]


def destination_for_skill(
    dest_root: Path,
    repo: str,
    category: str,
    source_path: PurePosixPath,
) -> Path:
    parts = source_path.parts
    if len(parts) < 3 or parts[0] != "skills":
        raise ValueError(f"Expected a skill path under skills/: {source_path}")

    collection = parts[1].lstrip(".")
    skill_name = parts[-1]
    return dest_root / repo_owner(repo) / collection / category / skill_name


def copy_skill(
    source_root: Path,
    source_path: str,
    dest_root: Path,
    repo: str,
    category: str,
    overwrite: bool,
) -> Path:
    normalized_source = PurePosixPath(source_path)
    if normalized_source.is_absolute() or ".." in normalized_source.parts:
        raise ValueError(f"Invalid skill path: {source_path}")

    src = source_root.joinpath(*normalized_source.parts)
    if not src.is_dir():
        raise FileNotFoundError(f"Skill path not found in archive: {source_path}")

    dst = destination_for_skill(dest_root, repo, category, normalized_source)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        if not overwrite:
            raise FileExistsError(
                f"Destination already exists: {dst}. Use --overwrite to replace it."
            )
        shutil.rmtree(dst)

    shutil.copytree(src, dst, symlinks=True)
    return dst


def main() -> int:
    args = parse_args()
    skill_paths = tuple(args.skill_paths or DEFAULT_SKILL_PATHS)
    tarball_url = build_tarball_url(args.repo, args.ref)
    dest_root = args.dest.expanduser().resolve()

    with tempfile.TemporaryDirectory(prefix="openai-skills-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        tarball_path = temp_dir / "repo.tar.gz"

        print(f"Downloading {tarball_url}", file=sys.stderr)
        urllib.request.urlretrieve(tarball_url, tarball_path)

        print("Extracting archive", file=sys.stderr)
        extracted_root = extract_tarball(tarball_path, temp_dir / "extract")

        copied_paths = []
        for skill_path in skill_paths:
            copied_paths.append(
                copy_skill(
                    extracted_root,
                    skill_path,
                    dest_root,
                    args.repo,
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
