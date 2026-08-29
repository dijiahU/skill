/**
 * Security anti-pattern analyzer.
 * Tool-first: uses Semgrep, ESLint, Bandit when available.
 * Regex fallback: ~20 anti-patterns for eval, SQL injection, XSS, weak crypto, etc.
 * Zero dependencies — pure Node.js.
 */

import { readLines } from '../utils/line-reader.mjs';
import { finding, SEVERITY } from '../utils/severity.mjs';
import { getToolsForCategory, runTool } from '../tools/runner.mjs';
import { deduplicateFindings } from '../tools/dedup.mjs';

const ANALYZER = 'security';

/**
 * Security anti-patterns grouped by language/context.
 * Each pattern has:
 * - name: human-readable label
 * - regex: pattern to match
 * - severity: how bad
 * - description: explanation
 * - remediation: fix guidance
 * - extensions: which file types to check (null = all code files)
 */
const PATTERNS = [
  // === Universal ===
  {
    name: 'eval() usage',
    regex: /\beval\s*\(/,
    severity: SEVERITY.HIGH,
    description: 'Use of eval() can execute arbitrary code. This is a common injection vector.',
    remediation: 'Replace eval() with a safer alternative. Parse JSON with JSON.parse(), use AST-based approaches for code generation.',
    extensions: ['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx', '.py', '.rb', '.php'],
  },
  {
    name: 'CORS wildcard',
    regex: /(?:Access-Control-Allow-Origin|cors)\s*[:(]\s*['"]?\*/,
    severity: SEVERITY.MEDIUM,
    description: 'CORS wildcard (*) allows any origin to access this resource. This can enable CSRF attacks.',
    remediation: 'Restrict CORS to specific trusted origins instead of using wildcard.',
    extensions: null,
  },
  {
    name: 'Hardcoded CORS origin',
    regex: /Access-Control-Allow-Origin['":\s]+(?:http:\/\/localhost|http:\/\/127\.0\.0\.1)/,
    severity: SEVERITY.LOW,
    description: 'CORS configured for localhost. Ensure this is not present in production.',
    remediation: 'Use environment-specific CORS configuration.',
    extensions: null,
  },

  // === JavaScript/TypeScript ===
  {
    name: 'innerHTML assignment',
    regex: /\.innerHTML\s*[=+]/,
    severity: SEVERITY.HIGH,
    description: 'Setting innerHTML with untrusted data enables XSS attacks.',
    remediation: 'Use textContent for text, or sanitize HTML with DOMPurify before using innerHTML.',
    extensions: ['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx', '.vue', '.svelte'],
  },
  {
    name: 'document.write()',
    regex: /document\.write\s*\(/,
    severity: SEVERITY.MEDIUM,
    description: 'document.write() can be exploited for XSS and causes performance issues.',
    remediation: 'Use DOM manipulation methods (createElement, appendChild) instead.',
    extensions: ['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'],
  },
  {
    name: 'Prototype pollution risk',
    regex: /\[['"]__proto__['"]\]|\bObject\.assign\(\s*\{\s*\}/,
    severity: SEVERITY.MEDIUM,
    description: 'Potential prototype pollution vector. Merging untrusted objects can modify Object.prototype.',
    remediation: 'Validate and sanitize object keys. Use Object.create(null) for dictionaries.',
    extensions: ['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'],
  },
  {
    name: 'dangerouslySetInnerHTML',
    regex: /dangerouslySetInnerHTML/,
    severity: SEVERITY.MEDIUM,
    description: 'React dangerouslySetInnerHTML bypasses XSS protection. Ensure input is sanitized.',
    remediation: 'Sanitize HTML with DOMPurify before passing to dangerouslySetInnerHTML.',
    extensions: ['.jsx', '.tsx', '.js', '.ts'],
  },
  {
    name: 'Disabled ESLint security rule',
    regex: /eslint-disable.*(?:no-eval|no-implied-eval|no-new-func|security)/,
    severity: SEVERITY.MEDIUM,
    description: 'Security-related ESLint rule disabled. This may hide real vulnerabilities.',
    remediation: 'Address the underlying issue instead of disabling the security rule.',
    extensions: ['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'],
  },
  {
    name: 'new Function() constructor',
    regex: /new\s+Function\s*\(/,
    severity: SEVERITY.HIGH,
    description: 'new Function() is similar to eval() — it compiles and executes arbitrary code.',
    remediation: 'Refactor to avoid dynamic code generation. Use configuration objects or strategy patterns.',
    extensions: ['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'],
  },
  {
    name: 'Unvalidated redirect',
    regex: /(?:res\.redirect|window\.location|location\.href)\s*[=(]\s*(?:req\.|params\.|query\.)/,
    severity: SEVERITY.MEDIUM,
    description: 'Redirect target may come from user input. This enables open redirect attacks.',
    remediation: 'Validate redirect URLs against a whitelist of allowed destinations.',
    extensions: ['.js', '.mjs', '.cjs', '.ts', '.tsx'],
  },
  {
    name: 'Weak crypto (MD5/SHA1)',
    regex: /(?:createHash|hashlib\.)\s*\(\s*['"](?:md5|sha1)['"]\s*\)/,
    severity: SEVERITY.MEDIUM,
    description: 'MD5 and SHA1 are cryptographically broken. Do not use for security purposes.',
    remediation: 'Use SHA-256 or SHA-3 for hashing. Use bcrypt/argon2 for password hashing.',
    extensions: ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.py'],
  },
  {
    name: 'Disabled TLS verification',
    regex: /(?:NODE_TLS_REJECT_UNAUTHORIZED|rejectUnauthorized)\s*[=:]\s*['"]?(?:0|false)/,
    severity: SEVERITY.HIGH,
    description: 'TLS certificate verification is disabled. This enables man-in-the-middle attacks.',
    remediation: 'Enable TLS verification. Fix certificate issues at the source.',
    extensions: null,
  },

  // === SQL ===
  {
    name: 'SQL injection risk (string concatenation)',
    regex: /(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)\s+.*\+\s*(?:req\.|params\.|query\.|user|input|data)/i,
    severity: SEVERITY.CRITICAL,
    description: 'SQL query built with string concatenation of user input. Classic SQL injection vulnerability.',
    remediation: 'Use parameterized queries or an ORM. Never concatenate user input into SQL.',
    extensions: ['.js', '.mjs', '.cjs', '.ts', '.tsx', '.py', '.rb', '.php', '.java', '.go'],
  },
  {
    name: 'SQL injection risk (template literal)',
    regex: /(?:query|execute|raw)\s*\(\s*`[^`]*\$\{/,
    severity: SEVERITY.HIGH,
    description: 'SQL query uses template literals with interpolated values. Possible SQL injection.',
    remediation: 'Use parameterized queries. Pass values as parameters, not in the query string.',
    extensions: ['.js', '.mjs', '.cjs', '.ts', '.tsx'],
  },

  // === Python ===
  {
    name: 'Python exec()',
    regex: /\bexec\s*\(/,
    severity: SEVERITY.HIGH,
    description: 'exec() executes arbitrary Python code. This is a code injection vector.',
    remediation: 'Replace exec() with a safer alternative. Use AST manipulation for code generation.',
    extensions: ['.py'],
  },
  {
    name: 'Python pickle (deserialization)',
    regex: /pickle\.(?:loads?|Unpickler)/,
    severity: SEVERITY.HIGH,
    description: 'Pickle deserialization of untrusted data can execute arbitrary code.',
    remediation: 'Use JSON or a safe serialization format for untrusted data.',
    extensions: ['.py'],
  },
  {
    name: 'Python subprocess shell=True',
    regex: /subprocess\.\w+\([^)]*shell\s*=\s*True/,
    severity: SEVERITY.HIGH,
    description: 'subprocess with shell=True is vulnerable to command injection.',
    remediation: 'Use subprocess with a list of arguments instead of shell=True.',
    extensions: ['.py'],
  },

  // === PHP ===
  {
    name: 'PHP system/exec/shell_exec',
    regex: /(?:system|exec|shell_exec|passthru|popen)\s*\(\s*\$/,
    severity: SEVERITY.CRITICAL,
    description: 'Shell command execution with variable input. Command injection vulnerability.',
    remediation: 'Use escapeshellarg() and escapeshellcmd(), or avoid shell commands entirely.',
    extensions: ['.php'],
  },

  // === Infrastructure ===
  {
    name: 'Debug mode enabled',
    regex: /(?:DEBUG|debug)\s*[=:]\s*(?:true|True|1|['"]true['"])/,
    severity: SEVERITY.LOW,
    description: 'Debug mode appears to be enabled. Ensure this is not active in production.',
    remediation: 'Use environment variables to control debug mode. Disable in production.',
    extensions: null,
  },
  {
    name: 'Exposed error details',
    regex: /(?:stack|stackTrace|stack_trace|traceback)\s*[)}\]]*\s*$/m,
    severity: SEVERITY.LOW,
    description: 'Stack traces may be exposed to users. This leaks internal implementation details.',
    remediation: 'Log full errors server-side. Show generic error messages to users.',
    extensions: null,
  },
  {
    name: 'HTTP (not HTTPS) URL',
    regex: /['"]http:\/\/(?!localhost|127\.0\.0\.1|0\.0\.0\.0|example\.com|schema\.org)/,
    severity: SEVERITY.LOW,
    description: 'HTTP URL found. Data sent over HTTP is not encrypted.',
    remediation: 'Use HTTPS for all external URLs.',
    extensions: null,
  },
];

const CODE_EXTENSIONS = new Set([
  '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx',
  '.py', '.rb', '.go', '.rs', '.java', '.kt', '.scala',
  '.ex', '.exs', '.php', '.cs', '.swift', '.c', '.cpp',
  '.vue', '.svelte', '.astro',
  '.yml', '.yaml', '.toml', '.json', '.xml',
  '.sh', '.bash', '.zsh',
  '.tf', '.hcl',
]);

/**
 * Run the security analyzer.
 *
 * @param {string} rootDir
 * @param {object[]} files
 * @param {object} [opts]
 * @param {Map} [opts.availableTools] - Available tools from discoverTools()
 * @param {object} [opts.ecosystem] - Ecosystem detection results
 * @returns {Promise<{ findings: object[], toolsMeta: object[] }>}
 */
export async function analyzeSecurity(rootDir, files, opts = {}) {
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
  const regexFindings = await regexSecurityAnalysis(rootDir, files);

  // Phase 3: Deduplicate
  const findings = deduplicateFindings(toolFindings, regexFindings);

  return { findings, toolsMeta };
}

/**
 * Original regex-based security analysis.
 */
async function regexSecurityAnalysis(rootDir, files) {
  const results = [];

  for (const file of files) {
    if (!CODE_EXTENSIONS.has(file.ext)) continue;

    // Skip test files for most checks — they often use eval etc intentionally
    const isTestFile = /(?:\.test\.|\.spec\.|__tests__|test_|_test\.)/.test(file.relativePath);

    const lineResult = await readLines(file.absolutePath);
    if (!lineResult) continue;

    for (let i = 0; i < lineResult.lines.length; i++) {
      const line = lineResult.lines[i];
      const trimmed = line.trim();

      // Skip comments
      if (trimmed.startsWith('//') || trimmed.startsWith('#') || trimmed.startsWith('*') || trimmed.startsWith('/*')) continue;

      for (const pattern of PATTERNS) {
        // Check file extension filter
        if (pattern.extensions && !pattern.extensions.includes(file.ext)) continue;

        // Skip low-severity in test files
        if (isTestFile && pattern.severity === SEVERITY.LOW) continue;

        if (pattern.regex.test(line)) {
          results.push(finding({
            analyzer: ANALYZER,
            severity: pattern.severity,
            title: `${pattern.name} in ${file.relativePath}`,
            description: pattern.description,
            file: file.relativePath,
            line: i + 1,
            snippet: trimmed.length > 200 ? trimmed.slice(0, 200) + '...' : trimmed,
            remediation: pattern.remediation,
          }));
          break; // One finding per line per pattern group
        }
      }
    }
  }

  return results;
}
