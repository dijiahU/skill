/**
 * Test coverage and quality analyzer.
 * Detects test presence, framework config, assertion quality, test ratio.
 * Zero dependencies — pure Node.js.
 */

import { readLines } from '../utils/line-reader.mjs';
import { readContent } from '../utils/line-reader.mjs';
import { finding, SEVERITY } from '../utils/severity.mjs';
import path from 'node:path';

const ANALYZER = 'tests';

/** Patterns that identify test files. */
const TEST_FILE_PATTERNS = [
  /\.test\.[jt]sx?$/,
  /\.spec\.[jt]sx?$/,
  /_test\.[jt]sx?$/,
  /test_.*\.[jt]sx?$/,
  /\.test\.py$/,
  /test_.*\.py$/,
  /.*_test\.py$/,
  /.*_test\.go$/,
  /.*_test\.rs$/,
  /\.spec\.rb$/,
  /.*Test\.java$/,
  /.*_test\.exs$/,
];

const TEST_DIR_PATTERNS = [
  '__tests__',
  'tests',
  'test',
  'spec',
  'specs',
  '__test__',
];

/** Weak assertion patterns (tests that don't really test anything). */
const WEAK_ASSERTIONS = [
  { pattern: /expect\([^)]+\)\.toBeTruthy\(\)/, name: 'toBeTruthy()' },
  { pattern: /expect\([^)]+\)\.toBeDefined\(\)/, name: 'toBeDefined()' },
  { pattern: /expect\([^)]+\)\.not\.toBeNull\(\)/, name: 'not.toBeNull()' },
  { pattern: /expect\(true\)\.toBe\(true\)/, name: 'expect(true).toBe(true)' },
  { pattern: /assert\.ok\(true\)/, name: 'assert.ok(true)' },
];

/**
 * Run the test analyzer.
 *
 * @param {string} rootDir
 * @param {object[]} files
 * @param {object} ecosystem
 * @returns {Promise<{ findings: object[], stats: object }>}
 */
