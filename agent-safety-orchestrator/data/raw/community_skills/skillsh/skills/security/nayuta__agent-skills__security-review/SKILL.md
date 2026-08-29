---
name: security-review
description: |
  Comprehensive AI-driven security code review. By default reviews only the
  changes in the current branch (git diff). Pass --full to review the entire
  codebase instead of just the diff.
  Performs multi-phase analysis: repository context research, systematic vulnerability
  scanning across 8 categories (secrets, injection, authentication, cryptography, input
  validation, data exposure, dependency risks, configuration), false positive filtering,
  and a structured report with severity ratings and remediation guidance.
  Only reports high-confidence findings (confidence >= 8/10) to minimize noise.
  Use before merging code changes, during security-focused PR review, or when
  auditing the security posture of a feature or an entire codebase.
  Pairs with security-scan for tool-based scanning of secrets and dependencies.
compatibility: Requires git for diff mode (default); full mode (`--full`) works without git using a find-based fallback. Language-agnostic — works on any codebase.
allowed-tools: Bash Read Glob Grep
metadata:
  version: "1.1.0"
  author: nayuta
---

# Security Review

## Purpose

Systematically analyze code for security vulnerabilities using structured
AI reasoning. Produces a confidence-filtered report with actionable remediation.

## Scan Modes

| Mode           | Flag     | Source of files to review                        |
| -------------- | -------- | ------------------------------------------------ |
| Diff (default) | _(none)_ | Files changed in the current branch (`git diff`) |
| Full codebase  | `--full` | All tracked source files (`git ls-files`)        |

Use **diff mode** (default) for pre-merge reviews to focus on what changed.
Use **`--full`** when onboarding a new codebase, performing a periodic audit,
or when no branch diff is available.

## Workflow

### Phase 1: Repository Context

Before analyzing file content, build context to reduce false positives:

1. Read key project files: `CLAUDE.md`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`
2. Identify tech stack, frameworks, ORM, auth library, and HTTP server
3. Note existing security patterns (middleware, validation helpers, auth guards)
4. Identify sensitive file types for this project (config, migrations, API handlers)

### Phase 2: Gather Files to Review

#### Default mode (diff only)

Collect the diff to review:

```bash
# Changes vs. main branch
git diff --merge-base origin/main

# Or vs. current remote HEAD
git diff origin/HEAD...HEAD

# Fallback: uncommitted changes
git diff HEAD
```

If the diff is empty, report "No changes to review" and stop.

Also note which files were changed:

```bash
git diff --name-only origin/main...HEAD
```

#### Full mode (`--full`)

Collect all tracked source files instead of the diff:

```bash
git ls-files
```

If the repository is not a git repo, use:

```bash
find . -type f \
  ! -path '*/.git/*' \
  ! -path '*/node_modules/*' \
  ! -path '*/__pycache__/*' \
  ! -path '*/vendor/*' \
  ! -path '*/.venv/*'
