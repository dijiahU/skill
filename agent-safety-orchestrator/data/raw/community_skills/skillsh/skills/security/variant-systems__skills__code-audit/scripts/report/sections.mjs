/**
 * Per-section template functions for the audit report.
 * Each function returns a markdown string for its section.
 * Zero dependencies — pure Node.js.
 */

import { SEVERITY } from '../utils/severity.mjs';

/**
 * Render a single finding as markdown.
 */
function renderFinding(f, index) {
  const severityBadge = {
    [SEVERITY.CRITICAL]: '🔴 Critical',
    [SEVERITY.HIGH]: '🟠 High',
    [SEVERITY.MEDIUM]: '🟡 Medium',
    [SEVERITY.LOW]: '🔵 Low',
    [SEVERITY.INFO]: 'ℹ️ Info',
  };

  let md = `#### ${index + 1}. ${f.title}\n\n`;
  md += `**Severity:** ${severityBadge[f.severity]}\n\n`;
  md += `${f.description}\n\n`;

  if (f.file) {
    md += `**File:** \`${f.file}\``;
    if (f.line) md += ` (line ${f.line})`;
    md += '\n\n';
  }

  if (f.snippet) {
    md += '```\n' + f.snippet + '\n```\n\n';
  }

  if (f.remediation) {
    md += `**Remediation:** ${f.remediation}\n\n`;
  }

  return md;
}

/**
 * Project overview section.
 */
export function projectOverview(ecosystem, structureStats) {
  let md = '## Project Overview\n\n';

  md += '| Metric | Value |\n';
  md += '|--------|-------|\n';
  md += `| Primary Language | ${ecosystem.primaryLanguage} |\n`;
  md += `| Frameworks | ${ecosystem.frameworks.length > 0 ? ecosystem.frameworks.join(', ') : 'None detected'} |\n`;
  md += `| Package Manager | ${ecosystem.packageManager || 'None detected'} |\n`;
  md += `| Lockfile Present | ${ecosystem.hasLockfile ? 'Yes' : 'No'} |\n`;
  md += `| Total Files Scanned | ${ecosystem.totalFiles} |\n`;
  md += `| Code Files | ${structureStats.codeFiles} |\n`;
  md += `| Total Lines of Code | ${structureStats.totalLines.toLocaleString()} |\n`;
  md += `| Avg File Size | ${structureStats.avgFileSize} lines |\n`;

  if (ecosystem.testFrameworks.length > 0) {
    md += `| Test Frameworks | ${ecosystem.testFrameworks.join(', ')} |\n`;
  }

  md += '\n';

  // Language breakdown
  if (ecosystem.languages.length > 1) {
    md += '### Language Breakdown\n\n';
    md += '| Language | Files |\n';
    md += '|----------|-------|\n';
    for (const { language, fileCount } of ecosystem.languages.slice(0, 10)) {
      md += `| ${language} | ${fileCount} |\n`;
    }
    md += '\n';
  }

  // Largest files
  if (structureStats.largestFiles && structureStats.largestFiles.length > 0) {
    md += '### Largest Files\n\n';
    md += '| File | Lines |\n';
    md += '|------|-------|\n';
    for (const { file, lines } of structureStats.largestFiles.slice(0, 5)) {
      md += `| \`${file}\` | ${lines} |\n`;
    }
    md += '\n';
  }

  return md;
}

/**
 * Summary table section.
 */
