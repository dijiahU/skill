// Native DSH integration. No benchmark runtime or npm dependencies required.
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, isAbsolute, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const name = 'safety-orchestrator';
export const inject = ['tools', 'systemPrompt'];
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const MATCHERS = ['bash', 'write_edit', 'pretool_generic', 'posttool', 'user_prompt', 'webfetch', 'stop', 'task'];
const TOOLS = Object.freeze({
  bash: 'Bash', read: 'Read', write: 'Write', edit: 'Edit',
  glob: 'Glob', grep: 'Grep', web_fetch: 'WebFetch', web_search: 'WebSearch',
  safety_reference: 'Read',
});
const UNAVAILABLE = 'Safety Orchestrator could not complete its checks; action withheld.';
const blocks = (text) => [{ type: 'text', text }];
const notice = (text) => ({
  id: randomUUID(), role: 'user', content: blocks(text),
  source: { kind: 'plugin', plugin: name },
});
const plainText = (content) => (content ?? [])
  .filter((block) => block.type === 'text').map((block) => block.text).join('\n');
const denied = (result) => result.decision === 'block'
  || result.hookSpecificOutput?.permissionDecision === 'deny';
const reason = (result) => result.reason
  || result.hookSpecificOutput?.permissionDecisionReason || 'Blocked by Safety Orchestrator.';
const context = (result) => result.hookSpecificOutput?.additionalContext;

function checkBundle(root) {
  for (const matcher of MATCHERS) {
    if (!statSync(resolve(root, `hooks/scripts/matcher_${matcher}.py`)).isFile()) {
      throw new Error(UNAVAILABLE);
    }
  }
}

// Exported for protocol regression tests; plugin config cannot substitute a runner.
export function createBridge({ root = ROOT, python = 'python3', timeoutMs = 120000 } = {}) {
  if (!Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 300000) {
    throw new Error('timeoutMs must be between 1 and 300000');
  }
  checkBundle(root);
  return async (event, signal) => {
    checkBundle(root);
    const input = JSON.stringify(event);
    if (Buffer.byteLength(input) > 4 * 1024 * 1024 || signal?.aborted) {
      throw new Error(UNAVAILABLE);
    }
    return new Promise((resolveResult, reject) => {
      // A process group lets timeout/cancellation stop the Python matchers too.
      const child = spawn(python, [resolve(root, 'adapters/codex/codex_hook.py')], {
        detached: true, stdio: ['pipe', 'pipe', 'pipe'],
        env: {
          ...process.env, PYTHONDONTWRITEBYTECODE: '1',
          SAFETY_ORCH_CORE: resolve(root, 'hooks/scripts'),
          SAFETY_ORCH_MANUAL_BRIDGE: '1', SAFETY_ORCH_FAIL_CLOSED: '1',
        },
      });
      let stdout = '';
      let size = 0;
      let failed = false;
      const abort = () => {
        failed = true;
        if (child.pid) {
          try { process.kill(-child.pid, 'SIGKILL'); } catch { child.kill('SIGKILL'); }
        }
      };
      const timer = setTimeout(abort, timeoutMs);
      signal?.addEventListener('abort', abort, { once: true });
      if (signal?.aborted) abort();
      child.stdout.setEncoding('utf8');
      child.stdout.on('data', (chunk) => {
        size += Buffer.byteLength(chunk);
        if (size > 1024 * 1024) abort();
        else stdout += chunk;
      });
      // Never echo raw tool output or Python diagnostics containing secrets.
      child.stderr.on('data', (chunk) => {
        size += chunk.length;
        if (size > 1024 * 1024) abort();
      });
      child.stdin.on('error', abort);
      child.on('error', () => { failed = true; });
      child.on('close', (code) => {
        clearTimeout(timer);
        signal?.removeEventListener('abort', abort);
        try {
          if (failed || ![0, 2].includes(code)) throw new Error();
          const result = JSON.parse(stdout);
          const usage = result.safetyOrchestratorUsage;
          if (usage?.hook_event !== event.hook_event_name || usage.error
              || !Array.isArray(usage.matchers) || !usage.matchers.length
              || (code === 2 && !denied(result))) throw new Error();
          resolveResult(result);
        } catch { reject(new Error(UNAVAILABLE)); }
      });
      child.stdin.end(input);
    });
  };
}

