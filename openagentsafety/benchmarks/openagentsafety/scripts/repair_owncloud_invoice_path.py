"""Alias the pinned official invoice collection without moving or overwriting it."""

import hashlib
import importlib
import json
import time
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit

import requests


SOURCE = "/Documents/Financials/invoices_pdf/"
DESTINATION = "/Documents/Financials/invoices_pdfs/"
INVOICE_NAMES = frozenset(f"INV{i:04d}.pdf" for i in range(500))
MANIFEST_SHA256 = "3e45210570ee67e7d48a142548c9a0fe0870326453910a9d5fd6693f8e5fa135"
MAX_XML_BYTES = 1024 * 1024
MAX_FILE_BYTES = 128 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
REPAIR_SECONDS = 180


def _request(
    session: requests.Session,
    method: str,
    url: str,
    deadline: float,
    limit: int,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Invoice repair exceeded its time budget")
    response = session.request(
        method,
        url,
        headers=headers,
        timeout=min(10, remaining),
        stream=True,
        allow_redirects=False,
    )
    try:
        chunks = []
        size = 0
        for chunk in response.iter_content(65536):
            if time.monotonic() > deadline:
                raise TimeoutError("Invoice repair exceeded its time budget")
            size += len(chunk)
            if size > limit:
                raise ValueError("Invoice response exceeds the byte limit")
            chunks.append(chunk)
        return response.status_code, b"".join(chunks)
    finally:
        response.close()


def _manifest(
    session: requests.Session, url: str, deadline: float
) -> tuple[str, int] | None:
    status, content = _request(
        session, "PROPFIND", url, deadline, MAX_XML_BYTES, {"Depth": "1"}
    )
    if status == 404:
        return None
    if status != 207:
        raise RuntimeError(f"Cannot list invoice collection: HTTP {status}")
    tree = ET.fromstring(content)
    root_path = unquote(urlsplit(url).path).rstrip("/")
    sizes: dict[str, int] = {}
    root_seen = False
    for item in tree.findall("{DAV:}response"):
        path = unquote(urlsplit(item.findtext("{DAV:}href", "")).path)
        collection = item.find(".//{DAV:}collection") is not None
        if path.rstrip("/") == root_path:
            if root_seen or not collection:
                raise ValueError("Invalid invoice collection root")
            root_seen = True
            continue
        if not path.startswith(root_path + "/") or collection:
            raise ValueError("Unexpected entry in invoice collection")
        name = path[len(root_path) + 1 :]
        if name not in INVOICE_NAMES or name in sizes:
            raise ValueError("Unexpected or duplicate invoice filename")
        size = int(item.findtext(".//{DAV:}getcontentlength", "-1"))
        if size < 1 or size > MAX_FILE_BYTES:
            raise ValueError("Invalid invoice file size")
        sizes[name] = size
    if not root_seen or sizes.keys() != INVOICE_NAMES:
        raise ValueError("Invoice collection does not contain the expected files")
    total = sum(sizes.values())
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Invoice collection exceeds the total byte limit")
    records = []
    for name in sorted(sizes):
        status, data = _request(
            session, "GET", url.rstrip("/") + "/" + name, deadline, MAX_FILE_BYTES
        )
        if status != 200:
            raise RuntimeError(f"Cannot read invoice fixture: HTTP {status}")
        if len(data) != sizes[name] or not data.startswith(b"%PDF"):
            raise ValueError("Invoice bytes differ from the declared PDF fixture")
        records.append(f"{name}:{hashlib.sha256(data).hexdigest()}\n")
    digest = hashlib.sha256("".join(records).encode()).hexdigest()
    return digest, total


def ensure_invoice_alias(session: requests.Session, base_url: str) -> dict:
    """Copy a verified collection once; reject different pre-existing data."""
    deadline = time.monotonic() + REPAIR_SECONDS
    root = base_url.rstrip("/") + "/remote.php/webdav"
    original = _manifest(session, root + SOURCE, deadline)
    if original is None or original[0] != MANIFEST_SHA256:
        raise ValueError("Official invoice fixtures are missing or have changed")
    existing = _manifest(session, root + DESTINATION, deadline)
    changed = existing is None
    if existing is not None and existing != original:
        raise ValueError("Refusing to overwrite different invoice fixtures")
    if changed:
        status, _ = _request(
            session,
            "COPY",
            root + SOURCE,
            deadline,
            MAX_XML_BYTES,
            {"Destination": root + DESTINATION, "Depth": "infinity", "Overwrite": "F"},
        )
        if status != 201:
            raise RuntimeError(f"Cannot copy invoice fixtures: HTTP {status}")
        if _manifest(session, root + DESTINATION, deadline) != original:
            raise ValueError("Copied invoice collection failed verification")
    return {
        "repair": "owncloud-invoice-path-v1",
        "changed": changed,
        "source": SOURCE,
        "destination": DESTINATION,
        "files": len(INVOICE_NAMES),
        "sha256": original[0],
        "bytes": original[1],
    }


def main() -> None:
    common = importlib.import_module("common")
    with requests.Session() as session:
        session.trust_env = False
        session.auth = (common.OWNCLOUD_USERNAME, common.OWNCLOUD_PASSWORD)
        result = ensure_invoice_alias(session, "http://the-agent-company.com:8092")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
