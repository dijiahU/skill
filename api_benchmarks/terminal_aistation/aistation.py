"""Harbor 0.22.0 Docker adapter with explicit resource retention.

Only single-service Linux tasks with public network policies are supported.
Unsupported task requirements fail before host resources are created.
"""
import importlib.metadata
import json
import os
import re
import subprocess
from pathlib import Path

from harbor.environments.base import ExecResult
from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import NetworkMode, TaskOS


def host_path(source: str) -> str:
    if not os.environ.get("DOCKER_HOST", "").startswith("tcp://"):
        return source
    pod = Path(os.environ["POD_USER_ROOT"]).resolve()
    resolved = Path(source).resolve()
    return str(Path(os.environ["HOST_USER_ROOT"]) / resolved.relative_to(pod))


class AIStationDocker(DockerEnvironment):
    """Retain containers and generated configs; never perform host cleanup."""

    def __init__(self, *args, **kwargs):
        if importlib.metadata.version("harbor") != "0.22.0":
            raise RuntimeError("This adapter requires harbor==0.22.0")
        task = kwargs["task_env_config"]
        policies = [kwargs.get("network_policy"), *(kwargs.get("phase_network_policies") or ())]
        if task.os != TaskOS.LINUX or any(
            p and p.network_mode != NetworkMode.PUBLIC for p in policies
        ):
            raise ValueError("Windows and restricted-network tasks need separate validation")
        allow_audited_compose = kwargs.pop("allow_audited_compose", False)
        env_dir = Path(kwargs["environment_dir"])
        if ((env_dir / "docker-compose.yaml").exists() and not allow_audited_compose) or kwargs.get("extra_docker_compose"):
            raise ValueError("Multi-service/custom Compose tasks need separate ownership review")
        if task.gpus or kwargs.get("override_gpus"):
            raise ValueError("Task GPU environments require a separately reserved GPU adapter")
        kwargs["session_id"] = "rick-saber-tbretry-20260913-r1-" + re.sub(
            r"[^a-z0-9_-]", "-", kwargs["session_id"].lower()
        )
        super().__init__(*args, **kwargs)
        self._env_vars.main_image_name = "rick-saber-terminal-" + self.environment_id
        self._retained_dir = self.trial_paths.trial_dir / "aistation" / self.session_id
        self._retained_dir.mkdir(parents=True, exist_ok=False)
        self._runtime_path = self._write("runtime.json", {"services": {"main": {
            "runtime": "runc",
            "labels": {"skilldistill.benchmark": "terminal-bench", "skilldistill.session": self.session_id},
        }}})
        self._started_here = False

    def _write(self, name, value):
        path = self._retained_dir / name
        with path.open("x") as stream:
            json.dump(value, stream, indent=2)
        return path

    @property
    def _docker_compose_paths(self):
        return [*super()._docker_compose_paths, self._runtime_path]

    def _write_mounts_compose_file(self):
        mounts = []
        for mount in self._mounts:
            if mount["type"] != "bind":
                raise ValueError("Only explicitly mapped bind mounts are supported")
            mounts.append({**mount, "source": host_path(mount["source"])})
        return self._write("mounts.json", {"services": {"main": {"volumes": mounts}}})

    def _write_resources_compose_file(self):
        from harbor.environments.docker import write_resources_compose_file
        from harbor.models.trial.config import ResourceMode
        return write_resources_compose_file(
            self._retained_dir / "resources.json",
            cpu_limit=self._resource_limit_value("cpu", auto_mode=ResourceMode.LIMIT),
            memory_limit_mb=self._resource_limit_value("memory", auto_mode=ResourceMode.LIMIT),
        )

    def _write_env_compose_file(self):
        return self._write("environment.json", {"services": {"main": {"environment": self._startup_env()}}})

    async def start(self, force_build=False):
        if force_build:
            raise ValueError("Forced image overwrite is disabled")
        for kind in ("container", "network", "volume"):
            result = subprocess.run(
                ["docker", kind, "ls", *(["-a"] if kind == "container" else []), "-q", "--filter", f"label=com.docker.compose.project={self.session_id}"],
                check=True, capture_output=True, text=True,
            )
            if result.stdout.strip():
                raise RuntimeError(f"Refusing existing {kind} resources for {self.session_id}")
        await super().start(force_build=False)
        self._started_here = True

    async def _run_docker_compose_command(self, command, **kwargs):
        # Harbor performs a stale-resource down before every up. Suppress only
        # that exact request; never turn a cleanup request into host mutation.
        if command == ["down", "--remove-orphans"] and not self._started_here:
            return ExecResult(stdout="Fresh scope; cleanup skipped", stderr="", return_code=0)
        if command[0] in {"down", "stop", "rm", "kill", "restart"}:
            raise RuntimeError("Host resource cleanup requires approval for the exact target")
        if command[0] == "build":
            existing = subprocess.run(
                ["docker", "image", "inspect", self._main_image_name],
                capture_output=True, text=True,
            )
            if existing.returncode == 0:
                return ExecResult(stdout="Reusing existing content-addressed image", stderr="", return_code=0)
        if command[0] == "up":
            command = [*command, "--no-recreate"]
        return await super()._run_docker_compose_command(command, **kwargs)

    async def stop(self, delete=False):
        self.logger.warning("Retained Docker scope %s; no stop/delete performed", self.session_id)
