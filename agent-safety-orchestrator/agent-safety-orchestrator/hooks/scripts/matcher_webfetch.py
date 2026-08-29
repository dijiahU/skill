#!/usr/bin/env python3
"""WebFetch|WebSearch matcher — runs before any outbound HTTP from the agent.

Atoms covered (2):
- detect-unsafe-url
- enforce-network-egress-allowlist
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from lib_common import (
    read_event, aggregate, check, UNSAFE_URL_PATTERNS,
)


def main() -> int:
    event = read_event()
    url = event.get("url") or event.get("tool_input", {}).get("url", "")
    if not url:
        return 0

    verdicts = []

    # detect-unsafe-url — block file://, javascript:, IMDS endpoints, localhost
    if UNSAFE_URL_PATTERNS.search(url):
        verdicts.append(check(
            "detect-unsafe-url", True,
            f"Unsafe URL scheme/target: {url}",
        ))

    # enforce-network-egress-allowlist
    allowlist = os.environ.get("SAFETY_ORCH_EGRESS_ALLOWLIST", "")
    if allowlist:
        allowed_hosts = {h.strip() for h in allowlist.split(",") if h.strip()}
        host = urlparse(url).hostname or ""
        if host and not _host_matches_any(host, allowed_hosts):
            verdicts.append(check(
                "enforce-network-egress-allowlist", True,
                f"Host '{host}' is not in egress allowlist",
            ))

    return aggregate(verdicts) if verdicts else 0


def _host_matches_any(host: str, allowed: set[str]) -> bool:
    """Wildcard matching: '*.example.com' matches 'foo.example.com'."""
    for pattern in allowed:
        if pattern == host:
            return True
        if pattern.startswith("*.") and host.endswith(pattern[1:]):
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
