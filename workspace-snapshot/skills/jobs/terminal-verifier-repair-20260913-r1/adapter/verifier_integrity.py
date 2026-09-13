"""Validate execution evidence for the pinned, pytest-based TB 2.1 tasks."""
import json
import hashlib
import math
from pathlib import Path


def assess_verifier(directory, reward):
    directory = Path(directory)
    result = {"valid": False, "reason": "missing_or_invalid_reward"}
    if type(reward) not in (int, float) or not math.isfinite(reward) or reward not in (0, 1):
        return result
    report = directory / "ctrf.json"
    try:
        data = json.loads(report.read_text())["results"]
        summary, tests = data["summary"], data["tests"]
        count = summary["tests"]
        if type(count) is not int or count <= 0 or not isinstance(tests, list):
            raise ValueError("No collected tests")
        if count != len(tests):
            raise ValueError("Incomplete test report")
        for status in ("passed", "failed", "skipped", "pending", "other"):
            if summary.get(status, 0) != sum(t.get("status") == status for t in tests):
                raise ValueError("Inconsistent test counts")
        if sum(t.get("status") in ("passed", "failed") for t in tests) == 0:
            raise ValueError("No executed tests")
        if any(t.get("status") not in ("passed", "failed", "skipped") for t in tests):
            raise ValueError("Incomplete test execution")
        if any(str(t.get("raw_status", "")).startswith(("setup_", "teardown_")) for t in tests):
            raise ValueError("Test fixture failure requires review")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {"valid": False, "reason": "verifier_execution_unconfirmed"}
    log_path = directory / "test-stdout.txt"
    log = log_path.read_text(errors="replace") if log_path.exists() else ""
    if "ERROR collecting" in log or "Interrupted:" in log:
        return {"valid": False, "reason": "verifier_collection_or_execution_error"}
    expected = 0 if summary.get("failed", 0) else 1
    if reward != expected:
        return {"valid": False, "reason": "reward_test_report_mismatch"}
    return {"valid": True, "reason": "", "tests": count,
            "passed_tests": summary.get("passed", 0), "failed_tests": summary.get("failed", 0)}


def assess_trial(path, row=None):
    path = Path(path)
    row = json.loads(path.read_text()) if row is None else row
    error = row.get("exception_info") or {}
    if error:
        return {"valid": False, "reason": error.get("exception_type", "trial_error")}
    reward = ((row.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    original = assess_verifier(path.parent / "verifier", reward)
    if original['valid']:
        return {**original, 'reward': reward}
    # Preserve a genuine original score, including zero. Only infrastructure
    # failures may use the first verified replay of the same retained artifacts.
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    replays = []
    for record in (path.parent / 'verifier').glob('repair-*/completion.json'):
        try:
            replay = json.loads(record.read_text())
            if (replay['source_result_sha256'] != source_hash
                    or Path(replay['source']).resolve() != path.parent.resolve()
                    or replay.get('model_api_calls') != 0
                    or replay.get('returncode') != 0):
                continue
            replay_verdict = assess_verifier(record.parent, replay.get('reward'))
            if replay_verdict['valid']:
                replays.append((replay['started_at_utc'], record, replay, replay_verdict))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if replays:
        _, record, replay, verdict = min(replays, key=lambda r: r[0])
        return {**verdict, 'reward': replay['reward'], 'verifier_replay': str(record)}
    return original
