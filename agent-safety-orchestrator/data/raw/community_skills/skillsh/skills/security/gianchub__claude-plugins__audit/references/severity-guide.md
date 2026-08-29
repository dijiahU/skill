# Severity Classification Guide

Use the following criteria to assign severity levels. When a finding could fit multiple levels, choose the higher severity and note the reasoning.

**Intent-based downgrades:** When the Intent Brief provides general context justifying a pattern (but not an explicit per-instance acknowledgment), reduce severity by one level (e.g., High → Medium) and cite the intent source in the finding. Never downgrade Critical findings below High — Critical severity indicates risk significant enough that even documented intent warrants attention.

### Critical

Reserve for findings that represent an immediate, exploitable threat or a near-certain path to significant damage:

- Remotely exploitable security vulnerabilities (injection, auth bypass, SSRF with internal network access).
- Direct paths to data loss or corruption (unprotected destructive operations, missing transaction safety on critical writes).
- Hardcoded production credentials or secrets committed to version control.
- Privilege escalation that grants administrative access to unauthorized users.

### High

Assign to findings that are likely to cause real-world bugs, outages, or security degradation under normal operating conditions:

- Correctness bugs that produce wrong results or crash the application for common inputs.
- Race conditions on data structures or resources accessed in production paths.
- Missing authorization checks on sensitive but non-critical endpoints.
- Error handling gaps that cause cascading failures (e.g., unhandled exceptions in request middleware that crash the entire process).

### Medium

Assign to findings that degrade quality, maintainability, or performance but are unlikely to cause immediate failures:

- Performance issues that cause slowdowns under realistic load (N+1 queries, blocking in async contexts, O(n^2) algorithms on growing datasets).
- Anti-patterns that make the code significantly harder to maintain or extend (god objects, deep nesting, SRP violations).
- Missing input validation on internal APIs where the blast radius is limited.
- Insecure defaults that are partially mitigated by other layers (e.g., missing CORS headers behind an API gateway that enforces its own).

### Low

Assign to findings that represent minor quality issues with limited practical impact:

- Dead code (unused imports, unreachable branches, orphaned tests) that adds noise but does not affect runtime behavior.
- Minor code smells (magic numbers in non-critical paths, slightly duplicated code blocks).
- Commented-out code that should be cleaned up.
- Missing pagination on endpoints with currently small datasets but potential future growth.
