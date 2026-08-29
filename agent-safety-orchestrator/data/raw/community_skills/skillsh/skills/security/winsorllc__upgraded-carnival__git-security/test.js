#!/usr/bin/env node
/**
 * Git Security Test Suite
 */

const { scanFile, secretPatterns, shouldScanFile } = require('./scan.js');

function runTest(name, fn) {
  console.log(`\n▶ ${name}`);
  try {
    fn();
    console.log('✓ PASSED');
    return true;
  } catch (err) {
    console.error('✗ FAILED:', err.message);
    return false;
  }
}

function assertEqual(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg}: expected "${expected}", got "${actual}"`);
  }
}

function assertArrayLength(arr, min, msg) {
  if (arr.length < min) {
    throw new Error(`${msg}: expected at least ${min} items, got ${arr.length}`);
  }
}

function assertTrue(value, msg) {
  if (!value) {
    throw new Error(`${msg}: expected true, got ${value}`);
  }
}

let passed = 0;
let failed = 0;

// Test 1: Secret patterns defined
if (runTest('Secret patterns defined', () => {
  assertArrayLength(secretPatterns, 5, 'should have at least 5 patterns');
  assertTrue(secretPatterns.every(p => p.name && p.pattern && p.severity), 'patterns have required fields');
})) passed++; else failed++;

// Test 2: Detect OpenAI key
if (runTest('Detect OpenAI key', () => {
  const testContent = 'const apiKey = "sk-abc123xyz789def456ghi012";\nconsole.log(apiKey);';
  const findings = scanFile('test.js', testContent);
  assertTrue(findings.some(f => f.pattern === 'OpenAI API Key'), 'should detect OpenAI key');
})) passed++; else failed++;

// Test 3: Detect private key
if (runTest('Detect private key', () => {
  const testContent = '-----BEGIN RSA PRIVATE KEY-----\nabc123\n-----END RSA PRIVATE KEY-----';
  const findings = scanFile('test.js', testContent);
  assertTrue(findings.some(f => f.pattern === 'Private Key'), 'should detect private key');
})) passed++; else failed++;

// Test 4: Ignore safe patterns
if (runTest('Ignore safe patterns', () => {
  const testContent = 'const apiKey = "your-api-key-here";\nconst secret = "****";';
  const findings = scanFile('test.js', testContent);
  assertEqual(findings.length, 0, 'should ignore placeholder values');
})) passed++; else failed++;

// Test 5: Should scan file filtering
if (runTest('Should scan file filtering', () => {
  assertEqual(shouldScanFile('src/app.js'), true, 'should scan .js files');
  assertEqual(shouldScanFile('.git/config'), false, 'should skip .git files');
  assertEqual(shouldScanFile('node_modules/magic/index.js'), false, 'should skip node_modules');
  assertEqual(shouldScanFile('test.js'), false, 'should skip test.js');
})) passed++; else failed++;

// Test 6: Detect database URL
if (runTest('Detect database URL', () => {
  const testContent = 'DATABASE_URL=postgres://user:password123@localhost/db';
  const findings = scanFile('.env', testContent);
  assertTrue(findings.some(f => f.pattern === 'Database URL'), 'should detect database URL');
})) passed++; else failed++;

// Test 7: Line number detection
if (runTest('Line number detection', () => {
  const testContent = 'line1\nline2\nconst key = "sk-abc123xyz789def456ghi012";\nline4';
  const findings = scanFile('test.js', testContent);
  assertTrue(findings.length > 0, 'should find secret');
  assertEqual(findings[0].line, 3, 'should report correct line number');
})) passed++; else failed++;

console.log('\n' + '='.repeat(50));
console.log(`Test Results: ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

process.exit(failed > 0 ? 1 : 0);
