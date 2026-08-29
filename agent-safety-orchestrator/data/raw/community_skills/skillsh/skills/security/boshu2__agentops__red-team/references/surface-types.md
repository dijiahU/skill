# Surface Types

Red-team v1 supports two surface types. Each surface defines what to probe, default personas, and entry points.

## Docs Surface

**What to probe:**

| Dimension | Question |
|-----------|----------|
| Discoverability | Can the persona find what they need from the entry point? |
| Completeness | Does the guide cover all steps without gaps? |
| Copy-paste readiness | Are commands ready to run without modification? |
| Jargon opacity | Are project-specific terms defined before use? |
| Navigation quality | How many hops to reach actionable content? |
| Prerequisite clarity | Are required tools, access, and knowledge stated upfront? |

**Default personas:** panicked-sre, junior-engineer, first-time-consumer

**Entry points:** README.md, docs/README.md

**Probing strategy:** Each persona starts from the entry point and attempts their goal-driven scenarios. The agent records every navigation step, noting friction points even on successful paths.

**Evidence requirements:** Every finding must include:
- File path and line number where the issue occurs
- Navigation path taken (entry_point -> file1 -> file2 -> ...)
- What the persona expected vs what they found
- Specific recommendation with actionable fix

## Skills Surface

**What to probe:**

| Dimension | Question |
|-----------|----------|
| Step executability | Can each step be followed without ambiguity? |
| Example coverage | Do quick start examples cover the main use case? |
| Error handling | What happens when a step fails? Is recovery documented? |
| Flag documentation | Are all flags listed with types, defaults, and examples? |
| Prerequisite declaration | Are dependencies and required tools stated? |
| Edge case handling | What happens with unusual input or missing files? |

**Default persona:** zero-context-agent

**Entry point:** `skills/<target>/SKILL.md`

**Probing strategy:** The zero-context-agent reads SKILL.md and attempts to execute the workflow step by step. It reports where instructions are ambiguous, where steps reference undefined terms, and where error recovery is missing.

## Deferred Surfaces (v2)

### Code Surface
Can a new contributor understand and modify a module? Are abstractions learnable? Is the API self-documenting?

### API/CLI Surface
Can a consumer integrate without tribal knowledge? Do error messages guide recovery? Are flags discoverable?

These surfaces require different probing strategies and are not yet validated by prototype.
