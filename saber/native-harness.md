# Native Harness A/B Evaluation

`run_harness.py --harness codex-native` runs the real Codex app-server agent
loop while preserving SABER's Docker task environment, injection timing, state
deltas, and existing judge contract. It does not call the model through
SABER's hand-written API loop.

## Isolation Contract

Each task gets a fresh temporary `HOME`, `CODEX_HOME`, and host workspace.
SABER exposes `saber_bash` plus the task's `mcp_*` tools through app-server
`dynamicTools`; calls are forwarded to `TaskRuntime`. A common routing hook
blocks Codex's built-in shell and file tools from touching benchmark state.
The skill treatment installs Safety Orchestrator into only that temporary home.
Treatment runs also expose `saber_skill_read` and `saber_skill_health` so the
Router can load its host-side support files without confusing them with paths
inside the Docker benchmark environment. These support calls are recorded in
the conversation metadata but do not enter the task trajectory or consume the
benchmark tool-step limit.

Because app-server dynamic tools are executed by the SABER client rather than
Codex's native tool executor, treatment runs explicitly wrap every benchmark
tool with the installed bridge: `PreToolUse` runs before `TaskRuntime`, and
`PostToolUse` runs before the result is returned to Codex. A pre-hook deny skips
Docker execution; a post-hook `modifiedOutput` replaces the raw result. The
adapter also invokes `UserPromptSubmit` and `Stop`. These client-side runs are
reported as `manual_hook_runs`, while any future native app-server events remain
separately visible as `app_server_hook_runs`.

The paired conditions therefore differ only in whether the Safety Orchestrator
skill and hooks are installed:

- `none` -> output under `<model>_codex-native-none`
- `safety-orchestrator` -> output under
  `<model>_codex-native-safety-orchestrator`

Codex's bundled system skills remain present in both conditions because they
are part of the native harness.

## Setup and Preflight

Add a native model entry to `config.json`:

```json
{
  "models": {
    "codex_native": {"id": "gpt-5.6-terra", "type": "codex-native"}
  }
}
```

Authenticate with `codex login` (or provide `OPENAI_API_KEY`), start Docker,
and build the sandbox image if needed:

```bash
docker build -t osbench-sandbox .
python3 run_harness.py --harness codex-native --model codex_native \
  --skill-mode none --preflight-only A_fs_001
python3 run_harness.py --harness codex-native --model codex_native \
  --skill-mode safety-orchestrator \
  --safety-orchestrator ../agent-safety-orchestrator/agent-safety-orchestrator \
  --preflight-only A_fs_001
```

Preflight initializes the real app-server and verifies isolated skills/hooks
without starting a model turn.

## Isolated Codex Runner

The Runner image packages the pinned Codex CLI, SABER, and Safety Orchestrator.
It does not contain or mount the host's Codex login state. It talks to the host
Docker daemon only to create sibling `osbench-sandbox` task containers.

Build it from the workspace containing both `saber/` and
`agent-safety-orchestrator/`, then run the no-model smoke check:

```bash
./scripts/run/codex_runner.sh build
./scripts/run/codex_runner.sh smoke
```

For a local or cluster model, configure a Responses-compatible endpoint:

```json
{
  "models": {
    "codex_local": {
      "id": "your-model-id",
      "type": "codex-native",
      "base_url": "http://host.docker.internal:8000/v1",
      "copy_codex_auth": false
    }
  }
}
```

For OpenRouter, keep the secret out of JSON and use its free router for a
zero-cost connectivity check:

```json
{
  "models": {
    "codex_openrouter_free": {
      "id": "openrouter/free",
      "type": "codex-native",
      "base_url": "https://openrouter.ai/api/v1",
      "key_env": "SABER_CODEX_PROVIDER_API_KEY",
      "copy_codex_auth": false
    }
  }
}
```

Export `SABER_CODEX_PROVIDER_API_KEY` only in the invoking shell. The Runner
forwards that variable by name, rejects `OPENAI_API_KEY`, and never writes the
provider key into its generated Codex config:

```bash
SABER_CODEX_CONFIG="$PWD/config.example.json" \
  ./scripts/run/codex_runner.sh run \
  --model codex_openrouter_free --skill-mode none --trace A_fs_001
```

This isolated `env_key` setup uses the raw OpenRouter model ID. The `~` prefix
shown in OpenRouter's command-auth Codex examples requires its model-catalog
alias expansion and must not be added here.

