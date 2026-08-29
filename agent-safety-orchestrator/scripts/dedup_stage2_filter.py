#!/usr/bin/env python3

"""Stage-2 filter: rule-based + repo-URL dedup + MinHash near-dup.

Reads the Stage-1 manifest and applies four rules to the surviving
representatives, producing a refined residual list. Like Stage 1, this is
non-destructive: nothing in `data/raw/` is moved or deleted; the decisions
land in a manifest under `reports/`.

Rules
-----
1. **short-content**          drop SKILL.md < MIN_SKILL_CHARS (default 200);
                              drop MCP entries with description+readme < MIN_MCP_CHARS (100).
                              These are skeletons or placeholders that even a
                              perfect LLM auditor cannot extract a useful
                              atomic capability from.

2. **branding-only-match**    drop SKILL.md skills where SECURITY_PATTERNS
                              regex matches **none** of the body — i.e. the
                              fetcher's keyword hit was driven only by site
                              wrapper / og:description boilerplate (the
                              skillsdirectory "Security-tested..." template is
                              the canonical case). Genuine security content
                              shows up in the upstream SKILL.md body itself.

3. **mcp-repo-url-dedup**     group MCP servers by their normalized upstream
                              GitHub URL (extracted from registry-specific
                              rawRecord paths). Stage 1 missed these because
                              cross-registry descriptions diverge; here we
                              join on repo identity directly. Pick the
                              representative by Stage-1's MCP_SOURCE_PRIORITY.

4. **minhash-near-dup**       cluster SKILL.md bodies by MinHash + LSH
                              banding; pairs with estimated Jaccard >= 0.85
                              are merged. Catches reformatted-but-near-
                              identical skills that strict hash missed.
                              Representatives picked by Stage-1's
                              SKILL_SOURCE_PRIORITY.

Output: reports/dedup_stage2_filter_<date>.json with explicit kept[] lists
and per-rule drop[] entries that include evidence strings for audit.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"
DEFAULT_STAGE1_MANIFEST = DEFAULT_REPORTS_DIR / "dedup_stage1_hash_2026-05-08.json"

DEFAULT_MIN_SKILL_CHARS = 200
DEFAULT_MIN_MCP_CHARS = 100
DEFAULT_MINHASH_THRESHOLD = 0.85
DEFAULT_MINHASH_NUM_HASHES = 64
DEFAULT_MINHASH_BANDS = 16
DEFAULT_MINHASH_ROWS = 4   # 16 * 4 = 64
DEFAULT_SHINGLE_K = 5

# Same priority maps as Stage 1, repeated here so the script is self-contained.
SKILL_SOURCE_PRIORITY: dict[str, int] = {
    "official_skills/openai": 10,
    "community_skills/agent-skills-directory": 20,
    "community_skills/clawhub": 30,
    "community_skills/skillsdirectory": 40,
    "community_skills/skillsh": 50,
}
SKILL_DEFAULT_PRIORITY = 99

MCP_SOURCE_PRIORITY: dict[str, int] = {
    "mcp_servers/modelcontextprotocol-registry": 10,
    "mcp_servers/smithery": 20,
    "mcp_servers/pulsemcp": 30,
    "mcp_servers/glama": 40,
    "mcp_servers/mcp-so": 50,
}
MCP_DEFAULT_PRIORITY = 99

# Keyword patterns shared with the fetchers; intentionally broad so any
# genuinely security-relevant SKILL.md body matches.
SECURITY_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bsecurity\b", r"\bsecure\b", r"\bcyber(?:security)?\b",
        r"\bvulnerab", r"\bcve(?:-\d{4}-\d+)?\b", r"\bthreat",
        r"\bmalware\b", r"\bmalicious\b", r"\bexploit",
        r"\bpentest", r"penetration test", r"\bred team\b", r"\bblue team\b",
        r"prompt injection", r"\bjailbreak",
        r"\bsecret(?:s)?\b", r"\bcredential", r"\bpassword",
        r"\bauthentication\b", r"\bauthorization\b", r"\bauthn\b", r"\bauthz\b",
        r"\boauth\b", r"\boidc\b", r"\bsaml\b", r"\brbac\b", r"access control",
        r"\bcompliance\b", r"\bprivacy\b", r"data protection",
        r"security audit", r"code audit", r"dependency audit",
        r"smart contract audit", r"\baudit log", r"\baudit trail",
        r"\bforensic", r"incident response", r"\bsiem\b", r"\bowasp\b",
        r"\bsast\b", r"\bdast\b", r"\bsbom\b", r"supply chain",
        r"container security", r"kubernetes security", r"cloud security",
        r"\bfirewall\b", r"\bwaf\b", r"\btls\b",
        r"\bencrypt", r"\bcryptograph", r"crypto protocol",
        r"\bphishing\b", r"\bransomware\b", r"\byara\b", r"\bctf\b",
        r"zero trust", r"least privilege", r"policy-as-code",
        r"secrets? scanning", r"token leakage",
        r"data loss prevention", r"\bdlp\b", r"\bmitre\b",
        r"\bscanner\b", r"\bguard(?:rail)?\b", r"\bguardian\b",
        r"\bpolicy\b", r"\btrust\b", r"\bvetter\b",
    )
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage-2 filter: short-content drop, branding-only-match drop, "
                    "MCP repo-URL dedup, MinHash near-dup."
    )
    p.add_argument("--stage1-manifest", type=Path, default=DEFAULT_STAGE1_MANIFEST,
                   help="Path to Stage-1 manifest. Default: %(default)s")
    p.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    p.add_argument("--manifest-name", default=None,
                   help="Output filename (default: dedup_stage2_filter_<YYYY-MM-DD>.json)")
    p.add_argument("--min-skill-chars", type=int, default=DEFAULT_MIN_SKILL_CHARS)
    p.add_argument("--min-mcp-chars", type=int, default=DEFAULT_MIN_MCP_CHARS)
    p.add_argument("--minhash-threshold", type=float, default=DEFAULT_MINHASH_THRESHOLD,
                   help="Jaccard threshold for near-dup merge. Default: %(default)s")
    p.add_argument("--no-minhash", action="store_true",
                   help="Skip the MinHash near-dup pass (faster).")
    p.add_argument("--print-top", type=int, default=10,
                   help="Print top-N MinHash clusters and repo-URL clusters.")
    p.add_argument("--dry-run", action="store_true",
                   help="Compute and summarize, but skip manifest write.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def priority_for_skill(rel_path: str) -> int:
    parts = rel_path.split("/")
    if len(parts) < 4:
        return SKILL_DEFAULT_PRIORITY
    key = f"{parts[2]}/{parts[3]}"
    return SKILL_SOURCE_PRIORITY.get(key, SKILL_DEFAULT_PRIORITY)


def priority_for_mcp(rel_path: str) -> int:
    parts = rel_path.split("/")
    if len(parts) < 4:
        return MCP_DEFAULT_PRIORITY
    key = f"{parts[2]}/{parts[3]}"
    return MCP_SOURCE_PRIORITY.get(key, MCP_DEFAULT_PRIORITY)


def source_tag_for(rel_path: str) -> str:
    parts = rel_path.split("/")
    return parts[3] if len(parts) >= 4 else "?"


def read_skill_md(rel_path: str) -> str:
    p = PROJECT_ROOT / rel_path / "SKILL.md"
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def read_mcp_metadata(rel_path: str) -> dict:
    p = PROJECT_ROOT / rel_path / "metadata.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def strip_markdown_frontmatter(text: str) -> str:
    """Drop YAML frontmatter so the regex doesn't match upstream metadata
    fields that mirror the same kind of branding boilerplate."""
    if text.startswith("---\n") or text.startswith("---\r\n"):
        end = text.find("\n---", 4)
        if end != -1:
            tail = text[end + 4 :]
            return tail.lstrip("\r\n")
    return text


def has_security_pattern_in_body(skill_md: str) -> tuple[bool, str | None]:
    body = strip_markdown_frontmatter(skill_md)
    for pat in SECURITY_PATTERNS:
        m = pat.search(body)
        if m:
            return True, m.group(0)
    return False, None


# ---------------------------------------------------------------------------
# MCP repo URL extraction + normalization
# ---------------------------------------------------------------------------

GITHUB_URL_RE = re.compile(r"https?://(?:www\.)?github\.com/[^\s\"'<>)]+", re.IGNORECASE)


def extract_repo_url(metadata: dict) -> str | None:
    """Return the upstream GitHub URL if present, else None."""
    raw = metadata.get("rawRecord") or {}

    # 1. modelcontextprotocol-registry: rawRecord.server.repository.url
    server = raw.get("server") if isinstance(raw, dict) else None
    if isinstance(server, dict):
        repo = server.get("repository")
        if isinstance(repo, dict) and isinstance(repo.get("url"), str):
            return repo["url"].strip()

    # 2. glama: rawRecord.repository.url
    repo = raw.get("repository") if isinstance(raw, dict) else None
    if isinstance(repo, dict) and isinstance(repo.get("url"), str):
        return repo["url"].strip()
    if isinstance(repo, str) and repo.strip():
        return repo.strip()

    # 3. pulsemcp: rawRecord.source_code_url
    if isinstance(raw, dict):
        sc = raw.get("source_code_url")
        if isinstance(sc, str) and sc.strip():
            return sc.strip()

    # 4. smithery: rawRecord.homepage (most are github), detail may also have repo
    if isinstance(raw, dict):
        hp = raw.get("homepage")
        if isinstance(hp, str) and "github.com" in hp.lower():
            return hp.strip()

    detail = metadata.get("detail")
    if isinstance(detail, dict):
        # detail.homepage / detail.repository / detail.source / etc.
        for key in ("homepage", "source", "repository"):
            val = detail.get(key)
            if isinstance(val, str) and "github.com" in val.lower():
                return val.strip()
            if isinstance(val, dict) and isinstance(val.get("url"), str):
                return val["url"].strip()

    # 5. last resort: scan the rawRecord JSON text for any github.com URL
    try:
        blob = json.dumps(raw, ensure_ascii=False)
        m = GITHUB_URL_RE.search(blob)
        if m:
            return m.group(0)
    except Exception:
        pass
    return None


def normalize_repo_url(url: str) -> str | None:
    """Normalize a GitHub repo URL to <owner>/<repo> lowercase, or None
    if it can't be cleanly normalized."""
    if not url:
        return None
    s = url.strip()
    s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^www\.", "", s, flags=re.IGNORECASE)
    if not s.lower().startswith("github.com/"):
        return None
    rest = s[len("github.com/"):].rstrip("/")
    rest = re.sub(r"\.git$", "", rest, flags=re.IGNORECASE)
    parts = rest.split("/")
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if not owner or not repo:
        return None
    return f"{owner.lower()}/{repo.lower()}"


