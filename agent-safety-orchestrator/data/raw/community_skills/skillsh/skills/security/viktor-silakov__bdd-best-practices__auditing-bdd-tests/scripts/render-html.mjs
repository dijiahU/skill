#!/usr/bin/env node

import { readFileSync, writeFileSync } from 'node:fs';

function usage() {
  console.log(`
render-html.mjs

Renders a standalone HTML report from JSON using templates/report.html.

Usage:
  node scripts/render-html.mjs <input.json> <output.html> [template.html]
`);
}

function replaceAll(template, replacements) {
  let html = template;
  for (const [key, value] of Object.entries(replacements)) {
    html = html.split(`{${key}}`).join(String(value));
  }
  return html;
}

function severityClass(sev) {
  if (sev === 'critical') return 'sev-critical';
  if (sev === 'warning') return 'sev-warning';
  return 'sev-info';
}

function buildAspectItems(aspects) {
  return (aspects || [])
    .map((a, index) => {
      const name = a?.name ?? `Aspect ${index + 1}`;
      const score = Number.isFinite(a?.score) ? a.score : 0;
      const safeScore = Math.max(0, Math.min(100, Math.round(score)));
      return `
<div class="aspect-item">
  <div class="aspect-header">
    <span class="aspect-name">${index + 1}. ${name}</span>
    <span class="aspect-score">${safeScore}/100</span>
  </div>
  <div class="progress"><div style="width: ${safeScore}%"></div></div>
</div>`.trim();
    })
    .join('\n');
}

function buildIssueRows(issues) {
  return (issues || [])
    .map((i) => {
      const id = i?.id ?? 'N/A';
      const sev = (i?.severity ?? 'info').toLowerCase();
      const aspect = i?.aspect ?? '';
      const issue = i?.issue ?? '';
      const effort = i?.effort ?? '';
      const sevCls = severityClass(sev);
      return `
<tr data-sev="${sev}">
  <td><code>${id}</code></td>
  <td class="${sevCls}">${sev.toUpperCase()}</td>
  <td>${aspect}</td>
  <td>${issue}</td>
  <td>${effort}</td>
</tr>`.trim();
    })
    .join('\n');
}

function computeCounts(issues) {
  const counts = { critical: 0, warning: 0, info: 0 };
  for (const i of issues || []) {
    const sev = (i?.severity ?? 'info').toLowerCase();
    if (sev === 'critical') counts.critical += 1;
    else if (sev === 'warning') counts.warning += 1;
    else counts.info += 1;
  }
  return counts;
}

function main() {
  const args = process.argv.slice(2);
  const inputPath = args[0];
  const outputPath = args[1];
  const templatePath = args[2] || 'templates/report.html';

  if (!inputPath || !outputPath) {
    usage();
    process.exit(2);
  }

  const data = JSON.parse(readFileSync(inputPath, 'utf-8'));
  const template = readFileSync(templatePath, 'utf-8');

  const issues = data.issues || [];
  const computedCounts = computeCounts(issues);
  const issueCounts = data.issue_counts || {};

  const replacements = {
    REPO_NAME: data.repo_name ?? '',
    BRANCH: data.branch ?? '',
    COMMIT_HASH: data.commit_hash ?? '',
    DATE: data.date ?? '',
    REPORT_ID: data.report_id ?? '',
    VERSION: data.version ?? '',

    GRADE: data.overall?.grade ?? '',
    DELTA_DIR: data.overall?.delta_dir ?? 'same',
    DELTA: data.overall?.delta ?? '',
    SCORE: Number.isFinite(data.overall?.score) ? String(Math.round(data.overall.score)) : '0',
    SCORE_DELTA: data.overall?.score_delta ?? '',

    CRITICAL_COUNT: String(issueCounts.critical ?? computedCounts.critical),
    WARNING_COUNT: String(issueCounts.warning ?? computedCounts.warning),
    INFO_COUNT: String(issueCounts.info ?? computedCounts.info),
    CRITICAL_DELTA: issueCounts.critical_delta ?? '',
    WARNING_DELTA: issueCounts.warning_delta ?? '',
    INFO_DELTA: issueCounts.info_delta ?? '',
    TOTAL_ISSUES: String(issues.length),

    TREND_TEXT: data.trend?.text ?? '',
    TREND_COLOR: data.trend?.color ?? 'text-muted',

    ASPECT_ITEMS: buildAspectItems(data.aspects || []),
    ISSUE_ROWS: buildIssueRows(issues),

    // Optional SVG details. If not provided, render empty layers.
    RADAR_POINTS: data.radar?.points ?? '',
    RADAR_POINT_CIRCLES: data.radar?.point_circles ?? '',
    RADAR_LABELS: data.radar?.labels ?? '',
    HISTORY_AREA_POINTS: data.history?.area_points ?? '',
    HISTORY_LINE_POINTS: data.history?.line_points ?? '',
    HISTORY_POINT_CIRCLES: data.history?.point_circles ?? '',
    HISTORY_X_LABELS: data.history?.x_labels ?? ''
  };

  const html = replaceAll(template, replacements);
  const leftovers = html.match(/\{[A-Z0-9_]+\}/g) || [];
  if (leftovers.length) {
    const unique = Array.from(new Set(leftovers)).slice(0, 25);
    throw new Error(`Unreplaced placeholders remain in HTML (${leftovers.length}): ${unique.join(', ')}`);
  }

  writeFileSync(outputPath, html);
  console.log(`OK: wrote ${outputPath}`);
}

main();

