#!/usr/bin/env node

/**
 * Code Audit — Main Orchestrator
 *
 * Runs all analyzers against a target directory and generates CODE_AUDIT_REPORT.md.
 * Uses external tools (Semgrep, Trivy, etc.) when available, falls back to regex.
 *
 * Usage:
 *   node scripts/audit.mjs [target-dir]
 *
 * If no target directory is provided, uses the current working directory.
 *
 * Zero dependencies — pure Node.js (18+).
 */

import { writeFile } from 'node:fs/promises';
import path from 'node:path';

// Utils
import { collectFiles } from './utils/fs-walk.mjs';
import { detectEcosystem } from './utils/detect-ecosystem.mjs';

// Tools
import { discoverTools, getMissingTools } from './tools/runner.mjs';

// Analyzers
import { analyzeStructure } from './analyzers/structure.mjs';
import { analyzeSecrets } from './analyzers/secrets.mjs';
import { analyzeSecurity } from './analyzers/security.mjs';
import { analyzeDependencies } from './analyzers/dependencies.mjs';
import { analyzeTests } from './analyzers/tests.mjs';
import { analyzeImports } from './analyzers/imports.mjs';
import { analyzeAiPatterns } from './analyzers/ai-patterns.mjs';

// Report
import { generateReport } from './report/generator.mjs';

const REPORT_FILENAME = 'CODE_AUDIT_REPORT.md';

async function main() {
  const startTime = Date.now();

  // Determine target directory
  const targetDir = path.resolve(process.argv[2] || process.cwd());

  console.log('');
  console.log('┌─────────────────────────────────────┐');
  console.log('│         Code Audit v2.0.0            │');
  console.log('│     by Variant Systems               │');
  console.log('└─────────────────────────────────────┘');
  console.log('');
  console.log(`Target: ${targetDir}`);
  console.log('');

  // Phase 1: Collect files
  process.stdout.write('Scanning files...');
  const files = await collectFiles(targetDir);
  console.log(` ${files.length} files found`);

  if (files.length === 0) {
    console.error('No files found. Check the target directory.');
    process.exit(1);
  }

  // Phase 2: Detect ecosystem
  process.stdout.write('Detecting ecosystem...');
  const ecosystem = await detectEcosystem(targetDir, files);
  console.log(` ${ecosystem.primaryLanguage} (${ecosystem.frameworks.join(', ') || 'no framework detected'})`);

  // Phase 3: Discover tools
  console.log('');
  process.stdout.write('Discovering tools...');
  const availableTools = await discoverTools();
  const missingTools = getMissingTools(availableTools, ecosystem.packageManager);

  if (availableTools.size > 0) {
    const toolNames = Array.from(availableTools.values()).map(t => t.tool.name);
    console.log(` ${availableTools.size} found (${toolNames.join(', ')})`);
  } else {
    console.log(' none found (using regex analysis)');
  }

  const toolOpts = { availableTools, ecosystem };

  // Phase 4: Run analyzers
  console.log('');
  console.log('Running analyzers:');

  const allFindings = [];
  const allToolsMeta = [];
  let structureStats = { totalFiles: 0, totalLines: 0, codeFiles: 0, avgFileSize: 0, largestFiles: [] };
  let testStats = null;
  let importStats = null;
  let depStats = null;

  // Structure (no external tools)
  process.stdout.write('  [1/7] Code structure...');
  const structureResult = await analyzeStructure(targetDir, files, ecosystem);
  allFindings.push(...structureResult.findings);
  structureStats = structureResult.stats;
  console.log(` ${structureResult.findings.length} findings`);

  // Secrets
  process.stdout.write('  [2/7] Secrets scan...');
  const secretsResult = await analyzeSecrets(targetDir, files, toolOpts);
  allFindings.push(...secretsResult.findings);
  if (secretsResult.toolsMeta) allToolsMeta.push(...secretsResult.toolsMeta);
  console.log(` ${secretsResult.findings.length} findings`);

  // Security
  process.stdout.write('  [3/7] Security patterns...');
  const securityResult = await analyzeSecurity(targetDir, files, toolOpts);
  allFindings.push(...securityResult.findings);
  if (securityResult.toolsMeta) allToolsMeta.push(...securityResult.toolsMeta);
  console.log(` ${securityResult.findings.length} findings`);

  // Dependencies
  process.stdout.write('  [4/7] Dependencies...');
  const depsResult = await analyzeDependencies(targetDir, files, ecosystem, toolOpts);
  allFindings.push(...depsResult.findings);
  depStats = depsResult.stats;
  if (depsResult.toolsMeta) allToolsMeta.push(...depsResult.toolsMeta);
  console.log(` ${depsResult.findings.length} findings`);

  // Tests (no external tools)
  process.stdout.write('  [5/7] Test coverage...');
  const testsResult = await analyzeTests(targetDir, files, ecosystem);
  allFindings.push(...testsResult.findings);
  testStats = testsResult.stats;
  console.log(` ${testsResult.findings.length} findings`);

  // Imports
  process.stdout.write('  [6/7] Import graph...');
  const importsResult = await analyzeImports(targetDir, files, toolOpts);
  allFindings.push(...importsResult.findings);
  importStats = importsResult.stats;
  if (importsResult.toolsMeta) allToolsMeta.push(...importsResult.toolsMeta);
  console.log(` ${importsResult.findings.length} findings`);

  // AI Patterns (no external tools)
  process.stdout.write('  [7/7] AI patterns...');
  const aiResult = await analyzeAiPatterns(targetDir, files);
  allFindings.push(...aiResult.findings);
  console.log(` ${aiResult.findings.length} findings`);

  // Phase 5: Generate report
  const durationMs = Date.now() - startTime;

  console.log('');
  process.stdout.write('Generating report...');

  const report = generateReport({
    findings: allFindings,
    ecosystem,
    structureStats,
    testStats,
    importStats,
    depStats,
    durationMs,
    toolsUsed: allToolsMeta,
    missingTools,
  });

  const reportPath = path.join(targetDir, REPORT_FILENAME);
  await writeFile(reportPath, report, 'utf-8');
  console.log(' done');

  // Summary
  console.log('');
  console.log('┌─────────────────────────────────────┐');
  console.log('│           Audit Complete             │');
  console.log('└─────────────────────────────────────┘');
  console.log('');

  const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
  for (const f of allFindings) counts[f.severity]++;

  if (counts.critical > 0) console.log(`  🔴 Critical: ${counts.critical}`);
  if (counts.high > 0) console.log(`  🟠 High:     ${counts.high}`);
  if (counts.medium > 0) console.log(`  🟡 Medium:   ${counts.medium}`);
  if (counts.low > 0) console.log(`  🔵 Low:      ${counts.low}`);
  if (counts.info > 0) console.log(`  ℹ️  Info:     ${counts.info}`);

  console.log('');
  console.log(`  Total: ${allFindings.length} findings in ${(durationMs / 1000).toFixed(1)}s`);

  if (allToolsMeta.length > 0) {
    const successTools = allToolsMeta.filter(m => m.status === 'success');
    if (successTools.length > 0) {
      console.log(`  Tools: ${successTools.map(m => m.toolName).join(', ')}`);
    }
  }

  if (missingTools.length > 0) {
    console.log(`  Installable: ${missingTools.length} additional tools available`);
  }

  console.log(`  Report: ${reportPath}`);
  console.log('');
}

main().catch(err => {
  console.error('');
  console.error('Audit failed:', err.message);
  console.error(err.stack);
  process.exit(1);
});
