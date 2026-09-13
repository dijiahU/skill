"""OAS-specific bounded cleanup; no changes to other SDK consumers."""

import subprocess

from openhands.sdk import get_logger
from openhands.workspace import DockerWorkspace


logger = get_logger(__name__)


def stop_owned_container(container_id: str) -> None:
    """Stop exactly the ID created by this workspace; bound host-client wait."""
    result = subprocess.run(
        ["docker", "stop", "--time", "10", container_id],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode and "No such container" not in result.stderr:
        raise RuntimeError(f"OAS workspace stop failed: {result.stderr[-1000:]}")


class BoundedDockerWorkspace(DockerWorkspace):
    """Do not hold a GPU consumer forever while stopping a vanished sandbox."""

    def cleanup(self) -> None:
        container_id = self._container_id
        if not container_id:
            return
        self._stop_logs.set()
        if self._logs_thread and self._logs_thread.is_alive():
            self._logs_thread.join(timeout=2)
        # No destructor retry after an explicit failed cleanup; leave the exact
        # ID in diagnostics for owned-resource review, never broad cleanup.
        self._container_id = None
        logger.info("Stopping OAS container with 30s deadline: %s", container_id)
        stop_owned_container(container_id)
