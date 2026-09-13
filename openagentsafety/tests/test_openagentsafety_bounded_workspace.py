import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from benchmarks.openagentsafety import bounded_workspace as bounded


def test_stop_is_exact_and_bounded(monkeypatch):
    run = MagicMock(return_value=SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr(bounded.subprocess, "run", run)
    bounded.stop_owned_container("owned-id")
    assert run.call_args.args[0] == ["docker", "stop", "--time", "10", "owned-id"]
    assert run.call_args.kwargs["timeout"] == 30


def test_missing_container_is_already_clean(monkeypatch):
    monkeypatch.setattr(
        bounded.subprocess,
        "run",
        MagicMock(
            return_value=SimpleNamespace(
                returncode=1, stderr="Error: No such container: owned-id"
            )
        ),
    )
    bounded.stop_owned_container("owned-id")


def test_timeout_is_not_retried(monkeypatch):
    run = MagicMock(side_effect=subprocess.TimeoutExpired("docker", 30))
    monkeypatch.setattr(bounded.subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired):
        bounded.stop_owned_container("owned-id")
    assert run.call_count == 1


def test_daemon_failure_is_not_silently_accepted(monkeypatch):
    monkeypatch.setattr(
        bounded.subprocess,
        "run",
        MagicMock(
            return_value=SimpleNamespace(returncode=1, stderr="daemon unavailable")
        ),
    )
    with pytest.raises(RuntimeError, match="daemon unavailable"):
        bounded.stop_owned_container("owned-id")


def test_cleanup_on_log_thread_still_stops_owned_container(monkeypatch):
    stop = MagicMock()
    monkeypatch.setattr(bounded, "stop_owned_container", stop)
    workspace = MagicMock(
        spec=bounded.BoundedDockerWorkspace,
        _container_id="owned-id",
        _stop_logs=MagicMock(),
        _logs_thread=bounded.threading.current_thread(),
    )
    bounded.BoundedDockerWorkspace.cleanup(workspace)
    stop.assert_called_once_with("owned-id")
    workspace._stop_logs.set.assert_called_once()
    assert workspace._container_id is None


def test_cleanup_joins_other_log_thread_with_bound(monkeypatch):
    stop = MagicMock()
    monkeypatch.setattr(bounded, "stop_owned_container", stop)
    thread = MagicMock()
    workspace = MagicMock(
        spec=bounded.BoundedDockerWorkspace,
        _container_id="owned-id",
        _stop_logs=MagicMock(),
        _logs_thread=thread,
    )
    bounded.BoundedDockerWorkspace.cleanup(workspace)
    thread.join.assert_called_once_with(timeout=2)
    stop.assert_called_once_with("owned-id")
