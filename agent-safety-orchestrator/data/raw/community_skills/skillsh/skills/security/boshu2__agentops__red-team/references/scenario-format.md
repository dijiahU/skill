# Scenario Format

Scenarios define specific tasks a persona attempts during a red-team probe.

## YAML Schema

```yaml
title: string           # Human-readable scenario name
persona: string          # Which persona runs this scenario (name field)
surface: string          # docs | skills
task: string             # What the persona must accomplish
entry_point: string      # Where the persona starts (file path)
pass_criteria: string    # What constitutes success
fail_criteria: string    # What constitutes failure
max_steps: integer       # Maximum navigation/action steps allowed
```

## Auto-Generation Rules

When no custom scenarios exist in `.agents/red-team/scenarios/`, the skill auto-generates scenarios based on the target surface.

### Docs Surface

For each entry point (README.md, docs/README.md), generate scenarios probing:

1. **Discoverability** -- Can the persona find the feature/guide they need?
2. **Completeness** -- Does the guide cover all steps end-to-end?
3. **Copy-paste readiness** -- Are commands copy-pasteable without modification?
4. **Jargon opacity** -- Are terms defined before use?

Default: 4-6 scenarios per persona.

### Skills Surface

For the target SKILL.md, generate scenarios probing:

1. **Step executability** -- Can each execution step be followed without ambiguity?
2. **Example coverage** -- Do quick start examples cover the common use case?
3. **Error handling** -- What happens when a step fails? Is recovery documented?
4. **Flag clarity** -- Are all flags documented with defaults and examples?

Default: 3-5 scenarios per persona.

## Custom Scenarios

Projects define custom scenarios in `.agents/red-team/scenarios/*.yaml`. Each file can contain one or more scenario definitions.

## Example

```yaml
title: "Find runbook for ArgoCD sync failure"
persona: panicked-sre
surface: docs
task: "Starting from docs/README.md, find the runbook for ArgoCD ComparisonError and identify the recovery command"
entry_point: "docs/README.md"
pass_criteria: "Reach actionable runbook with copy-paste commands in <=3 navigation hops"
fail_criteria: "Cannot find runbook, or runbook lacks copy-paste commands, or requires >5 hops"
max_steps: 10
```
