import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { randomUUID, createHash } from 'node:crypto';
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, rmSync, cpSync, realpathSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { test, after } from 'node:test';
import { apply, createBridge } from '../adapters/dsh/index.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const temp = mkdtempSync(resolve(tmpdir(), 'dsh-safety-'));
process.env.SAFETY_ORCH_STATUS_DIR = resolve(temp, 'state');
process.env.SAFETY_ORCH_CACHE_DIR = resolve(temp, 'cache');
process.env.SAFETY_ORCH_RECOVERY_POLICY = 'recheck';
after(() => rmSync(temp, { recursive: true, force: true }));
const signal = () => new AbortController().signal;
const blocks = (text) => [{ type: 'text', text }];
const success = (value) => ({ isError: false, value, content: blocks(String(value)) });
const user = (text, kind = 'user') => ({
  id: randomUUID(), role: 'user', content: blocks(text), source: { kind, plugin: 'test' },
});

function host(plugin = apply, config) {
  const handlers = new Map();
  const definitions = new Map();
  const guards = [];
  const sections = [];
  const ctx = {
    on: (name, fn) => { handlers.set(name, fn); },
    systemPrompt: { section: (section) => sections.push(section) },
    tools: {
      register: (tool) => definitions.set(tool.name, tool),
      get: (name) => definitions.get(name),
      guard: (fn) => guards.push(fn),
    },
  };
  plugin(ctx, config);
  return { handlers, guards, definitions, sections, ctx };
}

function agent() {
  const messages = [];
  const events = [];
  return {
    session: { header: { id: randomUUID(), cwd: temp }, snapshotEvents: () => events },
    inject: (message) => messages.push(message), steer: (message) => messages.push(message),
    messages, events,
  };
}

async function admit(host, agent, messages = [user('Inspect the project files.')], turn = 1) {
  return host.handlers.get('agent/pre-step')({ agent, turn, step: 1, signal: signal() },
    async () => ({ kind: 'enter', messages }));
}

function execution(agent, name = 'bash', args = { command: 'printf safe' }) {
  return { agent, name, arguments: args, token: Symbol(), callId: randomUUID(), signal: signal() };
}

async function pre(host, exec, next = async () => ({ kind: 'allow' })) {
  const result = await host.handlers.get('tools/pre-execute')(exec, next);
  if (result.kind === 'allow') {
    for (const guard of host.guards) {
      const reason = guard(exec);
      if (reason) return { kind: 'deny', reason };
    }
  }
  return result;
}

const post = (host, exec, result, next = async () => ({ kind: 'accept' })) =>
  host.handlers.get('tools/post-execute')(exec, result, next);
const done = (host, exec) => host.handlers.get('tools/result')(exec);

test('native names preserve file arguments and reject destructive commands; safe recovery passes', async () => {
  const h = host(); const a = agent(); await admit(h, a);
  assert.equal((await pre(h, execution(a, 'bash', { command: 'rm -rf /' }))).kind, 'deny');
  assert.equal((await pre(h, execution(a, 'write', {
    file_path: resolve(temp, '.env'), content: 'AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE',
  }))).kind, 'deny');
  const safe = execution(a);
  assert.equal((await pre(h, safe)).kind, 'allow'); done(h, safe);
  const write = execution(a, 'write', { file_path: resolve(temp, 'hello.txt'), content: 'hello' });
  assert.equal((await pre(h, write)).kind, 'allow'); done(h, write);
});

test('bash workdir resolves local script content before execution', async () => {
  const folder = resolve(temp, 'scripts'); mkdirSync(folder);
  writeFileSync(resolve(folder, 'danger.sh'), 'rm -rf /\n');
  const h = host(); const a = agent(); await admit(h, a);
  assert.equal((await pre(h, execution(a, 'bash', {
    command: 'bash danger.sh', workdir: 'scripts',
  }))).kind, 'deny');
});

