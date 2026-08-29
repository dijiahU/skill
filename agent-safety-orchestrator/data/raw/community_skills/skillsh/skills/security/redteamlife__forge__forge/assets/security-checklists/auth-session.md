# Auth And Session

- [ ] Credential, token, or session handling follows the system's intended trust boundary.
- [ ] Automation tokens use least privilege; issue-state checks prefer read-only tokens, and assignment tokens represent the intended owner.
- [ ] Session expiration, revocation, and logout behavior were considered where the change touches auth state.
- [ ] Password reset, MFA, or account recovery flows are not weakened by the change.
- [ ] Authorization checks are based on server-side truth, not client-provided role or ownership data.
