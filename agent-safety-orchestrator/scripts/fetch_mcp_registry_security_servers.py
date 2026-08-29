#!/usr/bin/env python3

"""Fetch security-related MCP servers from modelcontextprotocol/registry.

The official registry exposes a cursor-paginated v0 API at
registry.modelcontextprotocol.io. The script walks the catalog, filters
candidates against the security keyword regex (extended with the project
book's MCP-oriented terms scanner / guardrail / policy / trust / vetter),
and writes each match as
data/raw/mcp_servers/modelcontextprotocol-registry/security/<slug>/metadata.json.
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
DEFAULT_REGISTRY = "modelcontextprotocol-registry"
DEFAULT_CATEGORY = "security"
DEFAULT_API_BASE = "https://registry.modelcontextprotocol.io"
DEFAULT_PAGE_SIZE = 100
DEFAULT_REQUEST_DELAY = 0.15

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
        # MCP-specific extension from the project book:
        r"\bscanner\b", r"\bguard(?:rail)?\b", r"\bguardian\b",
        r"\bpolicy\b", r"\btrust\b", r"\bvetter\b",
    )
)


@dataclass(frozen=True)
class ServerCandidate:
    name: str
    slug: str
    title: str
    description: str
    record: dict[str, object]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch security-related MCP servers from the official "
                    "modelcontextprotocol/registry into the local mcp_servers "
                    "storage layout."
    )
    p.add_argument("--api-base", default=DEFAULT_API_BASE,
                   help="Registry API base. Default: %(default)s")
    p.add_argument("--dest", type=Path, default=DEFAULT_DEST_ROOT,
                   help="Destination root. Default: %(default)s")
    p.add_argument("--registry", default=DEFAULT_REGISTRY,
                   help="Registry directory name. Default: %(default)s")
    p.add_argument("--category", default=DEFAULT_CATEGORY,
                   help="Local category. Default: %(default)s")
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE,
                   help="Page size. Default: %(default)s")
    p.add_argument("--max-servers", type=int, default=0,
                   help="Cap saved servers after filter. 0 = no cap.")
    p.add_argument("--no-content-filter", action="store_true",
                   help="Save every server, skipping the keyword regex.")
    p.add_argument("--overwrite", action="store_true",
                   help="Replace existing destination directories.")
    p.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY,
                   help="Sleep between requests. Default: %(default)s")
    p.add_argument("--dry-run", action="store_true",
                   help="Print candidates without writing files.")
    p.add_argument("--print-results", action="store_true",
                   help="Print every saved candidate at the end.")
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


def to_candidate(entry: dict[str, object]) -> ServerCandidate | None:
    server = entry.get("server") if isinstance(entry.get("server"), dict) else None
    if not server:
        return None
    name = server.get("name")
    if not isinstance(name, str):
        return None
    description = str(server.get("description") or "")
    title = str(server.get("title") or "")
    # name pattern is reverse-DNS like "io.github.foo/bar" — pick last segment
    # then prefix with first segment for uniqueness.
    parts = name.split("/")
    if len(parts) >= 2:
        owner = parts[0].split(".")[-1] or parts[0]
        slug = f"{owner}__{parts[1]}"
    else:
        slug = name.replace(".", "-")
    return ServerCandidate(
        name=name,
        slug=slug,
        title=title,
        description=description,
        record=dict(entry),
    )


def candidate_text(c: ServerCandidate) -> str:
    repo = c.record.get("server", {}).get("repository") if isinstance(c.record.get("server"), dict) else None
    repo_text = ""
    if isinstance(repo, dict):
        repo_text = str(repo.get("url") or "")
    elif isinstance(repo, str):
        repo_text = repo
    return "\n".join([c.name, c.slug, c.title, c.description, repo_text])


def is_security(c: ServerCandidate) -> bool:
    return any(p.search(candidate_text(c)) for p in SECURITY_PATTERNS)


def normalized_dirname(slug: str) -> str:
    n = re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-._")
    return n.lower() or "server"


def fetch_all(api_base: str, page_size: int, request_delay: float,
              filter_fn, max_servers: int) -> list[ServerCandidate]:
    base = api_base.rstrip("/")
    cursor = None
    matched: list[ServerCandidate] = []
    seen: set[str] = set()
    pages = 0
    while True:
        params = {"limit": page_size}
        if cursor:
            params["cursor"] = cursor
        url = f"{base}/v0/servers?{urllib.parse.urlencode(params)}"
        data = http_get_json(url)
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected payload from {url}")
        items = data.get("servers") or []
        page_match = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            cand = to_candidate(item)
            if cand is None or cand.name in seen:
                continue
            seen.add(cand.name)
            if filter_fn(cand):
                matched.append(cand)
                page_match += 1
                if max_servers and len(matched) >= max_servers:
                    break
        pages += 1
        meta = data.get("metadata") or {}
        next_cursor = meta.get("nextCursor") if isinstance(meta, dict) else None
        print(
            f"[mcp-registry] page={pages} got={len(items)} matched_this_page={page_match} "
            f"matched_total={len(matched)} cursor={'<more>' if next_cursor else '<end>'}",
            file=sys.stderr,
        )
        if max_servers and len(matched) >= max_servers:
            break
        if not isinstance(next_cursor, str) or not next_cursor:
            break
        cursor = next_cursor
        if request_delay > 0:
            time.sleep(request_delay)
    return matched


def destination_for(args: argparse.Namespace, slug: str) -> Path:
    return (
        args.dest.expanduser().resolve()
        / args.registry
        / args.category
        / normalized_dirname(slug)
    )


def write_metadata(dest: Path, c: ServerCandidate) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "registry": "modelcontextprotocol-registry",
        "name": c.name,
        "slug": c.slug,
        "title": c.title,
        "description": c.description,
        "rawRecord": c.record,
    }
    (dest / "metadata.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.max_servers < 0:
        raise ValueError("--max-servers must be >= 0")
    if args.page_size < 1:
        raise ValueError("--page-size must be >= 1")

    filter_fn = (lambda _c: True) if args.no_content_filter else is_security
    candidates = fetch_all(args.api_base, args.page_size, args.request_delay,
                            filter_fn, args.max_servers)
    print(f"Discovered {len(candidates)} matching server(s).", file=sys.stderr)

    if args.dry_run:
        for c in candidates:
            print(f"{c.slug} | {c.name} | {c.description[:80]}")
        return 0

    saved = 0
    skipped = 0
    for c in candidates:
        dest = destination_for(args, c.slug)
        if dest.exists() and not args.overwrite:
            skipped += 1
            continue
        write_metadata(dest, c)
        saved += 1

    print(f"Done: saved={saved} skipped-existing={skipped} total={len(candidates)}.")
    if args.print_results:
        for c in candidates:
            print(f"{c.slug} -> {destination_for(args, c.slug)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
