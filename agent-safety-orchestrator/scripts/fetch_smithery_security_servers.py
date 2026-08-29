#!/usr/bin/env python3

"""Fetch security-related MCP servers from Smithery.

Smithery exposes a public registry API at registry.smithery.ai. The script
combines a built-in security keyword query set (the project book's
scanner / guardrail / audit / policy / trust / vetter plus the broader
SECURITY_PATTERNS) with page-based pagination, deduplicates by qualifiedName,
and writes each match as
data/raw/mcp_servers/smithery/security/<owner>__<name>/metadata.json.

The detail endpoint at /servers/<qualifiedName> returns richer info than the
listing (e.g. README, deployment instructions) and is fetched per match unless
--no-detail is given.
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
DEFAULT_REGISTRY = "smithery"
DEFAULT_CATEGORY = "security"
DEFAULT_API_BASE = "https://registry.smithery.ai"
DEFAULT_PAGE_SIZE = 50  # conservative; api accepts higher
DEFAULT_REQUEST_DELAY = 0.15
DEFAULT_WORKERS = 4

DEFAULT_QUERIES = (
    "security", "secure", "scanner", "guardrail", "audit",
    "policy", "trust", "vetter", "vulnerability", "credential",
    "secret", "compliance", "encryption", "authentication",
    "authorization", "owasp", "sast", "dast", "sbom",
    "phishing", "ransomware", "siem", "firewall", "waf",
    "prompt injection", "jailbreak", "supply chain",
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
    qualified_name: str
    namespace: str
    slug: str
    display_name: str
    description: str
    record: dict[str, object]
    queries: tuple[str, ...] = ()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch security-related MCP servers from Smithery into "
                    "the local mcp_servers storage layout."
    )
    p.add_argument("--api-base", default=DEFAULT_API_BASE,
                   help="Smithery registry API base. Default: %(default)s")
    p.add_argument("--dest", type=Path, default=DEFAULT_DEST_ROOT)
    p.add_argument("--registry", default=DEFAULT_REGISTRY)
    p.add_argument("--category", default=DEFAULT_CATEGORY)
    p.add_argument("--query", action="append", dest="queries", default=None,
                   help="Search query. Repeat for multiple. Default: built-in security set.")
    p.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    p.add_argument("--max-servers", type=int, default=0,
                   help="Cap saved servers after dedup+filter. 0 = no cap.")
    p.add_argument("--no-content-filter", action="store_true",
                   help="Save every search hit, skipping the content regex pass.")
    p.add_argument("--no-detail", action="store_true",
                   help="Skip per-server detail fetch (faster, less metadata).")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY)
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                   help="Concurrent detail fetches. Default: %(default)s")
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
    qn = item.get("qualifiedName")
    if not isinstance(qn, str) or "/" not in qn:
        return None
    namespace, slug = qn.split("/", 1)
    return ServerCandidate(
        qualified_name=qn,
        namespace=namespace,
        slug=slug,
        display_name=str(item.get("displayName") or slug),
        description=str(item.get("description") or ""),
        record=dict(item),
        queries=queries,
    )


def candidate_text(c: ServerCandidate) -> str:
    return "\n".join([
        c.qualified_name, c.display_name, c.description,
        str(c.record.get("homepage") or ""),
    ])


def is_security(c: ServerCandidate) -> bool:
    return any(p.search(candidate_text(c)) for p in SECURITY_PATTERNS)


def normalized_dirname(qualified_name: str) -> str:
    raw = qualified_name.replace("/", "__")
    n = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return n.lower() or "server"


def search_query(api_base: str, query: str, page_size: int,
                 request_delay: float) -> list[ServerCandidate]:
    base = api_base.rstrip("/")
    page = 1
    found: list[ServerCandidate] = []
    while True:
        url = f"{base}/servers?{urllib.parse.urlencode({'q': query, 'page': page, 'pageSize': page_size})}"
        data = http_get_json(url)
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected payload from {url}")
        items = data.get("servers") or []
        for it in items:
            if isinstance(it, dict):
                cand = to_candidate(it, (query,))
                if cand:
                    found.append(cand)
        pagination = data.get("pagination") or {}
        total = pagination.get("totalPages") if isinstance(pagination, dict) else None
        print(f"[smithery] q={query!r} page={page} got={len(items)} running={len(found)} total_pages={total}",
              file=sys.stderr)
        if not items or not isinstance(total, int) or page >= total:
            break
        page += 1
        if request_delay > 0:
            time.sleep(request_delay)
    return found


def fetch_detail(api_base: str, qualified_name: str) -> dict[str, object]:
    url = f"{api_base.rstrip('/')}/servers/{urllib.parse.quote(qualified_name, safe='/')}"
    data = http_get_json(url)
    return data if isinstance(data, dict) else {}


def destination_for(args: argparse.Namespace, qualified_name: str) -> Path:
    return (
        args.dest.expanduser().resolve()
        / args.registry
        / args.category
        / normalized_dirname(qualified_name)
    )


def write_metadata(dest: Path, c: ServerCandidate, detail: dict[str, object] | None) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "registry": "smithery",
        "qualifiedName": c.qualified_name,
        "namespace": c.namespace,
        "slug": c.slug,
        "displayName": c.display_name,
        "description": c.description,
        "discoveryQueries": list(c.queries),
        "rawRecord": c.record,
        "detail": detail or {},
    }
    (dest / "metadata.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.max_servers < 0 or args.page_size < 1 or args.workers < 1:
        raise ValueError("Invalid numeric flag")

    queries = tuple(args.queries or DEFAULT_QUERIES)
    by_qn: dict[str, ServerCandidate] = {}
    for q in queries:
        for c in search_query(args.api_base, q, args.page_size, args.request_delay):
            existing = by_qn.get(c.qualified_name)
            if existing is None:
                by_qn[c.qualified_name] = c
            else:
                merged_queries = tuple(dict.fromkeys((*existing.queries, *c.queries)))
                by_qn[c.qualified_name] = ServerCandidate(
                    qualified_name=existing.qualified_name,
                    namespace=existing.namespace,
                    slug=existing.slug,
                    display_name=existing.display_name,
                    description=existing.description,
                    record=existing.record,
                    queries=merged_queries,
                )
        if args.request_delay > 0:
            time.sleep(args.request_delay)

    candidates = list(by_qn.values())
    if not args.no_content_filter:
        candidates = [c for c in candidates if is_security(c)]
    candidates.sort(key=lambda c: c.qualified_name)
    if args.max_servers:
        candidates = candidates[: args.max_servers]
    print(f"Discovered {len(candidates)} matching server(s) after dedup+filter.", file=sys.stderr)

    if args.dry_run:
        for c in candidates:
            print(f"{c.qualified_name} | queries={','.join(c.queries)} | {c.description[:80]}")
        return 0

    def run_one(c: ServerCandidate) -> tuple[str, str]:
        dest = destination_for(args, c.qualified_name)
        if dest.exists() and not args.overwrite:
            return c.qualified_name, "skipped-existing"
        detail: dict[str, object] | None = None
        if not args.no_detail:
            try:
                detail = fetch_detail(args.api_base, c.qualified_name)
            except Exception as e:
                # Detail endpoint is best-effort: a 404 / stale id should not
                # abort the whole batch. Save the listing record anyway.
                print(f"[smithery] detail fetch failed for {c.qualified_name}: {e}",
                      file=sys.stderr)
                detail = {"_detailFetchError": str(e)}
            if args.request_delay > 0:
                time.sleep(args.request_delay)
        write_metadata(dest, c, detail)
        return c.qualified_name, "saved"

    saved = skipped = 0
    if args.workers == 1:
        for c in candidates:
            _, status = run_one(c)
            if status == "saved": saved += 1
            else: skipped += 1
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for fut in as_completed([ex.submit(run_one, c) for c in candidates]):
                _, status = fut.result()
                if status == "saved": saved += 1
                else: skipped += 1

    print(f"Done: saved={saved} skipped-existing={skipped} total={len(candidates)}.")
    if args.print_results:
        for c in candidates:
            print(f"{c.qualified_name} -> {destination_for(args, c.qualified_name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