test('unadmitted agents, PTC, background and unknown tools are denied', async () => {
  const h = host(); const a = agent();
  assert.equal((await pre(h, execution(a))).kind, 'deny');
  await admit(h, a);
  for (const exec of [
    execution(a, 'run_code', { code: 'return 1' }),
    execution(a, 'mcp__exec', { command: 'printf safe' }),
    execution(a, 'bash', { command: 'printf safe', run_in_background: true }),
    { ...execution(a), parent: Symbol() },
  ]) assert.equal((await pre(h, exec)).kind, 'deny');
  assert.match(h.guards[0](execution(a)), /withheld/);
});

test('calls serialize per agent; another session remains independent', async () => {
  const h = host(); const a = agent(); const b = agent();
  await admit(h, a); await admit(h, b);
  const first = execution(a); const other = execution(b);
  assert.equal((await pre(h, first)).kind, 'allow');
  assert.equal((await pre(h, execution(a))).kind, 'deny');
  assert.equal((await pre(h, other)).kind, 'allow'); done(h, other);
  done(h, first);
  const later = execution(a);
  assert.equal((await pre(h, later)).kind, 'allow'); done(h, later);
});

test('downstream denials remain denials', async () => {
  const h = host(); const a = agent(); await admit(h, a);
  const exec = execution(a);
  assert.equal((await pre(h, exec, async () => ({ kind: 'deny', reason: 'Host policy' }))).reason, 'Host policy');
  assert.match(h.guards[0](exec), /withheld/);
});

test('post-check removes raw structured secrets even if rendered text is innocuous', async () => {
  const h = host(); const a = agent(); await admit(h, a);
  const exec = execution(a, 'read', { file_path: resolve(temp, 'notes.txt') });
  const secret = 'AKIAIOSFODNN7EXAMPLE';
  const decision = await post(h, exec, {
    isError: false, value: { access_key: secret }, content: blocks('read complete'),
  });
  assert.equal(decision.kind, 'block');
  assert.ok(!JSON.stringify(decision).includes(secret));
  assert.ok(!('value' in decision));
});

test('post-check scans error details and deferred contexts; rejects unseen replacement rendering', async () => {
  const h = host(); const a = agent(); await admit(h, a);
  const exec = execution(a, 'read', { file_path: resolve(temp, 'notes.txt') });
  const secret = 'AKIAIOSFODNN7EXAMPLE';
  for (const result of [
    { isError: true, error: { message: secret }, content: blocks('failed') },
    { ...success('ok'), additionalContexts: [user(secret, 'tool')] },
    { ...success('ok'), meta: { credential: secret } },
  ]) {
    const decision = await post(h, exec, result);
    assert.equal(decision.kind, 'block');
    assert.ok(!JSON.stringify(decision).includes(secret));
  }
  assert.equal((await post(h, exec, success('ok'), async () => ({ kind: 'accept', value: 'new' }))).kind, 'block');
  const downstream = await post(h, exec, success('ok'), async () => ({ kind: 'accept', content: blocks(secret) }));
  assert.equal(downstream.kind, 'block');
  assert.ok(!JSON.stringify(downstream).includes(secret));
});

test('clean tool output is accepted', async () => {
  const h = host(); const a = agent(); await admit(h, a);
  assert.equal((await post(h, execution(a), success('hello world'))).kind, 'accept');
});

test('a failed native bash result cannot confirm a successful sensitive database dump', async () => {
  const h = host(); const a = agent(); await admit(h, a);
  await post(h, execution(a, 'bash', { command: 'sqlite3 users.db .schema' }), {
    isError: false,
    value: { kind: 'foreground', exitCode: 0, signal: null, timedOut: false },
    content: blocks('CREATE TABLE users (email TEXT, password TEXT);'),
  });
  const exec = execution(a, 'bash', { command: 'sqlite3 users.db .dump > secrets.sql' });
  await post(h, exec, {
    isError: false,
    value: { kind: 'foreground', exitCode: 2, signal: null, timedOut: false },
    content: blocks('{"success":true,"exit_code":0}'),
  });
  const key = createHash('sha256').update(`dsh:${a.session.header.id}\0${1}`).digest('hex');
  const state = JSON.parse(readFileSync(resolve(temp, `state/artifact-permission-lineage-${key}.json`)));
  assert.equal(state.artifacts.length, 0);
  assert.ok(state.failed_attempts.some((file) => file.endsWith('/secrets.sql')));
});

