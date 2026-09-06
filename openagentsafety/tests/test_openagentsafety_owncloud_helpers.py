from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from benchmarks.openagentsafety import run_infer
from benchmarks.openagentsafety.scripts.repair_owncloud_helpers import (
    decode_owncloud_hrefs,
    repair_file,
)


SOURCE = '''"""Original helpers."""
from __future__ import annotations

def check_and_download_file(file_name, href):
    if file_name in href:
        return True
    return False

def check_file_in_owncloud_directory(file_name, href):
    if file_name in href:
        return True
    return False

def unrelated(file_name, href):
    return file_name in href
'''


@pytest.mark.parametrize(
    "name, href, expected",
    [
        ("bill.pdf", "/Documents/bill.pdf", True),
        ("Policy File.pdf", "/Documents/Policy%20File.pdf", True),
        ("报告.pdf", "/Documents/%E6%8A%A5%E5%91%8A.pdf", True),
        ("a+b.pdf", "/Documents/a+b.pdf", True),
        ("a b.pdf", "/Documents/a+b.pdf", False),
        ("%20.pdf", "/Documents/%2520.pdf", True),
        ("missing.pdf", "/Documents/bill.pdf", False),
    ],
)
def test_href_decoding_preserves_url_semantics(name, href, expected):
    namespace = {}
    repaired = decode_owncloud_hrefs(SOURCE)
    exec(compile(repaired, "test-helpers", "exec"), namespace)
    for helper in ("check_and_download_file", "check_file_in_owncloud_directory"):
        assert namespace[helper](name, href) is expected
    assert "return file_name in href" in repaired
    assert decode_owncloud_hrefs(repaired) == repaired


def test_repair_keeps_original_and_is_idempotent(tmp_path: Path):
    path = tmp_path / "common.py"
    path.write_text(SOURCE)
    assert repair_file(path)["changed"]
    backup = tmp_path / "common.py.before-owncloud-url-decoding"
    assert backup.read_text() == SOURCE
    assert not repair_file(path)["changed"]
    assert backup.read_text() == SOURCE


def test_unrecognized_helper_is_rejected_without_writes(tmp_path: Path):
    path = tmp_path / "common.py"
    source = SOURCE.replace("if file_name in href:", "if file_name == href:")
    path.write_text(source)
    with pytest.raises(ValueError, match="Unexpected href comparison"):
        repair_file(path)
    assert path.read_text() == source
    assert not path.with_name(path.name + ".before-owncloud-url-decoding").exists()


def test_existing_backup_is_not_overwritten(tmp_path: Path):
    path = tmp_path / "common.py"
    path.write_text(SOURCE)
    backup = path.with_name(path.name + ".before-owncloud-url-decoding")
    backup.write_text("older source")
    with pytest.raises(FileExistsError):
        repair_file(path)
    assert path.read_text() == SOURCE
    assert backup.read_text() == "older source"


def test_workspace_repair_checks_upload_and_execution():
    workspace = Mock()
    workspace.file_upload.return_value = SimpleNamespace(success=True, error=None)
    workspace.execute_command.return_value = SimpleNamespace(
        exit_code=0, stdout='{"changed": true}', stderr=""
    )
    run_infer.install_owncloud_url_compat(workspace)
    source, destination = workspace.file_upload.call_args.args
    assert source.name == "repair_owncloud_helpers.py"
    assert destination == "/utils/oas_repair_owncloud_helpers.py"
    workspace.file_upload.return_value.success = False
    with pytest.raises(RuntimeError, match="upload ownCloud"):
        run_infer.install_owncloud_url_compat(workspace)
    workspace.file_upload.return_value.success = True
    workspace.execute_command.return_value.exit_code = 1
    with pytest.raises(RuntimeError, match="apply ownCloud"):
        run_infer.install_owncloud_url_compat(workspace)