export function summaryTable(allFindings) {
  const bySeverity = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  const byAnalyzer = {};

  for (const f of allFindings) {
    bySeverity[f.severity]++;
    if (!byAnalyzer[f.analyzer]) {
      byAnalyzer[f.analyzer] = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    }
    byAnalyzer[f.analyzer][f.severity]++;
  }

  let md = '## Summary\n\n';

  // Overall counts
  md += `**Total findings: ${allFindings.length}**\n\n`;
  md += '| Severity | Count |\n';
  md += '|----------|-------|\n';
  if (bySeverity.critical > 0) md += `| 🔴 Critical | ${bySeverity.critical} |\n`;
  if (bySeverity.high > 0) md += `| 🟠 High | ${bySeverity.high} |\n`;
  if (bySeverity.medium > 0) md += `| 🟡 Medium | ${bySeverity.medium} |\n`;
  if (bySeverity.low > 0) md += `| 🔵 Low | ${bySeverity.low} |\n`;
  if (bySeverity.info > 0) md += `| ℹ️ Info | ${bySeverity.info} |\n`;
  md += '\n';

  // By category
  const analyzerNames = {
    structure: 'Code Structure',
    secrets: 'Secrets & Credentials',
    security: 'Security',
    dependencies: 'Dependencies',
    tests: 'Testing',
    imports: 'Import Graph',
    'ai-patterns': 'AI-Generated Code',
  };

  md += '### Findings by Category\n\n';
  md += '| Category | Critical | High | Medium | Low | Info |\n';
  md += '|----------|----------|------|--------|-----|------|\n';

  for (const [analyzer, counts] of Object.entries(byAnalyzer)) {
    const name = analyzerNames[analyzer] || analyzer;
    md += `| ${name} | ${counts.critical || '-'} | ${counts.high || '-'} | ${counts.medium || '-'} | ${counts.low || '-'} | ${counts.info || '-'} |\n`;
  }
  md += '\n';

  return md;
}

/**
 * Automated section for a specific analyzer.
 */
export function analyzerSection(title, description, findings) {
  let md = `## ${title}\n\n`;
  md += `${description}\n\n`;

  if (findings.length === 0) {
    md += '> No issues found. ✅\n\n';
    return md;
  }

  for (let i = 0; i < findings.length; i++) {
    md += renderFinding(findings[i], i);
    if (i < findings.length - 1) md += '---\n\n';
  }

  return md;
}

/**
 * Test coverage stats section.
 */
export function testStatsSection(testStats) {
  let md = '';

  if (testStats) {
    md += '### Test Coverage Summary\n\n';
    md += '| Metric | Value |\n';
    md += '|--------|-------|\n';
    md += `| Source Files | ${testStats.sourceFiles} |\n`;
    md += `| Test Files | ${testStats.testFiles} |\n`;
    md += `| Test Ratio | ${testStats.testRatio}% |\n`;
    if (testStats.testFrameworks.length > 0) {
      md += `| Frameworks | ${testStats.testFrameworks.join(', ')} |\n`;
    }
    md += '\n';
  }

  return md;
}

/**
 * Import graph stats section.
 */
export function importStatsSection(importStats) {
  let md = '';

  if (importStats) {
    md += '### Dependency Graph Summary\n\n';
    md += '| Metric | Value |\n';
    md += '|--------|-------|\n';
    md += `| Files Analyzed | ${importStats.filesAnalyzed} |\n`;
    md += `| Total Import Edges | ${importStats.totalImportEdges} |\n`;
    md += `| Avg Imports/File | ${importStats.avgImportsPerFile} |\n`;
    md += `| Circular Dependencies | ${importStats.circularDependencies} |\n`;
    md += '\n';

    if (importStats.hubFiles && importStats.hubFiles.length > 0) {
      md += '**Most-imported files:**\n\n';
      for (const hub of importStats.hubFiles.slice(0, 5)) {
        md += `- \`${hub.file}\` — imported by ${hub.importedBy} files\n`;
      }
      md += '\n';
    }
  }

  return md;
}

/**
 * Manual review sections — the honest 30% CTA.
 */