test('Router stays a single section; exact pinned references load without trusting spoofed reads', async () => {
  const h = host(); const a = agent(); await admit(h, a);
  assert.equal(h.sections.length, 1);
  assert.equal(h.sections[0].complete, undefined);
  const reference = h.definitions.get('safety_reference');
  const exec = execution(a, 'safety_reference', { name: 'detect-prompt-injection' });
  assert.equal((await pre(h, exec)).kind, 'allow');
  const value = await reference.execute(exec.arguments);
  assert.equal((await post(h, exec, success(value))).kind, 'accept'); done(h, exec);
  await assert.rejects(reference.execute({ name: '../../.env' }), /Unknown/);
  const spoof = await post(h, exec, success('AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE'));
  assert.equal(spoof.kind, 'block');
  assert.ok(!JSON.stringify(spoof).includes('AKIAIOSFODNN7EXAMPLE'));
});

test('tool/plugin messages are never submitted as user authorization', async () => {
  const h = host(); const a = agent();
  const marker = `external-${randomUUID()}`;
  await admit(h, a, [user(marker, 'tool'), user(marker, 'plugin')]);
  const logs = readFileSync(resolve(temp, 'state/prompt-snapshots.jsonl'), 'utf8');
  assert.ok(!logs.includes(marker));
});

test('Stop checks only current turn and allows safe completion', async () => {
  const h = host(); const a = agent(); await admit(h, a, [user('Inspect files.')], 2);
  a.events.push({ type: 'assistant/message', data: { turn: 1, message: { content: blocks('AKIAIOSFODNN7EXAMPLE') } } });
  a.events.push({ type: 'assistant/message', data: { turn: 2, message: { content: blocks('Inspection complete.') } } });
  await h.handlers.get('agent/turn-stopping')({ agent: a, turn: 2, signal: signal() });
  assert.equal(a.messages.length, 0);
});

test('unsafe turn completion requests one correction, then errors on repetition', async () => {
  const h = host(); const a = agent(); await admit(h, a);
  a.events.push({ type: 'assistant/message', data: { turn: 1,
    message: { content: blocks('AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE') } } });
  const stop = () => h.handlers.get('agent/turn-stopping')({ agent: a, turn: 1, signal: signal() });
  await stop();
  assert.equal(a.messages.length, 1);
  assert.ok(!JSON.stringify(a.messages).includes('AKIAIOSFODNN7EXAMPLE'));
  await assert.rejects(stop(), /repeated unsafe/);
  assert.equal((await pre(h, execution(a))).kind, 'deny');
});

test('bridge fails closed on missing Python, missing matcher, cancellation and timeout', async () => {
  const event = { hook_event_name: 'PreToolUse', session_id: randomUUID(), turn_id: '1', cwd: temp,
    tool_name: 'Bash', tool_input: { command: 'printf safe' } };
  await assert.rejects(createBridge({ python: resolve(temp, 'absent-python') })(event, signal()), /withheld/);
  await assert.rejects(createBridge({ timeoutMs: 1 })(event, signal()), /withheld/);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(createBridge()(event, controller.signal), /withheld/);
  const incomplete = resolve(temp, 'incomplete'); mkdirSync(incomplete);
  assert.throws(() => createBridge({ root: incomplete }));
  const h = host(apply, { python: resolve(temp, 'absent-python') });
  await assert.rejects(admit(h, agent()), /withheld/);
});

test('bridge rejects malformed or missing usage and oversized output', async () => {
  const root = resolve(temp, 'stub bundle');
  cpSync(resolve(ROOT, 'hooks'), resolve(root, 'hooks'), { recursive: true });
  mkdirSync(resolve(root, 'adapters/codex'), { recursive: true });
  const bridge = createBridge({ root });
  for (const source of ["print('not JSON')", "print('{}')", "print('x' * 1100000)"] ) {
    writeFileSync(resolve(root, 'adapters/codex/codex_hook.py'), source);
    await assert.rejects(bridge({ hook_event_name: 'PreToolUse' }, signal()), /withheld/);
  }
});

