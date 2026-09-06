import hashlib
from unittest.mock import Mock

import pytest
import requests

from benchmarks.openagentsafety import run_infer
from benchmarks.openagentsafety.scripts import repair_owncloud_survey_path as repair


PDF = b"%PDF-original-survey"
BASE = "http://the-agent-company.com:8092"


def response(status: int = 200, content: bytes = PDF) -> requests.Response:
    value = requests.Response()
    value.status_code = status
    value._content = content
    assert value.content == content
    return value


@pytest.fixture
def session(monkeypatch):
    monkeypatch.setattr(repair, "SURVEY_SHA256", hashlib.sha256(PDF).hexdigest())
    return Mock(spec=requests.Session)


def test_alias_copies_pinned_original_and_verifies_identical_bytes(session):
    session.get.side_effect = [response(), response(404), response()]
    session.request.side_effect = [response(201), response(201)]
    result = repair.ensure_survey_alias(session, BASE)
    assert result["changed"]
    assert result["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert [call.args[0] for call in session.request.call_args_list] == [
        "MKCOL",
        "COPY",
    ]
    copy = session.request.call_args_list[-1]
    assert copy.args[1] == BASE + "/remote.php/webdav" + repair.SOURCE
    assert copy.kwargs["headers"] == {
        "Destination": BASE + "/remote.php/webdav" + repair.DESTINATION,
        "Overwrite": "F",
    }


def test_alias_is_idempotent_and_never_rewrites_existing_copy(session):
    session.get.side_effect = [response(), response()]
    assert not repair.ensure_survey_alias(session, BASE)["changed"]
    session.request.assert_not_called()


@pytest.mark.parametrize("source", [response(404), response(content=b"%PDF-changed")])
def test_alias_rejects_missing_or_changed_official_data(session, source):
    session.get.return_value = source
    with pytest.raises(ValueError, match="missing or has changed"):
        repair.ensure_survey_alias(session, BASE)
    session.request.assert_not_called()


def test_alias_does_not_overwrite_a_different_existing_destination(session):
    session.get.side_effect = [response(), response(content=b"%PDF-user-data")]
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        repair.ensure_survey_alias(session, BASE)
    session.request.assert_not_called()


def test_existing_food_file_is_not_treated_as_a_directory(session):
    session.get.side_effect = [response(), response(404)]
    session.request.side_effect = [response(405), response(207, b"<not-collection/>")]
    with pytest.raises(ValueError, match="not a WebDAV collection"):
        repair.ensure_survey_alias(session, BASE)
    assert [call.args[0] for call in session.request.call_args_list] == [
        "MKCOL",
        "PROPFIND",
    ]


def test_copy_rejection_does_not_retry_or_force_overwrite(session):
    session.get.side_effect = [response(), response(404)]
    session.request.side_effect = [response(201), response(412)]
    with pytest.raises(RuntimeError, match="HTTP 412"):
        repair.ensure_survey_alias(session, BASE)
    assert session.request.call_count == 2


def test_copied_bytes_must_match_source(session):
    session.get.side_effect = [
        response(),
        response(404),
        response(content=b"%PDF-wrong"),
    ]
    session.request.side_effect = [response(201), response(201)]
    with pytest.raises(ValueError, match="byte-for-byte"):
        repair.ensure_survey_alias(session, BASE)


def test_reads_are_bounded_and_auth_failures_are_not_absence(session, monkeypatch):
    monkeypatch.setattr(repair, "MAX_BYTES", 5)
    session.get.return_value = response()
    with pytest.raises(ValueError, match="exceeds"):
        repair.read_pdf(session, BASE)
    session.get.return_value = response(401)
    with pytest.raises(requests.HTTPError):
        repair.read_pdf(session, BASE)


@pytest.mark.parametrize(
    "instance",
    [
        {"dependencies": [], "problem_statement": repair.DESTINATION},
        {"dependencies": ["owncloud"], "problem_statement": "Find the survey"},
    ],
)
def test_unaffected_tasks_are_not_modified(instance):
    workspace = Mock()
    run_infer.install_owncloud_survey_compat(workspace, instance)
    workspace.file_upload.assert_not_called()
    workspace.execute_command.assert_not_called()
