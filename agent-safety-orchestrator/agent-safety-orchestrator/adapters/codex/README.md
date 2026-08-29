# Safety Orchestrator — Codex adapter

Runs the same Safety Orchestrator atoms on **OpenAI Codex** (codex-cli). It is a
per-host **adapter** in the "one safety core, many adapters" design: the
atom-evaluation logic is **the repo's own** `hooks/scripts/matcher_*.py` —
reused verbatim, not copied — and only the host I/O is Codex-specific. The
Claude Code plugin and this adapter share one core; there is no vendored
duplicate.

> **Status.** Verified against **codex-cli 0.64.0** + the official hooks /
> approvals docs. The deterministic bridge is smoke-tested end-to-end and in CI
> (`Dual-host proof` step). Treat the `apply_patch`, `PostToolUse`, and
> `SubagentStart` mappings as best-effort until exercised against a live session.

## Two layers (same as the Claude Code plugin)

| Layer | How it maps to Codex | Determinism |
|---|---|---|
| **Hook layer** (60 hook + 21 hybrid atoms) | `hooks.json` → `codex_hook.py`, a bridge that translates each Codex hook event into the event the shared matchers expect, runs them, and returns Codex's `permissionDecision: deny` / `exit 2` | **Deterministic** — Codex blocks before the tool runs |
| **Skill layer** (14 skill + 21 hybrid atoms) | the single `safety-router-skill` (14 archetype docs nested under `references/archetypes/`) installed into `$CODEX_HOME/skills/` — Codex reads the same agentskills.io format; archetypes are Read-on-route reference docs, so the layer is router-first | Model-invoked (advisory) |

## How the bridge works

```
Codex hook event (stdin JSON)
   │  hook_event_name, tool_name, tool_input, ...
   ▼
codex_hook.py  ── dispatch by event/tool ──►  <repo>/hooks/scripts/matcher_*.py
   │                                              (the SHARED core, event-in/verdict-out)
   ▼
Codex output:
   PreToolUse block → {"hookSpecificOutput":{"permissionDecision":"deny",...}} + exit 2
   other events     → {"decision":"block","reason":...}
   pass             → exit 0
```

The bridge finds the shared core in priority order (`$SAFETY_ORCH_CORE` →
installed `core/hooks/scripts` → in-repo `../../hooks/scripts`), so the **same
file** works whether it runs from the repo or from a Codex install.

One `PreToolUse` matcher `.*` is enough — the bridge dispatches internally
(`Bash` → bash checks, `apply_patch` → write/edit checks, every tool → generic
trust/rate/supply-chain checks), so there is no per-tool duplication.

App-server clients that expose a remote shell as a dynamic function can opt
that function into the same Bash matcher path. Set a comma-separated alias list
before starting Codex, for example:

```bash
SAFETY_ORCH_BASH_TOOL_NAMES=saber_bash codex app-server --stdio
```

The default remains only Codex's canonical `Bash` hook name.

Clients that execute app-server dynamic tools themselves must also invoke the
bridge around that execution, because discovery via `hooks/list` does not make
client-owned functions pass through Codex's native tool executor. Set
`SAFETY_ORCH_MANUAL_BRIDGE=1` for those bridge subprocesses; `PostToolUse` then
returns `hookSpecificOutput.modifiedOutput` so the client can replace a tool
result with the deterministic matcher's sanitized value.

## ⚠️ Coverage caveat (Codex-specific, by design)

Codex `PreToolUse` does **not** reliably intercept `unified_exec` streaming
shell or `WebSearch`, and has no `Task` tool. So a few atoms (network egress /
unsafe-URL / SSRF, and some shell variants) **cannot be caught by the hook
alone**. Back them with the OS-level sandbox + approvals in
[`config.backstop.toml`](config.backstop.toml) (`sandbox_mode = "workspace-write"`,
`network_access = false`, `approval_policy = "on-request"`). Determinism is a
property of the enforcement point: where the hook can't reach, the sandbox does.

## Install

Use the repo-root unified installer (recommended):

```bash
./install.sh --host codex                          # into ~/.codex
CODEX_HOME=/tmp/codex-test ./install.sh --host codex   # ISOLATED trial (touches nothing real)
```

…or run this adapter's installer directly (`adapters/codex/install.sh`) — same effect.

The installer is **safe**: it never overwrites an existing `hooks.json` or
`config.toml` (it writes a `.safety-orchestrator` sidecar for you to merge), and
skips skills whose name already exists. It **assembles** the deployment from the
repo's single source of truth — copying `hooks/scripts/` + `helpers/` +
`atoms.json` into `$CODEX_HOME/safety-orchestrator/core/`, the bridge alongside
it, and the skills into `$CODEX_HOME/skills/` — then renders the absolute bridge
path into `hooks.json`. Ensure `[features] hooks = true` in `config.toml`
(default on), then start `codex`.

## Testing (no model calls, no quota burned)

Feed the bridge a Codex event directly:

```bash
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf /home"}}' \
  | python3 codex_hook.py
# → {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
#     "permissionDecisionReason":"[detect-destructive-flag] ..."}}   (exit 2)
```

For a live check, install into an isolated `CODEX_HOME` and run
`codex exec` there — never the real `~/.codex` for experiments.

## Layout

```
adapters/codex/
├── codex_hook.py          # the host adapter (thin I/O bridge)
├── hooks.json             # Codex hook wiring (template; install.sh renders the path)
├── config.backstop.toml   # sandbox + approval backstop (merge into config.toml)
└── install.sh             # safe installer (assembles core from the repo root)
```

No `core/` or `skills/` here: this adapter reuses the repo's own
`hooks/scripts/`, `helpers/`, `atoms.json`, and `skills/`. The installer copies
them out at install time, so the deployment is self-contained while the source
stays single-copy.
