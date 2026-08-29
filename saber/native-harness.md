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
