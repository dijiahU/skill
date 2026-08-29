#!/usr/bin/env python3

"""Fetch security-related MCP servers from Glama.

Glama exposes a public cursor-paginated API at glama.ai/api/mcp/v1/servers
(search via query=). The script combines security-oriented search queries
with the SECURITY_PATTERNS regex (extended with the project book's
scanner / guardrail / policy / trust / vetter), deduplicates by id, and
writes each match as
data/raw/mcp_servers/glama/security/<owner>__<name>/metadata.json.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "mcp_servers"
DEFAULT_REGISTRY = "glama"
DEFAULT_CATEGORY = "security"
DEFAULT_API_BASE = "https://glama.ai"
DEFAULT_PAGE_SIZE = 100
DEFAULT_REQUEST_DELAY = 0.2

DEFAULT_QUERIES = (
    "security", "scanner", "guardrail", "audit", "policy",
    "trust", "vetter", "vulnerability", "credential", "secret",
    "compliance", "encryption", "authentication", "authorization",
    "owasp", "sast", "dast", "sbom", "phishing", "ransomware",
    "siem", "firewall", "waf", "prompt injection", "jailbreak",
    "supply chain",
)

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


@dataclass(frozen=True)
class ServerCandidate:
    server_id: str
    namespace: str
    slug: str
    name: str
    description: str
    record: dict[str, object]
    queries: tuple[str, ...] = ()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch security-related MCP servers from Glama into the "
                    "local mcp_servers storage layout."
    )
    p.add_argument("--api-base", default=DEFAULT_API_BASE)
    p.add_argument("--dest", type=Path, default=DEFAULT_DEST_ROOT)
    p.add_argument("--registry", default=DEFAULT_REGISTRY)
    p.add_argument("--category", default=DEFAULT_CATEGORY)
    p.add_argument("--query", action="append", dest="queries", default=None,
                   help="Search query. Repeat. Default: built-in security set.")
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE,
                   help="`first` parameter, default %(default)s")
    p.add_argument("--max-servers", type=int, default=0)
    p.add_argument(
        "--max-pages-per-query",
        type=int,
        default=0,
        help="Stop each query after this many API pages. 0 = no page cap.",
    )
    p.add_argument("--no-content-filter", action="store_true")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--print-results", action="store_true")
    return p.parse_args()


def urlopen_with_retries(request: urllib.request.Request) -> bytes:
    last: BaseException | None = None
    for attempt in range(7):
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                return resp.read()
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


def http_get_json(url: str) -> object:
    req = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "distill-skill-fetcher",
    })
    return json.loads(urlopen_with_retries(req).decode("utf-8"))


def to_candidate(item: dict[str, object], queries: tuple[str, ...]) -> ServerCandidate | None:
    sid = item.get("id")
    if not isinstance(sid, str):
        return None
    namespace = str(item.get("namespace") or "")
    slug = str(item.get("slug") or sid)
    return ServerCandidate(
        server_id=sid,
        namespace=namespace,
        slug=slug,
        name=str(item.get("name") or slug),
        description=str(item.get("description") or ""),
        record=dict(item),
        queries=queries,
    )


def candidate_text(c: ServerCandidate) -> str:
    repo = c.record.get("repository")
    repo_text = ""
    if isinstance(repo, dict):
        repo_text = str(repo.get("url") or "")
    elif isinstance(repo, str):
        repo_text = repo
    attrs = c.record.get("attributes") or []
    attr_text = " ".join(a for a in attrs if isinstance(a, str))
    return "\n".join([c.server_id, c.namespace, c.slug, c.name, c.description, repo_text, attr_text])


def is_security(c: ServerCandidate) -> bool:
    return any(p.search(candidate_text(c)) for p in SECURITY_PATTERNS)


def normalized_dirname(namespace: str, slug: str) -> str:
    raw = f"{namespace}__{slug}" if namespace else slug
    n = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return n.lower() or "server"


def search_query(api_base: str, query: str, page_size: int,
                 request_delay: float,
                 max_pages_per_query: int = 0) -> list[ServerCandidate]:
    base = api_base.rstrip("/")
    cursor: str | None = None
    found: list[ServerCandidate] = []
    pages = 0
    while True:
        params = {"query": query, "first": page_size}
        if cursor:
            params["after"] = cursor
        url = f"{base}/api/mcp/v1/servers?{urllib.parse.urlencode(params)}"
        data = http_get_json(url)
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected payload from {url}")
        items = data.get("servers") or []
        for it in items:
            if isinstance(it, dict):
                cand = to_candidate(it, (query,))
                if cand:
                    found.append(cand)
        pages += 1
        page_info = data.get("pageInfo") or {}
        has_next = bool(page_info.get("hasNextPage")) if isinstance(page_info, dict) else False
        next_cursor = page_info.get("endCursor") if isinstance(page_info, dict) else None
        print(f"[glama] q={query!r} page={pages} got={len(items)} running={len(found)} more={has_next}",
              file=sys.stderr)
        if max_pages_per_query and pages >= max_pages_per_query:
            print(
                f"[glama] q={query!r} stopped at max_pages_per_query={max_pages_per_query}",
                file=sys.stderr,
            )
            break
        if not items or not has_next or not isinstance(next_cursor, str):
            break
        cursor = next_cursor
        if request_delay > 0:
            time.sleep(request_delay)
    return found


def destination_for(args: argparse.Namespace, namespace: str, slug: str) -> Path:
    return (
        args.dest.expanduser().resolve()
        / args.registry
        / args.category
        / normalized_dirname(namespace, slug)
    )


def write_metadata(dest: Path, c: ServerCandidate) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "registry": "glama",
        "id": c.server_id,
        "namespace": c.namespace,
        "slug": c.slug,
        "name": c.name,
        "description": c.description,
        "discoveryQueries": list(c.queries),
        "rawRecord": c.record,
    }
    (dest / "metadata.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.max_servers < 0 or args.max_pages_per_query < 0 or args.page_size < 1:
        raise ValueError("Invalid numeric flag")

    queries = tuple(args.queries or DEFAULT_QUERIES)
    by_id: dict[str, ServerCandidate] = {}
    for q in queries:
        for c in search_query(
            args.api_base,
            q,
            args.page_size,
            args.request_delay,
            args.max_pages_per_query,
        ):
            existing = by_id.get(c.server_id)
            if existing is None:
                by_id[c.server_id] = c
            else:
                merged = tuple(dict.fromkeys((*existing.queries, *c.queries)))
                by_id[c.server_id] = ServerCandidate(
                    server_id=existing.server_id,
                    namespace=existing.namespace,
                    slug=existing.slug,
                    name=existing.name,
                    description=existing.description,
                    record=existing.record,
                    queries=merged,
                )
        if args.request_delay > 0:
            time.sleep(args.request_delay)

    candidates = list(by_id.values())
    if not args.no_content_filter:
        candidates = [c for c in candidates if is_security(c)]
    candidates.sort(key=lambda c: (c.namespace, c.slug))
    if args.max_servers:
        candidates = candidates[: args.max_servers]
    print(f"Discovered {len(candidates)} matching server(s) after dedup+filter.", file=sys.stderr)

    if args.dry_run:
        for c in candidates:
            print(f"{c.namespace}/{c.slug} | queries={','.join(c.queries)} | {c.description[:80]}")
        return 0

    saved = skipped = 0
    for c in candidates:
        dest = destination_for(args, c.namespace, c.slug)
        if dest.exists() and not args.overwrite:
            skipped += 1
            continue
        write_metadata(dest, c)
        saved += 1

    print(f"Done: saved={saved} skipped-existing={skipped} total={len(candidates)}.")
    if args.print_results:
        for c in candidates:
            print(f"{c.namespace}/{c.slug} -> {destination_for(args, c.namespace, c.slug)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
