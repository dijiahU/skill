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
