# Token Usage Data Model

Use this schema when converting collector output into project memory.

## Session Summary

```yaml
session_id: string
agent: codex | codex-sidecar | claude-code
source_file: string
project_root: string
cwd: string | null
started_at: iso8601 | null
ended_at: iso8601 | null
model_provider: string | null
model: string | null
git_branch: string | null

usage:
  input_tokens: integer
  cached_input_tokens: integer
  cache_creation_input_tokens: integer
  cache_read_input_tokens: integer
  output_tokens: integer
  reasoning_output_tokens: integer
  total_context_tokens: integer
  fresh_tokens: integer
  cached_tokens: integer

classification:
  phase: string | null
  task_type: string | null
  confidence: exact | inferred | manual | unknown

artifacts:
  commits: [string]
  prs: [string]
  experiment_runs: [string]
  reports: [string]
  paper_sections: [string]
  memory_updates: [string]
  sidecar_runs: [string]

outcome: shipped | synthesized | diagnosed | blocked | abandoned | unknown
notes: string
```

## Field Semantics

- `total_context_tokens`: total context observed by the agent. For Claude Code, include cache reads. For Codex, use `total_tokens` when reported.
- `fresh_tokens`: non-cached input plus cache creation plus output. This is usually the better proxy for incremental effort/cost.
- `cached_tokens`: prompt-cache reads or cached input. This measures context reuse and should not be treated as equal to fresh work.
- `reasoning_output_tokens`: keep separate when reported. Do not add it again if the provider's `output_tokens` already includes reasoning.
- `confidence`: use `exact` for provider-reported token fields, `inferred` for phase/task labels, `manual` for user-entered estimates, and `unknown` when the basis is unclear.
- `codex-sidecar`: session summaries derived from `.agent/sidecars/*/model.json`. Exact usage exists only if Codex CLI token numbers were copied into the metadata; otherwise the run still counts as a lifecycle artifact with zero known token fields.

## Interpretation

Prefer project-facing language:

- "attention concentrated in writing and tooling"
- "fresh token burn increased during debugging"
- "high cached-token share suggests context reuse"
- "yield was decision-heavy rather than commit-heavy"

Avoid simplistic claims:

- "more tokens means better project"
- "low commit yield means low productivity"
- "cache reads are the same as new work"
