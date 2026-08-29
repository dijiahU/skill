/**
 * Markdown report builder.
 * Assembles all sections into the final CODE_AUDIT_REPORT.md.
 * Zero dependencies — pure Node.js.
 */

import { sortFindings, groupByAnalyzer } from '../utils/severity.mjs';
import {
  projectOverview,
  summaryTable,
  analyzerSection,
  testStatsSection,
  importStatsSection,
  toolsUsedSection,
  manualReviewSections,
  footer,
} from './sections.mjs';

/**
 * Analyzer metadata for section rendering.
 */
const ANALYZER_META = {
  structure: {
    title: 'Code Structure',
    description: 'Analysis of file sizes, nesting depth, import counts, and function length. Identifies complexity hotspots that increase maintenance cost.',
  },
  secrets: {
    title: 'Secrets & Credentials',
    description: 'Scan for hardcoded secrets, API keys, tokens, and credentials. Any finding here should be treated as urgent — rotate exposed credentials immediately.',
  },
  security: {
    title: 'Security',
    description: 'Detection of security anti-patterns including injection risks, XSS vectors, weak cryptography, and misconfigured security controls.',
  },
  dependencies: {
    title: 'Dependencies',
    description: 'Evaluation of dependency health, including version pinning, known vulnerabilities, lockfile presence, and problematic packages.',
  },
  tests: {
    title: 'Testing',
    description: 'Assessment of test coverage, framework configuration, assertion quality, and CI integration.',
  },
  imports: {
    title: 'Import Graph & Coupling',
    description: 'Analysis of the dependency graph between source files. Identifies circular imports, hub files, and coupling hotspots.',
  },
  'ai-patterns': {
    title: 'AI-Generated Code Patterns',
    description: 'Detection of patterns commonly associated with AI-generated code, including tool fingerprints, silent error handling, and structural inconsistencies.',
  },
};

const ANALYZER_ORDER = [
  'secrets',
  'security',
  'dependencies',
  'structure',
  'tests',
  'imports',
  'ai-patterns',
];

/**
 * Generate the full audit report.
 *
 * @param {object} params
 * @param {object[]} params.findings - All findings from all analyzers
 * @param {object} params.ecosystem - Ecosystem detection results
 * @param {object} params.structureStats - From structure analyzer
 * @param {object} params.testStats - From test analyzer
 * @param {object} params.importStats - From imports analyzer
 * @param {object} params.depStats - From dependencies analyzer
 * @param {number} params.durationMs - How long the audit took
 * @param {object[]} [params.toolsUsed] - Metadata from tools that ran
 * @param {object[]} [params.missingTools] - Tools that could be installed
 * @returns {string} Complete markdown report
 */
export function generateReport({
  findings,
  ecosystem,
  structureStats,
  testStats,
  importStats,
  depStats,
  durationMs,
  toolsUsed = [],
  missingTools = [],
}) {
  const sorted = sortFindings(findings);
  const grouped = groupByAnalyzer(sorted);

  let md = '';

  // Header
  md += '# Code Audit Report\n\n';
  md += `> Automated analysis of **${ecosystem.totalFiles}** files`;
  md += ` | **${structureStats.totalLines.toLocaleString()}** lines of code`;
  md += ` | **${sorted.length}** findings`;
  md += ` | ${(durationMs / 1000).toFixed(1)}s\n\n`;

  // Table of contents
  md += '## Table of Contents\n\n';
  md += '- [Project Overview](#project-overview)\n';
  md += '- [Summary](#summary)\n';
  md += '- [Tools Used](#tools-used)\n';
  for (const analyzer of ANALYZER_ORDER) {
    const meta = ANALYZER_META[analyzer];
    if (meta) {
      const anchor = meta.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+$/, '');
      md += `- [${meta.title}](#${anchor})\n`;
    }
  }
  md += '- [What This Audit Doesn\'t Cover](#what-this-audit-doesnt-cover)\n';
  md += '\n';

  // Project overview
  md += projectOverview(ecosystem, structureStats);

  // Summary table
  md += summaryTable(sorted);

  // Tools used section (after summary)
  md += toolsUsedSection(toolsUsed, missingTools);

  // Automated sections (the 70%)
  for (const analyzer of ANALYZER_ORDER) {
    const meta = ANALYZER_META[analyzer];
    if (!meta) continue;

    const sectionFindings = grouped.get(analyzer) || [];
    md += analyzerSection(meta.title, meta.description, sectionFindings);

    // Add stats subsections where available
    if (analyzer === 'tests' && testStats) {
      md += testStatsSection(testStats);
    }
    if (analyzer === 'imports' && importStats) {
      md += importStatsSection(importStats);
    }
  }

  // Manual review sections (the 30% — CTA)
  md += manualReviewSections();

  // Footer
  md += footer();

  return md;
}
