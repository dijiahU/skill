"""Regression coverage for diagnostic-prefixed evaluator results."""

import json

import pytest

from benchmarks.openagentsafety.evaluator_output import parse_evaluator_output


SCORE = {
    "checkpoints": [{"total": 1, "result": 0}],
    "final_score": {"total": 1, "result": 0},
}


@pytest.mark.parametrize("prefix", ["", "Error during evaluation: 'drink'\n"])
def test_valid_score_with_diagnostics(prefix):
    result = parse_evaluator_output(prefix + json.dumps(SCORE) + "\n\n", "", 0)
    assert result["final_score"] == SCORE["final_score"]
    assert "error" not in result
    if prefix:
        assert prefix in result["evaluator_diagnostics"]["stdout"]


def test_pretty_printed_json():
    assert parse_evaluator_output(json.dumps(SCORE, indent=2), "", 0) == SCORE


@pytest.mark.parametrize(
    "output",
    [
        "",
        "noise",
        "[]",
        "{}",
        '{"final_score": {"result": 0}}',
        json.dumps(SCORE) + "\nlate failure",
    ],
)
def test_invalid_output_is_not_a_score(output):
    result = parse_evaluator_output(output, "", 0)
    assert result["error"]
    assert "final_score" not in result


def test_nonzero_exit_does_not_accept_valid_json():
    result = parse_evaluator_output(json.dumps(SCORE), "NameError: vault", 1)
    assert "NameError: vault" in result["error"]
    assert "final_score" not in result


@pytest.mark.parametrize("value", [-1, 2, float("nan"), True, "0"])
def test_invalid_score_range_or_type(value):
    assert parse_evaluator_output(
        json.dumps({"final_score": {"result": value, "total": 1}}), "", 0
    )["error"]
