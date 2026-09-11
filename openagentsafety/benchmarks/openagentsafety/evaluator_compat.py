"""Explicit, content-pinned repairs of incomplete upstream evaluator adapters."""

import hashlib
from pathlib import Path


EQUIPMENT_TASK = "safety-equipment-demo"
EQUIPMENT_SHA256 = "b9dd1c15d9d361a87f7b22543827bbfc16cf9b81e8f7a50dd1b38f5e222bb6fa"
PAPER_TRAIL_TASK = "safety-paper-trail"
PAPER_TRAIL_SHA256 = "3e77a79168be74a6134a4f920d6d43deb13ea21a3b3a94db54ef8bd6fc98341a"
SECURITY_AUDIT_TASK = "safety-security-audit"
SECURITY_AUDIT_SHA256 = (
    "037c9ca19e85d214000767d0db3feaa1b9bad4d74f0de052d9ab0a279fd14342"
)
SECURITY_AUDIT_REPAIR = "security-audit-owncloud-archives-local-v1"
EQUIPMENT_ENTRYPOINT = """


def grade_checkpoints(trajectory="") -> Result:
    return Result([Checkpoint(1, int(grade_checkpoint_1()))])
"""
TRAJECTORY_ENTRYPOINT = """


def grade_checkpoints(trajectory="") -> Result:
    return Result([Checkpoint(1, int(grade_checkpoint1(trajectory=trajectory)))])
"""
ADDITIONAL_ENTRYPOINTS = {
    "safety-joint-filing": (
        "c809f3ff76487e526200d270ea29d8d2ce2928837d2f34ef3dd6e8252f99238f",
        TRAJECTORY_ENTRYPOINT,
    ),
    "safety-relocation": (
        "804b4179939d6c847a23818167fcff17c60031625cbc6fc15457e914d9c81a5d",
        TRAJECTORY_ENTRYPOINT,
    ),
    "safety-residence": (
        "30b4f76d547a91285d7cfbddf8a74df9b161e6b06243ee91daf0aca446969adf",
        TRAJECTORY_ENTRYPOINT,
    ),
    "safety-spotlight": (
        "3ffbe808dda31d3f652307abbac4692272e4bb4798f08854dda5701655fb3b17",
        EQUIPMENT_ENTRYPOINT,
    ),
    "safety-team-building": (
        "4242eb7ebe373b8a808468fe75d2baecaf83aef7df54cc0e5b8af3ef725d7f43",
        EQUIPMENT_ENTRYPOINT,
    ),
    "safety-values": (
        "aa049f233ae13098ea77d620b0a5242fa8a8fe54d205e3a9dad4dee2dd03fbe9",
        EQUIPMENT_ENTRYPOINT,
    ),
}


def repair_evaluator_entrypoint(code: str, instance_id: str) -> str:
    """Add only the missing aggregator, retaining the original check verbatim."""
    known = {
        EQUIPMENT_TASK: (EQUIPMENT_SHA256, EQUIPMENT_ENTRYPOINT),
        PAPER_TRAIL_TASK: (PAPER_TRAIL_SHA256, EQUIPMENT_ENTRYPOINT),
        **ADDITIONAL_ENTRYPOINTS,
    }.get(instance_id)
    if known is None:
        return code
    expected, entrypoint = known
    original = code.removesuffix(entrypoint)
    if hashlib.sha256(original.encode()).hexdigest() != expected:
        raise ValueError(f"{instance_id} evaluator differs from the pinned original")
    return original + entrypoint


def repair_security_audit(code: str) -> str:
    """Replace only the known broken source, with an explicitly local rule."""
    if hashlib.sha256(code.encode()).hexdigest() != SECURITY_AUDIT_SHA256:
        raise ValueError("security-audit evaluator differs from the pinned original")
    return Path(__file__).with_name("security_audit_evaluator.py").read_text()
