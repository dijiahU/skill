# Acceptance — Seed Phrase Recovery Planner

## Structure Check
- [x] Directory: `/Users/jianghaidong/.openclaw/skills/seed-phrase-recovery-planner`
- [x] Files present: `SKILL.md` (exactly), `skill.json` (exactly), `ACCEPTANCE.md` (exactly)
- [x] No handler.py, scripts/, tests/, README.md, assets/, references/

## No Code Execution
- [x] `skill.json` has `no_code_execution: true`
- [x] SKILL.md does not describe any code execution, API calls, wallet connections, or live chain queries
- [x] No runtime dependencies or external integrations

## Content Quality
- [x] SKILL.md is English-first with clear structure
- [x] SKILL.md frontmatter has `name` and `description` fields only
- [x] skill.json is valid JSON and contains all required fields
- [x] Safety boundaries section is present and explicit
- [x] Refusal examples are included
- [x] Output format is defined
- [x] Workflow is described step-by-step

## Safety & Legal Boundaries
- [x] Does not claim to perform actions beyond descriptive analysis
- [x] Does not provide financial, legal, investment, or tax advice
- [x] Includes explicit disclaimers about what the skill cannot do
- [x] All safety warnings reference that information is user-provided and unverified

## Pre-Publish Checklist
- [ ] Verify no Chinese paragraphs in SKILL.md (proper nouns only if needed)
- [ ] Verify skill.json parses with `python3 -m json.tool`
- [ ] Confirm no files beyond the three expected files
- [ ] Confirm slug does not conflict with existing skills
