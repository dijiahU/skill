# SABER v10 paired run controller

## Latest diagnostic status (2026-09-07)

The completed `v10-paired-20260907-r3` pilot produced all 520 records:
511 passed technical validation and 9 failed. These are technical integrity
counts, not task or safety scores. Keep the original raw results unchanged.
Targeted MiniMax replay passed its single failed case (20 tool calls); this
non-reproduction does not explain or erase the original stream disconnection.
Targeted gpt-oss replay passed 6 of 8 records and captured two remaining failures.

One captured gpt-oss response used a `response.completed` event with nested
`status=incomplete` and an empty output array. The local streaming proxy now
corrects the terminal event to match the nested status, preserves original
upstream captures, and never invents final text or retries partial tool output.
The actual captured response replay and 18 CPU tests pass; the live
`protocol-gptoss-r7` probe also passed tool roundtrip, long-context budgeting,
and Unicode SSE checks. Earlier protocol reports remain historical and must not
be relabeled as current-source validation.

Diagnostic replays use `run_saber_v10_failure_diagnostic.py` under `gpu-idle`,
new resource scopes, copied source snapshots, and separate result directories.
They never advance pilot, full-run, or scoring gates. Optional stream captures
are local diagnostic artifacts and must not be included in code uploads.

`successful_recovery_actions` currently counts recovery tool calls with a
successful delivery outcome. It does not establish task progress or persistent
workspace improvement; even a successful standalone `cd` can increment it.
The total high-risk block limit remains cumulative regardless of this counter.


## Current generation-first execution

The user authorized creating and deleting new task sandboxes while preserving
all previously existing resources. Frozen batch `v10-paired-20260907-r1`
terminated after Mistral baseline with 51/52 technically valid records; later
conditions and models were not launched. Preserve this failed batch. Its
seven-case fixture smoke is source-bound and passed;
complete fixture report `fixture_runtime_preflight_r4.json` passed all 754 runs.
The previous complete r3 fixture run had 747/754 successes. Its seven failures
were fixed without changing task content: shell-aware initializer detection and
correct recognition of authored opaque attachments. Targeted rerun passed 7/7.

The former r7 Mistral baseline had 49/52 technically valid records. An actual
failed request identified malformed historical tool arguments being parsed again
by vLLM before template rendering. The budget guard preserves rejected arguments
and their native parse-error output in a valid diagnostic envelope; the same
adapted history is counted and submitted. New malformed calls remain rejected
before tool execution. Actual Mistral replay returned400 before and200 after,
and all five refreshed extended protocol probes passed. Per-lifecycle counting
rejections now retain exact request/body evidence without authentication headers.

The 20260907-r1 failure exposed another explicitly rejected historical call:
malformed `request_user_input` arguments followed by the exact native output
`request_user_input is unavailable in Default mode`. The guard now recognizes
this exact tool/output pair, retaining raw arguments and the rejection without
inventing execution. Eight budget tests and the `protocol-mistral-r4` actual
captured-request replay passed (original400, adapted200). The remaining models'
current-source probes are pending; aggregate them into
`protocol_probe_report_r3.json` before preparing a fresh batch. Do not reuse
older protocol reports whose dependency hashes predate this guard change.

Current batch `v10-paired-20260907-r3` uses `protocol_probe_report_r4.json`,
which passed all five models after adding the third observed native rejection:
exact `unsupported call: {name}`. Its malformed history is preserved as a
non-executed diagnostic envelope. The actual captured Mistral request returned
400 before adaptation and 200 after; independent CPU replay also passed.

Pilot now continues other conditions and model waves when completed workers
produce technically invalid records. These failures are retained, reported with
exit code 3 after safe lifecycle cleanup, and still fail final pilot acceptance.
Worker crashes, setup, source, ownership, and cleanup failures still stop the run.
Full execution retains its previous stop-on-failure behavior. This gathers the
remaining authorized diagnostics without authorizing full generation or scoring
from a failed pilot. The 24 controller tests include these boundaries.

For new generation-first freezes, select both
`--judge-validation-phase before_scoring` and
`--fixture-validation-phase before_full` with `--prepare`. Pilot requires the
real source-bound fixture smoke and all five actual protocol probes. Complete
754-run fixture validation may run concurrently with pilot; it must pass before
full generation, together with pilot technical and semantic validation.
Readiness explicitly reports `smoke_only_full_pending`,
`judge_full_pipeline=null`, `deferred_until_scoring`, and
`scoring_authorized=false`. Use `--check-judge-gate` on the frozen controller
before scoring; it requires all 24 source-bound full-pipeline cases. The defaults
and old freezes retain strict before-pilot policies. Policies are immutable
once frozen.

Service contracts include inherited search paths. Prepare in the same recorded
runtime environment as the actual probes; do not leak a test PYTHONPATH into
preparation. The r5 batch reproduces the probe's recorded PATH. The current 20260907-r1 batch and all refreshed probes
use an explicit stable operational PATH, with inherited PYTHONPATH, CPATH,
LIBRARY_PATH and LD_LIBRARY_PATH cleared before sourcing aistation_env.sh.

New inner sandbox scopes include the batch date and revision, for example
`v10-20260906-r2-pilot-glm-base`. Before starting a model lifecycle the controller
checks all its outer and inner scopes and refuses any pre-existing container;
it never adopts those containers for cleanup. This supersedes the older
unversioned inner-scope examples below for new freezes.

Judge r9 terminated after a utility length failure. The corrected utility prompt
passed a four-case real smoke in r11 and was promoted. Historical C_code_003 gold
was separately adjudicated blind and revised with preserved original inputs;
full Judge acceptance and final scoring remain pending.

Earlier failed freezes, the r7 pilot, and r8 diagnostic attempts are retained.
The r8 diagnostic is not a formal pilot and cannot establish full acceptance. See `reports/v10-fixes-20260906/continuation_20260907.md` and
actual batch status for authoritative execution outcomes.

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
  --report /2024233123/skills/reports/v10-fixes-20260906/fixture_runtime_preflight_r3.json
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
