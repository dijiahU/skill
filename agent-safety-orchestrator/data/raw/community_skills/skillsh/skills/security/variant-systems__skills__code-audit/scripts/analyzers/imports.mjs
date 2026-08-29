/**
 * Import/dependency graph analyzer.
 * Tool-first: uses Madge for circular dependency detection when available.
 * Regex fallback: DFS cycle detection on adjacency graph + coupling analysis.
 * Zero dependencies — pure Node.js.
 */

import { readLines } from '../utils/line-reader.mjs';
import { finding, SEVERITY } from '../utils/severity.mjs';
import { getToolsForCategory, runTool } from '../tools/runner.mjs';
import { deduplicateFindings } from '../tools/dedup.mjs';
import path from 'node:path';

const ANALYZER = 'imports';

const CODE_EXTENSIONS = new Set([
  '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
  '.py', '.ex', '.exs',
]);

/**
 * Run the imports analyzer.
 *
 * @param {string} rootDir
 * @param {object[]} files
 * @param {object} [opts]
 * @param {Map} [opts.availableTools] - Available tools from discoverTools()
 * @param {object} [opts.ecosystem] - Ecosystem detection results
 * @returns {Promise<{ findings: object[], stats: object, toolsMeta: object[] }>}
 */
export async function analyzeImports(rootDir, files, opts = {}) {
  const { availableTools, ecosystem } = opts;
  const toolsMeta = [];
  const codeFiles = files.filter(f => CODE_EXTENSIONS.has(f.ext));

  // Phase 1: Run external tools if available
  const toolFindings = [];
  if (availableTools) {
    const tools = getToolsForCategory(availableTools, ANALYZER, ecosystem?.packageManager);

    for (const toolEntry of tools) {
      const result = await runTool(toolEntry, rootDir, ANALYZER);
      if (result) {
        toolFindings.push(...result.findings);
        toolsMeta.push(result.meta);
      }
    }
  }

  // Phase 2: Run regex/graph analysis (always — needed for stats + hub detection)
  const { findings: regexFindings, stats } = await graphAnalysis(rootDir, codeFiles);

  // Phase 3: Deduplicate circular dependency findings
  const findings = deduplicateFindings(toolFindings, regexFindings);

  return { findings, stats, toolsMeta };
}

/**
 * Original graph-based import analysis.
 */
async function graphAnalysis(rootDir, codeFiles) {
  const findings = [];

  // Build adjacency graph: file -> [files it imports]
  const graph = new Map();  // relativePath -> Set<relativePath>
  const inDegree = new Map(); // how many files import this file
  const outDegree = new Map(); // how many files this file imports

  for (const file of codeFiles) {
    const result = await readLines(file.absolutePath);
    if (!result) continue;

    const imports = extractImports(result.lines, file.ext, file.relativePath, rootDir);
    const resolvedImports = new Set();

    for (const imp of imports) {
      // Try to resolve relative import to an actual file
      const resolved = resolveImport(imp, file.relativePath, codeFiles);
      if (resolved) {
        resolvedImports.add(resolved);
      }
    }

    graph.set(file.relativePath, resolvedImports);
    outDegree.set(file.relativePath, resolvedImports.size);

    for (const dep of resolvedImports) {
      inDegree.set(dep, (inDegree.get(dep) || 0) + 1);
    }
  }

  // Detect circular imports via DFS
  const cycles = detectCycles(graph);

  for (const cycle of cycles) {
    const cycleStr = cycle.join(' → ');
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.MEDIUM,
      title: `Circular import detected (${cycle.length} files)`,
      description: `Circular dependency chain: ${cycleStr}. Circular imports can cause initialization issues, make testing difficult, and indicate tight coupling.`,
      file: cycle[0],
      remediation: 'Break the cycle by extracting shared code into a separate module, or use dependency injection.',
    }));
  }

  // Detect hub files (imported by many files)
  const hubThreshold = Math.max(10, codeFiles.length * 0.15);
  const hubs = [];
  for (const [file, count] of inDegree.entries()) {
    if (count >= hubThreshold) {
      hubs.push({ file, importedBy: count });
    }
  }

  hubs.sort((a, b) => b.importedBy - a.importedBy);

  for (const hub of hubs.slice(0, 5)) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.LOW,
      title: `Hub file: ${hub.file} (imported by ${hub.importedBy} files)`,
      description: `This file is imported by ${hub.importedBy} other files, making it a central coupling point. Changes here have a wide blast radius.`,
      file: hub.file,
      remediation: 'Consider if this module has too many responsibilities. Split into focused sub-modules if possible.',
    }));
  }

  // Coupling score
  const totalEdges = Array.from(outDegree.values()).reduce((sum, n) => sum + n, 0);
  const avgCoupling = codeFiles.length > 0
    ? (totalEdges / codeFiles.length).toFixed(1)
    : 0;

  const stats = {
    filesAnalyzed: codeFiles.length,
    totalImportEdges: totalEdges,
    avgImportsPerFile: parseFloat(avgCoupling),
    circularDependencies: cycles.length,
    hubFiles: hubs.map(h => ({ file: h.file, importedBy: h.importedBy })),
  };

  if (cycles.length > 5) {
    findings.push(finding({
      analyzer: ANALYZER,
      severity: SEVERITY.HIGH,
      title: `${cycles.length} circular dependency chains detected`,
      description: `The project has ${cycles.length} circular import chains. This level of circular dependency suggests the module architecture needs restructuring.`,
      remediation: 'Conduct a dependency audit. Introduce clear module boundaries and uni-directional data flow.',
    }));
  }

  return { findings, stats };
}

