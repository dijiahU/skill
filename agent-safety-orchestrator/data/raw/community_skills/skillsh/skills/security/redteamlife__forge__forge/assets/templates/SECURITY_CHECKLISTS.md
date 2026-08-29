# Security Checklists

This file is the project-local selection of the shared checklist assets in `assets/security-checklists/`.

Use the General checklist for every task, then apply the relevant surface-specific sections for the change.

## General

- [ ] Inputs are validated or safely constrained.
- [ ] Outputs that cross trust boundaries are encoded, filtered, or otherwise constrained appropriately.
- [ ] New permissions, access paths, or secrets handling are documented.
- [ ] Sensitive data exposure risk was reviewed.
- [ ] Logging and telemetry avoid leaking secrets, tokens, or sensitive user data.
- [ ] Dependency or integration changes were reviewed for trust-boundary impact.
- [ ] The outcome for each item is recorded in `docs/forge/EVALUATION.md` as `pass`, `n/a`, or escalated.

## Frontend

- [ ] User-controlled content is safely rendered and protected against XSS or unsafe HTML injection.
- [ ] Sensitive data is not exposed unnecessarily in the browser, local storage, or client logs.
- [ ] Authentication state, CSRF assumptions, and session handling are understood for browser flows.
- [ ] Frontend feature flags, admin routes, or hidden controls do not create false security assumptions.

## Backend

- [ ] Server-side authorization is enforced at the correct boundary and is not delegated only to the client.
- [ ] Input validation occurs before privileged actions, data writes, or downstream service calls.
- [ ] Error handling does not leak stack traces, secrets, or internal topology.
- [ ] Background jobs, workers, or internal service calls operate with the minimum required privilege.

## API

- [ ] Authentication and authorization are enforced consistently on every protected endpoint.
- [ ] Request schemas, parameter validation, and content-type handling are explicit.
- [ ] Rate limiting, abuse controls, or anti-automation protections were considered where relevant.
- [ ] API responses do not expose internal-only fields or sensitive identifiers unnecessarily.

## Repository Governance

- [ ] Branch protection or protected-branch rules match the documented release and integration branches.
- [ ] Required status checks are configured for governed merges.
- [ ] CODEOWNERS or equivalent reviewer routing exists for security-sensitive paths where the project requires it.
- [ ] `SECURITY.md` or an equivalent responsible-disclosure process exists when the repo is public or externally shared.

## CI Security

- [ ] Secret scanning is enabled or explicitly not applicable.
- [ ] SAST is enabled for the relevant language or framework, for example CodeQL or Semgrep.
- [ ] CI findings are visible in SARIF, the hosting provider security UI, or another documented review surface.
- [ ] Security checks are required before merge when the project security profile requires them.

## Supply Chain

- [ ] Dependency/SCA scanning is enabled or explicitly not applicable.
- [ ] Dependency update automation, such as Dependabot or Renovate, is documented when used.
- [ ] Builds can produce an SBOM when project policy, customers, or auditors require one.
- [ ] Vulnerability triage ownership and SLA expectations are documented.

## Continuous Delivery Security

- [ ] Deployment environments, approval gates, and rollback expectations are documented.
- [ ] Infrastructure-as-code changes are validated before deployment.
- [ ] DAST is configured or explicitly not applicable for deployable web services.
- [ ] Preview, lab, or cloud resources have cleanup ownership to avoid stale exposure and surprise cost.
