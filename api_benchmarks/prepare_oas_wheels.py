"""Build OAS dependency wheels inside its target Linux/amd64 base image."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

from api_benchmarks.bench import HERE, ROOT, environment


PACKAGES = ("openhands-sdk", "openhands-tools", "openhands-agent-server")
BASE_IMAGE = "ghcr.io/sani903/openagentsafety_base_image-image:1.0"


def main() -> None:
    settings = environment(HERE / ".env")
    cache = Path(
        settings.get("OPENAGENTSAFETY_WHEELHOUSE", str(HERE / ".cache/oas-wheels"))
    )
    cache = cache.expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    source = ROOT / "openagentsafety/vendor/software-agent-sdk"
    digest = hashlib.sha256()
    for name in PACKAGES:
        for path in sorted((source / name).rglob("*")):
            if path.is_file() and not any(
                part in {"__pycache__", "build"} or part.endswith(".egg-info")
                for part in path.parts
            ):
                digest.update(str(path.relative_to(source)).encode())
                digest.update(path.read_bytes())
    expected = {
        "platform": "linux/amd64",
        "base_image": BASE_IMAGE,
        "sdk_sha256": digest.hexdigest(),
        "lock_sha256": hashlib.sha256(
            (ROOT / "openagentsafety/uv.lock").read_bytes()
        ).hexdigest(),
    }
    marker = cache / "linux-build.json"
    if (
        marker.exists()
        and json.loads(marker.read_text()) == expected
        and all(
            list(cache.glob(name.replace("-", "_") + "-*.whl")) for name in PACKAGES
        )
    ):
        print("Using verified Linux OAS wheel cache")
        return
    uv = settings.get("UV_BIN", str(HERE / ".venv-tools/bin/uv"))
    freeze = subprocess.check_output(
        [
            uv,
            "pip",
            "freeze",
            "--python",
            str(ROOT / "openagentsafety/.venv/bin/python"),
        ],
        text=True,
        env={**os.environ, "UV_CACHE_DIR": str(HERE / ".cache/uv")},
    )
    (cache / "constraints.txt").write_text(
        "\n".join(
            line
            for line in freeze.splitlines()
            if line
            and not line.startswith("-e ")
            and not line.lower().startswith(PACKAGES)
        )
        + "\n"
    )
    command = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--entrypoint",
        "bash",
    ]
    proxy = settings.get("OAS_BUILD_HTTP_PROXY")
    if proxy:
        command += ["-e", f"HTTP_PROXY={proxy}", "-e", f"HTTPS_PROXY={proxy}"]
    command += [
        "-e",
        "PIP_DEFAULT_TIMEOUT=120",
        "-e",
        "PIP_RETRIES=3",
        "-v",
        f"{source}:/sdk:ro",
        "-v",
        f"{cache}:/wheelhouse",
        BASE_IMAGE,
        "-lc",
        "set -euo pipefail; mkdir -p /tmp/sdk-build; "
        "cp -a /sdk/openhands-sdk /sdk/openhands-tools /sdk/openhands-agent-server /tmp/sdk-build/; "
        "python -m pip wheel --find-links /wheelhouse --constraint /wheelhouse/constraints.txt --wheel-dir /wheelhouse "
        "/tmp/sdk-build/openhands-sdk /tmp/sdk-build/openhands-tools /tmp/sdk-build/openhands-agent-server",
    ]
    subprocess.run(command, check=True)
    marker.write_text(json.dumps(expected, indent=2) + "\n")


if __name__ == "__main__":
    main()
