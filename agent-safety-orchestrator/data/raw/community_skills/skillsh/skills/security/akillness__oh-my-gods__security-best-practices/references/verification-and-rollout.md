# Verification and Rollout

Use this reference when the user needs to know what evidence should prove the
security controls are real rather than merely intended.

## Merge-blocking evidence

Require stronger proof when the changed boundary is high risk:

- auth or session changes
- permission enforcement
- secret handling
- request validation
- CSRF or cookie changes
- externally reachable APIs

Good merge blockers:

- config or code diff that clearly adds the control
- automated checks for validation, auth, or header behavior where feasible
- focused manual verification notes for browser/session behavior when automation
  is impractical

## Release-focused evidence

Release-time checks can be broader than merge checks:

- production-like header verification
- environment-specific secret wiring confirmation
- rate-limit behavior on the highest-risk endpoints
- monitoring or alert coverage for abuse and auth failures

## Control-to-evidence examples

| Control | Good evidence |
|---|---|
| CSP / headers | response-header inspection in a deployed environment |
| Input validation | request tests for reject paths, not only happy paths |
| CSRF | state-changing request check without token or origin proof |
| Secrets | runtime injection path verified, no hardcoded fallback secrets |
| Rate limiting | threshold behavior observed on sensitive endpoints |
| SSRF guardrails | outbound target allowlist or parser validation proved in tests or config |

## When to route elsewhere

- `testing-strategies` if the real question is what layers should prove the risk
- `backend-testing` if the tests need to be written
- `playwriter` only when browser/runtime verification in an existing session is
  required
- `security-review` if the task has become a code-level exploit hunt
