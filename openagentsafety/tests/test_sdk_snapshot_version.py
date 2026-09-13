"""SDK provenance must work in both submodule checkouts and flattened backups."""

from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from benchmarks.utils.version import _get_submodule_sha


def test_original_submodule_revision_is_preserved(tmp_path: Path) -> None:
    revision = "a" * 40
    with patch(
        "benchmarks.utils.version.subprocess.run",
        return_value=CompletedProcess([], 0, f" {revision} vendor/sdk (main)\n", ""),
    ):
        assert _get_submodule_sha(tmp_path) == revision


def test_snapshot_hash_tracks_source_and_ignores_build_output(tmp_path: Path) -> None:
    sdk = tmp_path / "openhands-sdk"
    sdk.mkdir()
    (sdk / "pyproject.toml").write_text('[project]\nname = "sdk"\n')
    code = sdk / "module.py"
    code.write_text("VERSION = 1\n")
    with patch(
        "benchmarks.utils.version.subprocess.run",
        return_value=CompletedProcess([], 0, "", ""),
    ):
        first = _get_submodule_sha(tmp_path)
        assert first.startswith("snapshot-")
        build = sdk / "build"
        build.mkdir()
        (build / "copy.py").write_text("generated")
        assert _get_submodule_sha(tmp_path) == first
        code.write_text("VERSION = 2\n")
        assert _get_submodule_sha(tmp_path) != first


def test_missing_sdk_fails_clearly(tmp_path: Path) -> None:
    with patch(
        "benchmarks.utils.version.subprocess.run",
        return_value=CompletedProcess([], 1, "", "missing git"),
    ):
        with pytest.raises(RuntimeError, match="snapshot is missing"):
            _get_submodule_sha(tmp_path)
