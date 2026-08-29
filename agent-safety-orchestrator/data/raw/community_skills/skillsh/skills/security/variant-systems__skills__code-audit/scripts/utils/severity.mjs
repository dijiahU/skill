/**
 * Severity constants and finding factory.
 * Zero dependencies — pure Node.js.
 */

export const SEVERITY = Object.freeze({
  CRITICAL: 'critical',
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
  INFO: 'info',
});

const SEVERITY_ORDER = {
  [SEVERITY.CRITICAL]: 0,
  [SEVERITY.HIGH]: 1,
  [SEVERITY.MEDIUM]: 2,
  [SEVERITY.LOW]: 3,
  [SEVERITY.INFO]: 4,
};

/**
 * Create a standardized finding object.
 *
 * @param {object} opts
 * @param {string} opts.analyzer   - Which analyzer produced this (e.g. "secrets")
 * @param {string} opts.severity   - One of SEVERITY values
 * @param {string} opts.title      - Short human-readable title
 * @param {string} opts.description - Detailed explanation
 * @param {string} [opts.file]     - Relative file path
 * @param {number} [opts.line]     - Line number (1-based)
 * @param {string} [opts.snippet]  - Code snippet for context
 * @param {string} [opts.remediation] - How to fix it
 * @param {'tool'|'regex'} [opts.source='regex'] - Whether this came from a tool or regex
 * @param {string} [opts.toolId] - Which tool produced this (e.g. "semgrep", "trivy")
 * @returns {object}
 */
export function finding({
  analyzer,
  severity,
  title,
  description,
  file = null,
  line = null,
  snippet = null,
  remediation = null,
  source = 'regex',
  toolId = null,
}) {
  if (!SEVERITY_ORDER.hasOwnProperty(severity)) {
    throw new Error(`Invalid severity: ${severity}`);
  }

  return Object.freeze({
    analyzer,
    severity,
    title,
    description,
    file,
    line,
    snippet,
    remediation,
    source,
    toolId,
  });
}

/**
 * Sort findings by severity (critical first).
 */
export function sortFindings(findings) {
  return [...findings].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
  );
}

/**
 * Count findings by severity.
 * @returns {{ critical: number, high: number, medium: number, low: number, info: number }}
 */
export function countBySeverity(findings) {
  const counts = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  };
  for (const f of findings) {
    counts[f.severity]++;
  }
  return counts;
}

/**
 * Group findings by analyzer name.
 * @returns {Map<string, object[]>}
 */
export function groupByAnalyzer(findings) {
  const map = new Map();
  for (const f of findings) {
    if (!map.has(f.analyzer)) map.set(f.analyzer, []);
    map.get(f.analyzer).push(f);
  }
  return map;
}
