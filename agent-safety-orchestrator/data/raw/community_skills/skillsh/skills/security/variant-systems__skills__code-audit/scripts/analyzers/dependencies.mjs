/**
 * Dependencies analyzer.
 * Tool-first: uses npm/pnpm/yarn audit, Trivy, OSV-Scanner, and ecosystem-specific auditors.
 * Regex fallback: package.json checks, version pinning, problematic deps.
 * Zero dependencies — pure Node.js.
 */

import { readContent } from '../utils/line-reader.mjs';
import { finding, SEVERITY } from '../utils/severity.mjs';
import { getToolsForCategory, runTool } from '../tools/runner.mjs';
import { deduplicateFindings } from '../tools/dedup.mjs';

const ANALYZER = 'dependencies';

/**
 * Run the dependencies analyzer.
 *
 * @param {string} rootDir
 * @param {object[]} files
 * @param {object} ecosystem
 * @param {object} [opts]
 * @param {Map} [opts.availableTools] - Available tools from discoverTools()
 * @returns {Promise<{ findings: object[], stats: object, toolsMeta: object[] }>}
 */
export async function analyzeDependencies(rootDir, files, ecosystem, opts = {}) {
  const { availableTools } = opts;
  const toolsMeta = [];
  const stats = {
    totalDeps: 0,
    prodDeps: 0,
    devDeps: 0,
    hasLockfile: ecosystem.hasLockfile,
    packageManager: ecosystem.packageManager,
    vulnerabilities: null,
  };

  // Phase 1: Run external tools if available
  const toolFindings = [];
  if (availableTools) {
    const tools = getToolsForCategory(availableTools, ANALYZER, ecosystem?.packageManager);

    for (const toolEntry of tools) {
      const result = await runTool(toolEntry, rootDir, ANALYZER);
      if (result) {
        toolFindings.push(...result.findings);
        toolsMeta.push(result.meta);

        // Extract vulnerability summary from tool meta
        if (result.findings.length > 0 && !stats.vulnerabilities) {
          const vuln = { critical: 0, high: 0, moderate: 0, low: 0 };
          for (const f of result.findings) {
            if (f.severity === SEVERITY.CRITICAL) vuln.critical++;
            else if (f.severity === SEVERITY.HIGH) vuln.high++;
            else if (f.severity === SEVERITY.MEDIUM) vuln.moderate++;
            else vuln.low++;
          }
          stats.vulnerabilities = vuln;
        }
      }
    }
  }

  // Phase 2: Run regex/heuristic analysis
  const regexFindings = [];

  // No lockfile warning
  if (ecosystem.packageJson && !ecosystem.hasLockfile) {
    regexFindings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.HIGH,
      title: 'No lockfile found',
      description: `A package.json exists but no lockfile (package-lock.json, yarn.lock, or pnpm-lock.yaml) was found. Without a lockfile, builds are not reproducible and may install different versions than expected.`,
      remediation: `Run \`${ecosystem.packageManager || 'npm'} install\` to generate a lockfile and commit it to version control.`,
    }));
  }

  // Analyze package.json
  if (ecosystem.packageJson) {
    await analyzePackageJson(rootDir, ecosystem.packageJson, regexFindings, stats);
  }

  // Analyze Python requirements
  const requirementsFile = files.find(f => f.relativePath === 'requirements.txt');
  if (requirementsFile) {
    await analyzePythonDeps(requirementsFile.absolutePath, regexFindings);
  }

  // Analyze mix.exs
  const mixFile = files.find(f => f.relativePath === 'mix.exs');
  if (mixFile) {
    await analyzeElixirDeps(mixFile.absolutePath, regexFindings);
  }

  // Phase 3: Deduplicate
  const findings = deduplicateFindings(toolFindings, regexFindings);

  return { findings, stats, toolsMeta };
}

/**
 * Analyze package.json for common issues.
 */