# ---------------------------------------------------------------------------
# MinHash + LSH on SKILL.md bodies
# ---------------------------------------------------------------------------

def shingles(text: str, k: int = DEFAULT_SHINGLE_K) -> set[str]:
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


# Pre-compute random salts for k hash permutations. Salts are deterministic
# from a fixed seed so reruns are reproducible.
_MINHASH_SALTS = [hashlib.sha256(f"distill-skill-{i}".encode()).digest()[:8]
                  for i in range(256)]


def minhash_signature(shingle_set: set[str], num_hashes: int) -> tuple[int, ...]:
    if not shingle_set:
        return tuple([0] * num_hashes)
    sig: list[int] = [0xFFFFFFFFFFFFFFFF] * num_hashes
    for sh in shingle_set:
        h = hashlib.sha256(sh.encode("utf-8")).digest()
        h_int = int.from_bytes(h[:8], "big")
        for i in range(num_hashes):
            salt = int.from_bytes(_MINHASH_SALTS[i], "big")
            v = h_int ^ salt
            if v < sig[i]:
                sig[i] = v
    return tuple(sig)


def estimated_jaccard(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a) if sig_a else 0.0


def lsh_candidate_pairs(sigs: list[tuple[int, ...]],
                         num_bands: int, rows_per_band: int) -> set[tuple[int, int]]:
    buckets: dict[tuple[int, tuple[int, ...]], list[int]] = defaultdict(list)
    for idx, sig in enumerate(sigs):
        for band_i in range(num_bands):
            start = band_i * rows_per_band
            band = sig[start : start + rows_per_band]
            buckets[(band_i, band)].append(idx)
    pairs: set[tuple[int, int]] = set()
    for items in buckets.values():
        if len(items) < 2:
            continue
        for i in range(len(items)):
            a = items[i]
            for j in range(i + 1, len(items)):
                b = items[j]
                pairs.add((min(a, b), max(a, b)))
    return pairs


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            nxt = self.parent[x]
            self.parent[x] = root
            x = nxt
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


