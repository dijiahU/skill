# FORGE DevSecOps Gates

Use this reference when a project asks for stronger security governance,
repository hardening, CI/CD security checks, supply-chain controls, or audit
evidence.

## Security Profiles

- `baseline`: task-local security review with project checklists.
- `repo-fortress`: baseline plus branch protection, CODEOWNERS, security policy,
  and repository risk visibility.
- `ci-security`: repo-fortress plus every-commit SAST, secret scanning,
  dependency/SCA checks, and SARIF or equivalent reporting.
- `full-devsecops`: ci-security plus CD pre-flight gates, DAST where applicable,
  SBOM generation, artifact/dependency provenance, and cleanup/rollback records.

## Repository Controls

Record in `docs/forge/SETUP.md`:

- branch protection and required status checks
- CODEOWNERS or equivalent reviewer routing
- `SECURITY.md` or responsible-disclosure process
- dashboard or metrics owner for risk, open findings, and gate health

## CI Controls

Use only tools the project actually runs. Common examples:

- secret scanning
- SAST, such as CodeQL or Semgrep
- dependency/SCA scanning, such as Dependabot, OSV-Scanner, or provider-native
  dependency review
- SARIF upload or comparable finding visibility

## CD Controls

For deployable services, record:

- environment separation and approval policy
- infrastructure-as-code validation
- DAST or authenticated DAST where practical
- rollback, cleanup, and cloud-cost cleanup expectations for lab or preview
  environments

## Supply Chain

For build artifacts or shipped software, record:

- dependency update automation
- vulnerability triage ownership
- SBOM generation and storage
- artifact provenance, signing, or attestation if required by project policy

## Gate Behavior

FORGE should not pretend these controls exist. If a task relies on a security
gate that is not actually configured, record it as missing setup evidence rather
than marking it pass.

