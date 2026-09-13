"""Cache the official pinned Linux Codex package and verify npm integrity."""

import base64
import hashlib
import json
from pathlib import Path
import subprocess


VERSION = "0.149.1"
CACHE = Path(__file__).resolve().parent / ".cache"


def download(url: str, target: Path) -> None:
    """Download a public package without provider credentials."""
    subprocess.run(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--retry",
            "3",
            "--max-time",
            "300",
            url,
            "--output",
            str(target),
        ],
        check=True,
    )


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    package = f"codex-{VERSION}-linux-x64"
    metadata = CACHE / f"{package}-package.json"
    download(f"https://registry.npmjs.org/@openai/codex/{VERSION}-linux-x64", metadata)
    dist = json.loads(metadata.read_text())["dist"]
    url = f"https://registry.npmjs.org/@openai/codex/-/{package}.tgz"
    if dist["tarball"] != url or not dist["integrity"].startswith("sha512-"):
        raise ValueError("Unexpected official package metadata")
    archive = CACHE / f"{package}.tgz"

    def valid() -> bool:
        if not archive.is_file():
            return False
        digest = base64.b64encode(
            hashlib.sha512(archive.read_bytes()).digest()
        ).decode()
        return f"sha512-{digest}" == dist["integrity"]

    if not valid():
        download(url, archive)
    if not valid():
        raise ValueError("Codex package integrity check failed")
    print(f"Validated Codex {VERSION} Linux x64 package: {archive}")
    print(f"Set TERMINALBENCH_CODEX_ARCHIVE={archive} in api_benchmarks/.env")


if __name__ == "__main__":
    main()
