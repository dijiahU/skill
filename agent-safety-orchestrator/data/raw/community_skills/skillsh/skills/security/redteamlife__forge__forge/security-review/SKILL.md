---
name: forge-security-review
description: Apply FORGE checklist-based security review to a task. Use when selecting a task-specific security checklist, reviewing trust-boundary and sensitive-data impact, and producing explicit pass, n-a, or escalated outcomes for each item.
---

# FORGE Security Review

Use this skill after implementation and before completion.

## Workflow

1. Read the task's `task_type` from `docs/forge/TASKS.yaml` if available.
2. Apply the General checklist plus the relevant surface-specific sections in `docs/forge/SECURITY_CHECKLISTS.md`.
3. If the project was bootstrapped from the shared assets, use only the sections relevant to the active change rather than reading every possible checklist.
4. If the change adds or modifies automation for GitHub, GitLab, Jira, Linear, or another tracker, review token scope and assignee semantics.
5. If the change touches repository settings, CI, CD, dependency management, build artifacts, or deployment, apply the matching DevSecOps checklist sections.
6. Require an explicit outcome for every item: `pass`, `n/a`, or escalated.
7. If any unresolved concern remains, stop before evaluation.

## Notes

- Free-form narrative is not enough by itself.
- Prefer recording results in `docs/forge/EVALUATION.md`.
- Keep the review crisp and machine-checkable where possible.
- Prefer read-only project or service tokens for issue-state verification.
- Use a human account or user-scoped token for assignment when claim ownership must represent the engineer.
- Do not treat a bot-assigned issue as human ownership unless project policy explicitly allows it.
- Do not claim SAST, DAST, SCA, SBOM, branch protection, CODEOWNERS, or security-policy coverage exists unless setup evidence is recorded.
- If a project declares `security_profile: ci-security` or `full-devsecops`, missing configured checks are findings, not silent `n/a` results.
- If `docs/forge/SECURITY_CHECKLISTS.md` is missing for a team workflow that expects it, stop and ask for it to be created rather than inventing ad hoc criteria.
- Shared baseline assets live under `assets/security-checklists/` in the installed skill pack; bootstrap may compose a smaller project-local checklist from those assets.