Use `codex_openrouter_free` only for connectivity smoke tests because it may
select a different underlying model for every request. Use a pinned entry such
as `codex_openrouter_laguna_free` from `config.example.json` for comparable A/B
runs when that free variant is available.
For multi-step tool tasks, prefer the pinned low-cost
`codex_openrouter_qwen_flash`; free variants can rate-limit between tool turns.
Its example configuration enables `preload_skill_references`, so treatment runs
inject the Router, health status, and all 14 distilled archetype references into
the developer instructions. Baseline runs ignore those documents. The result
metadata records the exact preloaded filenames, making the treatment condition
auditable without relying on the model to request each reference dynamically.

For regions where OpenAI, Anthropic, and Google API models are unavailable, the
`codex_deepseek_official` example uses DeepSeek's native Responses endpoint. Set
the same runtime-only `SABER_CODEX_PROVIDER_API_KEY` variable to a DeepSeek key;
do not add the key itself to `config.json`. The `deepseek-chat` alias is resolved
by DeepSeek, so record the concrete model returned by the provider when reporting
benchmark results.

Run a single task inside the Runner with:

```bash
./scripts/run/codex_runner.sh run \
  --model codex_local --skill-mode none --trace A_fs_001
```

On a cluster, replace `host.docker.internal` with the model service DNS name.
The provider must implement streaming OpenAI Responses tool calls; Chat
Completions alone is not sufficient for Codex.

## Cluster Migration

Each worker needs Linux Docker with access to its daemon socket, outbound access
to the configured model endpoint, and persistent storage for `saber/results/`.
The Runner is ephemeral: it uses the Docker socket to create one sibling
`osbench-sandbox` container per task and removes that task container during
cleanup. Treat Docker-socket access as privileged and dedicate benchmark workers
to this workload.

Build both images on each worker or publish them to the cluster registry, then
run the token-free smoke test:

```bash
cd saber
docker build -t osbench-sandbox .
./scripts/run/codex_runner.sh build
./scripts/run/codex_runner.sh smoke
```

Keep provider credentials in the cluster secret manager. Inject the key only
into the invoking process and point the Runner at an untracked config file:

```bash
export SABER_CODEX_PROVIDER_API_KEY="$(secret-manager read deepseek-api-key)"
export SABER_CODEX_CONFIG="$PWD/config.json"

./scripts/run/codex_runner.sh run \
  --model codex_deepseek_official --skill-mode none \
  --pilot --limit 3 --trace
./scripts/run/codex_runner.sh run \
  --model codex_deepseek_official --skill-mode safety-orchestrator \
  --pilot --limit 3 --trace
```

Do not put the literal secret in shell history, JSON, images, or result files;
the command substitution above is illustrative and should be replaced with the
cluster's native secret injection mechanism. Persist `results/` outside the
ephemeral worker and keep baseline and treatment directories separate.

Start with one worker, then increase concurrency to 2, 4, and 8 while monitoring
API throttling, Docker CPU/memory, task latency, and cleanup. A harness process
can exit successfully even when an individual JSON result contains `error`, so
audit every result before judging and retry provider failures separately. Do not
score 429s, timeouts, or transport failures as model safety failures.

For reproducibility, pin the Runner image digest, Codex CLI version, model ID,
task manifest, and Safety Orchestrator commit. Record the concrete provider model
returned for aliases such as `deepseek-chat`. Run the judge only after both
conditions have the same valid task IDs.

## Live Trace

Add `--trace` to stream completed assistant messages, dynamic tool calls and
results, manual safety-hook calls/verdicts, native hook completions, blocked
host-tool attempts, and the final turn status to stderr while a Codex task runs.
Long values are previewed at 4,000 characters; the result JSON still contains
the complete trajectory and conversation.

```bash
python3 run_harness.py --harness codex-native --model codex_native \
  --skill-mode none --trace --overwrite A_fs_001
```

Trace output is observational only: enabling it does not change the app-server
request, task runtime, or saved result schema.

## Paired Run and Judging

Use the exact same deterministic subset for both conditions:

```bash
python3 run_harness.py --harness codex-native --model codex_native \
  --skill-mode none --subset tasks/harness_subset_100.json
python3 run_harness.py --harness codex-native --model codex_native \
  --skill-mode safety-orchestrator \
  --safety-orchestrator ../agent-safety-orchestrator/agent-safety-orchestrator \
  --subset tasks/harness_subset_100.json

python3 judge_osbench.py codex_native_codex-native-none
python3 judge_osbench.py codex_native_codex-native-safety-orchestrator
```

Keep the Codex CLI and model id fixed across both runs. Raw results record the
Codex user-agent version, discovered skills, hook activity, dynamic tools, and
host-tool gate events in `harness_meta`. App-server `dynamicTools` is currently
experimental, so pinning the CLI version is important for reproducibility.
