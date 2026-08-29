#!/usr/bin/env python3

"""Fetch security-related MCP servers from PulseMCP.

PulseMCP exposes a public, unauthenticated API at api.pulsemcp.com that
lists ~14k MCP servers. The script paginates the catalog (server-driven
`next` URL), filters by name + short_description against the security
keyword regex shared with the SKILL.md fetchers (extended with MCP-oriented
terms scanner / guardrail / policy / trust / vetter from the project book),
and writes each match as
data/raw/mcp_servers/pulsemcp/security/<slug>/metadata.json.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = PROJECT_ROOT / "data" / "raw" / "mcp_servers"
DEFAULT_REGISTRY = "pulsemcp"
DEFAULT_CATEGORY = "security"
DEFAULT_API_BASE = "https://api.pulsemcp.com"
DEFAULT_PAGE_SIZE = 100  # accepted up to 100 by api
DEFAULT_REQUEST_DELAY = 0.15
DEFAULT_WORKERS = 1  # writes are local; single thread is fine for io-light json

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
    page_url: str
    external_url: str | None
    short_description: str
    record: dict[str, object]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch security-related MCP servers from PulseMCP into the "
            "local mcp_servers storage layout."
        )
    )
    parser.add_argument("--api-base", default=DEFAULT_API_BASE,
                        help="PulseMCP API base. Default: %(default)s")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST_ROOT,
                        help="Destination root. Default: %(default)s")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY,
                        help="Registry directory under destination root. Default: %(default)s")
    parser.add_argument("--category", default=DEFAULT_CATEGORY,
                        help="Local category directory. Default: %(default)s")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE,
                        help="Page size (api caps at 100). Default: %(default)s")
    parser.add_argument("--max-servers", type=int, default=0,
                        help="Cap total saved servers after filter. 0 = no cap.")
    parser.add_argument("--no-content-filter", action="store_true",
                        help="Save every server, skipping the keyword regex.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing destination directories.")
    parser.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY,
                        help="Sleep between requests. Default: %(default)s")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print candidates without writing files.")
    parser.add_argument("--print-results", action="store_true",
                        help="Print every saved candidate at the end.")
    return parser.parse_args()


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
        "Accept": "application/json",
        "User-Agent": "distill-skill-fetcher",
    })
    return json.loads(urlopen_with_retries(req).decode("utf-8"))


def to_candidate(item: dict[str, object]) -> ServerCandidate | None:
    page_url = item.get("url")
    name = item.get("name")
    if not isinstance(page_url, str) or not isinstance(name, str):
        return None
    # PulseMCP page URL: https://www.pulsemcp.com/servers/<slug>
    slug = page_url.rstrip("/").rsplit("/", 1)[-1] or name
    desc = item.get("short_description")
    return ServerCandidate(
        name=name,
        slug=slug,
        page_url=page_url,
        external_url=item.get("external_url") if isinstance(item.get("external_url"), str) else None,
        short_description=desc if isinstance(desc, str) else "",
        record=item,
    )


def candidate_text(c: ServerCandidate) -> str:
    return "\n".join([c.name, c.slug, c.short_description, c.external_url or ""])


def is_security(c: ServerCandidate) -> bool:
    text = candidate_text(c)
    return any(p.search(text) for p in SECURITY_PATTERNS)


def normalized_dirname(slug: str) -> str:
    n = re.sub(r"[^A-Za-z0-9._-]+", "-", slug).strip("-._")
    return n.lower() or "server"


def fetch_all(api_base: str, page_size: int, request_delay: float,
              filter_fn, max_servers: int) -> list[ServerCandidate]:
    """Walk the catalog using the api's `next` URL until exhausted or
    enough security-matched candidates are accumulated."""
    url = f"{api_base.rstrip('/')}/v0beta/servers?count_per_page={page_size}"
    matched: list[ServerCandidate] = []
    seen_slugs: set[str] = set()
    pages = 0
    total = None
    while url:
        data = http_get_json(url)
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected payload from {url}")
        if total is None:
            total = data.get("total_count")
        items = data.get("servers") or []
        page_match = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            cand = to_candidate(item)
            if cand is None or cand.slug in seen_slugs:
                continue
            seen_slugs.add(cand.slug)
            if filter_fn(cand):
                matched.append(cand)
                page_match += 1
                if max_servers and len(matched) >= max_servers:
                    break
        pages += 1
        print(
            f"[pulsemcp] page={pages} got={len(items)} matched_this_page={page_match} "
            f"matched_total={len(matched)} catalog_total={total}",
            file=sys.stderr,
        )
        if max_servers and len(matched) >= max_servers:
            break
        url = data.get("next") if isinstance(data.get("next"), str) else None
        if request_delay > 0 and url:
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
        "registry": "pulsemcp",
        "name": c.name,
        "slug": c.slug,
        "pageUrl": c.page_url,
        "externalUrl": c.external_url,
        "shortDescription": c.short_description,
        "rawRecord": c.record,
    }
    (dest / "metadata.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.max_servers < 0:
        raise ValueError("--max-servers must be >= 0")
    if args.page_size < 1 or args.page_size > 100:
        raise ValueError("--page-size must be in [1, 100]")

    filter_fn = (lambda _c: True) if args.no_content_filter else is_security
    candidates = fetch_all(args.api_base, args.page_size, args.request_delay,
                            filter_fn, args.max_servers)
    print(f"Discovered {len(candidates)} matching server(s).", file=sys.stderr)

    if args.dry_run:
        for c in candidates:
            print(f"{c.slug} | {c.name} | {c.short_description[:80]}")
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