# ---------------------------------------------------------------------------
# Rule application
# ---------------------------------------------------------------------------

def apply_skill_rules(skill_paths: list[str], args: argparse.Namespace
                      ) -> tuple[list[str], list[dict], list[dict]]:
    """Apply short-content + branding-only-match. Return (kept, drops, debug_records)."""
    kept: list[str] = []
    drops: list[dict] = []
    debug: list[dict] = []
    for path in skill_paths:
        body = read_skill_md(path)
        if len(body) < args.min_skill_chars:
            drops.append({
                "path": path, "rule": "short-content",
                "evidence": f"SKILL.md len={len(body)} < {args.min_skill_chars}",
            })
            continue
        ok, sample = has_security_pattern_in_body(body)
        if not ok:
            drops.append({
                "path": path, "rule": "branding-only-match",
                "evidence": "no SECURITY_PATTERNS hit in SKILL.md body (frontmatter stripped)",
            })
            continue
        kept.append(path)
        debug.append({"path": path, "match": sample})
    return kept, drops, debug


def apply_skill_minhash(kept_paths: list[str], args: argparse.Namespace
                         ) -> tuple[list[str], list[dict], list[dict]]:
    """Cluster surviving SKILL.md bodies by MinHash. Return (kept_after, drops, cluster_summary)."""
    if args.no_minhash or not kept_paths:
        return kept_paths, [], []
    print(f"[stage2] MinHash on {len(kept_paths)} skill candidates "
          f"(threshold={args.minhash_threshold}, hashes={DEFAULT_MINHASH_NUM_HASHES})",
          file=sys.stderr)
    sigs: list[tuple[int, ...]] = []
    for path in kept_paths:
        body = strip_markdown_frontmatter(read_skill_md(path))
        sigs.append(minhash_signature(shingles(body), DEFAULT_MINHASH_NUM_HASHES))

    pairs = lsh_candidate_pairs(sigs, DEFAULT_MINHASH_BANDS, DEFAULT_MINHASH_ROWS)
    uf = UnionFind(len(kept_paths))
    confirmed_pairs = 0
    for a, b in pairs:
        if estimated_jaccard(sigs[a], sigs[b]) >= args.minhash_threshold:
            uf.union(a, b)
            confirmed_pairs += 1
    print(f"[stage2] LSH candidate pairs={len(pairs)}, confirmed near-dup pairs={confirmed_pairs}",
          file=sys.stderr)

    by_root: dict[int, list[int]] = defaultdict(list)
    for i in range(len(kept_paths)):
        by_root[uf.find(i)].append(i)

    new_kept: list[str] = []
    drops: list[dict] = []
    cluster_summary: list[dict] = []
    for root, members in by_root.items():
        if len(members) == 1:
            new_kept.append(kept_paths[members[0]])
            continue
        # Pick representative by source priority then path length / lex.
        members_sorted = sorted(members, key=lambda i: (
            priority_for_skill(kept_paths[i]),
            len(kept_paths[i]),
            kept_paths[i],
        ))
        rep = kept_paths[members_sorted[0]]
        new_kept.append(rep)
        for idx in members_sorted[1:]:
            drops.append({
                "path": kept_paths[idx], "rule": "minhash-near-dup",
                "evidence": f"near-duplicate of {rep} (jaccard >= {args.minhash_threshold})",
            })
        cluster_summary.append({
            "size": len(members_sorted),
            "representative": rep,
            "duplicates": [kept_paths[i] for i in members_sorted[1:]],
            "uniqueSources": sorted({source_tag_for(kept_paths[i]) for i in members_sorted}),
        })
    cluster_summary.sort(key=lambda c: -c["size"])
    return new_kept, drops, cluster_summary


