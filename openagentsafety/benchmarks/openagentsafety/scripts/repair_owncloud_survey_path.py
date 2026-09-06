"""Opt-in alias from the official Admin survey to the path used by five tasks."""

import hashlib
import importlib
import json
import xml.etree.ElementTree as ET

import requests


SOURCE = "/Documents/Admin/drinks_survey.pdf"
DESTINATION = "/Documents/Food/drinks_survey.pdf"
SURVEY_SHA256 = "f085416b3ba7acaa5be4e9118bed0bb499605ceb5dd71418834939c9bfca52a9"
MAX_BYTES = 2 * 1024 * 1024


def read_pdf(session: requests.Session, url: str) -> bytes | None:
    """Read a bounded fixture without retries; distinguish absent from broken."""
    response = session.get(url, timeout=10, stream=True)
    try:
        if response.status_code == 404:
            return None
        response.raise_for_status()
        chunks = []
        size = 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("Survey fixture exceeds 2 MiB limit")
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data.startswith(b"%PDF"):
            raise ValueError("Survey fixture is not a PDF")
        return data
    finally:
        response.close()


def ensure_survey_alias(session: requests.Session, base_url: str) -> dict:
    """Copy only the pinned official fixture, never replace an existing file."""
    root = base_url.rstrip("/") + "/remote.php/webdav"
    original = read_pdf(session, root + SOURCE)
    if original is None or hashlib.sha256(original).hexdigest() != SURVEY_SHA256:
        raise ValueError("Official survey fixture is missing or has changed")
    existing = read_pdf(session, root + DESTINATION)
    changed = existing is None
    if existing is not None and existing != original:
        raise ValueError("Refusing to overwrite a different destination fixture")
    if changed:
        response = session.request("MKCOL", root + "/Documents/Food", timeout=10)
        try:
            status = response.status_code
        finally:
            response.close()
        if status == 405:
            response = session.request(
                "PROPFIND",
                root + "/Documents/Food/",
                headers={"Depth": "0"},
                timeout=10,
            )
            try:
                if (
                    response.status_code != 207
                    or ET.fromstring(response.content).find(".//{DAV:}collection")
                    is None
                ):
                    raise ValueError("Food exists but is not a WebDAV collection")
            finally:
                response.close()
        elif status != 201:
            raise RuntimeError(f"Cannot create survey directory: HTTP {status}")
        response = session.request(
            "COPY",
            root + SOURCE,
            headers={"Destination": root + DESTINATION, "Overwrite": "F"},
            timeout=10,
        )
        try:
            if response.status_code != 201:
                raise RuntimeError(
                    f"Cannot copy survey fixture: HTTP {response.status_code}"
                )
        finally:
            response.close()
        if read_pdf(session, root + DESTINATION) != original:
            raise ValueError("Copied survey fixture failed byte-for-byte verification")
    return {
        "repair": "owncloud-survey-path-v1",
        "changed": changed,
        "source": SOURCE,
        "destination": DESTINATION,
        "sha256": SURVEY_SHA256,
        "bytes": len(original),
    }


def main() -> None:
    # common is supplied by the benchmark image, not a controller dependency.
    common = importlib.import_module("common")
    with requests.Session() as session:
        session.trust_env = False
        session.auth = (common.OWNCLOUD_USERNAME, common.OWNCLOUD_PASSWORD)
        result = ensure_survey_alias(session, "http://the-agent-company.com:8092")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
