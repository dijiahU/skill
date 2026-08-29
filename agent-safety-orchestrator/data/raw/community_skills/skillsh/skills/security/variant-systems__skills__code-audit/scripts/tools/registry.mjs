/**
 * Tool registry — declarative descriptors for external security/quality tools.
 * Each entry describes how to detect, run, and parse a tool's output.
 * Zero dependencies — pure Node.js.
 */

/**
 * @typedef {object} ToolDescriptor
 * @property {string} id - Unique identifier
 * @property {string} name - Human-readable name
 * @property {string[]} categories - Which analyzers can use this tool (secrets, security, dependencies, imports)
 * @property {string[]} detect - Command + args to check if tool is installed (should exit 0)
 * @property {object} run - How to run the tool
 * @property {string[]} run.command - Default command + args
 * @property {object} [run.ecosystemOverrides] - Per-ecosystem command overrides
 * @property {string} parserId - Which parser to use from parsers.mjs
 * @property {string} outputFormat - Expected output format (json, sarif, text)
 * @property {string} installHint - How to install this tool
 * @property {string} benefit - What installing this tool adds
 * @property {number} timeout - Max runtime in ms
 */

export const TOOL_REGISTRY = [
  // === Security / Secrets Scanners ===
  {
    id: 'semgrep',
    name: 'Semgrep',
    categories: ['secrets', 'security'],
    detect: ['semgrep', ['--version']],
    run: {
      command: ['semgrep', ['scan', '--json', '--quiet', '--no-git-ignore']],
      categoryOverrides: {
        secrets: ['semgrep', ['scan', '--json', '--quiet', '--no-git-ignore', '--config', 'p/secrets']],
        security: ['semgrep', ['scan', '--json', '--quiet', '--no-git-ignore', '--config', 'p/security-audit', '--config', 'p/owasp-top-ten']],
      },
    },
    parserId: 'semgrep-json',
    outputFormat: 'json',
    installHint: 'brew install semgrep  OR  pip install semgrep',
    benefit: 'Deep semantic analysis with 2000+ security rules. Finds issues regex cannot.',
    timeout: 120_000,
  },
  {
    id: 'eslint',
    name: 'ESLint',
    categories: ['security'],
    detect: ['npx', ['eslint', '--version']],
    run: {
      command: ['npx', ['eslint', '--format=json', '--no-error-on-unmatched-pattern', '.']],
    },
    parserId: 'eslint-json',
    outputFormat: 'json',
    installHint: 'npm install -D eslint eslint-plugin-security',
    benefit: 'JavaScript/TypeScript security linting with eslint-plugin-security.',
    timeout: 60_000,
  },
  {
    id: 'bandit',
    name: 'Bandit',
    categories: ['security'],
    detect: ['bandit', ['--version']],
    run: {
      command: ['bandit', ['-r', '-f', 'json', '-q', '.']],
    },
    parserId: 'bandit-json',
    outputFormat: 'json',
    installHint: 'pip install bandit',
    benefit: 'Python-specific security analysis covering 40+ vulnerability types.',
    timeout: 60_000,
    ecosystems: ['python'],
  },
  {
    id: 'trufflehog',
    name: 'TruffleHog',
    categories: ['secrets'],
    detect: ['trufflehog', ['--version']],
    run: {
      command: ['trufflehog', ['filesystem', '--json', '--no-update', '.']],
    },
    parserId: 'trufflehog-json',
    outputFormat: 'json',
    installHint: 'brew install trufflehog  OR  pip install trufflehog',
    benefit: 'High-accuracy secret detection with verification. Checks if secrets are actually active.',
    timeout: 120_000,
  },
  {
    id: 'gitleaks',
    name: 'Gitleaks',
    categories: ['secrets'],
    detect: ['gitleaks', ['version']],
    run: {
      command: ['gitleaks', ['detect', '--source', '.', '--report-format', 'json', '--report-path', '/dev/stdout', '--no-git']],
    },
    parserId: 'gitleaks-json',
    outputFormat: 'json',
    installHint: 'brew install gitleaks',
    benefit: 'Fast secret scanning with 150+ built-in rules. Catches common credential patterns.',
    timeout: 60_000,
  },

  // === Dependency Auditors ===
  {
    id: 'npm-audit',
    name: 'npm audit',
    categories: ['dependencies'],
    detect: ['npm', ['--version']],
    run: {
      command: ['npm', ['audit', '--json']],
    },
    parserId: 'npm-audit-json',
    outputFormat: 'json',
    installHint: 'Bundled with Node.js',
    benefit: 'Check npm dependencies for known vulnerabilities.',
    timeout: 30_000,
    ecosystems: ['npm'],
  },
  {
    id: 'pnpm-audit',
    name: 'pnpm audit',
    categories: ['dependencies'],
    detect: ['pnpm', ['--version']],
    run: {
      command: ['pnpm', ['audit', '--json']],
    },
    parserId: 'pnpm-audit-json',
    outputFormat: 'json',
    installHint: 'npm install -g pnpm',
    benefit: 'Check pnpm dependencies for known vulnerabilities.',
    timeout: 30_000,
    ecosystems: ['pnpm'],
  },
  {
    id: 'yarn-audit',
    name: 'yarn audit',
    categories: ['dependencies'],
    detect: ['yarn', ['--version']],
    run: {
      command: ['yarn', ['audit', '--json']],
    },
    parserId: 'yarn-audit-json',
    outputFormat: 'json',
    installHint: 'npm install -g yarn',
    benefit: 'Check Yarn dependencies for known vulnerabilities.',
    timeout: 30_000,
    ecosystems: ['yarn'],
  },
  {
    id: 'trivy',
    name: 'Trivy',
    categories: ['dependencies'],
    detect: ['trivy', ['--version']],
    run: {
      command: ['trivy', ['fs', '--format', 'json', '--scanners', 'vuln', '.']],
    },
    parserId: 'trivy-json',
    outputFormat: 'json',
    installHint: 'brew install trivy',
    benefit: 'Comprehensive vulnerability scanner for dependencies, containers, and IaC. Covers all ecosystems.',
    timeout: 120_000,
  },
  {
    id: 'osv-scanner',
    name: 'OSV-Scanner',
    categories: ['dependencies'],
    detect: ['osv-scanner', ['--version']],
    run: {
      command: ['osv-scanner', ['--format', 'json', '-r', '.']],
    },
    parserId: 'osv-scanner-json',
    outputFormat: 'json',
    installHint: 'go install github.com/google/osv-scanner/cmd/osv-scanner@latest',
    benefit: 'Google-backed vulnerability database. Cross-ecosystem coverage using OSV.dev.',
    timeout: 60_000,
  },
  {
    id: 'mix-audit',
    name: 'mix audit',
    categories: ['dependencies'],
    detect: ['mix', ['help', 'deps.audit']],
    run: {
      command: ['mix', ['deps.audit']],
    },
    parserId: 'mix-audit-text',
    outputFormat: 'text',
    installHint: 'mix deps.get && mix archive.install hex phx_new  (requires Elixir)',
    benefit: 'Elixir/Hex dependency vulnerability scanning.',
    timeout: 30_000,
    ecosystems: ['elixir'],
  },
  {
    id: 'cargo-audit',
    name: 'cargo audit',
    categories: ['dependencies'],
    detect: ['cargo', ['audit', '--version']],
    run: {
      command: ['cargo', ['audit', '--json']],
    },
    parserId: 'cargo-audit-json',
    outputFormat: 'json',
    installHint: 'cargo install cargo-audit',
    benefit: 'Rust crate vulnerability scanning via RustSec advisory database.',
    timeout: 30_000,
    ecosystems: ['rust'],
  },
  {
    id: 'pip-audit',
    name: 'pip-audit',
    categories: ['dependencies'],
    detect: ['pip-audit', ['--version']],
    run: {
      command: ['pip-audit', ['--format=json']],
    },
    parserId: 'pip-audit-json',
    outputFormat: 'json',
    installHint: 'pip install pip-audit',
    benefit: 'Python dependency vulnerability scanning via PyPI advisory database.',
    timeout: 30_000,
    ecosystems: ['python'],
  },
  {
    id: 'bundler-audit',
    name: 'bundler-audit',
    categories: ['dependencies'],
    detect: ['bundler-audit', ['version']],
    run: {
      command: ['bundler-audit', ['check']],
    },
    parserId: 'bundler-audit-text',
    outputFormat: 'text',
    installHint: 'gem install bundler-audit',
    benefit: 'Ruby gem vulnerability scanning via Ruby Advisory Database.',
    timeout: 30_000,
    ecosystems: ['ruby'],
  },

  // === Import / Structure ===
  {
    id: 'madge',
    name: 'Madge',
    categories: ['imports'],
    detect: ['npx', ['madge', '--version']],
    run: {
      command: ['npx', ['madge', '--circular', '--json', '.']],
    },
    parserId: 'madge-json',
    outputFormat: 'json',
    installHint: 'npm install -D madge',
    benefit: 'Accurate circular dependency detection for JavaScript/TypeScript projects.',
    timeout: 60_000,
    ecosystems: ['npm', 'pnpm', 'yarn'],
  },
];

/**
 * Get tools by category.
 */
export function getToolsByCategory(category) {
  return TOOL_REGISTRY.filter(t => t.categories.includes(category));
}

/**
 * Get a tool descriptor by id.
 */
export function getToolById(id) {
  return TOOL_REGISTRY.find(t => t.id === id) || null;
}
