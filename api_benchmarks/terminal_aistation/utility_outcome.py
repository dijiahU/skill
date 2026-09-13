"""Expected agent stops still require official artifact verification."""
EXPECTED_BUDGET_REASONS = frozenset({
    "consecutive_safety_blocks", "total_high_risk_block_limit",
    "task_attempt_limit", "support_attempt_limit", "runtime_step_limit",
    "repeated_no_progress",
})


def classify(meta):
    status = meta.get("turn_status")
    if status == "completed":
        return "completed"
    if (status == "interrupted_by_harness" and meta.get("host_budget_terminated") is True
            and meta.get("termination_reason") in EXPECTED_BUDGET_REASONS):
        return "harness_terminated"
    raise RuntimeError("Model did not complete normally: " + str(status))
