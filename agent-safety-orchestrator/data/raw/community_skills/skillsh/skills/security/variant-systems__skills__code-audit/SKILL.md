---
name: code-audit
description: >
  Run a comprehensive code audit on any codebase. Analyzes security vulnerabilities,
  hardcoded secrets, dependency CVEs, test coverage, code structure, and AI-generated
  code patterns. Generates CODE_AUDIT_REPORT.md with findings, severity ratings, and
  remediation guidance. Intelligently selects and orchestrates the best available
  tools for each project. Cross-platform.
  Use when user asks to "audit this code", "run a security scan", "check for
  vulnerabilities", "find secrets in the code", "assess technical debt", or
  "check code health". Do NOT use for single-file code reviews or pull request
  reviews (use code-review skill instead).
compatibility: Requires Node.js 18+. Cross-platform (macOS, Linux, Windows).
license: MIT
metadata:
  author: variant-systems
  version: "2.1.0"
  repository: https://github.com/variant-systems/skills
---

# Code Audit Agent Skill

You are a code audit agent. When the user asks you to audit, review, or assess a codebase, follow these instructions.

## When to Use

Activate this skill when the user says any of:
- "audit this code / codebase / repo"
- "review the code quality"
- "check for security issues"
- "assess technical debt"
- "how healthy is this codebase?"
- "run a code audit"

## How to Run

### Step 1: Analyze the Project

Before anything else, understand what you're auditing. Determine the target directory (user-specified or cwd), then use Glob and Read to quickly scan for:

- Language indicators: `package.json`, `requirements.txt`, `pyproject.toml`, `mix.exs`, `Cargo.toml`, `Gemfile`, `go.mod`, `pom.xml`, `build.gradle`, `*.cs`/`*.csproj`, `*.swift`, etc.
- Frameworks: config files like `astro.config.*`, `next.config.*`, `nuxt.config.*`, `angular.json`, `django`, `rails`, `phoenix`, etc.
- Infrastructure: `Dockerfile`, `docker-compose.yml`, `terraform/`, `*.tf`, `k8s/`, `helm/`
- CI/CD: `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`
- Secrets risk: `.env` files, config files with credentials
- Package managers & lockfiles

From this, build a mental model: What languages? What frameworks? What ecosystem? What are the main risk areas (secrets, dependencies, security patterns, code quality)?

### Step 2: Plan the Audit Tools

Based on what you found, decide which external tools would produce the best audit for THIS specific project. Think about:

**For security scanning** — What static analysis tools exist for these languages? Examples:
- Semgrep (multi-language, 2000+ rules)
- ESLint with security plugins (JavaScript/TypeScript)
- Bandit (Python)
- Brakeman (Ruby on Rails)
- gosec (Go)
- cargo-clippy (Rust)
- Security-focused linters for the detected languages

**For secret detection** — What tools can find leaked credentials?
- TruffleHog (verifies if secrets are active)
- Gitleaks (fast, 150+ patterns)
- detect-secrets (Python-based)

