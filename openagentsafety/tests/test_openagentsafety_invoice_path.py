import hashlib
from unittest.mock import Mock

import pytest
import requests

from benchmarks.openagentsafety import run_infer
from benchmarks.openagentsafety.scripts import repair_owncloud_invoice_path as repair


BASE = "http://the-agent-company.com:8092"
ROOT = "/remote.php/webdav"
PDFS = {"INV0000.pdf": b"%PDF-first", "INV0001.pdf": b"%PDF-second"}


def response(status: int, content: bytes = b"") -> requests.Response:
    value = requests.Response()
    value.status_code = status
    value._content = content
    assert value.content == content
    return value


def listing(path: str, files: dict[str, bytes]) -> bytes:
    entries = [
        f"<d:response><d:href>{path}</d:href><d:propstat><d:prop>"
        "<d:resourcetype><d:collection/></d:resourcetype>"
        "</d:prop></d:propstat></d:response>"
    ]
    for name, content in files.items():
        entries.append(
            f"<d:response><d:href>{path}{name}</d:href><d:propstat><d:prop>"
            f"<d:getcontentlength>{len(content)}</d:getcontentlength>"
            "</d:prop></d:propstat></d:response>"
        )
    return (
        '<d:multistatus xmlns:d="DAV:">' + "".join(entries) + "</d:multistatus>"
    ).encode()


@pytest.fixture
def dav(monkeypatch):
    manifest = "".join(
        f"{name}:{hashlib.sha256(data).hexdigest()}\n"
        for name, data in sorted(PDFS.items())
    )
    monkeypatch.setattr(repair, "INVOICE_NAMES", frozenset(PDFS))
    monkeypatch.setattr(
        repair, "MANIFEST_SHA256", hashlib.sha256(manifest.encode()).hexdigest()
    )
    collections = {ROOT + repair.SOURCE: dict(PDFS)}

    def request(method, url, **kwargs):
        assert kwargs["allow_redirects"] is False
        assert 0 < kwargs["timeout"] <= 10
        path = url.removeprefix(BASE)
        if method == "PROPFIND":
            assert kwargs["headers"] == {"Depth": "1"}
            return (
                response(207, listing(path, collections[path]))
                if path in collections
                else response(404)
            )
        if method == "GET":
            parent, name = path.rsplit("/", 1)
            return response(200, collections[parent + "/"][name])
        assert method == "COPY"
        assert kwargs["headers"] == {
            "Destination": BASE + ROOT + repair.DESTINATION,
            "Overwrite": "F",
            "Depth": "infinity",
        }
        assert ROOT + repair.DESTINATION not in collections
        collections[ROOT + repair.DESTINATION] = dict(collections[path])
        return response(201)

    session = Mock(spec=requests.Session)
    session.request.side_effect = request
    return session, collections


def test_copy_verifies_all_files_and_preserves_original(dav):
    session, collections = dav
    result = repair.ensure_invoice_alias(session, BASE)
    assert result["changed"]
    assert result["files"] == 2
    assert result["bytes"] == sum(map(len, PDFS.values()))
    assert collections[ROOT + repair.SOURCE] == PDFS
    assert collections[ROOT + repair.DESTINATION] == PDFS
    assert sum(c.args[0] == "COPY" for c in session.request.call_args_list) == 1


def test_existing_identical_copy_is_not_rewritten(dav):
    session, collections = dav
    collections[ROOT + repair.DESTINATION] = dict(PDFS)
    assert not repair.ensure_invoice_alias(session, BASE)["changed"]
    assert all(c.args[0] != "COPY" for c in session.request.call_args_list)


@pytest.mark.parametrize("path", [repair.SOURCE, repair.DESTINATION])
def test_changed_source_or_destination_fails_without_overwrite(dav, path):
    session, collections = dav
    collections[ROOT + path] = {**PDFS, "INV0000.pdf": b"%PDF-changed"}
    with pytest.raises(ValueError, match="changed|Refusing to overwrite"):
        repair.ensure_invoice_alias(session, BASE)
    assert all(c.args[0] != "COPY" for c in session.request.call_args_list)


@pytest.mark.parametrize("status", [401, 403, 500])
def test_service_failures_are_not_treated_as_missing(dav, status):
    session, _ = dav
    session.request.side_effect = None
    session.request.return_value = response(status)
    with pytest.raises(RuntimeError, match=f"HTTP {status}"):
        repair.ensure_invoice_alias(session, BASE)
    assert session.request.call_count == 1


def test_missing_source_is_not_fabricated(dav):
    session, collections = dav
    collections.clear()
    with pytest.raises(ValueError, match="missing"):
        repair.ensure_invoice_alias(session, BASE)
    assert session.request.call_count == 1


def test_unexpected_file_is_rejected(dav):
    session, collections = dav
    collections[ROOT + repair.SOURCE]["extra.pdf"] = b"%PDF-extra"
    with pytest.raises(ValueError, match="Unexpected"):
        repair.ensure_invoice_alias(session, BASE)
    assert session.request.call_count == 1


@pytest.mark.parametrize(
    "limit", ["MAX_XML_BYTES", "MAX_FILE_BYTES", "MAX_TOTAL_BYTES"]
)
def test_data_reads_are_bounded(dav, monkeypatch, limit):
    session, _ = dav
    monkeypatch.setattr(repair, limit, 1)
    with pytest.raises(ValueError, match="limit|size"):
        repair.ensure_invoice_alias(session, BASE)
    assert all(c.args[0] != "COPY" for c in session.request.call_args_list)


def test_expired_budget_does_not_send_requests(dav, monkeypatch):
    session, _ = dav
    monkeypatch.setattr(repair, "REPAIR_SECONDS", -1)
    with pytest.raises(TimeoutError, match="time budget"):
        repair.ensure_invoice_alias(session, BASE)
    session.request.assert_not_called()


def test_copy_failure_is_not_retried(dav):
    session, _ = dav
    original_request = session.request.side_effect

    def request(method, *args, **kwargs):
        return (
            response(412)
            if method == "COPY"
            else original_request(method, *args, **kwargs)
        )

    session.request.side_effect = request
    with pytest.raises(RuntimeError, match="HTTP 412"):
        repair.ensure_invoice_alias(session, BASE)
    assert sum(c.args[0] == "COPY" for c in session.request.call_args_list) == 1


@pytest.mark.parametrize(
    "instance",
    [
        {"dependencies": [], "problem_statement": repair.DESTINATION},
        {"dependencies": ["owncloud"], "problem_statement": repair.SOURCE},
    ],
)
def test_unaffected_tasks_are_not_modified(instance):
    workspace = Mock()
    run_infer.install_owncloud_invoice_compat(workspace, instance)
    workspace.file_upload.assert_not_called()


def test_affected_task_installs_bounded_repair():
    workspace = Mock()
    workspace.execute_command.return_value.exit_code = 0
    workspace.execute_command.return_value.stdout = "verified"
    run_infer.install_owncloud_invoice_compat(
        workspace,
        {"dependencies": ["owncloud"], "problem_statement": repair.DESTINATION},
    )
    workspace.file_upload.assert_called_once()
    assert workspace.execute_command.call_args.kwargs["timeout"] == 210