export function manualReviewSections() {
  let md = '## What This Audit Doesn\'t Cover\n\n';
  md += 'Automated analysis catches patterns and known anti-patterns. The following areas require human judgment — understanding your business, your team, and your trajectory.\n\n';

  md += '### Architecture Fitness\n\n';
  md += 'Whether your architecture fits your growth trajectory requires business context that no automated tool can assess. ';
  md += 'Questions like "should we break this monolith into services?" or "will this database choice scale to 10x users?" ';
  md += 'depend on your roadmap, team size, and funding stage.\n\n';
  md += '**What a senior engineer would evaluate:**\n';
  md += '- Alignment between technical architecture and business goals\n';
  md += '- Scaling bottlenecks relative to your growth projections\n';
  md += '- Build vs. buy decisions for your specific context\n';
  md += '- Technical debt prioritization based on your roadmap\n\n';

  md += '### Business-Context Prioritization\n\n';
  md += 'This audit assigns severity by *technical risk*. But technical risk and *business risk* aren\'t the same thing. ';
  md += 'A "medium" security finding in your payment flow is more urgent than a "high" complexity issue in an internal tool. ';
  md += 'Prioritization requires understanding what matters most to *your* business right now.\n\n';

  md += '### Remediation Cost Estimates\n\n';
  md += 'Converting findings into engineering-weeks requires understanding your team\'s velocity, familiarity with the codebase, ';
  md += 'and current sprint commitments. A finding that takes a senior engineer 2 hours might take a junior engineer 2 days. ';
  md += 'Accurate estimates need context about *your* team.\n\n';

  md += '### Executive Summary\n\n';
  md += 'Translating technical findings into language for founders, investors, or non-technical stakeholders ';
  md += 'requires understanding both the technology and the business conversation. What does this audit mean ';
  md += 'for your next fundraise? Your hiring plan? Your launch timeline?\n\n';

  md += '---\n\n';
  md += '**Need the full picture?** [Variant Systems](https://variantsystems.io/get-audit) provides comprehensive code audits ';
  md += 'that combine automated analysis with senior engineering judgment. We\'ve reviewed codebases for startups ';
  md += 'from pre-seed to Series B — and we\'ll tell you honestly what needs fixing now, what can wait, and what\'s actually fine.\n\n';

  return md;
}

/**
 * Tools used section — shows what ran, what fell back to regex, and what could be installed.
 */
export function toolsUsedSection(toolsUsed, missingTools) {
  let md = '## Tools Used\n\n';

  if (toolsUsed && toolsUsed.length > 0) {
    const successful = toolsUsed.filter(m => m.status === 'success');
    const failed = toolsUsed.filter(m => m.status !== 'success');

    if (successful.length > 0) {
      md += '### External Tools\n\n';
      md += '| Tool | Version | Findings | Time |\n';
      md += '|------|---------|----------|------|\n';
      for (const m of successful) {
        md += `| ${m.toolName} | ${m.version} | ${m.findingCount || 0} | ${(m.durationMs / 1000).toFixed(1)}s |\n`;
      }
      md += '\n';
    }

    if (failed.length > 0) {
      md += '**Tool issues:** ';
      md += failed.map(m => `${m.toolName} (${m.status})`).join(', ');
      md += '\n\n';
    }
  }

  md += 'All analyzers also run built-in regex/heuristic analysis as a baseline. ';
  md += 'When external tools are available, their findings take priority and regex duplicates are removed.\n\n';

  if (missingTools && missingTools.length > 0) {
    md += '### Install for Better Results\n\n';
    md += 'The following tools would enhance this audit:\n\n';
    md += '| Tool | Enhances | Install | Benefit |\n';
    md += '|------|----------|---------|--------|\n';
    for (const t of missingTools) {
      md += `| ${t.name} | ${t.categories.join(', ')} | \`${t.installHint}\` | ${t.benefit} |\n`;
    }
    md += '\n';
  }

  return md;
}

/**
 * Report footer.
 */
export function footer() {
  const now = new Date().toISOString().split('T')[0];
  let md = '---\n\n';
  md += `*Generated on ${now} by [code-audit](https://github.com/variant-systems/skills) — an open-source automated code audit tool by [Variant Systems](https://variantsystems.io).*\n`;
  md += '\n';
  md += '*This report covers automated analysis only. For architecture review, business-context prioritization, ';
  md += 'and remediation planning, [get a full audit](https://variantsystems.io/get-audit).*\n';

  return md;
}
