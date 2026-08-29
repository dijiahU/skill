#!/usr/bin/env node

import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { execFileSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const skillRoot = join(__dirname, '..');
const sampleJson = join(skillRoot, 'examples', 'sample-report.json');
const templateHtml = join(skillRoot, 'templates', 'report.html');

const outDir = join(process.cwd(), '.smoke-output');
const outHtml = join(outDir, 'auditing-bdd-tests-report.html');

mkdirSync(outDir, { recursive: true });

execFileSync(
  process.execPath,
  [join(skillRoot, 'scripts', 'render-html.mjs'), sampleJson, outHtml, templateHtml],
  { stdio: 'inherit' }
);