/**
 * Extract import paths from source lines.
 * Returns relative import paths (not package imports).
 */
function extractImports(lines, ext, filePath, rootDir) {
  const imports = [];

  for (const line of lines) {
    const trimmed = line.trim();

    // JS/TS: import ... from '...'
    const esImport = trimmed.match(/(?:import|export)\s+.*?from\s+['"]([^'"]+)['"]/);
    if (esImport && esImport[1].startsWith('.')) {
      imports.push(esImport[1]);
      continue;
    }

    // JS/TS: require('...')
    const cjsImport = trimmed.match(/require\s*\(\s*['"]([^'"]+)['"]\s*\)/);
    if (cjsImport && cjsImport[1].startsWith('.')) {
      imports.push(cjsImport[1]);
      continue;
    }

    // JS/TS: dynamic import('...')
    const dynamicImport = trimmed.match(/import\s*\(\s*['"]([^'"]+)['"]\s*\)/);
    if (dynamicImport && dynamicImport[1].startsWith('.')) {
      imports.push(dynamicImport[1]);
      continue;
    }

    // Python: from .module import ...
    const pyRelative = trimmed.match(/from\s+(\.+\w*)\s+import/);
    if (pyRelative) {
      imports.push(pyRelative[1]);
      continue;
    }

    // Elixir: alias MyApp.Module
    const exAlias = trimmed.match(/alias\s+(\w+(?:\.\w+)+)/);
    if (exAlias) {
      imports.push(exAlias[1]);
    }
  }

  return imports;
}

/**
 * Resolve a relative import to a file in the project.
 */
function resolveImport(importPath, fromFile, allFiles) {
  const fromDir = path.dirname(fromFile);
  let resolved = path.join(fromDir, importPath);

  // Normalize path separators
  resolved = resolved.split(path.sep).join('/');

  // Try exact match
  const exact = allFiles.find(f => f.relativePath === resolved);
  if (exact) return exact.relativePath;

  // Try with extensions
  const extensions = ['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx', '.py', '.ex', '.exs'];
  for (const ext of extensions) {
    const withExt = resolved + ext;
    const match = allFiles.find(f => f.relativePath === withExt);
    if (match) return match.relativePath;
  }

  // Try index files
  for (const ext of extensions) {
    const indexPath = resolved + '/index' + ext;
    const match = allFiles.find(f => f.relativePath === indexPath);
    if (match) return match.relativePath;
  }

  return null;
}

/**
 * Detect cycles in a directed graph using DFS.
 * Returns array of cycles, each cycle is an array of node names.
 */
function detectCycles(graph) {
  const visited = new Set();
  const inStack = new Set();
  const cycles = [];
  const stackPath = [];

  function dfs(node) {
    if (inStack.has(node)) {
      // Found a cycle — extract it
      const cycleStart = stackPath.indexOf(node);
      if (cycleStart !== -1) {
        const cycle = stackPath.slice(cycleStart);
        cycle.push(node); // Close the loop
        cycles.push(cycle);
      }
      return;
    }

    if (visited.has(node)) return;

    visited.add(node);
    inStack.add(node);
    stackPath.push(node);

    const neighbors = graph.get(node) || new Set();
    for (const neighbor of neighbors) {
      dfs(neighbor);
    }

    stackPath.pop();
    inStack.delete(node);
  }

  for (const node of graph.keys()) {
    if (!visited.has(node)) {
      dfs(node);
    }
  }

  // Deduplicate cycles (same cycle can be detected from different starting nodes)
  const seen = new Set();
  return cycles.filter(cycle => {
    const key = [...cycle].sort().join('|');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
