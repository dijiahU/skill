# FORGE Setup

Use this file to record the project's FORGE enforcement setup.

Sections marked `<!-- FORGE-section: <profile> -->` are included by `forge-bootstrap`
based on the project's `security_profile`. Bootstrap drops sections that exceed
the configured profile so the file does not carry dead checklist boilerplate.
Section gating order (each level adds the section above):

- always: Local Hooks, Agent Surfaces, CI Enforcement, External Tracker Access, Team Closeout, Release Reconciliation, Follow-Up
- `repo-fortress`: Branch Protection
- `ci-security`: CI Security, Supply Chain
- `full-devsecops`: Continuous Delivery Security

<!-- FORGE-section: always -->

## Local Hooks

- `pre-commit` installed: yes/no
- `commit-msg` installed: yes/no
- `pre-push` installed: yes/no
- Notes:

## Agent Surfaces

- Root `AGENTS.md` generated: yes/no
- Root `CLAUDE.md` generated: yes/no
- Cursor rules installed: yes/no
- Codex hooks installed: yes/no
- Copilot instructions installed: yes/no
- Windsurf rules installed: yes/no
- Agent-specific deviations from the shared FORGE policy:

## CI Enforcement

- `ci_enforcement` enabled in `docs/forge/AI.md`: yes/no
- `ci/` assets copied into the repo: yes/no
- Workflow or pipeline configured: yes/no
- Provider: GitHub / GitLab / other

## External Tracker Access

- Task source: local / github / gitlab / external
- Issue read verification method: CLI / MCP / read-only token / manual
- Issue assignment method: human / user PAT / project token / manual
- Token scope policy:
  - Prefer read-only project or service tokens for issue-state verification.
  - Use a human account or user-scoped token for assignment when claim ownership must represent the engineer.
  - Do not treat a bot-assigned issue as human ownership unless project policy explicitly allows it.

<!-- FORGE-section: repo-fortress -->

## Branch Protection

- Main branch protected: yes/no
- Release branch protected: yes/no
- Required FORGE checks enabled: yes/no
- CODEOWNERS or reviewer routing configured: yes/no
- Security policy / responsible disclosure documented: yes/no
- Risk or security dashboard owner:
- Coordination branch protected: yes/no
- Coordination branch name:

<!-- FORGE-section: ci-security -->

## CI Security

- Secret scanning enabled: yes/no/n/a
- SAST enabled: yes/no/n/a
- SAST tool: CodeQL / Semgrep / other
- Findings uploaded to SARIF or provider security UI: yes/no/n/a
- Dependency/SCA scanning enabled: yes/no/n/a
- Dependency update automation: Dependabot / Renovate / other / none
- Required security checks before merge: yes/no

## Supply Chain

- SBOM generated: yes/no/n/a
- SBOM tool or format:
- OSV or vulnerability scan in build: yes/no/n/a
- Artifact provenance/signing/attestation: yes/no/n/a
- Vulnerability triage owner:

<!-- FORGE-section: full-devsecops -->

## Continuous Delivery Security

- CD pipeline configured: yes/no/n/a
- Environment approvals documented: yes/no/n/a
- Infrastructure-as-code validation: yes/no/n/a
- DAST configured: yes/no/n/a
- Authenticated DAST documented: yes/no/n/a
- Preview/lab/cloud cleanup owner:
- Rollback procedure documented: yes/no/n/a

<!-- FORGE-section: always -->

## Team Closeout

- Merge semantics for integration: PR / squash / fast-forward-only / other
- Merge semantics for release promotion: PR / fast-forward-only / other
- Closeout helper used before integration: yes/no
- Closeout helper path or documented manual procedure:
- Tasks release active claim on `integrated` or `complete`: yes/no

## Release Reconciliation

- Release promotion process documented: yes/no
- Who confirms promotion into the release branch:
- How tasks are reconciled from `integrated` to `complete`:
- Release PR / release commit evidence recorded on tasks: yes/no

## Follow-Up

- Remaining setup tasks:
- Owner:
- Target date:
