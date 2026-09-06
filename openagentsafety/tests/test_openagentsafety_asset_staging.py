from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from benchmarks.openagentsafety import run_infer


class FakeResponse:
    def __init__(self, content: bytes, error: Exception | None = None):
        self.content = content
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error


class FakeWorkspace:
    def __init__(self):
        self._container_id = "workspace-id"
        self.uploads: list[tuple[Path, str]] = []
        self.commands: list[tuple[str, int]] = []

    def execute_command(self, command: str, timeout: int):
        self.commands.append((command, timeout))
        if command.startswith("grep the-agent-company"):
            return SimpleNamespace(
                exit_code=0,
                stdout="127.0.0.1 the-agent-company.com\n",
                stderr="",
            )
        if command.startswith("test -e"):
            destination = command.split("test -e ", 1)[1].split(" &&", 1)[0]
            source = next(path for path, dest in self.uploads if dest == destination)
            return SimpleNamespace(
                exit_code=0, stdout=f"{source.stat().st_size}\n", stderr=""
            )
        return SimpleNamespace(exit_code=0, stdout="", stderr="")

    def file_upload(self, source_path: Path, destination_path: str):
        self.uploads.append((source_path, destination_path))
        return SimpleNamespace(success=True, error=None)


class FakeHealthResponse:
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self._message = message
        self.text = message

    def json(self):
        return {"message": self._message}


class FakeHealthSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.trust_env = True
        self.closed = False

    def get(self, url, timeout, **kwargs):
        self.calls.append((url, timeout))
        key = "owncloud" if url.endswith("/status.php") else url.rsplit("/", 1)[-1]
        if url.endswith("/users/sign_in"):
            key = "gitlab"
        return self.responses[key]

    def close(self):
        self.closed = True


def test_task_assets_are_cached_and_uploaded(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse(b"content")

    monkeypatch.setenv("OPENAGENTSAFETY_ASSET_CACHE", str(tmp_path))
    monkeypatch.setattr(run_infer.requests, "get", fake_get)
    workspace = FakeWorkspace()
    url = "https://example.test/task/workspace/input.txt"
    instance = {
        "has_workspace": True,
        "workspace_files": [url],
        "has_utils": True,
        "utils_files": ["https://example.test/task/utils/evaluator.py"],
    }

    run_infer.download_files_for_task(workspace, instance)
    run_infer.download_files_for_task(workspace, instance)

    assert len(calls) == 2
    assert [destination for _, destination in workspace.uploads] == [
        "/workspace/input.txt",
        "/utils/evaluator.py",
        "/workspace/input.txt",
        "/utils/evaluator.py",
    ]
    assert all(source.read_bytes() == b"content" for source, _ in workspace.uploads)


def test_report_distinguishes_partial_graded_trajectory(tmp_path):
    output = tmp_path / "output.jsonl"
    report = tmp_path / "report.json"
    output.write_text(
        run_infer.json.dumps(
            {
                "instance_id": "partial",
                "error": None,
                "test_result": {
                    "final_score": {"result": 0, "total": 1},
                    "skilldistill": {
                        "conversation_error": "Remote conversation got stuck",
                        "graded_from_partial_trajectory": True,
                    },
                },
            }
        )
        + "\n"
    )
    run_infer.generate_report(str(output), str(report), "test-model")
    result = run_infer.json.loads(report.read_text())
    assert result["error_instances"] == 0
    assert result["conversation_error_instances"] == 1
    assert result["partial_trajectory_ids"] == ["partial"]


def test_http_failure_fails_before_upload(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAGENTSAFETY_ASSET_CACHE", str(tmp_path))
    monkeypatch.setattr(
        run_infer.requests,
        "get",
        lambda url, timeout: FakeResponse(b"", RuntimeError("connection failed")),
    )
    monkeypatch.setattr(run_infer.time, "sleep", lambda seconds: None)
    workspace = FakeWorkspace()

    with pytest.raises(RuntimeError, match="Failed to download"):
        run_infer.download_files_for_task(
            workspace,
            {
                "has_workspace": True,
                "workspace_files": ["https://example.test/workspace/empty.txt"],
            },
        )

    assert workspace.uploads == []


def test_intentionally_empty_asset_is_preserved(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAGENTSAFETY_ASSET_CACHE", str(tmp_path))
    monkeypatch.setattr(
        run_infer.requests, "get", lambda url, timeout: FakeResponse(b"")
    )
    workspace = FakeWorkspace()

    run_infer.download_files_for_task(
        workspace,
        {
            "has_utils": True,
            "utils_files": ["https://example.test/utils/dependencies.yml"],
        },
    )

    assert len(workspace.uploads) == 1
    assert workspace.uploads[0][0].stat().st_size == 0


def test_dependency_initialization_skips_tasks_without_services():
    workspace = FakeWorkspace()

    run_infer.initialize_task_dependencies(workspace, {"dependencies": []})

    assert workspace.commands == []


def test_dependency_lease_blocks_same_service_and_releases_on_error(
    monkeypatch, tmp_path
):
    lock_path = tmp_path / "dependency.lock"
    monkeypatch.setenv("OPENAGENTSAFETY_DEPENDENCY_LOCK", str(lock_path))
    fcntl = run_infer.fcntl
    with pytest.raises(RuntimeError, match="task failed"):
        with run_infer.task_dependency_lease({"dependencies": ["owncloud"]}):
            with (tmp_path / "dependency.lock.owncloud").open("a") as same:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(same, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with run_infer.task_dependency_lease({"dependencies": ["plane"]}):
                pass
            raise RuntimeError("task failed")
    with (tmp_path / "dependency.lock.owncloud").open("a") as released:
        fcntl.flock(released, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_dependency_lease_orders_multiple_services(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAGENTSAFETY_DEPENDENCY_LOCK", str(tmp_path / "lease"))
    acquired = []
    monkeypatch.setattr(
        run_infer.fcntl, "flock", lambda file, operation: acquired.append(file.name)
    )
    with run_infer.task_dependency_lease(
        {"dependencies": ["plane", "gitlab", "plane"]}
    ):
        assert acquired == [
            str(tmp_path / "lease.gitlab"),
            str(tmp_path / "lease.plane"),
        ]


def test_worker_holds_dependency_lease_through_parent_cleanup(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAGENTSAFETY_DEPENDENCY_LOCK", str(tmp_path / "lease"))
    fcntl = run_infer.fcntl

    def parent_worker(self, instance, *args):
        with (tmp_path / "lease.gitlab").open("a") as lock_file:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return instance, Mock(spec=run_infer.EvalOutput)

    monkeypatch.setattr(run_infer.Evaluation, "_process_one_sync", parent_worker)
    evaluator = object.__new__(run_infer.OpenAgentSafetyEvaluation)
    instance = run_infer.EvalInstance(
        id="lease-test", data={"dependencies": ["gitlab"]}
    )
    result, _ = evaluator._process_one_sync(instance, 1)
    assert result is instance
    with (tmp_path / "lease.gitlab").open("a") as released:
        fcntl.flock(released, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_plane_reset_and_workspace_use_nonconflicting_network(monkeypatch):
    compose = Mock()
    monkeypatch.setattr(run_infer, "_plane_backup_paths", lambda: [])
    monkeypatch.setattr(run_infer, "_validate_plane_project_containers", Mock())
    monkeypatch.setattr(run_infer, "_api_compose", compose)
    monkeypatch.setattr(run_infer, "_wait_for_dependency_health", Mock())

    run_infer.reset_plane_dependency()

    assert len(compose.call_args_list) == 2
    for call in compose.call_args_list:
        override = call.kwargs["override"]
        assert "subnet: 192.168.240.0/24" in override
        assert f"name: {run_infer.SERVICE_FORWARD_ROUTES['plane'][0][0]}" in override
        assert '"18091:80"' in override
        assert call.kwargs["project"] == "skilldistill-oas-plane-isolated"


def test_host_mapping_uses_task_local_forwarders():
    workspace = FakeWorkspace()

    run_infer.setup_host_mapping(workspace)

    assert workspace.commands[0][0] == (
        "echo '127.0.0.1 the-agent-company.com' >> /etc/hosts"
    )


def test_service_forwarding_connects_once_per_network(monkeypatch):
    checked = Mock()
    validated = Mock()
    monkeypatch.setattr(run_infer, "_run_checked", checked)
    monkeypatch.setattr(run_infer, "_validate_service_route", validated)
    monkeypatch.setattr(
        run_infer, "_workspace_container_id", lambda workspace: "workspace-id"
    )
    workspace = FakeWorkspace()

    run_infer.setup_service_forwarding(
        workspace, {"dependencies": ["owncloud", "owncloud"]}
    )

    connect_calls = [
        call
        for call in checked.call_args_list
        if call.args[0][:3] == ["docker", "network", "connect"]
    ]
    assert len(connect_calls) == 1
    assert connect_calls[0].args[0] == [
        "docker",
        "network",
        "connect",
        "skilldistill-oas-core-network",
        "workspace-id",
    ]
    exec_call = checked.call_args_list[-1].args[0]
    assert exec_call[:6] == [
        "docker",
        "exec",
        "-d",
        "workspace-id",
        "python",
        "-c",
    ]
    assert run_infer.json.loads(exec_call[-1]) == [
        [8092, "skilldistill-oas-owncloud", 80],
        [9980, "skilldistill-oas-owncloud-collabora", 9980],
    ]
    assert validated.call_count == 2
    assert len(workspace.commands) == 2


def test_workspace_container_validation_rejects_unowned_container(monkeypatch):
    info = {"Config": {"Labels": {}}, "NetworkSettings": {"Networks": {}}}
    monkeypatch.setattr(
        run_infer.subprocess,
        "run",
        Mock(
            return_value=SimpleNamespace(
                returncode=0,
                stdout=run_infer.json.dumps([info]),
                stderr="",
            )
        ),
    )
    workspace = FakeWorkspace()

    with pytest.raises(RuntimeError, match="unrecognized workspace"):
        run_infer._workspace_container_id(workspace)


def test_dependency_initialization_dispatches_local_reset(monkeypatch, tmp_path):
    reset = Mock()
    monkeypatch.setenv(
        "OPENAGENTSAFETY_DEPENDENCY_LOCK", str(tmp_path / "dependency.lock")
    )
    monkeypatch.setattr(run_infer, "reset_owncloud_dependency", reset)
    workspace = FakeWorkspace()

    run_infer.initialize_task_dependencies(
        workspace,
        {"dependencies": ["owncloud", "owncloud"]},
    )

    reset.assert_called_once_with()
    assert workspace.commands == []


def test_gitlab_only_dependency_uses_local_reset(monkeypatch):
    reset = Mock()
    monkeypatch.setattr(run_infer, "reset_gitlab_dependency", reset)
    workspace = FakeWorkspace()

    run_infer.initialize_task_dependencies(
        workspace,
        {"dependencies": ["gitlab"]},
    )

    reset.assert_called_once_with()
    assert workspace.commands == []


def test_gitlab_reset_removes_only_expected_volumes_and_never_pulls(monkeypatch):
    info = {
        "Config": {
            "Labels": {
                "com.docker.compose.project": "skilldistill-oas-gitlab-isolated",
                "com.docker.compose.service": "gitlab",
            }
        },
        "Mounts": [
            {"Type": "volume", "Destination": "/etc/gitlab"},
            {"Type": "volume", "Destination": "/var/log/gitlab"},
            {"Type": "volume", "Destination": "/var/opt/gitlab"},
        ],
    }
    completed = [
        SimpleNamespace(returncode=0, stdout=run_infer.json.dumps([info]), stderr=""),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
        SimpleNamespace(returncode=0, stdout="", stderr=""),
    ]
    run = Mock(side_effect=completed)
    session = FakeHealthSession({"gitlab": FakeHealthResponse(200, "ok")})
    repair = Mock()
    monkeypatch.setattr(run_infer.subprocess, "run", run)
    monkeypatch.setattr(run_infer.requests, "Session", lambda: session)
    monkeypatch.setattr(run_infer, "repair_gitlab_access_token", repair)

    run_infer.reset_gitlab_dependency()

    assert run.call_args_list[0].args[0] == [
        "docker",
        "inspect",
        "skilldistill-oas-gitlab-isolated",
    ]
    assert run.call_args_list[1].args[0][:6] == [
        "docker",
        "compose",
        "-p",
        "skilldistill-oas-gitlab-isolated",
        "-f",
        "-",
    ]
    assert run.call_args_list[1].args[0][-5:] == [
        "rm",
        "-f",
        "-s",
        "-v",
        "gitlab",
    ]
    assert run.call_args_list[2].args[0][-5:] == [
        "up",
        "--pull",
        "never",
        "-d",
        "gitlab",
    ]
    assert "--pull" in run.call_args_list[2].args[0]
    assert "never" in run.call_args_list[2].args[0]
    for call in run.call_args_list[1:]:
        config = run_infer.json.loads(call.kwargs["input"])
        omnibus = config["services"]["gitlab"]["environment"]["GITLAB_OMNIBUS_CONFIG"]
        assert "puma['worker_processes'] = 2" in omnibus
        assert "external_url 'http://the-agent-company.com:8929'" in omnibus
        assert "gitlab_rails['gitlab_shell_ssh_port'] = 2424" in omnibus
        assert (
            config["services"]["gitlab"]["container_name"] == run_infer.GITLAB_CONTAINER
        )
        assert config["services"]["gitlab"]["ports"] == ["18929:8929"]
    repair.assert_called_once_with()


def test_gitlab_token_activation_is_short_lived(monkeypatch):
    completed = SimpleNamespace(
        returncode=0,
        stdout="oas_gitlab_token_active=true\n",
        stderr="",
    )
    run = Mock(return_value=completed)
    monkeypatch.setattr(run_infer.subprocess, "run", run)

    run_infer.repair_gitlab_access_token()

    command = run.call_args.args[0]
    assert command[:5] == [
        "docker",
        "exec",
        run_infer.GITLAB_CONTAINER,
        "gitlab-rails",
        "runner",
    ]
    assert "Date.current + 1" in command[5]
    assert "revoked:" not in command[5]


def test_gitlab_token_can_be_expired_after_batch(monkeypatch):
    completed = SimpleNamespace(
        returncode=0,
        stdout="oas_gitlab_token_expired=true\n",
        stderr="",
    )
    run = Mock(return_value=completed)
    monkeypatch.setattr(run_infer.subprocess, "run", run)

    run_infer.expire_gitlab_access_token()

    assert "Date.yesterday" in run.call_args.args[0][5]


def test_dependency_initialization_rejects_unknown_service():
    workspace = FakeWorkspace()

    with pytest.raises(RuntimeError, match="Unsupported task dependencies: jira"):
        run_infer.initialize_task_dependencies(
            workspace,
            {"dependencies": ["jira"]},
        )


def test_dependency_initialization_surfaces_reset_failure(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "OPENAGENTSAFETY_DEPENDENCY_LOCK", str(tmp_path / "dependency.lock")
    )
    monkeypatch.setattr(
        run_infer,
        "reset_owncloud_dependency",
        Mock(side_effect=RuntimeError("owncloud service unavailable")),
    )

    with pytest.raises(RuntimeError, match="owncloud service unavailable"):
        run_infer.initialize_task_dependencies(
            FakeWorkspace(),
            {"dependencies": ["owncloud"]},
        )


def test_dependency_preflight_skips_tasks_without_services(monkeypatch):
    session_factory = Mock()
    monkeypatch.setattr(run_infer.requests, "Session", session_factory)

    run_infer.preflight_task_dependencies({"dependencies": []})

    session_factory.assert_not_called()


def test_dependency_preflight_checks_each_service_without_proxy(monkeypatch):
    session = FakeHealthSession(
        {
            "owncloud": FakeHealthResponse(200, "ok"),
            "gitlab": FakeHealthResponse(200, "ok"),
        }
    )
    monkeypatch.setenv("OPENAGENTSAFETY_DOCKER_HOST_ADDR", "10.0.0.2")
    monkeypatch.setenv("OPENAGENTSAFETY_DEPENDENCY_PREFLIGHT_TIMEOUT", "4")
    monkeypatch.setattr(run_infer.requests, "Session", lambda: session)

    run_infer.preflight_task_dependencies(
        {"dependencies": ["owncloud", "gitlab", "owncloud"]}
    )

    assert session.trust_env is False
    assert session.calls == [
        ("http://10.0.0.2:2999/api/healthcheck/owncloud", (2.0, 4.0)),
        ("http://10.0.0.2:18929/users/sign_in", (2.0, 4.0)),
    ]
    assert session.closed is True


def test_dependency_preflight_reports_all_unhealthy_services(monkeypatch):
    monkeypatch.setattr(run_infer, "_plane_direct_health", lambda timeout: False)
    session = FakeHealthSession(
        {
            "owncloud": FakeHealthResponse(500, "Web service is not available yet"),
            "plane": FakeHealthResponse(400, "failed to login"),
        }
    )
    monkeypatch.setenv("OPENAGENTSAFETY_SERVICE_CONTROL_URL", "http://oas:2999/")
    monkeypatch.setattr(run_infer.requests, "Session", lambda: session)

    with pytest.raises(RuntimeError) as exc_info:
        run_infer.preflight_task_dependencies({"dependencies": ["owncloud", "plane"]})

    message = str(exc_info.value)
    assert "owncloud: HTTP 500 (Web service is not available yet)" in message
    assert "plane: isolated service authentication unavailable" in message
    assert session.closed is True


def test_dependency_preflight_can_allow_cold_start(monkeypatch):
    session_factory = Mock()
    monkeypatch.setenv("OPENAGENTSAFETY_DEPENDENCY_PREFLIGHT", "0")
    monkeypatch.setattr(run_infer.requests, "Session", session_factory)

    run_infer.preflight_task_dependencies({"dependencies": ["gitlab"]})

    session_factory.assert_not_called()


def test_prefetch_failure_happens_before_workspace_allocation(monkeypatch):
    docker_workspace = Mock()
    monkeypatch.setattr(run_infer, "build_workspace_image", lambda: "test:image")
    monkeypatch.setattr(
        run_infer,
        "prefetch_task_assets",
        Mock(side_effect=RuntimeError("asset unavailable")),
    )
    monkeypatch.setattr(run_infer, "DockerWorkspace", docker_workspace)
    evaluator = Mock(
        spec=run_infer.OpenAgentSafetyEvaluation, metadata=Mock(details={})
    )
    instance = Mock(spec=run_infer.EvalInstance, id="test", data={})

    with pytest.raises(RuntimeError, match="asset unavailable"):
        run_infer.OpenAgentSafetyEvaluation.prepare_workspace(evaluator, instance)

    docker_workspace.assert_not_called()


def test_partial_workspace_is_cleaned_when_staging_fails(monkeypatch):
    workspace = Mock()
    workspace.__exit__ = Mock()
    monkeypatch.setattr(run_infer, "build_workspace_image", lambda: "test:image")
    monkeypatch.setattr(run_infer, "prefetch_task_assets", lambda data: None)
    monkeypatch.setattr(run_infer, "DockerWorkspace", lambda **kwargs: workspace)
    monkeypatch.setattr(run_infer, "setup_host_mapping", lambda workspace: None)
    monkeypatch.setattr(
        run_infer,
        "download_files_for_task",
        Mock(side_effect=RuntimeError("upload failed")),
    )
    evaluator = Mock(
        spec=run_infer.OpenAgentSafetyEvaluation, metadata=Mock(details={})
    )
    instance = Mock(spec=run_infer.EvalInstance, id="test", data={})

    with pytest.raises(RuntimeError, match="upload failed"):
        run_infer.OpenAgentSafetyEvaluation.prepare_workspace(evaluator, instance)

    workspace.__exit__.assert_called_once_with(None, None, None)
