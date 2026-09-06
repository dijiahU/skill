"""Explicit, content-pinned repairs of incomplete upstream evaluator adapters."""

import hashlib


EQUIPMENT_TASK = "safety-equipment-demo"
EQUIPMENT_SHA256 = "b9dd1c15d9d361a87f7b22543827bbfc16cf9b81e8f7a50dd1b38f5e222bb6fa"
PAPER_TRAIL_TASK = "safety-paper-trail"
PAPER_TRAIL_SHA256 = "3e77a79168be74a6134a4f920d6d43deb13ea21a3b3a94db54ef8bd6fc98341a"
EQUIPMENT_ENTRYPOINT = """


def grade_checkpoints(trajectory="") -> Result:
    return Result([Checkpoint(1, int(grade_checkpoint_1()))])
"""


def repair_evaluator_entrypoint(code: str, instance_id: str) -> str:
    """Add only the missing aggregator, retaining the original check verbatim."""
    expected = {
        EQUIPMENT_TASK: EQUIPMENT_SHA256,
        PAPER_TRAIL_TASK: PAPER_TRAIL_SHA256,
    }.get(instance_id)
    if expected is None:
        return code
    original = code.removesuffix(EQUIPMENT_ENTRYPOINT)
    if hashlib.sha256(original.encode()).hexdigest() != expected:
        raise ValueError(f"{instance_id} evaluator differs from the pinned original")
    return original + EQUIPMENT_ENTRYPOINT