export async function analyzeTests(rootDir, files, ecosystem) {
  const findings = [];

  // Classify files
  const codeExtensions = new Set([
    '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
    '.py', '.rb', '.go', '.rs', '.java', '.kt',
    '.ex', '.exs', '.php', '.cs',
  ]);

  const testFiles = [];
  const sourceFiles = [];

  for (const file of files) {
    if (!codeExtensions.has(file.ext)) continue;

    const isTest = TEST_FILE_PATTERNS.some(p => p.test(file.relativePath)) ||
                   TEST_DIR_PATTERNS.some(d => file.relativePath.includes(path.sep + d + path.sep) || file.relativePath.startsWith(d + path.sep));

    if (isTest) {
      testFiles.push(file);
    } else {
      sourceFiles.push(file);
    }
  }

  const testRatio = sourceFiles.length > 0
    ? (testFiles.length / sourceFiles.length * 100).toFixed(1)
    : 0;

  const stats = {
    sourceFiles: sourceFiles.length,
    testFiles: testFiles.length,
    testRatio: parseFloat(testRatio),
    testFrameworks: ecosystem.testFrameworks,
  };

  // No tests at all
  if (testFiles.length === 0 && sourceFiles.length > 5) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.HIGH,
      title: 'No test files found',
      description: `The project has ${sourceFiles.length} source files but no test files were detected. Tests are essential for catching regressions and enabling safe refactoring.`,
      remediation: 'Start with integration tests for critical paths, then add unit tests for complex logic.',
    }));
  } else if (stats.testRatio < 20 && sourceFiles.length > 10) {
    // Low test coverage
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.MEDIUM,
      title: `Low test ratio (${testRatio}%)`,
      description: `Only ${testFiles.length} test files for ${sourceFiles.length} source files (${testRatio}% ratio). Aim for at least one test file per module.`,
      remediation: 'Prioritize tests for business-critical code paths and complex logic.',
    }));
  }

  // No test framework configured
  if (ecosystem.testFrameworks.length === 0 && sourceFiles.length > 5) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.MEDIUM,
      title: 'No test framework configured',
      description: 'No test framework was detected in project dependencies or configuration files.',
      remediation: 'Add a test framework. For JS/TS: Vitest or Jest. For Python: pytest. For Elixir: ExUnit (built-in).',
    }));
  }

  // Check for CI test configuration
  const hasCI = files.some(f =>
    f.relativePath.includes('.github/workflows') ||
    f.relativePath === '.gitlab-ci.yml' ||
    f.relativePath === '.circleci/config.yml' ||
    f.relativePath === 'Jenkinsfile' ||
    f.relativePath === 'bitbucket-pipelines.yml'
  );

  if (hasCI) {
    // Check if CI runs tests
    const ciFiles = files.filter(f => f.relativePath.includes('.github/workflows'));
    let ciRunsTests = false;

    for (const ciFile of ciFiles) {
      const content = await readContent(ciFile.absolutePath);
      if (content && /(?:test|jest|vitest|pytest|mix test|cargo test|go test)/i.test(content)) {
        ciRunsTests = true;
        break;
      }
    }

    if (!ciRunsTests && testFiles.length > 0) {
      findings.push(finding({
        analyzer: ANALYZER,
        severity: SEVERITY.MEDIUM,
        title: 'CI does not appear to run tests',
        description: 'CI configuration was found but no test commands were detected. Tests should run automatically on every push.',
        remediation: 'Add a test step to your CI pipeline.',
      }));
    }
  } else if (testFiles.length > 0) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.MEDIUM,
      title: 'No CI/CD configuration found',
      description: 'Tests exist but no CI/CD pipeline was detected. Tests should run automatically.',
      remediation: 'Set up GitHub Actions, GitLab CI, or another CI service to run tests on push.',
    }));
  }

  // Analyze test quality
  let snapshotOnlyCount = 0;
  let weakAssertionFiles = [];
  let emptyTestCount = 0;

  for (const testFile of testFiles) {
    const result = await readLines(testFile.absolutePath);
    if (!result) continue;

    const content = result.lines.join('\n');
    let hasRealAssertion = false;
    let hasSnapshotOnly = false;
    let hasWeakAssertion = false;

    // Check for real assertions
    const assertionPatterns = [
      /expect\([^)]+\)\.(?:toBe|toEqual|toStrictEqual|toMatch|toThrow|toHaveBeenCalled|toContain|toHaveLength)\(/,
      /assert\.\w+\(/,
      /\.should\.\w+/,
      /assert_eq!|assert_ne!/,
      /assertEqual|assertRaises|assertTrue|assertFalse/,
      /assert\s+\w+/,
    ];

    for (const pattern of assertionPatterns) {
      if (pattern.test(content)) {
        hasRealAssertion = true;
        break;
      }
    }

    // Snapshot-only tests
    if (/toMatchSnapshot|toMatchInlineSnapshot/.test(content) && !hasRealAssertion) {
      hasSnapshotOnly = true;
      snapshotOnlyCount++;
    }

    // Weak assertions
    for (const { pattern, name } of WEAK_ASSERTIONS) {
      if (pattern.test(content)) {
        hasWeakAssertion = true;
        weakAssertionFiles.push({ file: testFile.relativePath, pattern: name });
        break;
      }
    }

    // Empty/todo tests
    const emptyTests = content.match(/(?:it|test)\s*\(\s*['"][^'"]+['"]\s*,\s*(?:\(\)\s*=>\s*\{\s*\}|function\s*\(\)\s*\{\s*\})/g);
    if (emptyTests) {
      emptyTestCount += emptyTests.length;
    }
  }

  if (snapshotOnlyCount > 3) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.MEDIUM,
      title: `${snapshotOnlyCount} snapshot-only test files`,
      description: `${snapshotOnlyCount} test files rely solely on snapshot tests with no behavioral assertions. Snapshots catch unexpected changes but don't verify correctness.`,
      remediation: 'Add behavioral assertions alongside snapshots to verify actual expected behavior.',
    }));
  }

  if (weakAssertionFiles.length > 3) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.LOW,
      title: `Weak assertions in ${weakAssertionFiles.length} test files`,
      description: `${weakAssertionFiles.length} test files contain assertions like toBeTruthy() or toBeDefined() that don't verify specific values. These can pass even when behavior is wrong.`,
      remediation: 'Replace weak assertions with specific value checks: toBe(), toEqual(), toMatch().',
    }));
  }

  if (emptyTestCount > 0) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.LOW,
      title: `${emptyTestCount} empty/placeholder tests`,
      description: `Found ${emptyTestCount} test cases with empty bodies. These provide false confidence in test counts.`,
      remediation: 'Implement or remove empty test cases.',
    }));
  }

  return { findings, stats };
}
