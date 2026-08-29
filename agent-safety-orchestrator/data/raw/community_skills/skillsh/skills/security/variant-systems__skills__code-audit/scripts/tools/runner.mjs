/**
 * Tool runner — discovers installed tools and executes them.
 * Handles detection, execution, timeout, and output parsing.
 * Zero dependencies — pure Node.js.
 */

import { execFile } from 'node:child_process';
import { TOOL_REGISTRY } from './registry.mjs';
import { PARSERS } from './parsers.mjs';

/**
 * Run a command and return { stdout, exitCode }.
 * Resolves even on non-zero exit (many tools exit non-zero when findings exist).
 */
function exec(command, args, opts = {}) {
  return new Promise((resolve) => {
    execFile(command, args, {
      timeout: opts.timeout || 30_000,
      maxBuffer: 10_000_000,
      cwd: opts.cwd || process.cwd(),
      env: { ...process.env, ...opts.env },
    }, (error, stdout, stderr) => {
      resolve({
        stdout: stdout || '',
        stderr: stderr || '',
        exitCode: error?.code ?? 0,
        timedOut: error?.killed || false,
      });
    });
  });
}

/**
 * Discover which tools are installed.
 * Runs all detect commands in parallel.
 *
 * @returns {Promise<Map<string, { tool: object, version: string }>>}
 *   Map from tool id to { tool descriptor, detected version string }
 */
export async function discoverTools() {
  const results = await Promise.allSettled(
    TOOL_REGISTRY.map(async (tool) => {
      const [cmd, args] = tool.detect;
      const result = await exec(cmd, args, { timeout: 10_000 });

      if (result.timedOut) return null;

      // Most --version commands output to stdout, some to stderr
      const output = (result.stdout || result.stderr || '').trim();
      // Extract version-like string
      const versionMatch = output.match(/(\d+\.\d+[\.\d]*)/);
      const version = versionMatch ? versionMatch[1] : 'unknown';

      // Consider the tool available if the command didn't completely fail
      // (many tools exit 0 on --version, but some detection commands may exit non-zero)
      if (result.stdout || result.stderr) {
        return { id: tool.id, tool, version };
      }

      return null;
    })
  );

  const available = new Map();
  for (const result of results) {
    if (result.status === 'fulfilled' && result.value) {
      available.set(result.value.id, result.value);
    }
  }

  return available;
}

/**
 * Get tools relevant to a specific analyzer category + ecosystem.
 *
 * @param {Map} available - Map from discoverTools()
 * @param {string} category - 'secrets', 'security', 'dependencies', 'imports'
 * @param {string|null} packageManager - e.g. 'npm', 'pnpm', 'yarn'
 * @returns {object[]} Array of { tool, version } for tools matching category + ecosystem
 */
export function getToolsForCategory(available, category, packageManager) {
  const matching = [];

  for (const [, entry] of available) {
    const tool = entry.tool;

    // Must match category
    if (!tool.categories.includes(category)) continue;

    // If tool has ecosystem restrictions, check them
    if (tool.ecosystems) {
      if (!packageManager || !tool.ecosystems.includes(packageManager)) continue;
    }

    matching.push(entry);
  }

  return matching;
}

/**
 * Run a single tool against a directory.
 *
 * @param {object} toolEntry - { tool, version } from discoverTools()
 * @param {string} rootDir - Target directory to scan
 * @param {string} analyzer - Which analyzer is calling ('secrets', 'security', etc.)
 * @returns {Promise<{ findings: object[], meta: object } | null>}
 */
export async function runTool(toolEntry, rootDir, analyzer) {
  const { tool, version } = toolEntry;

  // Determine command: use category override if available
  let [cmd, args] = tool.run.categoryOverrides?.[analyzer] || tool.run.command;
  args = [...args]; // clone to avoid mutation

  const startTime = Date.now();
  const result = await exec(cmd, args, {
    cwd: rootDir,
    timeout: tool.timeout || 60_000,
  });

  const durationMs = Date.now() - startTime;

  if (result.timedOut) {
    return {
      findings: [],
      meta: {
        toolId: tool.id,
        toolName: tool.name,
        version,
        status: 'timeout',
        durationMs,
      },
    };
  }

  // Many tools output to stdout even on non-zero exit (findings = non-zero)
  const output = result.stdout || '';
  if (!output.trim()) {
    return {
      findings: [],
      meta: {
        toolId: tool.id,
        toolName: tool.name,
        version,
        status: output ? 'empty' : 'no-output',
        durationMs,
      },
    };
  }

  // Parse the output
  const parser = PARSERS[tool.parserId];
  if (!parser) {
    return {
      findings: [],
      meta: {
        toolId: tool.id,
        toolName: tool.name,
        version,
        status: 'no-parser',
        durationMs,
      },
    };
  }

  const findings = parser(output, analyzer, tool.id);

  return {
    findings,
    meta: {
      toolId: tool.id,
      toolName: tool.name,
      version,
      status: 'success',
      findingCount: findings.length,
      durationMs,
    },
  };
}

/**
 * Get list of tools that aren't installed but would enhance the audit.
 *
 * @param {Map} available - Map from discoverTools()
 * @param {string|null} packageManager - e.g. 'npm', 'pnpm'
 * @returns {object[]} Array of { id, name, categories, installHint, benefit }
 */
export function getMissingTools(available, packageManager) {
  const missing = [];

  for (const tool of TOOL_REGISTRY) {
    if (available.has(tool.id)) continue;

    // Skip ecosystem-specific tools that don't apply
    if (tool.ecosystems && (!packageManager || !tool.ecosystems.includes(packageManager))) continue;

    missing.push({
      id: tool.id,
      name: tool.name,
      categories: tool.categories,
      installHint: tool.installHint,
      benefit: tool.benefit,
    });
  }

  return missing;
}
