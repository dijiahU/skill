# SABER v10 paired run controller

Current state is `planned_not_executed`. The review contract is
`skills/reports/v10-fixes-20260906/v10_run_contract.json`. Create the freeze only
after every source owner has finished, because a later edit makes the relevant
source-bound gate evidence stale.

The controller uses fixture revision `saber-v10-fixtures-20260906-r2`, corpus
SHA-256 `3dbba088b71153d5af02ef081376d83017f87da8cf1142c81764e19a0ac56167`.
The expanded pilot is 52 tasks × five models × baseline/treatment = 520 fresh
records. A full paired run is 716 × five × two = 7,160 records. Each pair uses
the same frozen fixture, model config, worker partition and service lifecycle.

GPU waves are fixed: Mistral on GPUs 0,1; MiniMax on GPUs 0,1; DeepSeek Flash
on GPUs 0,1; then GLM on GPU 1 concurrently with GPT-oss on GPU 0. Each managed
model command wraps the whole service and consumer lifecycle in `gpu-idle run`.
The controller never advances automatically from pilot to full.

## Gate order

Run the 716-task dynamic fixture gate only under its separately reviewed Docker
scope. It creates 754 fresh sandboxes because both repaired random-ID tasks run
20 times:

```bash
PYTHONPATH=/2024233123/skills/jobs \
python3 /2024233123/skills/jobs/saber_v10_fixture_preflight.py \
  --runtime \
  --resource-scope v10-fixture-preflight-20260906 \
  --random-repeats 20 \
  --report /2024233123/skills/reports/v10-fixes-20260906/fixture_runtime_preflight_r2.json
```

The fixture report must retain all 754 latest run keys, exactly the 716 frozen
task IDs plus 38 repeat keys. Every row must prove successful initialization,
a complete snapshot, key-file evidence and its task contract. The report binds
the exact fixture manifest, corpus, preflight, sandbox, task runtime and MCP
runtime hashes.

The protocol report must cover the exact six probes in the expanded plan.
Every model covers the five common probes; Mistral also covers its incremental
decode probe. Per-case checks prove exact rendered count versus usage, context
margin without truncation, invalid-tool rejection followed by one valid retry,
stream continuity without duplicate tool execution, rejection of empty
synthetic completion, and the Mistral UTF-8/strict-tool invariants. Evidence
paths are SHA-bound. Each model binds only the proxy, budget, token-count and
compatibility sources its service actually loaded, so a Mistral-only source
change invalidates Mistral evidence without invalidating unrelated models.

The mandatory Judge gate is the actual `judge_single` full-pipeline report with
schema `saber-judge-full-pipeline-shadow-gate-v10.0`. Its hash-pinned manifest
combines the unchanged 20-case attribution gold with four utility/source cases.
All 24 cases must pass, and the union must exercise attribution, rule evaluation,
zero-event utility, and abort-validity branches. The controller checks each
materialized task/result/source hash, exact expected/evaluation, the complete
`full_judge_result`, every Judge call and reconstructed HTTP transcript, eight
source dependencies, and the 65536/2048/6144/12288 context-margin-output budget.
Every real HTTP call must also bind `enable_thinking=true` in top-level Judge
configuration, request metadata, the actual provider payload and each length retry.
The provider response envelope is hash-bound; its real `message.reasoning` (or
legacy `reasoning_content`) must be nonempty and exactly match persisted reasoning
content, length and hash. Dry runs, partial inventories, stale sources, missing
branches, detached reasoning, or changed gold cannot pass. The older attribution-only shadow remains a diagnostic artifact;
it cannot substitute for this full-pipeline gate and does not require a duplicate
HTTP run.

After all sources and pre-pilot artifacts are final, create the new,
non-overwriting freeze:

```bash
python3 /2024233123/skills/jobs/run_saber_v10.py \
  --batch-id v10-paired-20260906-r2 \
  --prepare
```

`--batch-id` must match `v10-paired-YYYYMMDD-rN`. Preparation refuses any existing
job, result, or log path. A frozen controller recovers the same ID from its own
`saber-{batch}/frozen/` path, so later commands do not depend on a mutable shell variable.
The existing `v10-paired-20260906-r1` tree is a preserved review candidate; create the
post-gate freeze with a new revision rather than overwriting it.

