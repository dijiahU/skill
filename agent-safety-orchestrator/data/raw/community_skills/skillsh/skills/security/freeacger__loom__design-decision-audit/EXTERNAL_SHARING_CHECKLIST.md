# Design Decision Audit External Sharing Checklist

Scope: This checklist covers only `.agents/skills/design-decision-audit`.
Excluded from this checklist:
- `.agents/skills/design-decision-audit-workspace`
- `docs/reports`
- other repo files outside the skill directory

## Current Conclusion

This skill directory is close to external-shareable form for instruction review and skill design discussion.

It is not fully repo-independent:
- the skill still references repo conventions such as `AGENTS.md`, `CONTRIBUTING.md`, `docs/design-docs/design-decision-checklist.md`, and `docs/reports/`
- the eval set still assumes the target repo contains matching relative paths

## Already Desensitized

- Local absolute filesystem paths have been removed from the skill directory
  - No machine-specific absolute paths remain in this directory
- Local username exposure has been removed from the skill directory
- Eval file references now use repo-relative paths
  - examples:
    - `.agents/skills/design-decision-audit/evals/files/...`
    - `AGENTS.md`
    - `docs/design-docs/design-decision-checklist.md`
- No obvious secret patterns were found in this directory
  - no API keys
  - no access tokens
  - no private keys
  - no password-like assignments
- No obvious real-user identifiers were found in this directory
  - no test UIDs
  - no order IDs
  - no business emails
  - no balance snapshots

## Intentionally Retained

- Skill behavior and review contract design
  - triggered modules
  - findings format
  - report-path logic
  - standalone override rules
  - conflicting-checklist priority rules
- Repo integration assumptions
  - `AGENTS.md`
  - `CONTRIBUTING.md`
  - `docs/design-docs/design-decision-checklist.md`
  - `docs/reports/`
- Eval sample semantics needed for audit quality
  - migration strategy
  - rollback
  - backward compatibility
  - observability
  - state machine
  - concurrency
  - async job isolation
  - semi-structured payload
  - conflicting checklist selection
- Project-facing file layout assumptions inside evals
  - `docs/exec-plans/completed/...`
  - `.agents/skills/design-decision-audit/evals/files/...`

## Residual External Sharing Risks

- Project coupling remains
  - readers outside this repo may not have the referenced files or directories
- Eval prompts reveal repo structure
  - even though they no longer reveal local machine paths, they still reveal internal repo layout
- Terminology is still domain-specific
  - some sample docs use project-flavored field names and review expectations

## Recommended Before External Distribution

- Safe to share as-is when:
  - the audience only needs the skill logic
  - the audience can read repo-relative examples as examples
  - the audience does not need runnable evals in another repo

- Adjust before sharing outside the repo when:
  - the recipient needs a repo-agnostic skill package
  - the recipient should not see internal repo structure
  - the evals must run in a different repository

## Minimal Additional Cleanup If Needed

- Replace repo-specific references with neutral placeholders
  - `AGENTS.md` -> `project review guide`
  - `docs/design-docs/design-decision-checklist.md` -> `project design checklist`
  - `docs/reports/` -> `project report directory`
- Swap the one real repo plan path in evals for a synthetic sample file
  - `docs/exec-plans/completed/2026-03-09-user-language-field-remediation-implementation-plan.md`
- Keep current design semantics
  - do not remove migration, compatibility, state, or observability signals
  - those signals are required for the skill to remain meaningful

## Verification Snapshot

- Files checked:
  - `SKILL.md`
  - `agents/openai.yaml`
  - `evals/evals.json`
  - `evals/files/*`
- Scan result:
  - no local absolute path
  - no obvious secret token pattern
  - no obvious business identifier pattern
