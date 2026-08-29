---
name: audit
description: Analyze npm audit results, identify actionable fixes vs noise, and recommend specific actions
---

# Security Audit

Intelligently analyze npm audit results. Distinguishes real threats from transitive dependency noise and recommends specific actions.

## When to Use

- After `make audit` shows vulnerabilities
- Before deploying to production
- When updating dependencies
- Periodic security check (integrated into `/preflight`)

## Instructions

### 1. Run Audit

```bash
pnpm audit --json 2>/dev/null || true
```

If no package.json exists, report "No Node.js project found" and exit.

### 2. Parse Each Vulnerability

For each vulnerability, determine:

#### A. Direct vs Transitive

Look at the `via` and `effects` fields:
- **Direct**: Your package.json depends on the vulnerable package
- **Transitive**: A dependency of a dependency is vulnerable

```bash
# Check if package is a direct dependency
grep -q '"<package-name>"' package.json && echo "DIRECT" || echo "TRANSITIVE"
```

#### B. Production vs Dev

```bash
# Check if it's a dev dependency
grep -A5 '"devDependencies"' package.json | grep -q '"<package-name>"' && echo "DEV" || echo "PROD"
```

For transitive deps, trace up to find the root:
```bash
pnpm why <vulnerable-package>
```

#### C. Exploitability

Consider:
- Is the vulnerable code path actually used?
- JWT vulnerabilities don't matter if you use Clerk
- XSS in markdown parser doesn't matter if you sanitize output
- Server-only packages aren't exposed to client attacks

### 3. Check for Existing Overrides

Before recommending fixes, check if overrides are already in place:

```bash
# Check package.json for pnpm overrides
grep -A20 '"pnpm"' package.json | grep -A15 '"overrides"'
```

> **Note:** This checks pnpm-style overrides only. npm uses `"overrides"` at root level, yarn uses `"resolutions"`.

If an override exists for the vulnerable package:
- Check if the override version is >= patched version
- If yes: vulnerability should be resolved (verify with `pnpm list <package>`)
- If no: override exists but needs version bump

### 4. Check for Fixes

For each vulnerability:

```bash
# Check if parent package has update
pnpm outdated <parent-package> 2>/dev/null

# Check latest version
pnpm info <parent-package> version
```

### 5. Classify

| Category | Criteria | Action |
|----------|----------|--------|
| **Critical** | Direct + Production + Exploitable | Fix immediately |
| **High** | Direct + Production | Update when convenient |
| **Medium** | Transitive + Production | Monitor, check for parent updates |
| **Low** | Dev dependency only | Can ignore, update eventually |
| **Overridden** | Has pnpm override >= patched version | Verify resolved, no action needed |
| **Noise** | Transitive + Dev + Not exploitable | Ignore |

### 6. Recommend Actions

For each non-noise vulnerability:

**If direct dependency:**
```bash
pnpm update <package>@latest
```

**If transitive (parent has fix):**
```bash
pnpm update <parent-package>@latest
```

**If transitive (no fix available):**
- Check GitHub issues on parent package for timeline:
  ```bash
  gh search issues --repo <owner/repo> "<vulnerable-package>" --state open
  ```
- Consider override (last resort):
```json
// package.json
"pnpm": {
  "overrides": {
    "<vulnerable-package>": ">=<fixed-version>"
  }
}
```

**If not exploitable in your context:**
- Document why it's not a risk
- Revisit on next audit

## Output Format

```markdown
## Security Audit Report

**Summary:** X vulnerabilities found, Y actionable

### Critical (fix now)
- **<package>** (<severity>) - <vulnerability>
  - Type: Direct / Production
  - Fix: `pnpm update <package>@<version>`

### Should Fix
- **<package>** (<severity>) - <vulnerability>
  - Type: Transitive via `<parent>`
  - Fix: `pnpm update <parent>@<version>`

### Monitor
- **<package>** (<severity>) - <vulnerability>
  - Type: Transitive via `<parent>`
  - Status: No fix available, tracked in <github-issue-link>

### Already Resolved (via override)
- **<package>** (<severity>) - <vulnerability>
  - Override: `"<package>": ">= <version>"` in package.json
  - Verified: `pnpm list <package>` shows <resolved-version>

### Noise (can ignore)
- **<package>** (<severity>) - <vulnerability>
  - Reason: Dev dependency only / Not exploitable because <reason>

### Recommended Actions
1. {specific command to run}
2. {specific command to run}

### Next Audit
Run `/audit` again after updates to verify fixes.
```

## Common Scenarios

### "Vulnerability in Prisma's dev tools"
Prisma bundles dev tools (Studio) with their own dependencies. These don't affect your production app.
- **Verdict:** Noise (dev tooling, not in your code path)

### "Vulnerability in testing framework"
Jest, Vitest, Playwright vulnerabilities are dev-only.
- **Verdict:** Low priority (update when convenient, doesn't affect prod)

### "JWT vulnerability but using Clerk"
If you don't use the vulnerable JWT code path, it's not exploitable.
- **Verdict:** Noise (not exploitable in your context)

### "XSS in markdown parser"
Only matters if you render untrusted markdown without sanitization.
- **Verdict:** Check if you sanitize. If yes, noise. If no, critical.

## Notes

- `pnpm audit` returns exit code 1 when vulnerabilities exist (expected)
- **Override caveat**: `pnpm audit` may still report vulnerabilities even with overrides, because it checks declared versions in lockfile metadata. Verify actual resolution with `pnpm list <package>`
- Some packages will never be fixed (abandoned) - consider alternatives
- Overrides can break things - use sparingly and test thoroughly
- After adding/changing overrides, run `pnpm install` to apply