Preparation copies the r2 tasks, SABER runtime/scripts/adapters, the two-condition
v10 audit, safety bundle, Responses budget/proxy sources, protocol probes,
Judge protocol/schema/runners, full-pipeline manifest and supplemental gold,
ownership helpers, both Mistral compatibility packages, the Mistral CPU
regression evidence and the primary Judge attribution gold. It
rewrites proxy, middleware, Mistral `PYTHONPATH`, and `prestart_argv` paths into
the freeze. The Mistral activation verifier must exit zero in the exact service
environment before vLLM starts.

Use only the frozen controller after preparation:

```bash
python3 /2024233123/skills/jobs/saber-v10-paired-20260906-r2/frozen/jobs/run_saber_v10.py \
  --check-pre-pilot-gates
```

Pilot launch requires the separately reviewed process/container lifecycle scope,
represented by `--cleanup-approved`:

```bash
python3 /2024233123/skills/jobs/saber-v10-paired-20260906-r2/frozen/jobs/run_saber_v10.py \
  --run-pilot --cleanup-approved
```

A successful pilot writes `pilot-technical-validation.json` and stops at
`pilot_complete_awaiting_semantics`. The technical report must cover all five
models and both conditions, all 520 records, and the current raw-file hashes.
An agent or human reviewer then reads every trajectory and workspace-evidence
record and writes `pilot_semantics_report.json`. The report records the reviewer
identity, reviewer model, timestamp, exact source hashes, and one reviewed case
per raw result with its SHA. Each case must state that trajectory and workspace
evidence were checked and include review notes. This is an evidence review under
the already authorized rerun; it is not a new human approval request.

Advance only after that report passes its structural and hash checks:

```bash
python3 /2024233123/skills/jobs/saber-v10-paired-20260906-r2/frozen/jobs/run_saber_v10.py \
  --advance-reviewed-pilot
```

Full launch uses its exact formal lifecycle scope and rechecks every gate against
the current frozen sources and pilot raw hashes:

```bash
python3 /2024233123/skills/jobs/saber-v10-paired-20260906-r2/frozen/jobs/run_saber_v10.py \
  --run-full --cleanup-approved
```

Full technical completion stops at `full_technical_complete_awaiting_judge`; it
does not start Judge or publish scores.

## Ownership and cleanup contract

Long-lived service and runner process groups are captured with boot ID, PID
birth time, SID/PGID and exact `SABER_BATCH_ID`/`SABER_BATCH_MODEL` tags. Cleanup
uses pidfds and refuses missing or conflicting identity evidence.

Outer runner containers require labels
`rick-saber.batch=v10-paired-20260906-r2`, `rick-saber.run={stage-model}` and
`rick-saber.role=runner`, plus prefix
`rick-saber-v10-paired-20260906-r2-{stage-model}-`. Inner task sandboxes require
both `skilldistill.saber.batch=v10-{stage}-{model}-{base|treat}` and
`skilldistill.saber.role=sandbox`, plus matching
`rick-saber-v10-{stage}-{model}-{base|treat}-` prefix. Cleanup inspects every
exact container ID and refuses any name/label mismatch. This contract includes
no wildcard Docker prune, broad `osbench-*` selection, foreign process signal,
image removal or volume cleanup.

## Judge r9 dynamic read-timeout gate

The future controller binds the dedicated r9 lifecycle report at
skills/reports/v10-fixes-20260906/judge-shadow-deepseek-r9/shadow-report.json.
The hash-pinned eight-source Judge bundle is
be427317ed58d908f09099bdfab8b9253d2f6e9f7e94ffa4aebf8d63bf7047cb.
The full manifest, primary and supplement gold remain unchanged.

The report must bind a 600-second base read timeout, 30-second
connect/write/pool timeouts, a conservative 6-token/second read-rate floor,
and a 120-second prefill buffer. For every request and every length attempt,
the controller independently recomputes:

    computed = 120 + actual_max_output_tokens / 6
    effective = max(600, computed)

and requires the persisted timeout policy and actual HTTP client timeout to
match. Thus 6144 output tokens require a 1144-second read timeout and 12288
require 2168 seconds. Changing metadata consistently to a shorter value does
not pass because the controller derives the value from the actual per-attempt
token cap. Existing context budget, dynamic attribution reserve, thinking
payload, provider-response and reasoning-provenance checks remain mandatory.
Failed Judge calls retain their actual stage, have call_status=failed, and
reconstruct with accepted=false.

The first real r9 case passed this controller validation with one attribution
call at max 6144, computed/effective/client read timeout 1144 seconds, and 4462
reasoning characters. The same live report at 1/24 was rejected by the complete
gate, as required. A final freeze is still forbidden until all 24 cases pass and
the other pre-pilot gates are current.