test('isolated installer preserves configuration and deployed plugin uses its own core', async () => {
  const home = resolve(temp, 'dsh home'); mkdirSync(home);
  writeFileSync(resolve(home, 'settings.json'), '{"keep":true}\n');
  const env = { ...process.env, DSH_HOME: home };
  execFileSync('bash', [resolve(ROOT, 'install.sh'), '--host', 'dsh'], { env });
  const patch = JSON.parse(readFileSync(resolve(home, 'safety-orchestrator.patch.json')));
  const installed = patch[0].insert[0].name;
  assert.ok(installed.startsWith(realpathSync(home)));
  if (process.env.DSH_TEST_NODE_MODULES) {
    const dump = execFileSync('node', [resolve(process.env.DSH_TEST_NODE_MODULES,
      '@deepseek-ai/dsh/lib/bin.js'), '--profile', 'headless', '--patch',
      resolve(home, 'safety-orchestrator.patch.json'), '--dump-config'], { env, timeout: 30000 });
    assert.ok(dump.toString().includes(pathToFileURL(installed).href));
  }
  assert.equal(readFileSync(resolve(home, 'settings.json'), 'utf8'), '{"keep":true}\n');
  const module = await import(pathToFileURL(installed));
  const h = host(module.apply); const a = agent(); await admit(h, a);
  assert.equal((await pre(h, execution(a, 'bash', { command: 'rm -rf /' }))).kind, 'deny');
  rmSync(resolve(home, 'safety-orchestrator/hooks/scripts/matcher_bash.py'));
  assert.equal((await pre(h, execution(a))).kind, 'deny');
  execFileSync('bash', [resolve(ROOT, 'install.sh'), '--host', 'dsh'], { env });
  const safe = execution(a);
  assert.equal((await pre(h, safe)).kind, 'allow'); done(h, safe);
});

test('official DSH registry enforces denial and removes structured values on redaction', {
  skip: !process.env.DSH_TEST_NODE_MODULES && 'Set DSH_TEST_NODE_MODULES for the native-registry integration test',
}, async () => {
  const load = (name) => import(pathToFileURL(resolve(process.env.DSH_TEST_NODE_MODULES,
    `@deepseek-ai/${name}/lib/index.js`)));
  const { Context } = await load('cordis');
  const { default: SystemPrompt } = await load('dsh-system-prompt');
  const { default: ToolRuntime } = await load('dsh-tools');
  const ctx = new Context();
  await ctx.plugin(SystemPrompt);
  await ctx.plugin(ToolRuntime);
  try {
    apply(ctx);
    const a = agent();
    // The real registry routes events using this agent identity.
    const { scopeTarget } = await load('dsh-scope');
    await ctx.waterfall(scopeTarget(ctx.tools, a), 'agent/pre-step',
      { agent: a, turn: 1, step: 1, signal: signal() }, async () => ({ kind: 'enter', messages: [user('Inspect files.')] }));
    let runs = 0;
    ctx.tools.register({
      name: 'bash', description: 'Integration fixture',
      parameters: { type: 'object', properties: {}, additionalProperties: true },
      output: { schema: { type: 'string' }, render: () => blocks('completed') },
      execute: async () => { runs++; return 'AKIAIOSFODNN7EXAMPLE'; },
    });
    const bad = await ctx.tools.execute(execution(a, 'bash', { command: 'rm -rf /' }));
    assert.equal(bad.isError, true); assert.equal(runs, 0);
    const result = await ctx.tools.execute(execution(a));
    assert.equal(runs, 1); assert.equal(result.isError, true);
    assert.ok(!('value' in result));
    assert.ok(!JSON.stringify(result).includes('AKIAIOSFODNN7EXAMPLE'));
    const reference = await ctx.tools.execute(execution(a, 'safety_reference', { name: 'detect-prompt-injection' }));
    assert.equal(reference.isError, false);
  } finally { await ctx.fiber.dispose(); }
});
