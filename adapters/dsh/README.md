# DeepSeek Harness adapter

This native DSH plugin connects prompt admission, tool execution and turn completion
to the shared safety core. It has no benchmark, dataset or model-provider dependency.
It reuses the JSON event dispatcher in `adapters/codex/codex_hook.py` in manual-bridge
mode; the eight Python matchers remain the single source of enforcement rules.

## Installation

Requirements: macOS or Linux, Python 3.10+, Node.js 22+, and a separately installed
DSH with the native tool guard and post-execution APIs. The offline integration
test targets `@deepseek-ai/dsh-tools` 0.1.5-rc.2 and Cordis 4.0.2; other DSH versions
need compatibility verification. No live model call is needed to install or test.

```bash
./install.sh --host dsh
dsh --patch "$HOME/.dsh/safety-orchestrator.patch.json"
# Headless usage also accepts the patch:
dsh --profile headless --patch "$HOME/.dsh/safety-orchestrator.patch.json" "Your task"
```

`DSH_HOME` changes the installation directory. The installer copies a standalone
framework bundle to `DSH_HOME/safety-orchestrator` and writes
`DSH_HOME/safety-orchestrator.patch.json`; the default is `~/.dsh`. Reinstall to
update the owned bundle and patch. Existing DSH settings, providers and credentials
are preserved. Load the patch once per DSH invocation. For a Python executable
outside `PATH`, edit the patch's `config.python`; `config.timeoutMs` defaults to
120000 and is bounded to 300000. These settings are trusted administrator inputs.
Choose a `DSH_HOME` outside the source repository for an isolated installation.

The Router is added as a system-prompt section. Its 14 archetypes and atom catalog
are exposed through the read-only `safety_reference` tool, loaded on demand by the
model. They are not registered as additional top-level skills. Export optional
settings from the repository's `.env.example` before starting DSH; no `.env` file
is automatically loaded.

## Supported behavior and limits

- Native `bash`, `read`, `write`, `edit`, `glob`, `grep`, `web_fetch` and
  `web_search` retain their full arguments. Bash `workdir` is resolved against
  the session workspace before checks. Only real user messages can grant prompt
  authorization; tool and plugin messages cannot.
- Calls without an admitted agent session, unknown tools, PTC `run_code`, nested
  PTC calls, background bash, image reads, and unreviewed MCP/subagent tools are
  denied. Use native foreground tools. Overlapping calls are denied and may be
  retried sequentially, preserving the core's stateful flow checks.
- A monotonic native guard requires a successful pre-check. Missing matchers,
  missing Python, malformed bridge results, cancellation, timeouts, and oversized
  input/output withhold the action or result. Tool effects already executed
  cannot be undone by a post-check.
- Post-checks examine rendered content, structured values, error details, metadata
  and deferred contexts. Redaction returns a native **blocked result with sanitized
  feedback**, removing both the original content and successful structured value.
  Consequently, even a successfully executed tool can appear as an error to DSH.
  Downstream value replacements are withheld because DSH renders them after the
  post-check. Exact results from the adapter's pinned reference tool are trusted.
- Turn completion checks the latest assistant message in that turn. A denial
  requests one corrective step; repeated denials stop with an error. DSH may have
  already streamed or logged the message: this is **not a final-answer redaction
  boundary**. It does not scrub DSH transcripts or earlier streaming output.
- Host plugins, tool implementations and framework files must be trusted. DSH
  definition-owned finalizers run after post hooks, and other plugins can replace
  prompt sections or intercept events. This adapter does not isolate hostile
  in-process plugins or arbitrary executable code. Keep DSH sandbox and approval
  controls enabled; static checks do not replace OS isolation.

The adapter follows the official [tool execution pipeline](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/tool-execution-pipeline.md)
and [tool registry API](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/core/tools/README.md).

## Offline verification

```bash
node --test tests/test_dsh_adapter.mjs
```

The suite exercises the real Python bridge and isolated installation. To also
exercise the official native tool registry, point `DSH_TEST_NODE_MODULES` at an
existing compatible DSH installation's `node_modules` directory. Without it, the
native-registry test is explicitly skipped; no packages or model APIs are fetched.
