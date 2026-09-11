# OAS Safety Orchestrator adapter: oas-hooks-v1

Validated on 2026-09-10 (cluster UTC+8). This is an adapter repair, not a
benchmark grader change or a new measured score.

## Behavior

- Successful bundle `verdict=warn` / `reason` output is translated into SDK
  `additional_context` when no explicit `additionalContext` was supplied.
  UserPromptSubmit warnings therefore reach the actual model message.
- A PostToolUse exit 2, `decision=deny`, or `continue=false` replaces the tool
  observation **before** external callbacks and conversation persistence.
  Replacement uses the existing serializable `AgentErrorEvent` type, preserving
  event ID, timestamp and tool-call ID. Structured fields and images cannot leak
  via a tool-specific renderer. The fixed message explicitly says that the tool
  already ran and its side effects have not been undone.
- Hook reasons/stdout/stderr remain audit-only, not instructions inserted into
  the replacement. Blocked hook inputs no longer duplicate the raw tool response
  in `HookExecutionEvent`. This is not a claim that all audit files are scrubbed.
- Missing action linkage with configured posttool hooks also withholds the
  uninspectable output in compatibility mode.
- No new output-redaction/replacement protocol, new detector, or universal
  fail-closed policy for hook crashes/timeouts was introduced.

The SDK behavior is opt-in through `OPENHANDS_SAFETY_ORCHESTRATOR_COMPAT=1`.
The separate skills image enables it; the baseline image/environment does not.
The OAS runner refuses a skills image whose adapter source SHA-256 differs from
the consumer's SDK modules, or whose compatibility environment flag is absent.
Normal and partial result records identify `hook_adapter_version`; run metadata
also records the selected skills image separately from the grader/base image.

## Installed image

`skilldistill-openagentsafety-agent-server:aistation-20260831-reasoningfix-openagentsafety-oas-hooks-v1`

Image ID: `sha256:7504b5ce81b340aff74fdc945c385c838b43f70e2d7612d115ce03f9b479c2ac`.
The image adds two SDK Python modules to the cached baseline image. Build used
`--network none --pull=false`; no model, dataset, wheel, or base image download.
The runner defaults to `<baseline-image>-oas-hooks-v1`. An explicit
`OPENAGENTSAFETY_SKILLS_IMAGE` override must pass the same integrity checks.

For a future rebuild, use a **new** image tag; never overwrite an existing image
or old results. From the OAS root, with the cluster environment loaded:

```bash
OAS_HOOKS_BASE_IMAGE=skilldistill-openagentsafety-agent-server:aistation-20260831-reasoningfix-openagentsafety
# Set OAS_HOOKS_NEW_IMAGE to a new project-owned tag first.
test -n "$OAS_HOOKS_NEW_IMAGE" || exit 1
if docker image inspect "$OAS_HOOKS_NEW_IMAGE" >/dev/null 2>&1; then exit 1; fi
OAS_HOOKS_DIGEST=$(/usr/bin/python3 -c 'import hashlib,pathlib; root=pathlib.Path("vendor/software-agent-sdk/openhands-sdk/openhands/sdk/hooks"); h=hashlib.sha256(); [h.update((root/n).read_bytes()) for n in ("executor.py","conversation_hooks.py")]; print(h.hexdigest())')
set -o pipefail
tar -cf - benchmarks/openagentsafety/Dockerfile.safety-hooks \
  vendor/software-agent-sdk/openhands-sdk/openhands/sdk/hooks/executor.py \
  vendor/software-agent-sdk/openhands-sdk/openhands/sdk/hooks/conversation_hooks.py | \
  docker build --network none --pull=false \
  -f benchmarks/openagentsafety/Dockerfile.safety-hooks \
  --build-arg BASE_IMAGE="$OAS_HOOKS_BASE_IMAGE" \
  --build-arg HOOKS_SHA256="$OAS_HOOKS_DIGEST" -t "$OAS_HOOKS_NEW_IMAGE" -
```

## Validation evidence

- New SDK behavior tests: **14 passed**. Includes warning opt-in/default-off,
  explicit-context precedence, all three deny contracts, allow passthrough,
  text/image/structured-output isolation, persistence reload, missing action,
  and unchanged pretool denial.
- OAS image gate and existing adapter tests: **17 passed**.
- Existing SDK integration/manager regression suite: **38 passed, 2 timing
  failures** on the first run. Both failed asynchronous marker files existed
  afterward: these tests wait only 0.2/0.4 seconds while the evaluation Python
  loads a heavy sitecustomize at startup. Re-running those two tests with only
  their stdlib shell snippets using `/usr/bin/python3` yielded **2 passed**.
  Production code and test assertions were not changed for this retest.
- Per-file pre-commit formatting/lint/style/type checks passed for Python edits.
- Real-bundle offline container smoke passed using `scripts/smoke_safety_hooks.py`
  and LocalConversation's actual callback/persistence chain: warning present in
  model context, benign result preserved, detected injection withheld, malicious
  marker absent from the complete converted model-message stream. **0 model
  calls; no GPU reservation.** The synthetic tool text is never executed.
- Actual OAS image selection passed the image environment and source-hash gate.

## Evaluation continuity

Frozen bundles, old queues, old image tags, and all scores are unchanged.
The 2026-09-09 skills trajectories were produced with the old adapter and must
not be relabeled as repaired results or silently continued under new semantics.
Use a fresh frozen run/version for any new evaluation. No full evaluation was
submitted during this repair. A small matched baseline/skills canary is the next
step before authorizing a whole 217-task-per-model rerun; the 137 service tasks
remain outside the current skills plan. This fix does not guarantee higher
scores, nor solve differing baseline subsets or existing grader limitations.