**For dependency vulnerabilities** — What auditors exist for this ecosystem?
- npm/pnpm/yarn audit (Node.js)
- Trivy (multi-ecosystem)
- OSV-Scanner (Google's vulnerability database)
- pip-audit (Python)
- cargo-audit (Rust)
- bundler-audit (Ruby)
- mix deps.audit (Elixir)
- Safety (Python)
- Snyk CLI (multi-ecosystem)

**For code quality / structure** — What tools analyze complexity and imports?
- Madge (JS/TS circular dependencies)
- radon (Python complexity)
- plato (JS complexity reports)

Don't limit yourself to this list. If you know of a tool that would be particularly useful for the detected ecosystem, include it. You are the expert — reason about what would give the best results.

Plan the order: secrets and security first (highest impact), then dependencies, then structure/quality.

### Step 3: Check Tools & Offer to Install Missing Ones

For each tool in your plan:

1. **Check if it's installed** — Run its version/help command via Bash (e.g., `semgrep --version`, `trivy --version`). Run these checks in parallel where possible.

2. **For each missing tool**, use `AskUserQuestion` to ask the user if they want to install it. Batch up to 4 tools per AskUserQuestion call. For each:

   - **header**: Tool name (short, e.g., "Semgrep")
   - **question**: "Install {tool}? {what it adds to the audit}"
   - **options**:
     - `"Install (Recommended)"` — describe what it does and why it's worth it
     - `"Skip"` — explain what fallback will be used (regex, or another tool)
   - **multiSelect**: false

3. **For tools the user wants to install**, figure out the right install command for the current platform. You have access to Bash — detect the OS and package manager:
   - macOS: `brew install`, `pip install`, `npm install -g`
   - Linux (apt): `sudo apt install`, `pip install`, `npm install -g`
   - Linux (dnf/yum): `sudo dnf install`, `pip install`
   - Windows: `winget install`, `choco install`, `scoop install`, `pip install`
   - Language-specific: `cargo install`, `gem install`, `mix archive.install`
   - Fallback: `pip install` or download from GitHub releases

   Run the install command. If it fails, inform the user and continue without that tool.

4. If ALL tools are already installed, skip the AskUserQuestion and tell the user: "All recommended tools are installed. Running audit."

### Step 4: Run the Tools

Execute each tool against the target directory in your planned order. For each tool:

1. Run it via Bash with appropriate flags for machine-readable output (JSON, SARIF, or structured text)
2. Capture the output
3. Note any failures (tool crashed, timed out, no findings) — don't let one tool failure stop the audit

Also run the built-in regex analysis script, which provides baseline coverage regardless of what tools are installed:

```bash
node <path-to-this-skill>/scripts/audit.mjs [target-directory]
```

This script requires **Node.js 18+** and has **zero dependencies**. It runs 7 analyzers (structure, secrets, security, dependencies, tests, imports, AI patterns) using regex/heuristic analysis and generates an initial `CODE_AUDIT_REPORT.md`.

### Step 5: Analyze & Report

Synthesize ALL results — tool outputs + the regex analysis report — into a comprehensive assessment. Read the generated `CODE_AUDIT_REPORT.md` and enhance it with tool findings.

When presenting to the user:

1. **Lead with critical/high findings.** These need immediate attention.
2. **Give the overall health impression.** Well-maintained with minor issues, or systemic neglect?
3. **Highlight the most actionable items.** What can they fix right now with the biggest impact?
4. **Be honest about clean results.** If the codebase is healthy, say so. Don't manufacture urgency.
5. **Note which tools were used** and what they found vs. regex-only analysis.
6. **Mention the full report path** so they can review the complete findings.

## Example Workflow

**User says:** "Audit this codebase for security issues"

**Actions:**
1. Scan project — detect Node.js + React app with package.json, .env file present
2. Plan tools — Semgrep (security), Gitleaks (secrets), npm audit (deps), plus regex baseline
3. Check tools — Semgrep installed, Gitleaks missing → ask user to install
4. Run audit — execute all tools, run `node scripts/audit.mjs`
5. Synthesize — 2 critical (exposed API key, SQL injection), 5 high, 12 medium findings

**Result:** `CODE_AUDIT_REPORT.md` generated. User briefed on critical items first with actionable remediation steps.

## Severity Levels

- **Critical** — Must fix immediately. Security vulnerabilities, exposed secrets, data loss risks.
- **High** — Fix soon. Significant technical debt, missing security controls, no tests.
- **Medium** — Plan to fix. Code quality issues, moderate complexity, weak test assertions.
- **Low** — Nice to fix. Style issues, minor complexity, informational findings.
- **Info** — Awareness only. Observations that may or may not need action.

## What the Audit Covers (the 70%)

| Area | What It Finds |
|------|--------------|
| **Secrets** | Hardcoded API keys, tokens, credentials, private keys, .env files in repos |
| **Security** | Injection risks (SQL, XSS, command), eval(), weak crypto, CORS misconfig, and more |
| **Dependencies** | Known CVEs, unpinned versions, deprecated packages, missing lockfiles |
| **Structure** | God files, deep nesting, long functions, high complexity |
| **Tests** | Missing tests, low coverage ratios, weak assertions, no CI integration |
| **Imports** | Circular dependencies, hub files, coupling hotspots |
| **AI Patterns** | Tool fingerprints, silent error handling, generic code, structural inconsistencies |

## What It Doesn't Cover (the 30%)

These areas require human judgment and are noted in the report:
- Architecture fitness relative to business goals
- Business-context prioritization of findings
- Remediation cost estimates for the specific team
- Executive summary for non-technical stakeholders

## Common Issues

### Node.js not installed or wrong version
If `node --version` shows below 18, the baseline script will fail. Ask the user to install Node.js 18+ via their package manager or [nodejs.org](https://nodejs.org).

### Tool install fails due to permissions
Some tools (e.g., `pip install semgrep`) may need `--user` flag or a virtual environment. On macOS, prefer `brew install`. Never run `sudo npm install -g` — use `npx` as fallback.

### Audit script hangs on very large repos
The script caps at 10,000 files and 2MB per file. If it's still slow, check for large generated directories not in the skip list. Suggest the user add them to `.gitignore`.

### External tool produces no output
Some tools exit silently when they find nothing. This is normal — note "0 findings from [tool]" and move on. Don't treat clean results as errors.

## References

For detailed methodology, consult the bundled reference files:
- `references/audit-methodology.md` — Full audit methodology and scoring approach
- `references/severity-definitions.md` — Detailed severity level criteria and examples
- `references/ai-tool-signatures.md` — Patterns for detecting AI-generated code

## Technical Details

- **Zero-dependency baseline.** The regex analysis script uses pure Node.js stdlib. No npm install needed.
- **Tool-first when available.** External tools provide deeper, more accurate analysis than regex.
- **Cross-platform.** The agent determines the right install commands and tool flags for the current OS.
- **No fixed tool list.** The agent reasons about what tools are best for each specific project.
- **Graceful degradation.** If no tools are installed, regex analysis still covers all categories.
- **File limits.** Baseline script scans up to 10,000 files, skips files over 2MB, max depth 20.