export function apply(ctx, config = {}) {
  const run = createBridge({ python: config.python ?? 'python3', timeoutMs: config.timeoutMs ?? 120000 });
  const states = new WeakMap();
  const approved = new WeakSet();
  const referenceRoot = resolve(ROOT, 'skills/safety-router-skill/references');
  const references = new Map([
    ['atoms-catalog', readFileSync(resolve(referenceRoot, 'atoms-catalog.md'), 'utf8')],
    ...readdirSync(resolve(referenceRoot, 'archetypes')).filter((file) => file.endsWith('.md'))
      .map((file) => [file.slice(0, -3), readFileSync(resolve(referenceRoot, 'archetypes', file), 'utf8')]),
  ]);
  const referenceTool = {
    name: 'safety_reference',
    description: 'Read a trusted Safety Orchestrator archetype or the atom catalog.',
    parameters: {
      type: 'object', properties: { name: { type: 'string', enum: [...references.keys()] } },
      required: ['name'], additionalProperties: false,
    },
    output: { schema: { type: 'string' }, render: (_args, value) => blocks(value) },
    async execute(args) {
      if (!references.has(args?.name)) throw new Error('Unknown safety reference');
      return references.get(args.name);
    },
  };
  ctx.tools.register(referenceTool);
  ctx.systemPrompt.section({
    name, order: 50,
    text: readFileSync(resolve(ROOT, 'skills/safety-router-skill/SKILL.md'), 'utf8')
      + '\n\nDSH host binding: use safety_reference with the archetype filename without .md '
      + 'when this Router asks to read a reference; use name atoms-catalog for the catalog. '
      + 'The safety hooks run automatically. Native foreground tools are supported; '
      + 'PTC, background jobs, image reads and unrecognized tools are withheld. '
      + 'Do not request parallel tools; retry safe calls sequentially if necessary.',
  });

  function envelope(agent, hook, extra = {}) {
    const state = states.get(agent);
    const header = agent?.session?.header;
    if (!state || !header?.id || !isAbsolute(header.cwd ?? '')) throw new Error(UNAVAILABLE);
    return {
      hook_event_name: hook, session_id: `dsh:${header.id}`, turn_id: String(state.turn),
      cwd: header.cwd, ...extra,
    };
  }

  function toolEvent(exec, hook) {
    if (!states.get(exec.agent)?.ready || !Object.hasOwn(TOOLS, exec.name)
        || exec.parent !== undefined || !exec.arguments || Array.isArray(exec.arguments)
        || typeof exec.arguments !== 'object') throw new Error(UNAVAILABLE);
    const args = exec.arguments;
    if (exec.name === 'bash' && (args.run_in_background || typeof args.command !== 'string')) {
      throw new Error('Only foreground bash commands are supported.');
    }
    if (['read', 'write', 'edit'].includes(exec.name) && typeof args.file_path !== 'string') {
      throw new Error(UNAVAILABLE);
    }
    const event = envelope(exec.agent, hook, {
      tool_name: TOOLS[exec.name], tool_input: args, tool_use_id: exec.callId,
    });
    if (exec.name === 'bash' && args.workdir !== undefined) {
      if (typeof args.workdir !== 'string') throw new Error(UNAVAILABLE);
      event.cwd = resolve(event.cwd, args.workdir);
    }
    return event;
  }

  ctx.on('agent/pre-step', async ({ agent, turn, signal }, next) => {
    const prior = states.get(agent);
    const state = prior?.turn === turn ? prior : { turn, stops: 0 };
    state.ready = false;
    states.set(agent, state);
    const decision = await next();
    if (decision.kind !== 'enter') return decision;
    // Tool/plugin messages must never become trusted user authorization.
    const users = decision.messages.filter((message) => message.source?.kind === 'user');
    const additions = [];
    if (users.length) {
      const result = await run(envelope(agent, 'UserPromptSubmit', {
        prompt: users.map((message) => plainText(message.content)).join('\n'),
      }), signal);
      if (denied(result)) throw new Error('Safety Orchestrator blocked this prompt.');
      if (context(result)) additions.push(notice(context(result)));
    }
    state.ready = true;
    return { ...decision, messages: [...decision.messages, ...additions] };
  });

  ctx.on('tools/pre-execute', async (exec, next) => {
    try {
      const result = await run(toolEvent(exec, 'PreToolUse'), exec.signal);
      if (denied(result)) return { kind: 'deny', reason: reason(result) };
      const decision = await next();
      if (['allow', 'ask'].includes(decision.kind)) approved.add(exec);
      if (context(result)) exec.agent.inject(notice(context(result)));
      return decision;
    } catch { return { kind: 'deny', reason: UNAVAILABLE }; }
  });
  ctx.tools.guard((exec) => {
    const state = states.get(exec.agent);
    if (!state?.ready || !approved.has(exec)) return UNAVAILABLE;
    // Stateful flow checks need ordered calls, including tool completion.
    if (state.active !== undefined) return 'Safety checks require sequential tool calls; retry after the active call completes.';
    state.active = exec.token;
    return undefined;
  });
  ctx.on('tools/result', (exec) => {
    const state = states.get(exec.agent);
    if (state?.active === exec.token) delete state.active;
    approved.delete(exec);
  });

  ctx.on('tools/post-execute', async (exec, result, next) => {
    try {
      const decision = await next();
      const contexts = decision.kind === 'block' ? (decision.additionalContexts ?? [])
        : [...(result.additionalContexts ?? []), ...(decision.additionalContexts ?? [])];
      const view = decision.kind === 'block'
        ? { isError: true, content: decision.feedback, additionalContexts: contexts }
        : { ...result, ...('value' in decision ? { value: decision.value } : {}),
          content: decision.content ?? result.content, additionalContexts: contexts };
      // Only this exact, pinned reference result is trusted, never arbitrary reads.
      const trusted = exec.name === referenceTool.name && decision.kind === 'accept'
        && ctx.tools.get(exec.name, exec.agent) === referenceTool && !view.isError
        && references.has(exec.arguments.name) && view.value === references.get(exec.arguments.name)
        && JSON.stringify(view.content) === JSON.stringify(blocks(view.value))
        && !view.meta && !contexts.length;
      if (trusted) return decision;
      // A value replacement is rendered AFTER post hooks. We cannot inspect that
      // future projection, so withhold it instead of certifying unseen content.
      if ('value' in decision) return { kind: 'block', feedback: blocks(UNAVAILABLE) };
      // DSH bash can successfully return a foreground result for a FAILED shell
      // process. Its typed exit status is authoritative; printed output is not.
      const executionStatus = exec.name === 'bash' ? {
        success: !result.isError && result.value?.kind === 'foreground'
          && result.value.exitCode === 0 && result.value.signal === null && !result.value.timedOut,
      } : { success: !result.isError };
      const checked = await run({
        ...toolEvent(exec, 'PostToolUse'), tool_response: view, ...executionStatus,
      }, exec.signal);
      if (denied(checked)) return { kind: 'block', feedback: blocks(reason(checked)) };
      const replacement = checked.hookSpecificOutput?.modifiedOutput;
      if (typeof replacement === 'string') {
        // Native block removes BOTH rendered content and the successful value.
        return { kind: 'block', feedback: blocks(replacement) };
      }
      return context(checked) ? {
        ...decision, additionalContexts: [...(decision.additionalContexts ?? []), notice(context(checked))],
      } : decision;
    } catch { return { kind: 'block', feedback: blocks(UNAVAILABLE) }; }
  });

  ctx.on('agent/turn-stopping', async ({ agent, turn, signal }) => {
    const state = states.get(agent);
    if (state?.turn !== turn) throw new Error(UNAVAILABLE);
    const last = [...agent.session.snapshotEvents()].reverse().find(
      (event) => event.type === 'assistant/message' && event.data.turn === turn,
    );
    const result = await run(envelope(agent, 'Stop', {
      last_assistant_message: plainText(last?.data.message.content),
    }), signal);
    if (denied(result)) {
      if (++state.stops > 1) {
        state.ready = false;
        throw new Error('Safety Orchestrator blocked repeated unsafe turn completion.');
      }
      agent.steer(notice(reason(result)));
    } else if (context(result)) agent.inject(notice(context(result)));
  });
}
