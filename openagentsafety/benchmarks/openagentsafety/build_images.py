"""Build OpenAgentSafety Docker image from vendor/software-agent-sdk"""

import logging
import os
import subprocess
import sys
from pathlib import Path

from benchmarks.utils.build_utils import run_docker_build_layer


logger = logging.getLogger(__name__)


def get_wheelhouse_path() -> Path:
    """Return the persistent wheel cache used for network-free image builds."""
    configured = os.getenv("OPENAGENTSAFETY_WHEELHOUSE")
    if configured:
        return Path(configured).expanduser().resolve()
    persistent_root = Path(os.getenv("POD_USER_ROOT", Path(__file__).parents[6]))
    return (persistent_root / "skills" / "cache" / "openagentsafety-wheels").resolve()


def prepare_wheelhouse() -> Path:
    """Build local SDK and dependency wheels outside the source checkout."""
    wheelhouse = get_wheelhouse_path()
    wheelhouse.mkdir(parents=True, exist_ok=True)
    required_patterns = (
        "openhands_sdk-*.whl",
        "openhands_tools-*.whl",
        "openhands_agent_server-*.whl",
    )
    if all(any(wheelhouse.glob(pattern)) for pattern in required_patterns):
        return wheelhouse

    repo_root = Path(__file__).parent.parent.parent
    sdk_root = repo_root / "vendor" / "software-agent-sdk"
    freeze = subprocess.run(
        ["uv", "pip", "freeze", "--python", sys.executable],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    excluded = ("openhands-sdk", "openhands-tools", "openhands-agent-server")
    constraints = wheelhouse / "constraints.txt"
    constraint_lines = [
        line
        for line in freeze.stdout.splitlines()
        if line and not line.startswith("-e ") and not line.lower().startswith(excluded)
    ]
    constraints.write_text("\n".join(constraint_lines) + "\n")
    command = [
        "uv",
        "run",
        "--with",
        "pip",
        "python",
        "-m",
        "pip",
        "wheel",
        "--constraint",
        str(constraints),
        "--wheel-dir",
        str(wheelhouse),
        str(sdk_root / "openhands-sdk"),
        str(sdk_root / "openhands-tools"),
        str(sdk_root / "openhands-agent-server"),
    ]
    env = os.environ.copy()
    env.update(
        {
            "PIP_DEFAULT_TIMEOUT": "300",
            "PIP_RETRIES": "20",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    logger.info("Preparing persistent OpenAgentSafety wheelhouse: %s", wheelhouse)
    subprocess.run(command, cwd=repo_root, env=env, check=True)
    return wheelhouse


def get_vendor_sdk_commit() -> str:
    """Get the commit hash of the vendor SDK."""
    repo_root = Path(__file__).parent.parent.parent
    vendor_sdk_path = repo_root / "vendor" / "software-agent-sdk"

    if not vendor_sdk_path.exists():
        raise RuntimeError(f"Vendor SDK not found at {vendor_sdk_path}")

    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=vendor_sdk_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to get SDK commit: {result.stderr}")

    return result.stdout.strip()


def get_image_name() -> str:
    image_name = os.getenv(
        "EVAL_AGENT_SERVER_IMAGE", "skilldistill-openagentsafety-agent-server"
    )
    tag_prefix = os.getenv("OPENAGENTSAFETY_IMAGE_TAG_PREFIX") or os.getenv(
        "IMAGE_TAG_PREFIX"
    )
    if tag_prefix:
        tag = f"{tag_prefix}-openagentsafety"
    else:
        tag = get_vendor_sdk_commit()
    return f"{image_name}:{tag}"


def check_image_exists(image_name: str) -> bool:
    """Check if a Docker image exists locally."""
    result = subprocess.run(
        ["docker", "images", "-q", image_name],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def build_workspace_image(force_rebuild: bool = False, no_cache: bool = False) -> str:
    """Build Docker image using SDK from vendor folder.

    Args:
        force_rebuild: if True, ignore existing images and rebuild.
        no_cache: if True, pass --no-cache to docker build to avoid layer cache.
    """
    image_name = get_image_name()

    if not force_rebuild and check_image_exists(image_name):
        logger.info(f"#### Using existing image: {image_name}")
        return image_name

    sdk_commit = get_vendor_sdk_commit()

    logger.info(f"#### Building Docker image: {image_name}")
    logger.info(f"#### SDK version: {sdk_commit}")
    logger.info("#### This will take approximately 3-5 minutes...")

    dockerfile_dir = Path(__file__).parent  # benchmarks/benchmarks/openagentsafety/
    build_context = dockerfile_dir.parent.parent

    logger.info(f"Build context: {build_context}")
    logger.info(f"Dockerfile: {dockerfile_dir / 'Dockerfile'}")
    wheelhouse = prepare_wheelhouse()

    # Use shared build helper for consistent error handling and logging
    result = run_docker_build_layer(
        dockerfile=dockerfile_dir / "Dockerfile",
        context=build_context,
        tags=[image_name],
        build_args=None,
        push=False,
        platform="linux/amd64",
        load=True,
        no_cache=no_cache,
        network=os.getenv("OPENAGENTSAFETY_BUILD_NETWORK", "host"),
        additional_contexts={"wheelhouse": str(wheelhouse)},
    )

    if result.error:
        logger.error(f"Build failed: {result.error}")
        raise RuntimeError(f"Failed to build Docker image: {result.error}")

    # Verify image exists in local docker after --load
    if not check_image_exists(image_name):
        raise RuntimeError(
            f"Image {image_name} was not created successfully (not present in local docker)"
        )

    logger.info(f"#### Successfully built {image_name}")
    return image_name


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    image = build_workspace_image(force_rebuild=True, no_cache=False)
    print(f"Image ready: {image}")
