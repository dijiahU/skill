/**
 * Secrets analyzer.
 * Tool-first: uses TruffleHog, Gitleaks, Semgrep when available.
 * Regex fallback: 18-pattern scan + .env detection.
 * Zero dependencies — pure Node.js.
 */

import { readLines } from '../utils/line-reader.mjs';
import { finding, SEVERITY } from '../utils/severity.mjs';
import { getToolsForCategory, runTool } from '../tools/runner.mjs';
import { deduplicateFindings } from '../tools/dedup.mjs';

const ANALYZER = 'secrets';

/**
 * Secret patterns. Each has:
 * - name: human-readable label
 * - pattern: regex to match
 * - severity: how bad is it
 * - description: what it means
 */
const SECRET_PATTERNS = [
  {
    name: 'AWS Access Key ID',
    pattern: /(?:^|[^A-Z0-9])AKIA[0-9A-Z]{16}(?:[^A-Z0-9]|$)/,
    severity: SEVERITY.CRITICAL,
    description: 'AWS access key ID found. These grant direct access to AWS resources.',
  },
  {
    name: 'AWS Secret Access Key',
    pattern: /(?:aws_secret_access_key|aws_secret_key)\s*[=:]\s*['"]?[A-Za-z0-9/+=]{40}['"]?/i,
    severity: SEVERITY.CRITICAL,
    description: 'AWS secret access key found. Combined with an access key, this grants full AWS access.',
  },
  {
    name: 'GitHub Token',
    pattern: /(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}/,
    severity: SEVERITY.CRITICAL,
    description: 'GitHub personal access token found. Can access repositories and perform actions.',
  },
  {
    name: 'Stripe Secret Key',
    pattern: /sk_(?:live|test)_[A-Za-z0-9]{24,}/,
    severity: SEVERITY.CRITICAL,
    description: 'Stripe secret key found. Can process charges and access customer data.',
  },
  {
    name: 'Stripe Publishable Key (Test)',
    pattern: /pk_test_[A-Za-z0-9]{24,}/,
    severity: SEVERITY.LOW,
    description: 'Stripe test publishable key found. Low risk but should still be in env vars.',
  },
  {
    name: 'OpenAI API Key',
    pattern: /sk-[A-Za-z0-9]{20,}T3BlbkFJ[A-Za-z0-9]{20,}/,
    severity: SEVERITY.HIGH,
    description: 'OpenAI API key found. Can incur charges on the associated account.',
  },
  {
    name: 'Generic API Key Assignment',
    pattern: /(?:api_key|apikey|api_secret|api_token)\s*[=:]\s*['"][A-Za-z0-9_\-]{20,}['"]/i,
    severity: SEVERITY.HIGH,
    description: 'Hardcoded API key found. Secrets should be in environment variables.',
  },
  {
    name: 'Generic Secret Assignment',
    pattern: /(?:secret|password|passwd|token)\s*[=:]\s*['"][^'"]{8,}['"]/i,
    severity: SEVERITY.MEDIUM,
    description: 'Possible hardcoded secret. Verify this is not a real credential.',
  },
  {
    name: 'Private Key Block',
    pattern: /-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----/,
    severity: SEVERITY.CRITICAL,
    description: 'Private key found in source code. This must be removed immediately.',
  },
  {
    name: 'Database Connection String',
    pattern: /(?:mongodb|postgres|postgresql|mysql|redis|amqp):\/\/[^:]+:[^@]+@[^\s'"]+/i,
    severity: SEVERITY.HIGH,
    description: 'Database connection string with credentials found. Use environment variables.',
  },
  {
    name: 'Slack Token',
    pattern: /xox[bpors]-[A-Za-z0-9\-]{10,}/,
    severity: SEVERITY.HIGH,
    description: 'Slack token found. Can access workspace messages and data.',
  },
  {
    name: 'Twilio Auth Token',
    pattern: /(?:twilio_auth_token|TWILIO_AUTH_TOKEN)\s*[=:]\s*['"]?[a-f0-9]{32}['"]?/i,
    severity: SEVERITY.HIGH,
    description: 'Twilio auth token found. Can send messages and access account.',
  },
  {
    name: 'SendGrid API Key',
    pattern: /SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}/,
    severity: SEVERITY.HIGH,
    description: 'SendGrid API key found. Can send emails from the associated account.',
  },
  {
    name: 'Google API Key',
    pattern: /AIza[A-Za-z0-9_\-]{35}/,
    severity: SEVERITY.HIGH,
    description: 'Google API key found. Depending on scope, may access various Google services.',
  },
  {
    name: 'Heroku API Key',
    pattern: /(?:heroku_api_key|HEROKU_API_KEY)\s*[=:]\s*['"]?[a-f0-9\-]{36}['"]?/i,
    severity: SEVERITY.HIGH,
    description: 'Heroku API key found. Can manage applications and infrastructure.',
  },
  {
    name: 'JWT Secret',
    pattern: /(?:jwt_secret|JWT_SECRET|jwt_key|JWT_KEY)\s*[=:]\s*['"][^'"]{8,}['"]/i,
    severity: SEVERITY.HIGH,
    description: 'JWT signing secret found. An attacker could forge authentication tokens.',
  },
  {
    name: 'Firebase Config',
    pattern: /(?:firebase_api_key|FIREBASE_API_KEY)\s*[=:]\s*['"]?AIza[A-Za-z0-9_\-]{35}['"]?/i,
    severity: SEVERITY.MEDIUM,
    description: 'Firebase API key found. Should be restricted and not hardcoded.',
  },
  {
    name: 'Anthropic API Key',
    pattern: /sk-ant-[A-Za-z0-9_\-]{20,}/,
    severity: SEVERITY.HIGH,
    description: 'Anthropic API key found. Can incur charges on the associated account.',
  },
];

/** Files that legitimately contain secret-like patterns. */
const IGNORE_FILES = new Set([
  '.env.example',
  '.env.sample',
  '.env.template',
  'example.env',
]);

/** Extensions to scan. */
const SCAN_EXTENSIONS = new Set([
  '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
  '.py', '.rb', '.go', '.rs', '.java', '.kt', '.scala',
  '.ex', '.exs', '.php', '.cs', '.swift', '.c', '.cpp',
  '.vue', '.svelte', '.astro',
  '.env', '.cfg', '.conf', '.config', '.ini', '.properties',
  '.yml', '.yaml', '.toml', '.json', '.xml',
  '.sh', '.bash', '.zsh',
  '.tf', '.tfvars',
  '.md', // Docs sometimes contain real secrets accidentally
]);

/**
 * Run the secrets analyzer.
 *
 * @param {string} rootDir
 * @param {object[]} files
 * @param {object} [opts]
 * @param {Map} [opts.availableTools] - Available tools from discoverTools()
 * @param {object} [opts.ecosystem] - Ecosystem detection results
 * @returns {Promise<{ findings: object[], toolsMeta: object[] }>}
 */
export async function analyzeSecrets(rootDir, files, opts = {}) {
  const { availableTools, ecosystem } = opts;
  const toolsMeta = [];

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

  // Phase 2: Run regex analysis
  const regexFindings = await regexSecretsAnalysis(rootDir, files);

  // Phase 3: Deduplicate
  const findings = deduplicateFindings(toolFindings, regexFindings);

  return { findings, toolsMeta };
}

/**
 * Original regex-based secrets analysis (extracted from previous analyzeSecrets).
 */
async function regexSecretsAnalysis(rootDir, files) {
  const findings = [];

  // Check for .env file committed to repo
  const envFiles = files.filter(f =>
    f.relativePath === '.env' ||
    (f.relativePath.endsWith('.env') && !IGNORE_FILES.has(f.relativePath.split('/').pop()))
  );

  for (const envFile of envFiles) {
    const basename = envFile.relativePath.split('/').pop();
    if (basename === '.env' || (basename.endsWith('.env') && !basename.includes('example') && !basename.includes('sample') && !basename.includes('template'))) {
      findings.push(finding({
        analyzer: ANALYZER,
        severity: SEVERITY.CRITICAL,
        title: `.env file in repository: ${envFile.relativePath}`,
        description: 'A .env file is present in the repository. This file typically contains secrets and should be in .gitignore.',
        file: envFile.relativePath,
        remediation: 'Add .env to .gitignore, remove the file from git history using `git filter-branch` or BFG Repo Cleaner, and rotate all secrets.',
      }));
    }
  }

  // Check if .gitignore includes .env
  const gitignoreFile = files.find(f => f.relativePath === '.gitignore');
  if (gitignoreFile) {
    const result = await readLines(gitignoreFile.absolutePath);
    if (result) {
      const hasEnvIgnore = result.lines.some(l => l.trim() === '.env' || l.trim() === '.env*' || l.trim() === '*.env');
      if (!hasEnvIgnore) {
        findings.push(finding({
          analyzer: ANALYZER,
          severity: SEVERITY.HIGH,
          title: '.env not in .gitignore',
          description: 'The .gitignore file does not appear to exclude .env files. This increases the risk of accidentally committing secrets.',
          file: '.gitignore',
          remediation: 'Add `.env` and `.env.*` patterns to .gitignore.',
        }));
      }
    }
  }

  // Scan files for secret patterns
  for (const file of files) {
    if (!SCAN_EXTENSIONS.has(file.ext)) continue;

    const basename = file.relativePath.split('/').pop();
    if (IGNORE_FILES.has(basename)) continue;

    // Skip test fixtures and mocks
    if (file.relativePath.includes('__fixtures__') ||
        file.relativePath.includes('__mocks__') ||
        file.relativePath.includes('test/fixtures') ||
        file.relativePath.includes('testdata')) continue;

    const result = await readLines(file.absolutePath);
    if (!result) continue;

    for (let i = 0; i < result.lines.length; i++) {
      const line = result.lines[i];

      // Skip comments
      const trimmed = line.trim();
      if (trimmed.startsWith('//') && !trimmed.includes('=') && !trimmed.includes(':')) continue;
      if (trimmed.startsWith('#') && !trimmed.includes('=') && !trimmed.includes(':')) continue;

      for (const pattern of SECRET_PATTERNS) {
        if (pattern.pattern.test(line)) {
          // Avoid duplicate findings for the same line
          const existing = findings.find(f =>
            f.file === file.relativePath &&
            f.line === i + 1 &&
            f.title.includes(pattern.name)
          );
          if (existing) continue;

          // Redact the actual secret from the snippet
          const snippet = redactLine(line.trim());

          findings.push(finding({
            analyzer: ANALYZER,
            severity: pattern.severity,
            title: `${pattern.name} in ${file.relativePath}`,
            description: pattern.description,
            file: file.relativePath,
            line: i + 1,
            snippet,
            remediation: 'Move this secret to an environment variable. If this has been committed, rotate the credential immediately.',
          }));
          break; // One finding per line max
        }
      }
    }
  }

  return findings;
}

/**
 * Redact sensitive values from a line for display.
 */
function redactLine(line) {
  // Replace long alphanumeric sequences (likely tokens/keys) with redaction
  return line.replace(
    /(['"])[A-Za-z0-9/+=_\-]{16,}\1/g,
    '$1[REDACTED]$1'
  ).replace(
    /(?<=[:=]\s*)[A-Za-z0-9/+=_\-]{20,}/g,
    '[REDACTED]'
  );
}
