"""Resume only unrecorded OAS tasks, with verified opt-in repairs and new notes."""

import argparse
import fcntl
import json
import subprocess
import time
from pathlib import Path


ROOT = Path("/2024233123/skills")
JOBS = ROOT / "jobs"
LOG = ROOT / "logs/openagentsafety-services-repaired-firstpass-20260905"
RESULTS = ROOT / (
    "results/openagentsafety/"
    "mgulavani__openagentsafety_full_updated_v3-train/openai/ZhipuAI"
)
GROUPS = [
    ("owncloud-only", 86),
    ("gitlab-only", 42),
    ("plane-only", 2),
    ("plane-gitlab", 6),
    ("gitlab-owncloud", 1),
]
FLAGS = [
    "--owncloud-url-decoding-compat",
    "--owncloud-survey-path-compat",
    "--owncloud-invoice-path-compat",
    "--evaluator-entrypoint-compat",
]


def records(pattern):
    found = {}
    for directory in RESULTS.glob(pattern):
        output = directory / "output.critic_attempt_1.jsonl"
        if not output.is_file():
            output = directory / "output.jsonl"
        if not output.is_file():
            continue
        for line in output.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                found[record["instance_id"]] = record
    return found


def selection_plan():
    expected = set((JOBS / "openagentsafety-services-137.txt").read_text().split())
    old = {}
    for group, _ in GROUPS:
        old.update(records(f"*_glm47-services-{group}-firstpass-20260905"))
    if not old.keys() <= expected:
        raise ValueError("Old results contain unexpected IDs")
    groups = []
    for group, count in GROUPS:
        original = (JOBS / f"openagentsafety-{group}-{count}.txt").read_text().split()
        pending = [task for task in original if task not in old]
        groups.append((group, pending))
    pending = [task for _, tasks in groups for task in tasks]
    if len(pending) != len(set(pending)) or set(pending) != expected - old.keys():
        raise ValueError(
            "Pending selection is not a disjoint coverage of the remainder"
        )
    return old, groups


def validate_probes():
    equipment = records("*_glm47-equipment-entrypoint-compat-probe-20260905")
    invoice = records("*_glm47-invoice-path-compat-probe-20260905")
    for task, source in [
        ("safety-equipment-demo", equipment),
        ("safety-compliance", invoice),
    ]:
        record = source.get(task)
        if record is None:
            raise RuntimeError(f"Representative verification is not finished: {task}")
        result = record.get("test_result") or {}
        if record.get("error") or result.get("error") or not result.get("final_score"):
            raise RuntimeError(
                f"Representative verification has a harness error: {task}"
            )
        details = (record.get("metadata") or {}).get("details") or {}
        if not all(details.get(flag[2:].replace("-", "_")) for flag in FLAGS):
            raise RuntimeError(
                f"Representative verification lacks repair metadata: {task}"
            )
    if not equipment["safety-equipment-demo"]["test_result"]["skilldistill"].get(
        "evaluator_compat"
    ):
        raise RuntimeError("Evaluator repair was not applied")
    logs = list(
        RESULTS.glob(
            "*_glm47-invoice-path-compat-probe-20260905/logs/instance_safety-compliance.log"
        )
    )
    if (
        len(logs) != 1
        or "ownCloud invoice path compatibility: " not in logs[0].read_text()
    ):
        raise RuntimeError("Real invoice directory repair was not verified")


def launch(group, pending):
    if not pending:
        return None
    note = f"glm47-services-{group}-repaired-firstpass-20260905"
    selection = JOBS / f"openagentsafety-{group}-repaired-remaining-20260905.txt"
    content = "\n".join(pending) + "\n"
    if selection.exists():
        if selection.read_text() != content:
            raise RuntimeError("Refusing to overwrite a changed continuation selection")
    else:
        with selection.open("x") as stream:
            stream.write(content)
    with (LOG / f"{group}.log").open("a") as stream:
        process = subprocess.Popen(
            [
                "bash",
                str(JOBS / "run_openagentsafety_service_probe.sh"),
                str(selection),
                note,
                *FLAGS,
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return {"group": group, "selected": len(pending), "note": note, "process": process}


def summarize(job):
    outputs = records("*_" + job["note"])
    errors = [
        task
        for task, row in outputs.items()
        if row.get("error") or (row.get("test_result") or {}).get("error")
    ]
    partial = sum(
        bool(
            (row.get("test_result") or {})
            .get("skilldistill", {})
            .get("conversation_error")
        )
        for row in outputs.values()
    )
    return {
        "group": job["group"],
        "selected": job["selected"],
        "recorded": len(outputs),
        "partial": partial,
        "harness_error_ids": errors,
        "pid": job["process"].pid,
        "exit_code": job["process"].poll(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    old, groups = selection_plan()
    plan = {
        "old_recorded": len(old),
        "remaining": sum(len(ids) for _, ids in groups),
        "groups": {group: len(ids) for group, ids in groups},
        "flags": FLAGS,
    }
    print(json.dumps(plan), flush=True)
    if args.dry_run:
        return 0
    validate_probes()
    LOG.mkdir(parents=True, exist_ok=True)
    with (LOG / "supervisor.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        jobs = [job for group, ids in groups[:3] if (job := launch(group, ids))]

        def wait_current():
            while True:
                status = [summarize(job) for job in jobs]
                (LOG / "progress.json").write_text(
                    json.dumps({**plan, "jobs": status}, indent=2) + "\n"
                )
                print(json.dumps(status), flush=True)
                if all(job["process"].poll() is not None for job in jobs):
                    return
                time.sleep(30)

        wait_current()
        # Do not dispatch new mixed-service groups after an infrastructure failure.
        for group, ids in groups[3:]:
            if any(
                summarize(job)["harness_error_ids"] or job["process"].returncode
                for job in jobs
            ):
                print(
                    "REVIEW_REQUIRED: mixed groups not launched after an error",
                    flush=True,
                )
                return 1
            job = launch(group, ids)
            if job:
                jobs.append(job)
                wait_current()
        return int(any(job["process"].returncode for job in jobs))


if __name__ == "__main__":
    raise SystemExit(main())
