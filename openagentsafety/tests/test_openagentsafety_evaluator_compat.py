import hashlib

import pytest

from benchmarks.openagentsafety import evaluator_compat as repair


ORIGINAL = "def grade_checkpoint_1():\n    return original_result\n"


@pytest.fixture
def pinned(monkeypatch):
    monkeypatch.setattr(
        repair, "EQUIPMENT_SHA256", hashlib.sha256(ORIGINAL.encode()).hexdigest()
    )


@pytest.mark.parametrize("original_result", [False, True])
def test_missing_aggregator_preserves_the_original_verdict(pinned, original_result):
    repaired = repair.repair_evaluator_entrypoint(ORIGINAL, repair.EQUIPMENT_TASK)
    assert repaired.startswith(ORIGINAL)
    namespace = {
        "original_result": original_result,
        "Result": list,
        "Checkpoint": lambda index, result: (index, result),
    }
    exec(repaired, namespace)
    assert namespace["grade_checkpoints"](trajectory="ignored") == [
        (1, int(original_result))
    ]


def test_repair_is_idempotent(pinned):
    repaired = repair.repair_evaluator_entrypoint(ORIGINAL, repair.EQUIPMENT_TASK)
    assert (
        repair.repair_evaluator_entrypoint(repaired, repair.EQUIPMENT_TASK) == repaired
    )


def test_unknown_code_is_not_silently_replaced():
    with pytest.raises(ValueError, match="pinned original"):
        repair.repair_evaluator_entrypoint("modified evaluator", repair.EQUIPMENT_TASK)


def test_other_tasks_are_unchanged():
    assert repair.repair_evaluator_entrypoint(ORIGINAL, "safety-unrelated") == ORIGINAL


@pytest.mark.parametrize("task", list(repair.ADDITIONAL_ENTRYPOINTS))
@pytest.mark.parametrize("verdict", [False, True])
def test_additional_entrypoints_preserve_verdict_and_forward_trajectory(
    monkeypatch, task, verdict
):
    _, suffix = repair.ADDITIONAL_ENTRYPOINTS[task]
    code = "# pinned test source\n"
    monkeypatch.setitem(
        repair.ADDITIONAL_ENTRYPOINTS,
        task,
        (hashlib.sha256(code.encode()).hexdigest(), suffix),
    )
    seen = []

    def check(trajectory=""):
        seen.append(trajectory)
        return verdict

    namespace = {
        "Result": list,
        "Checkpoint": lambda total, result: (total, result),
        "grade_checkpoint1": check,
        "grade_checkpoint_1": check,
    }
    patched = repair.repair_evaluator_entrypoint(code, task)
    assert patched.startswith(code)
    assert repair.repair_evaluator_entrypoint(patched, task) == patched
    exec(patched, namespace)
    assert namespace["grade_checkpoints"]("agent-only evidence") == [(1, int(verdict))]
    assert seen == (
        ["agent-only evidence"] if suffix == repair.TRAJECTORY_ENTRYPOINT else [""]
    )
    with pytest.raises(ValueError, match="pinned original"):
        repair.repair_evaluator_entrypoint(code + "# changed", task)


def test_second_known_missing_entrypoint_is_also_pinned(monkeypatch):
    monkeypatch.setattr(
        repair, "PAPER_TRAIL_SHA256", hashlib.sha256(ORIGINAL.encode()).hexdigest()
    )
    repaired = repair.repair_evaluator_entrypoint(ORIGINAL, repair.PAPER_TRAIL_TASK)
    assert repaired == ORIGINAL + repair.EQUIPMENT_ENTRYPOINT
    with pytest.raises(ValueError, match="pinned original"):
        repair.repair_evaluator_entrypoint(
            ORIGINAL + "# changed", repair.PAPER_TRAIL_TASK
        )
