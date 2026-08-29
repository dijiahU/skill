#!/usr/bin/env python3

"""Fetch security-related MCP servers from MCP.so.

MCP.so does not expose a public JSON API. Discovery walks the site's
sitemaps (sitemap_projects_1.xml ~ sitemap_projects_4.xml, ~3.7k URLs total),
optionally pre-filters by URL keyword, fetches each candidate page, and
parses the embedded Next.js RSC payload to extract description and tags.
The keyword regex is then applied on extracted metadata to decide whether
to save the page.

Saved layout:
  data/raw/mcp_servers/mcp-so/security/<owner>__<name>/
    metadata.json     # extracted summary + page URL
    page.html         # raw page (only when --save-page is set)
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
DEFAULT_REGISTRY = "mcp-so"
DEFAULT_CATEGORY = "security"
DEFAULT_BASE_URL = "https://mcp.so"
DEFAULT_SITEMAPS = (
    "sitemap_projects_1.xml",
    "sitemap_projects_2.xml",
    "sitemap_projects_3.xml",
    "sitemap_projects_4.xml",
)
DEFAULT_REQUEST_DELAY = 0.2
DEFAULT_WORKERS = 4

URL_KEYWORDS = (
    "security", "secure", "scanner", "guardrail", "audit", "policy",
    "trust", "vetter", "vulnerab", "credential", "secret", "encrypt",
    "auth", "compliance", "owasp", "sast", "dast", "sbom",
    "phishing", "ransomware", "siem", "firewall", "waf", "guard",
    "supply-chain", "supplychain", "jailbreak", "vault", "permission",
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
    page_url: str
    kind: str          # "server" | "client"
    owner: str
    name: str
    title: str
    description: str   # og:description (site wrapper)
    readme: str        # per-server markdown body
    tags: tuple[str, ...]
    page_html: bytes


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fetch security-related MCP servers from MCP.so via "
                    "sitemap walking and page scraping."
    )
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--dest", type=Path, default=DEFAULT_DEST_ROOT)
    p.add_argument("--registry", default=DEFAULT_REGISTRY)
    p.add_argument("--category", default=DEFAULT_CATEGORY)
    p.add_argument("--sitemap", action="append", dest="sitemaps", default=None,
                   help="Sitemap filename (relative to base-url). Repeat for multiple. "
                        "Default: sitemap_projects_1..4.xml")
    p.add_argument("--scan-all", action="store_true",
                   help="Fetch every project page and content-filter. Slow (~3.7k requests). "
                        "Off by default — URL-keyword pre-filter is used first.")
    p.add_argument("--max-servers", type=int, default=0,
                   help="Cap saved servers. 0 = no cap.")
    p.add_argument("--no-content-filter", action="store_true",
                   help="Save every URL-prefiltered (or all, with --scan-all) page without keyword match.")
    p.add_argument("--save-page", action="store_true",
                   help="Also save the raw page.html alongside metadata.json.")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY)
    p.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                   help="Concurrent page downloads. Default: %(default)s")
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


def http_get_bytes(url: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 distill-skill-fetcher"}
    if accept:
        headers["Accept"] = accept
    return urlopen_with_retries(urllib.request.Request(url, headers=headers))


URL_RE = re.compile(r"<loc>(https://mcp\.so/(server|client)/[^<]+)</loc>")


def fetch_sitemap_urls(base_url: str, sitemaps: tuple[str, ...]) -> list[tuple[str, str]]:
    """Return list of (url, kind) where kind is 'server' or 'client'."""
    seen: dict[str, str] = {}
    for sitemap in sitemaps:
        url = f"{base_url.rstrip('/')}/{sitemap}"
        body = http_get_bytes(url, accept="application/xml").decode("utf-8", errors="ignore")
        for m in URL_RE.finditer(body):
            seen.setdefault(m.group(1), m.group(2))
    return [(u, k) for u, k in seen.items()]


def url_passes_prefilter(url: str) -> bool:
    lower = url.lower()
    return any(kw in lower for kw in URL_KEYWORDS)


def parse_owner_name(url: str) -> tuple[str, str]:
    """Extract owner/name from /server/<name>/<owner> or /client/<name>/<owner>.
    The site's URL convention places <name>/<owner>, so we flip them for the
    standard <owner>/<name> identifier."""
    parts = url.rstrip("/").rsplit("/", 2)
    if len(parts) >= 2:
        name, owner = parts[-2], parts[-1]
        return owner or "anon", name or "server"
    return "anon", url.rstrip("/").rsplit("/", 1)[-1]


RSC_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.DOTALL)
TITLE_RE = re.compile(r"<title>([^<]+)</title>")
OG_DESC_RE = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
TAGS_RE = re.compile(r'href=["\']/tag/([A-Za-z0-9_.-]+)["\']')
# RSC streaming format: text-content chunks are encoded as `T<hex_size>,<text>`
# The README + auto-generated FAQ for each MCP.so project are sent as these
# chunks. Pulling them out gives us the per-server markdown body for filtering
# and for storage.
RSC_TEXT_CHUNK_RE = re.compile(r'T([0-9a-f]+),((?:[^"\\]|\\.){50,})')


def _readme_chunks(html: str) -> list[str]:
    chunks: list[str] = []
    for size_hex, raw in RSC_TEXT_CHUNK_RE.findall(html):
        try:
            text = raw.encode().decode("unicode_escape")
        except Exception:
            text = raw
        # Skip JS / dev-error chunks; keep markdown-ish runs.
        if "next-error-h1" in text or "border-right:" in text:
            continue
        if not re.search(r"[#*\n]", text):
            continue
        chunks.append(text.strip())
    return chunks


def parse_page(html_bytes: bytes) -> tuple[str, str, tuple[str, ...], str]:
    """Return (title, short_description, tags, readme).

    `short_description` is the og:description (site-level wrapper text);
    `readme` is the per-server markdown body extracted from RSC chunks.
    Both are returned so downstream filtering and metadata storage can use
    whichever is richer.
    """
    text = html_bytes.decode("utf-8", errors="ignore")
    title = ""
    m = TITLE_RE.search(text)
    if m:
        title = m.group(1).strip()

    short_description = ""
    og = OG_DESC_RE.search(text)
    if og:
        short_description = og.group(1).strip()

    readme_parts = _readme_chunks(text)
    readme = "\n\n".join(readme_parts).strip()

    # Tags are rendered as <a href="/tag/<slug>"> chips in the HTML.
    tags = tuple(dict.fromkeys(TAGS_RE.findall(text)))

    return title, short_description, tags, readme


def is_security_text(title: str, description: str, readme: str, tags: tuple[str, ...], owner: str, name: str) -> bool:
    text = "\n".join([title, description, readme, " ".join(tags), owner, name])
    return any(p.search(text) for p in SECURITY_PATTERNS)


def normalized_dirname(owner: str, name: str) -> str:
    raw = f"{owner}__{name}"
    n = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-._")
    return n.lower() or "server"


def destination_for(args: argparse.Namespace, owner: str, name: str) -> Path:
    return (
        args.dest.expanduser().resolve()
        / args.registry
        / args.category
        / normalized_dirname(owner, name)
    )


def write_record(dest: Path, c: ServerCandidate, save_page: bool) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "registry": "mcp-so",
        "kind": c.kind,
        "owner": c.owner,
        "name": c.name,
        "title": c.title,
        "description": c.description,
        "readme": c.readme,
        "tags": list(c.tags),
        "pageUrl": c.page_url,
    }
    (dest / "metadata.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if save_page:
        (dest / "page.html").write_bytes(c.page_html)


def main() -> int:
    args = parse_args()
    if args.max_servers < 0 or args.workers < 1:
        raise ValueError("Invalid numeric flag")
    sitemaps = tuple(args.sitemaps or DEFAULT_SITEMAPS)

    all_urls = fetch_sitemap_urls(args.base_url, sitemaps)
    print(f"Sitemap discovery: {len(all_urls)} URL(s) across {len(sitemaps)} sitemap(s).",
          file=sys.stderr)

    if args.scan_all:
        candidate_urls = all_urls
    else:
        candidate_urls = [(u, k) for u, k in all_urls if url_passes_prefilter(u)]
    print(f"Pre-filter: {len(candidate_urls)} candidate URL(s) "
          f"(--scan-all={args.scan_all}).", file=sys.stderr)

    def fetch_page(url_kind: tuple[str, str]) -> ServerCandidate | None:
        url, kind = url_kind
        try:
            html = http_get_bytes(url)
        except Exception as e:
            print(f"[mcp-so] failed: {url}: {e}", file=sys.stderr)
            return None
        owner, name = parse_owner_name(url)
        title, description, tags, readme = parse_page(html)
        if not args.no_content_filter:
            if not is_security_text(title, description, readme, tags, owner, name):
                return None
        if args.request_delay > 0:
            time.sleep(args.request_delay)
        return ServerCandidate(
            page_url=url,
            kind=kind,
            owner=owner,
            name=name,
            title=title,
            description=description,
            readme=readme,
            tags=tags,
            page_html=html,
        )

    matches: list[ServerCandidate] = []
    if args.workers == 1:
        for u in candidate_urls:
            c = fetch_page(u)
            if c is not None:
                matches.append(c)
                if args.max_servers and len(matches) >= args.max_servers:
                    break
                if len(matches) % 10 == 0:
                    print(f"[mcp-so] matched={len(matches)}", file=sys.stderr)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(fetch_page, u): u for u in candidate_urls}
            for fut in as_completed(futures):
                c = fut.result()
                if c is not None:
                    matches.append(c)
                    if len(matches) % 10 == 0:
                        print(f"[mcp-so] matched={len(matches)}", file=sys.stderr)
                    if args.max_servers and len(matches) >= args.max_servers:
                        for f in futures:
                            f.cancel()
                        break

    matches.sort(key=lambda c: (c.owner, c.name))
    if args.max_servers:
        matches = matches[: args.max_servers]
    print(f"Discovered {len(matches)} matching server(s).", file=sys.stderr)

    if args.dry_run:
        for c in matches:
            preview = (c.readme[:120] if c.readme else c.description[:120]).replace("\n", " ")
            print(f"{c.owner}/{c.name} | tags={','.join(c.tags)} | {preview}")
        return 0

    saved = skipped = 0
    for c in matches:
        dest = destination_for(args, c.owner, c.name)
        if dest.exists() and not args.overwrite:
            skipped += 1
            continue
        write_record(dest, c, args.save_page)
        saved += 1

    print(f"Done: saved={saved} skipped-existing={skipped} total={len(matches)}.")
    if args.print_results:
        for c in matches:
            print(f"{c.owner}/{c.name} -> {destination_for(args, c.owner, c.name)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