async function analyzePackageJson(rootDir, pkg, findings, stats) {
  const deps = pkg.dependencies || {};
  const devDeps = pkg.devDependencies || {};
  stats.prodDeps = Object.keys(deps).length;
  stats.devDeps = Object.keys(devDeps).length;
  stats.totalDeps = stats.prodDeps + stats.devDeps;

  // Excessive dependencies
  if (stats.prodDeps > 50) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.MEDIUM,
      title: `High dependency count (${stats.prodDeps} production deps)`,
      description: `This project has ${stats.prodDeps} production dependencies. A large dependency tree increases attack surface, bundle size, and maintenance burden.`,
      remediation: 'Audit dependencies. Remove unused packages. Consider lighter alternatives for heavy dependencies.',
    }));
  }

  // Check for wildcard/latest versions
  const allDeps = { ...deps, ...devDeps };
  for (const [name, version] of Object.entries(allDeps)) {
    if (version === '*' || version === 'latest') {
      findings.push(finding({
        analyzer: ANALYZER,
        severity: SEVERITY.HIGH,
        title: `Unpinned dependency: ${name}@${version}`,
        description: `The dependency "${name}" is set to "${version}". This means any version could be installed, including ones with breaking changes or vulnerabilities.`,
        file: 'package.json',
        remediation: `Pin to a specific version range: \`"${name}": "^x.y.z"\``,
      }));
    }
  }

  // Check for deprecated/risky patterns
  if (pkg.scripts) {
    const scripts = Object.entries(pkg.scripts);
    for (const [name, cmd] of scripts) {
      if (typeof cmd === 'string' && cmd.includes('--no-verify')) {
        findings.push(finding({
          analyzer: ANALYZER,
          severity: SEVERITY.MEDIUM,
          title: `Script "${name}" bypasses git hooks (--no-verify)`,
          description: `The npm script "${name}" uses --no-verify, which skips pre-commit/pre-push hooks. This bypasses quality gates.`,
          file: 'package.json',
          remediation: 'Remove --no-verify from the script. Fix the underlying hook issues instead.',
        }));
      }
    }
  }

  // Missing engines field
  if (!pkg.engines) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.LOW,
      title: 'No engines field in package.json',
      description: 'The package.json does not specify required Node.js version. Different Node versions may behave differently.',
      file: 'package.json',
      remediation: 'Add an "engines" field: `"engines": { "node": ">=18" }`',
    }));
  }

  // Check for known problematic packages
  const problematic = [
    { name: 'moment', message: 'moment.js is in maintenance mode and adds ~300KB. Consider date-fns, dayjs, or Temporal.', severity: SEVERITY.LOW },
    { name: 'lodash', message: 'Full lodash adds ~70KB. Use lodash-es or individual imports.', severity: SEVERITY.LOW },
    { name: 'request', message: 'The "request" package is deprecated. Use fetch(), got, or axios.', severity: SEVERITY.MEDIUM },
    { name: 'node-uuid', message: 'node-uuid is deprecated. Use the built-in crypto.randomUUID() (Node 19+) or the "uuid" package.', severity: SEVERITY.LOW },
  ];

  for (const { name, message, severity } of problematic) {
    if (deps[name] || devDeps[name]) {
      findings.push(finding({
        analyzer: ANALYZER,
        severity,
        title: `Problematic dependency: ${name}`,
        description: message,
        file: 'package.json',
        remediation: `Replace "${name}" with a modern alternative.`,
      }));
    }
  }
}

/**
 * Analyze Python requirements.txt
 */
async function analyzePythonDeps(filePath, findings) {
  const content = await readContent(filePath);
  if (!content) return;

  const lines = content.split('\n').filter(l => l.trim() && !l.startsWith('#'));
  let unpinnedCount = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.includes('==') && !trimmed.includes('>=') && !trimmed.includes('~=')) {
      unpinnedCount++;
    }
  }

  if (unpinnedCount > 0) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.MEDIUM,
      title: `${unpinnedCount} unpinned Python dependencies`,
      description: `${unpinnedCount} dependencies in requirements.txt lack version constraints. Builds may not be reproducible.`,
      file: 'requirements.txt',
      remediation: 'Pin all dependencies to specific versions: `package==x.y.z`',
    }));
  }
}

/**
 * Analyze Elixir mix.exs for basic issues.
 */
async function analyzeElixirDeps(filePath, findings) {
  const content = await readContent(filePath);
  if (!content) return;

  // Check for git dependencies (less reproducible than hex)
  const gitDeps = content.match(/git:\s*["'][^"']+["']/g);
  if (gitDeps && gitDeps.length > 0) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.LOW,
      title: `${gitDeps.length} git-based Elixir dependencies`,
      description: 'Git dependencies are less reproducible than Hex packages. They can change without version bumps.',
      file: 'mix.exs',
      remediation: 'Prefer Hex packages when available. If using git deps, pin to a specific commit SHA.',
    }));
  }
}
