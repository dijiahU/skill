# Severity Definitions

Standard severity scale used by the code audit tool. Designed for honesty — we don't inflate severity to create urgency.

## Scale

### Critical

**Definition:** Active security risk, data exposure, or system compromise vector. Could be exploited today by an attacker with access to the codebase or deployed application.

**Examples:**
- Hardcoded AWS secret keys in source code
- Private keys committed to repository
- SQL injection with direct user input concatenation
- `.env` file with production credentials in repo

**Action:** Fix immediately. Rotate any exposed credentials. Do not deploy until resolved.

**SLA guidance:** Same day.

---

### High

**Definition:** Significant security risk or systemic quality issue. Creates ongoing problems that compound over time. May not be immediately exploitable but represents a clear gap.

**Examples:**
- `eval()` with potentially untrusted input
- No lockfile (non-reproducible builds)
- No test files in a project with 50+ source files
- Database connection strings in code
- TLS verification disabled

**Action:** Fix this sprint. These issues create risk exposure and technical debt that gets harder to fix over time.

**SLA guidance:** Within 1 week.

---

### Medium

**Definition:** Moderate concern. Won't cause immediate security incidents or outages, but creates technical debt, maintenance burden, or suboptimal practices that accumulate.

**Examples:**
- CORS wildcard configuration
- God files (>500 lines)
- Circular imports between modules
- Snapshot-only tests with no behavioral assertions
- Multiple silent catch blocks

**Action:** Plan to fix. Add to backlog with appropriate priority.

**SLA guidance:** Within 1-2 sprints.

---

### Low

**Definition:** Minor issue, style concern, or best-practice deviation. The code works and isn't at risk, but could be cleaner or more maintainable.

**Examples:**
- Large files approaching threshold (300+ lines)
- Deep nesting (>4 levels)
- Weak test assertions (toBeTruthy instead of specific values)
- console.log statements in production code
- High import count in a single file

**Action:** Fix when convenient. Good candidates for refactoring sprints or new-contributor tasks.

**SLA guidance:** No specific deadline.

---

### Info

**Definition:** Observation that provides context. Not necessarily a problem, but worth knowing about. May inform other decisions.

**Examples:**
- AI tool fingerprints detected (Cursor, Copilot, etc.)
- Language and framework breakdown
- Dependency count statistics

**Action:** Acknowledge. Use for context in decision-making. No fix required.

---

## Severity Assignment Principles

1. **No inflation.** A clean codebase gets a clean report. We don't flag style preferences as security issues.

2. **Context matters.** `eval()` in a test helper is different from `eval()` in a request handler. We try to account for context where possible.

3. **Err toward lower severity.** When uncertain, we assign the lower severity. It's better to under-report than to cry wolf.

4. **Technical risk, not business risk.** Automated tools assign severity by technical characteristics. Business-context prioritization requires human judgment — see the "What This Audit Doesn't Cover" section in the report.

5. **Actionable.** Every finding above Info severity includes a remediation suggestion. Findings without clear remediation are informational.