def apply_mcp_rules(mcp_paths: list[str], args: argparse.Namespace
                    ) -> tuple[list[str], list[dict], list[dict]]:
    """Apply repo-URL dedup + short-content. Return (kept, drops, repo_clusters)."""
    # First: short-content + extract repo URL per candidate.
    survivors: list[tuple[str, str | None]] = []  # (path, normalized_repo_url)
    drops: list[dict] = []
    for path in mcp_paths:
        meta = read_mcp_metadata(path)
        desc = (meta.get("description") or meta.get("shortDescription") or "")
        readme = meta.get("readme") or ""
        body_len = len(desc) + len(readme)
        if body_len < args.min_mcp_chars:
            drops.append({
                "path": path, "rule": "short-content",
                "evidence": f"description+readme len={body_len} < {args.min_mcp_chars}",
            })
            continue
        url = extract_repo_url(meta)
        norm = normalize_repo_url(url) if url else None
        survivors.append((path, norm))

    # Then: group by normalized repo URL.
    by_url: dict[str, list[str]] = defaultdict(list)
    no_url: list[str] = []
    for path, norm in survivors:
        if norm:
            by_url[norm].append(path)
        else:
            no_url.append(path)

    kept: list[str] = list(no_url)  # cannot dedup these; keep all
    repo_clusters: list[dict] = []
    for url, members in by_url.items():
        if len(members) == 1:
            kept.append(members[0])
            continue
        members_sorted = sorted(members, key=lambda p: (priority_for_mcp(p), len(p), p))
        rep = members_sorted[0]
        kept.append(rep)
        for dup in members_sorted[1:]:
            drops.append({
                "path": dup, "rule": "mcp-repo-url-dedup",
                "evidence": f"shares repo {url} with kept representative {rep}",
            })
        repo_clusters.append({
            "size": len(members_sorted),
            "repo": url,
            "representative": rep,
            "duplicates": members_sorted[1:],
            "uniqueSources": sorted({source_tag_for(p) for p in members_sorted}),
        })
    repo_clusters.sort(key=lambda c: -c["size"])
    return kept, drops, repo_clusters