```

Filter out binary, generated, and non-source files (images, compiled artifacts,
lock files, minified assets). Focus on files likely to contain executable logic:
source code, configuration templates, infrastructure definitions, and scripts.

If the file set is large (> 200 files), prioritise by security sensitivity:

1. Auth, session, and permission handlers
2. API route handlers and controllers
3. Database query builders and ORMs
4. Configuration files and environment templates
5. Remaining source files

Note which files are being reviewed in the Phase 5 report header.

### Phase 3: Vulnerability Analysis

Systematically check each reviewed file against all 8 categories below.
Work through each category in order. For each finding, record:

- **Category** and sub-type
- **File** and **line number**
- **Evidence** (the exact code snippet)
- **Impact** (what an attacker could do)
- **Confidence** (1–10, explained in Phase 4)

#### Category 1: Secrets and Credentials

Patterns to find:

- Hardcoded API keys, tokens, passwords, private keys in source
- Credentials embedded in connection strings or URLs
- Secrets committed to config files not in `.gitignore`
- Environment variable values (not references) in source code

Signs it is NOT a finding:

- Value contains `example`, `test`, `dummy`, `placeholder`, `your-key-here`
- File is in `tests/`, `fixtures/`, `examples/`, `docs/`
- Key is a public key or certificate (not private)

#### Category 2: Injection

Sub-types to check:

| Sub-type              | Patterns                                                             |
| --------------------- | -------------------------------------------------------------------- |
| SQL injection         | String concatenation or interpolation into query, raw query builders |
| Command injection     | `exec`, `spawn`, `system`, `shell_exec` with user-controlled input   |
| LDAP injection        | Unescaped user input in LDAP filters                                 |
| Template injection    | User input rendered through template engines                         |
| XPath / XML injection | User input in XPath expressions or XML parsers                       |
| NoSQL injection       | Unvalidated objects passed to `find()`, `aggregate()`, etc.          |

Signs it is NOT a finding:

- Parameterized queries / prepared statements used
- Input validated to a strict allowlist before use
- Query builder with explicit escaping (e.g., `knex`, `sqlalchemy` ORM methods)

#### Category 3: Authentication and Authorization

Check for:

- Missing authentication guards on new endpoints or routes
- Insecure direct object reference (IDOR): resource ID taken from user input without ownership check
- Privilege escalation: role or permission check missing or bypassable
- Broken JWT validation: algorithm confusion (`alg: none`), missing signature check, missing expiry check
- Session fixation or session not invalidated on logout/privilege change
- Password hashing: plaintext storage, MD5/SHA1 without salt

Signs it is NOT a finding:

- Auth middleware applied at router level (covers all child routes)
- Resource fetched with user ID scoped query (`WHERE user_id = current_user_id`)

#### Category 4: Cryptography

Check for:

- Weak algorithms: MD5, SHA1, DES, 3DES, RC4 for security purposes
- Static IVs or nonces used with AES-GCM or ChaCha20
- Insufficient key lengths (RSA < 2048 bits, EC < 256 bits)
- `Math.random()` or `rand()` used for security tokens, session IDs, or CSRF tokens
- Custom crypto implementation replacing standard library

Signs it is NOT a finding:

- Weak hash used only for cache keys, ETags, or content deduplication (not security)
- Algorithm is for checksum / data integrity, not authentication

#### Category 5: Input Validation and Output Encoding

Check for:

- Cross-site scripting (XSS): user input rendered as HTML without escaping
- Server-side request forgery (SSRF): user-supplied URL fetched server-side without allowlist
- Path traversal: user input used in file paths without normalization
- Open redirect: user-controlled redirect URL without domain validation
- Unsafe deserialization: `pickle.loads`, `yaml.load` (without Loader), `eval`, `JSON.parse` on untrusted input
- ReDoS: unbounded regex on user input

Signs it is NOT a finding:

- Framework auto-escapes template output (check framework docs)
- URL validated against explicit allowlist of known-good domains
- File path resolved with `realpath` and checked to remain within base directory

#### Category 6: Sensitive Data Exposure

Check for:

- PII, passwords, tokens logged to application logs
- Sensitive fields returned in API responses that should be excluded
- Detailed error messages (stack traces, internal paths, DB errors) returned to client
- Sensitive data stored in browser localStorage or cookies without `HttpOnly`/`Secure` flags

Signs it is NOT a finding:

- Logging in a debug-only path behind feature flag
- Error handler strips stack traces in production builds

#### Category 7: Dependency Risks

Check for:

- New packages added with known CVEs (cross-reference security-scan output)
- `npm install --legacy-peer-deps` or `pip install --trusted-host` bypassing integrity checks
- Package version pinned to a compromised version range
- Direct use of `eval`-style packages (`node-serialize`, `serialize-javascript` < 3.1)

Signs it is NOT a finding:

- Package used only in dev/test environment
- Vulnerability does not affect the code path used

#### Category 8: Security Configuration

Check for:

- New endpoints missing rate limiting or authentication middleware
- CORS wildcard (`Access-Control-Allow-Origin: *`) on authenticated endpoints
- Disabled CSRF protection
- `DEBUG=True` or equivalent in production configuration
- TLS verification disabled (`verify=False`, `InsecureSkipVerify: true`)
- Exposed admin panels, metrics endpoints, or debug routes without access control

Signs it is NOT a finding:

- Wildcard CORS on a fully public, read-only API
- TLS skip in test environment code never deployed to production

### Phase 4: False Positive Filtering

For each potential finding, apply the confidence score:

| Score | Meaning                                               |
| ----- | ----------------------------------------------------- |
| 10    | Exploitable with certainty, clear reproduction path   |
| 9     | Very likely exploitable, minor assumption required    |
| 8     | Likely exploitable, context supports it               |
| 7     | Possibly exploitable, but requires more investigation |
| ≤6    | Probable false positive or low-impact edge case       |

**Only include findings with confidence ≥ 8 in the final report.**

Factors that increase confidence:

- User input flows directly to sink with no sanitization in the reviewed code
- New code, not an existing pattern (reduces "was already there" dismissals)
- Impact is high (RCE, auth bypass, data exfiltration)

Factors that decrease confidence:

- Framework or library likely handles it transparently
- Existing middleware or validation covers the case
- Finding is in test or documentation code

### Phase 5: Report

If there are no findings with confidence ≥ 8:

```markdown
## Security Review

**Date**: <ISO 8601>
**Mode**: diff | full
**Files reviewed**: N
**Findings**: None above confidence threshold.

No high-confidence security vulnerabilities found in the reviewed files.
Run security-scan for tool-based secret and dependency checks.
```

Otherwise, use this format:

```markdown
## Security Review

**Date**: <ISO 8601>
**Mode**: diff | full
**Branch**: <branch-name> ← omit in full mode if not on a feature branch
**Files reviewed**: N
**High-confidence findings**: N (Critical: N | High: N | Medium: N)

---

## Critical

### [SEC-001] <Vulnerability type> in <component>

**File**: `path/to/file.ts:42`
**Category**: Injection > SQL Injection
**Confidence**: 9/10

**Evidence**:
\`\`\`typescript
const result = db.query(`SELECT * FROM users WHERE id = ${req.params.id}`);
\`\`\`

**Impact**: Attacker can read, modify, or delete arbitrary database records.

**Remediation**:
\`\`\`typescript
const result = db.query("SELECT \* FROM users WHERE id = $1", [req.params.id]);
\`\`\`

---

## High

### [SEC-002] ...

---

## Medium

### [SEC-003] ...

---

## Recommended Next Steps

1. Fix Critical and High findings before merging
2. Run `security-scan` for dependency and secret scanning
3. Add regression tests for confirmed vulnerabilities
```

## Integration

- Run **security-scan** first to catch secrets and known CVEs in dependencies
- Use this skill for AI reasoning over logic flaws and design issues
- Together they form a complete pre-merge security gate
- For a full codebase audit, run both with `--full`:
  - `/security-scan --full` then `/security-review --full`

## References

- [Vulnerability Categories Detail](references/vulnerability-categories.md) — deeper patterns and examples per category
