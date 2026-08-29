# security

Run repository security work in Codex with severity-first findings, gate-aware triage, and explicit remediation paths.

## Codex Execution Profile

1. Treat `skills/security/SKILL.md` as the canonical security contract and `skills-codex/security/SKILL.md` as the Codex-facing artifact.
2. Lead with concrete findings, blocked release conditions, and the evidence that triggered them.
3. Keep output structured so release and implementation flows can act on it immediately.

## Guardrails

1. Do not blur informational noise with real release blockers.
2. Prefer exact files, scanners, and commands over generic security prose.
3. Call out missing tooling or incomplete coverage explicitly.
