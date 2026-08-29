/**
 * Structure analyzer.
 * Detects god files, deep nesting, mixed concerns, and complexity signals.
 * Zero dependencies — pure Node.js.
 */

import { readLines } from '../utils/line-reader.mjs';
import { finding, SEVERITY } from '../utils/severity.mjs';

const ANALYZER = 'structure';

/** Thresholds */
const GOD_FILE_LINES = 500;
const LARGE_FILE_LINES = 300;
const DEEP_NESTING_LEVELS = 4;
const HIGH_IMPORT_COUNT = 10;
const MAX_FUNCTION_LINES = 80;

/**
 * Run the structure analyzer.
 *
 * @param {string} rootDir
 * @param {object[]} files - From fs-walk
 * @param {object} ecosystem - From detect-ecosystem
 * @returns {Promise<{ findings: object[], stats: object }>}
 */
export async function analyzeStructure(rootDir, files, ecosystem) {
  const findings = [];
  const stats = {
    totalFiles: files.length,
    totalLines: 0,
    codeFiles: 0,
    avgFileSize: 0,
    largestFiles: [],
  };

  const codeExtensions = new Set([
    '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
    '.py', '.rb', '.go', '.rs', '.java', '.kt', '.scala',
    '.ex', '.exs', '.php', '.cs', '.swift', '.c', '.cpp',
    '.vue', '.svelte', '.astro',
  ]);

  const fileSizes = []; // { relativePath, lines }

  for (const file of files) {
    if (!codeExtensions.has(file.ext)) continue;

    const result = await readLines(file.absolutePath);
    if (!result) continue;

    stats.codeFiles++;
    stats.totalLines += result.totalLines;

    fileSizes.push({
      relativePath: file.relativePath,
      absolutePath: file.absolutePath,
      lines: result.totalLines,
      ext: file.ext,
    });

    // God files (>500 lines)
    if (result.totalLines > GOD_FILE_LINES) {
      findings.push(finding({
        analyzer: ANALYZER,
        severity: SEVERITY.MEDIUM,
        title: `God file: ${file.relativePath} (${result.totalLines} lines)`,
        description: `This file has ${result.totalLines} lines, well above the ${GOD_FILE_LINES}-line threshold. Large files are harder to test, review, and maintain. Consider splitting into focused modules.`,
        file: file.relativePath,
        remediation: 'Break this file into smaller, focused modules with single responsibilities.',
      }));
    } else if (result.totalLines > LARGE_FILE_LINES) {
      findings.push(finding({
        analyzer: ANALYZER,
        severity: SEVERITY.LOW,
        title: `Large file: ${file.relativePath} (${result.totalLines} lines)`,
        description: `This file has ${result.totalLines} lines. Not critical, but worth watching as it grows.`,
        file: file.relativePath,
        remediation: 'Consider splitting if this file continues to grow.',
      }));
    }

    // Deep nesting detection
    const maxIndent = detectDeepNesting(result.lines, file.ext);
    if (maxIndent > DEEP_NESTING_LEVELS) {
      findings.push(finding({
        analyzer: ANALYZER,
        severity: SEVERITY.LOW,
        title: `Deep nesting in ${file.relativePath} (${maxIndent} levels)`,
        description: `Code is nested ${maxIndent} levels deep. Deep nesting reduces readability. Consider early returns, guard clauses, or extracting functions.`,
        file: file.relativePath,
        remediation: 'Use early returns, guard clauses, or extract nested logic into helper functions.',
      }));
    }

    // High import count
    const importCount = countImports(result.lines, file.ext);
    if (importCount > HIGH_IMPORT_COUNT) {
      findings.push(finding({
        analyzer: ANALYZER,
        severity: SEVERITY.LOW,
        title: `High import count in ${file.relativePath} (${importCount} imports)`,
        description: `This file imports from ${importCount} different modules, suggesting it may have too many responsibilities.`,
        file: file.relativePath,
        remediation: 'Consider if this file is doing too much. Split into smaller modules with fewer dependencies.',
      }));
    }

    // Long functions
    const longFuncs = detectLongFunctions(result.lines, file.ext);
    for (const func of longFuncs) {
      findings.push(finding({
        analyzer: ANALYZER,
        severity: SEVERITY.LOW,
        title: `Long function in ${file.relativePath} (~${func.lines} lines at line ${func.startLine})`,
        description: `A function starting at line ${func.startLine} spans approximately ${func.lines} lines. Long functions are harder to understand and test.`,
        file: file.relativePath,
        line: func.startLine,
        remediation: 'Extract sub-operations into well-named helper functions.',
      }));
    }
  }

  // Compute stats
  stats.avgFileSize = stats.codeFiles > 0
    ? Math.round(stats.totalLines / stats.codeFiles)
    : 0;

  stats.largestFiles = fileSizes
    .sort((a, b) => b.lines - a.lines)
    .slice(0, 10)
    .map(f => ({ file: f.relativePath, lines: f.lines }));

  return { findings, stats };
}

/**
 * Detect maximum nesting depth by counting leading whitespace.
 */
function detectDeepNesting(lines, ext) {
  let maxDepth = 0;
  const indentSize = ext === '.py' ? 4 : 2; // Python uses 4, most others use 2

  for (const line of lines) {
    const trimmed = line.trimStart();
    if (!trimmed || trimmed.startsWith('//') || trimmed.startsWith('#') || trimmed.startsWith('*')) continue;

    const leadingSpaces = line.length - line.trimStart().length;
    // Also count tabs
    const leadingTabs = line.match(/^\t*/)[0].length;
    const depth = leadingTabs > 0 ? leadingTabs : Math.floor(leadingSpaces / indentSize);
    if (depth > maxDepth) maxDepth = depth;
  }

  return maxDepth;
}

/**
 * Count import/require statements.
 */
function countImports(lines, ext) {
  let count = 0;
  for (const line of lines) {
    const trimmed = line.trim();
    if (
      trimmed.startsWith('import ') ||
      trimmed.startsWith('from ') ||
      trimmed.match(/^(const|let|var)\s+.*=\s*require\(/) ||
      trimmed.startsWith('use ') ||       // PHP/Rust
      trimmed.startsWith('using ') ||      // C#
      trimmed.startsWith('require ') ||    // Ruby
      trimmed.startsWith('include ')       // C/C++
    ) {
      count++;
    }
  }
  return count;
}

/**
 * Detect functions longer than MAX_FUNCTION_LINES.
 * Heuristic: looks for function declarations and counts lines until matching brace depth.
 */
function detectLongFunctions(lines, ext) {
  const results = [];
  const funcPattern = /^(?:export\s+)?(?:async\s+)?(?:function\s+\w+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>|\w+\s*=>))|(?:def\s+\w+|(?:pub\s+)?fn\s+\w+)/;

  let inFunction = false;
  let braceDepth = 0;
  let funcStart = 0;

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();

    if (!inFunction && funcPattern.test(trimmed)) {
      inFunction = true;
      funcStart = i + 1; // 1-based
      braceDepth = 0;
    }

    if (inFunction) {
      for (const ch of trimmed) {
        if (ch === '{') braceDepth++;
        if (ch === '}') braceDepth--;
      }

      if (braceDepth <= 0 && i > funcStart - 1) {
        const funcLines = i - funcStart + 2; // inclusive
        if (funcLines > MAX_FUNCTION_LINES) {
          results.push({ startLine: funcStart, lines: funcLines });
        }
        inFunction = false;
      }
    }
  }

  return results;
}
