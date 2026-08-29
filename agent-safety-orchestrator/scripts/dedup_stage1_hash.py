#!/usr/bin/env python3

"""Stage-1 hard dedup of fetched skill / MCP server candidates.

Goal: cheap, deterministic deduplication before any LLM auditing. Two
candidates with identical content fingerprint are functionally the same
artifact (typically the same upstream skill mirrored by multiple aggregators).

This script does NOT move or delete any files in `data/raw/`. It writes a
cluster manifest to `reports/dedup_stage1_hash_<date>.json` describing:
  - which candidates collapse into which cluster
  - which one is picked as the representative
  - the resulting residual count

Fingerprint rules:
  SKILL.md skill         : sha256 of the SKILL.md body, normalized
                           (line endings → \\n, trailing whitespace stripped).
                           Auxiliary files (scripts/, references/, agents/,
                           README, etc.) are intentionally ignored — two
                           skills with identical SKILL.md are the same
                           skill regardless of supporting files. Stage-2
                           near-dedup can refine this further if needed.

  MCP server (metadata.json) : sha256 of normalized `name + "\\n" + description`.
                           This catches the same upstream project listed in
                           multiple registries. Tools-list-aware fingerprints
                           can be added in Stage 2 if Stage 1 leaves too much
                           residual cross-registry duplication.

Representative selection within a cluster: smallest source-priority rank
first, then shortest path string as tiebreaker (deterministic).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data" / "raw"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"


# Lower rank = higher priority when picking the cluster representative.
# Source priority encodes "trust this version of the skill more if duplicates exist".
SKILL_SOURCE_PRIORITY: dict[str, int] = {
    # official_skills tier
    "official_skills/openai": 10,
    # curated indexes (have metadata + quality signals)
    "community_skills/agent-skills-directory": 20,
    # zip-download marketplaces (clean per-skill content)
    "community_skills/clawhub": 30,
    # large but mixed-quality
    "community_skills/skillsdirectory": 40,
    "community_skills/skillsh": 50,
}
SKILL_DEFAULT_PRIORITY = 99

MCP_SOURCE_PRIORITY: dict[str, int] = {
    "mcp_servers/modelcontextprotocol-registry": 10,  # official
    "mcp_servers/smithery": 20,                        # rich detail
    "mcp_servers/pulsemcp": 30,
    "mcp_servers/glama": 40,
    "mcp_servers/mcp-so": 50,
}
MCP_DEFAULT_PRIORITY = 99


@dataclass
class Candidate:
    kind: str           # "skill" | "mcp"
    path: str           # relative-to-PROJECT_ROOT path of the artifact dir
    file: str           # relative path of the file used for fingerprinting
    fingerprint: str    # sha256 hex
    priority: int       # source priority rank (lower = preferred)
    source_tag: str     # human-readable source label, e.g. "skillsh" / "smithery"
    name: str           # best-effort display name


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage-1 hard dedup of fetched skills + MCP servers. "
                    "Writes a cluster manifest to reports/; does not move data."
    )
    p.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT,
                   help="Root of fetched artifacts. Default: %(default)s")
    p.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR,
                   help="Where to write the manifest. Default: %(default)s")
    p.add_argument("--manifest-name", default=None,
                   help="Manifest filename (default: dedup_stage1_hash_<YYYY-MM-DD>.json)")
    p.add_argument("--print-top", type=int, default=10,
                   help="Print the N largest clusters at the end. Default: %(default)s")
    p.add_argument("--dry-run", action="store_true",
                   help="Compute and summarize, but skip manifest write.")
    return p.parse_args()


def normalize_skill_md(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines).rstrip() + "\n"


def fingerprint_skill(skill_md: Path) -> str:
    raw = skill_md.read_text(encoding="utf-8", errors="ignore")
    return hashlib.sha256(normalize_skill_md(raw).encode("utf-8")).hexdigest()


def normalize_mcp_signature(name: str, description: str) -> str:
    name = (name or "").strip().lower()
    desc = (description or "").strip().lower()
    desc = " ".join(desc.split())
    return f"{name}\n{desc}"


def fingerprint_mcp(metadata_json: Path) -> tuple[str, str]:
    """Return (fingerprint, display_name)."""
    raw = json.loads(metadata_json.read_text(encoding="utf-8"))
    # try a hierarchy of name/description fields across registries
    name = (
        raw.get("name")
        or raw.get("displayName")
        or raw.get("title")
        or raw.get("slug")
        or raw.get("qualifiedName")
        or ""
    )
    description = (
        raw.get("description")
        or raw.get("shortDescription")
        or raw.get("readme")  # mcp.so saves the README here
        or ""
    )
    if isinstance(description, str) and len(description) > 4000:
        # very long readmes trigger spurious uniqueness on cross-registry dupes;
        # cap at a stable prefix for the fingerprint.
        description = description[:4000]
    sig = normalize_mcp_signature(str(name), str(description))
    fp = hashlib.sha256(sig.encode("utf-8")).hexdigest()
    return fp, str(name).strip() or metadata_json.parent.name


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def source_tag_for_path(path_str: str) -> str:
    """Return the marketplace / registry segment of a path."""
    parts = path_str.split("/")
    # data/raw/<tier>/<source>/...
    if len(parts) >= 4 and parts[0] == "data" and parts[1] == "raw":
        return parts[3]
    return parts[0] if parts else "?"


def priority_for_skill_path(path_str: str) -> int:
    """e.g. data/raw/community_skills/skillsh/... → priority of skillsh."""
    parts = path_str.split("/")
    if len(parts) < 4:
        return SKILL_DEFAULT_PRIORITY
    key = f"{parts[2]}/{parts[3]}"
    return SKILL_SOURCE_PRIORITY.get(key, SKILL_DEFAULT_PRIORITY)


def priority_for_mcp_path(path_str: str) -> int:
    parts = path_str.split("/")
    if len(parts) < 4:
        return MCP_DEFAULT_PRIORITY
    key = f"{parts[2]}/{parts[3]}"
    return MCP_SOURCE_PRIORITY.get(key, MCP_DEFAULT_PRIORITY)


def collect_skill_candidates(data_root: Path, project_root: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    bases = [
        data_root / "official_skills",
        data_root / "community_skills",
    ]
    for base in bases:
        if not base.is_dir():
            continue
        # SKILL.md files at any depth under base
        for skill_md in base.rglob("SKILL.md"):
            if not skill_md.is_file():
                continue
            try:
                fp = fingerprint_skill(skill_md)
            except Exception as e:
                print(f"[skip] {skill_md}: {e}", file=sys.stderr)
                continue
            artifact_dir = skill_md.parent
            rel_dir = relative_to_root(artifact_dir, project_root)
            rel_file = relative_to_root(skill_md, project_root)
            candidates.append(Candidate(
                kind="skill",
                path=rel_dir,
                file=rel_file,
                fingerprint=fp,
                priority=priority_for_skill_path(rel_dir),
                source_tag=source_tag_for_path(rel_dir),
                name=artifact_dir.name,
            ))
    return candidates


def collect_mcp_candidates(data_root: Path, project_root: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    base = data_root / "mcp_servers"
    if not base.is_dir():
        return candidates
    for metadata in base.rglob("metadata.json"):
        if not metadata.is_file():
            continue
        try:
            fp, display = fingerprint_mcp(metadata)
        except Exception as e:
            print(f"[skip] {metadata}: {e}", file=sys.stderr)
            continue
        artifact_dir = metadata.parent
        rel_dir = relative_to_root(artifact_dir, project_root)
        rel_file = relative_to_root(metadata, project_root)
        candidates.append(Candidate(
            kind="mcp",
            path=rel_dir,
            file=rel_file,
            fingerprint=fp,
            priority=priority_for_mcp_path(rel_dir),
            source_tag=source_tag_for_path(rel_dir),
            name=display,
        ))
    return candidates


def cluster_candidates(items: list[Candidate]) -> list[dict]:
    by_fp: dict[str, list[Candidate]] = defaultdict(list)
    for c in items:
        by_fp[c.fingerprint].append(c)

    clusters = []
    for fp, members in by_fp.items():
        # representative = lowest priority rank; ties broken by shortest path,
        # then lexicographic.
        members_sorted = sorted(
            members,
            key=lambda c: (c.priority, len(c.path), c.path),
        )
        rep = members_sorted[0]
        dup_paths = [c.path for c in members_sorted[1:]]
        cluster = {
            "fingerprint": fp,
            "size": len(members_sorted),
            "representative": {
                "path": rep.path,
                "source": rep.source_tag,
                "priority": rep.priority,
                "name": rep.name,
            },
            "duplicates": [
                {"path": c.path, "source": c.source_tag, "priority": c.priority, "name": c.name}
                for c in members_sorted[1:]
            ],
            "duplicateSources": sorted({c.source_tag for c in members_sorted[1:]}),
        }
        clusters.append(cluster)

    clusters.sort(key=lambda cl: (-cl["size"], cl["representative"]["path"]))
    return clusters


def cluster_summary(clusters: list[dict]) -> dict[str, int]:
    total = sum(cl["size"] for cl in clusters)
    multi = sum(1 for cl in clusters if cl["size"] > 1)
    collapsed = sum(cl["size"] - 1 for cl in clusters)
    return {
        "totalInputs": total,
        "uniqueClusters": len(clusters),
        "multiMemberClusters": multi,
        "collapsedItems": collapsed,
        "collapseRatioPercent": round(collapsed / total * 100, 2) if total else 0.0,
    }


def cross_source_overlap(clusters: list[dict]) -> list[dict]:
    """Surface clusters that pull duplicates across distinct sources — these
    are the "real" cross-aggregator collisions worth eyeballing."""
    overlaps = []
    for cl in clusters:
        sources = {cl["representative"]["source"], *cl["duplicateSources"]}
        if cl["size"] > 1 and len(sources) > 1:
            overlaps.append({**cl, "uniqueSources": sorted(sources)})
    return overlaps


def main() -> int:
    args = parse_args()
    data_root = args.data_root.expanduser().resolve()
    project_root = PROJECT_ROOT

    print(f"Scanning {data_root}", file=sys.stderr)
    skills = collect_skill_candidates(data_root, project_root)
    mcps = collect_mcp_candidates(data_root, project_root)
    print(f"Found {len(skills)} SKILL.md skill(s), {len(mcps)} MCP server(s).",
          file=sys.stderr)

    skill_clusters = cluster_candidates(skills)
    mcp_clusters = cluster_candidates(mcps)

    skill_summary = cluster_summary(skill_clusters)
    mcp_summary = cluster_summary(mcp_clusters)
    skill_overlaps = cross_source_overlap(skill_clusters)
    mcp_overlaps = cross_source_overlap(mcp_clusters)

    print(
        f"\nSKILL.md  : {skill_summary['totalInputs']} input → "
        f"{skill_summary['uniqueClusters']} unique "
        f"(collapsed {skill_summary['collapsedItems']}, "
        f"{skill_summary['collapseRatioPercent']}%)"
    )
    print(
        f"MCP server: {mcp_summary['totalInputs']} input → "
        f"{mcp_summary['uniqueClusters']} unique "
        f"(collapsed {mcp_summary['collapsedItems']}, "
        f"{mcp_summary['collapseRatioPercent']}%)"
    )
    print(
        f"Cross-source overlap: {len(skill_overlaps)} skill cluster(s), "
        f"{len(mcp_overlaps)} MCP cluster(s)"
    )

    if args.print_top > 0:
        print(f"\n--- Top {args.print_top} skill clusters by size ---")
        for cl in skill_clusters[: args.print_top]:
            sources = sorted({cl["representative"]["source"], *cl["duplicateSources"]})
            print(f"  size={cl['size']:3d}  sources={sources}  rep={cl['representative']['name'][:50]}")
        print(f"\n--- Top {args.print_top} MCP clusters by size ---")
        for cl in mcp_clusters[: args.print_top]:
            sources = sorted({cl["representative"]["source"], *cl["duplicateSources"]})
            print(f"  size={cl['size']:3d}  sources={sources}  rep={cl['representative']['name'][:50]}")

    if args.dry_run:
        print("\n[dry-run] manifest not written.")
        return 0

    today = datetime.date.today().isoformat()
    manifest_name = args.manifest_name or f"dedup_stage1_hash_{today}.json"
    manifest_path = args.reports_dir.expanduser().resolve() / manifest_name
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "stage": "hash-dedup",
        "ranAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataRoot": str(data_root),
        "fingerprintRules": {
            "skill": "sha256 of normalized SKILL.md body (line-endings + trailing-whitespace normalized)",
            "mcp": "sha256 of normalized 'name\\ndescription' (lowercased, whitespace-collapsed; description capped at 4000 chars)",
        },
        "skillSourcePriority": SKILL_SOURCE_PRIORITY,
        "mcpSourcePriority": MCP_SOURCE_PRIORITY,
        "skill": {
            **skill_summary,
            "clusters": skill_clusters,
            "crossSourceOverlapCount": len(skill_overlaps),
        },
        "mcp": {
            **mcp_summary,
            "clusters": mcp_clusters,
            "crossSourceOverlapCount": len(mcp_overlaps),
        },
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nManifest written: {relative_to_root(manifest_path, project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
