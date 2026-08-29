# Audit Methodology

This document describes the methodology behind the automated code audit tool. It's designed for progressive disclosure — start with the summary, dive into specifics as needed.

## Philosophy

**Honest assessment over manufactured urgency.**

A clean codebase should get a clean report. We don't inflate severity to create fear. We don't flag best-practice aspirations as critical issues. We report what we find, at the severity it deserves.

**70/30 principle.**

Automated tools can reliably detect ~70% of code quality issues: known anti-patterns, security vulnerabilities, structural problems, missing tests. The remaining ~30% — architecture fitness, business-context prioritization, cost estimation — requires human judgment. We're explicit about this boundary.

**Zero dependencies, zero excuses.**

The tool runs on any system with Node.js 18+. No npm install, no Docker, no API keys. Lower the barrier to entry and more people will actually audit their code.

## Analysis Pipeline

```
Files → Filter → Ecosystem Detection → Analyzers (7) → Findings → Report
```

### 1. File Collection

- Recursive walk from project root
- Skip: `node_modules`, `.git`, `dist`, `build`, binary files, lockfiles, sourcemaps
- Limit: 10,000 files, 2MB per file, 20 levels deep
- Cross-platform: `path.join()` everywhere, no shell commands

### 2. Ecosystem Detection

Before running analyzers, we detect:

- **Primary language** — by file extension frequency
- **Frameworks** — by config file presence (astro.config.mjs → Astro, next.config.js → Next.js, etc.)
- **Package manager** — by lockfile type (pnpm-lock.yaml → pnpm, etc.)
- **Test frameworks** — from dependencies and config files
- **Package dependencies** — parsed from package.json, requirements.txt, mix.exs

This context shapes how analyzers interpret findings. A `.py` file with `exec()` is treated differently than a `.js` file.

### 3. Analyzers

Each analyzer runs independently and returns an array of findings. Findings have a standard shape:

```
{
  analyzer: string,     // Which analyzer produced this
  severity: string,     // critical | high | medium | low | info
  title: string,        // Short summary
  description: string,  // Detailed explanation
  file?: string,        // Relative file path
  line?: number,        // Line number (1-based)
  snippet?: string,     // Code context (secrets redacted)
  remediation?: string  // How to fix
}
```

#### Structure Analyzer
- **God files**: >500 lines (medium), >300 lines (low)
- **Deep nesting**: >4 indent levels
- **High imports**: >10 import statements per file
- **Long functions**: >80 lines per function

#### Secrets Analyzer
- 18 regex patterns covering AWS, GitHub, Stripe, OpenAI, Anthropic, Google, Slack, database URLs, private keys, JWTs, and generic patterns
- Checks for `.env` files committed to repo
- Verifies `.gitignore` includes `.env`
- Redacts actual secret values in report snippets

#### Security Analyzer
- ~20 anti-patterns grouped by language
- Universal: eval(), CORS wildcard, disabled TLS
- JavaScript: innerHTML, document.write, prototype pollution, dangerouslySetInnerHTML
- SQL: string concatenation, template literal injection
- Python: exec(), pickle, subprocess shell=True
- Infrastructure: debug mode, exposed stack traces

#### Dependencies Analyzer
- Lockfile presence check
- Version pinning (wildcards, `latest`)
- Known problematic packages (moment, lodash full, deprecated request)
- Missing `engines` field
- Delegates to native `npm audit` / `pnpm audit` when available

#### Tests Analyzer
- Test file detection by naming convention and directory
- Test-to-source ratio calculation
- Test framework detection
- CI integration check (GitHub Actions, GitLab CI, etc.)
- Assertion quality: snapshot-only, weak assertions, empty test bodies

#### Imports Analyzer
- Builds directed graph of file imports
- DFS cycle detection for circular dependencies
- Hub file identification (imported by many files)
- Coupling score (average imports per file)

#### AI Patterns Analyzer
- Tool fingerprint detection (Cursor, Bolt, Lovable, Copilot, v0, etc.)
- Silent catch blocks (empty error handlers)
- Generic error messages
- Commented-out code
- Inconsistent naming conventions within files
- Near-duplicate file detection via structural signatures

### 4. Report Generation

Findings are:
1. Sorted by severity (critical first)
2. Grouped by analyzer
3. Rendered into markdown sections with consistent formatting
4. Preceded by project overview and summary table
5. Followed by manual review sections (the honest 30%)

## Severity Definitions

| Level | Definition | Action |
|-------|-----------|--------|
| **Critical** | Active security risk or data exposure. Could be exploited today. | Fix immediately. |
| **High** | Significant risk or systemic quality issue. Creates ongoing problems. | Fix this sprint. |
| **Medium** | Moderate concern. Won't cause immediate issues but creates technical debt. | Plan to fix. |
| **Low** | Minor issue or style concern. Cosmetic or aspirational improvement. | Fix when convenient. |
| **Info** | Observation. Not necessarily a problem, but worth knowing about. | Acknowledge. |

## Known Limitations

1. **Regex over AST.** We use regex patterns, not abstract syntax trees. This means some false positives (regex matches in comments or strings) and false negatives (complex patterns across multiple lines). Acceptable for a first-pass tool.

2. **No data flow analysis.** We detect `eval(userInput)` as a pattern, but we can't trace whether `userInput` actually contains untrusted data. Static analysis tools like Semgrep or CodeQL handle this better.

3. **No runtime analysis.** We can't detect issues that only manifest at runtime — memory leaks, race conditions, performance bottlenecks.

4. **Single-file scope.** Most analyzers look at one file at a time. The imports analyzer builds a cross-file graph, but other analyzers don't consider cross-file interactions.

5. **English-centric.** Pattern matching assumes English keywords and conventions.

## What Comes Next

For teams that want deeper analysis, a full audit from Variant Systems includes:
- Architecture review with business context
- Prioritized remediation roadmap with cost estimates
- Performance profiling and optimization recommendations
- Security review with threat modeling
- Executive summary for stakeholders

See [variantsystems.io/get-audit](https://variantsystems.io/get-audit) for details.
