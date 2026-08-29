# security-suite

Operate the security suite for Codex with artifact discipline, composable scans, and policy-ready output.

## Codex Execution Profile

1. Treat `skills/security-suite/SKILL.md` as the canonical security-suite contract and `skills-codex/security-suite/SKILL.md` as the Codex-facing artifact.
2. Keep scan composition explicit: what ran, what evidence was captured, and what policy result followed.
3. Prefer concise, operator-ready summaries backed by durable artifacts.

## Guardrails

1. Do not hide partial coverage or failed tools.
2. Separate raw evidence from the final security judgment.
3. Keep outputs reproducible enough for later diffing and follow-up scans.