# ---------------------------------------------------------------------------
# Manifest write + summary
# ---------------------------------------------------------------------------

def by_rule_counts(drops: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for d in drops:
        counts[d["rule"]] += 1
    return dict(counts)


def main() -> int:
    args = parse_args()

    if not args.stage1_manifest.is_file():
        print(f"Stage-1 manifest not found: {args.stage1_manifest}", file=sys.stderr)
        return 2

    stage1 = json.loads(args.stage1_manifest.read_text(encoding="utf-8"))
    skill_inputs = [cl["representative"]["path"] for cl in stage1["skill"]["clusters"]]
    mcp_inputs = [cl["representative"]["path"] for cl in stage1["mcp"]["clusters"]]
    print(f"Stage 1 reps: {len(skill_inputs)} skill, {len(mcp_inputs)} MCP",
          file=sys.stderr)

    # SKILL.md rules
    skill_kept_after_rules, skill_drops_rules, skill_debug = apply_skill_rules(skill_inputs, args)
    print(f"After short-content + branding-only-match: {len(skill_kept_after_rules)} skill remain "
          f"(dropped {len(skill_drops_rules)})", file=sys.stderr)

    # SKILL.md MinHash
    skill_kept, minhash_drops, minhash_clusters = apply_skill_minhash(
        skill_kept_after_rules, args)
    skill_drops_all = skill_drops_rules + minhash_drops
    print(f"After MinHash: {len(skill_kept)} skill remain "
          f"(MinHash dropped {len(minhash_drops)})", file=sys.stderr)

    # MCP rules
    mcp_kept, mcp_drops, repo_clusters = apply_mcp_rules(mcp_inputs, args)
    print(f"After MCP rules: {len(mcp_kept)} MCP remain (dropped {len(mcp_drops)})",
          file=sys.stderr)

    # Print summary
    print()
    print(f"=== Stage 2 result ===")
    print(f"SKILL.md  : {len(skill_inputs)} → {len(skill_kept)} "
          f"(dropped {len(skill_drops_all)}, "
          f"{round(len(skill_drops_all)/len(skill_inputs)*100, 2) if skill_inputs else 0}%)")
    by_rule_skill = by_rule_counts(skill_drops_all)
    for rule, n in by_rule_skill.items():
        print(f"    by rule: {rule}={n}")
    print(f"MCP server: {len(mcp_inputs)} → {len(mcp_kept)} "
          f"(dropped {len(mcp_drops)}, "
          f"{round(len(mcp_drops)/len(mcp_inputs)*100, 2) if mcp_inputs else 0}%)")
    by_rule_mcp = by_rule_counts(mcp_drops)
    for rule, n in by_rule_mcp.items():
        print(f"    by rule: {rule}={n}")
    total_in = len(skill_inputs) + len(mcp_inputs)
    total_out = len(skill_kept) + len(mcp_kept)
    print(f"\nResidual after Stage 2: {total_out} (was {total_in} after Stage 1, "
          f"original 10249)")

    if args.print_top > 0:
        print(f"\n--- top {args.print_top} MCP repo-URL clusters ---")
        for cl in repo_clusters[: args.print_top]:
            print(f"  size={cl['size']} repo={cl['repo']} sources={cl['uniqueSources']}")
        print(f"\n--- top {args.print_top} SKILL.md MinHash clusters ---")
        for cl in minhash_clusters[: args.print_top]:
            print(f"  size={cl['size']} sources={cl['uniqueSources']} rep={cl['representative']}")

    if args.dry_run:
        print("\n[dry-run] manifest not written.")
        return 0

    today = datetime.date.today().isoformat()
    manifest_name = args.manifest_name or f"dedup_stage2_filter_{today}.json"
    manifest_path = args.reports_dir.expanduser().resolve() / manifest_name
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "stage": "stage2-filter",
        "ranAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "stage1Manifest": str(args.stage1_manifest.resolve().relative_to(PROJECT_ROOT.resolve())),
        "thresholds": {
            "minSkillChars": args.min_skill_chars,
            "minMcpChars": args.min_mcp_chars,
            "minhashThreshold": args.minhash_threshold,
            "minhashEnabled": not args.no_minhash,
        },
        "skill": {
            "inputCount": len(skill_inputs),
            "keptCount": len(skill_kept),
            "droppedCount": len(skill_drops_all),
            "byRule": by_rule_skill,
            "kept": sorted(skill_kept),
            "dropped": skill_drops_all,
            "minhashClusters": minhash_clusters,
        },
        "mcp": {
            "inputCount": len(mcp_inputs),
            "keptCount": len(mcp_kept),
            "droppedCount": len(mcp_drops),
            "byRule": by_rule_mcp,
            "kept": sorted(mcp_kept),
            "dropped": mcp_drops,
            "repoUrlClusters": repo_clusters,
        },
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nManifest written: {relative_to_root(manifest_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
