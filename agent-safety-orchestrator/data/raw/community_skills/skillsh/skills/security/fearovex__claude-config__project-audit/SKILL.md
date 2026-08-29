---
name: project-audit
description: >
  Deep diagnostic of Claude/SDD configuration. Read-only. Produces audit-report.md consumed by /project-fix.
  Trigger: /project-audit, audit project, review claude config, project health check.
format: procedural
---

# project-audit

> Deep diagnostic of Claude/SDD configuration. Read-only. Produces a structured report that /project-fix consumes as its spec.

**Triggers**: `/project-audit`, audit project, review claude config, sdd diagnostic, project health check

---

## Role in SDD meta-config flow

This skill is the **equivalent of the SPEC phase** of the SDD cycle, applied to the project configuration:

```
/project-audit  →  audit-report.md  →  /project-fix  →  /project-audit (verify)
     (spec)           (artifact)          (apply)           (verify)
```

The generated report IS the specification that `/project-fix` implements. Without audit, there is no fix.

**Absolute rule**: This skill NEVER modifies files. It only reads and reports.

---

## Output artifact

When finished, save the report at:

```
[project_root]/.claude/audit-report.md
```

This file persists between sessions and is the input for `/project-fix`.

---

## Audit Kernel

`project-audit` operates as a stable read-only kernel with three stages:

| Stage             | Responsibility                                                      | Output                                                     |
| ----------------- | ------------------------------------------------------------------- | ---------------------------------------------------------- |
| Discovery         | Gather structural facts from the project and runtime environment    | Presence/absence facts, path resolution, baseline metadata |
| Evaluation        | Apply the dimension rules to the discovered facts and file contents | Findings, score, violations, required actions              |
| Report generation | Render the audit state into a persistent artifact                   | `.claude/audit-report.md`                                  |

The kernel is intentionally stable. Detailed dimension rules can evolve, but the command remains: discover, evaluate, report.

---

## Dimension Classes

`project-audit` uses two dimension classes.

| Class                    | Dimensions                      | Score impact                      | Role                                                              |
| ------------------------ | ------------------------------- | --------------------------------- | ----------------------------------------------------------------- |
| Scored dimensions        | D1, D2, D3, D4, D6, D7, D8     | Contribute to the 100-point score | Determine operational health and SDD readiness                    |
| Informational dimensions | D9, D10, D11, D12, D13, D14    | No base-score impact              | Surface quality debt, coverage gaps, and internal inconsistencies |

Notes:

- D5 was intentionally removed in an earlier change and is not part of the current model.
- Informational dimensions may still emit actionable findings, but they do not change the base 100-point score unless a dimension explicitly states otherwise.

---

## Compatibility Policy

Compatibility behavior is a separate policy layer of `project-audit`, not an implicit side effect of individual dimensions.

Compatibility rules currently include:

- **Repo-shape compatibility**: global-config repos may use root `CLAUDE.md`, and local skill discovery may resolve to `skills/` instead of `.claude/skills/`.
- **Historical terminology compatibility**: archived materials may still mention older section labels, but active skill validation uses the canonical `## Process` and `## Rules` headings.
- **Non-scored extension compatibility**: informational dimensions may evolve without changing the base scoring model.

This policy MUST be explicit whenever compatibility behavior affects how a finding is evaluated.

---

## Process

I run all dimensions systematically, reading real files. Never assume.

---

### Dimension 1 — CLAUDE.md

**Objective**: Verify that the project's CLAUDE.md is complete, accurate, and enables SDD.

**Project type detection (run before checks):**

Check if the project is a `global-config` repo:

- Condition A: `install.sh` + `sync.sh` exist at project root, OR
- Condition B: project root contains `skills/` directory with SDD phase skills

If detected as global-config:

- Accept `CLAUDE.md` at root as equivalent to `.claude/CLAUDE.md`
- Note in report header: `Project Type: global-config`
- The CLAUDE.md path check passes without penalty

**Checks to run:**

| Check                                                                    | How I verify                                 | Severity if fails |
| ------------------------------------------------------------------------ | -------------------------------------------- | ----------------- |
| Exists `.claude/CLAUDE.md` (or root `CLAUDE.md` for global-config repos) | Attempt to read it                           | ❌ CRITICAL       |
| Not empty (>50 lines)                                                    | Count lines                                  | ❌ CRITICAL       |
| Has Stack section                                                        | Search for `## Tech Stack` or `## Stack`     | ⚠️ HIGH           |
| Stack matches package.json/pyproject.toml                                | Read both, compare key versions              | ⚠️ HIGH           |
| Has Architecture section                                                 | Search for `## Architecture`                 | ⚠️ HIGH           |
| Has Skills registry                                                      | Search for skills table                      | ⚠️ HIGH           |
| Has Unbreakable Rules                                                    | Search for `## Unbreakable Rules` or similar | ⚠️ MEDIUM         |
| Has Plan Mode Rules                                                      | Search for `## Plan Mode`                    | ℹ️ LOW            |
| Mentions SDD (any `/sdd-*` command)                                      | Search for text `/sdd-`                      | ⚠️ HIGH           |
| References to ai-context/ are correct                                    | Verify that mentioned paths exist            | ⚠️ MEDIUM         |

**For the stack**: I read `package.json` (or equivalent), extract the 5-10 most important dependencies, and compare with what is declared in CLAUDE.md. I report specific discrepancies with declared version vs real version.

**Template path verification (D1 additive check):**

1. Read CLAUDE.md and locate the `## Documentation Conventions` section (or equivalent section referencing `docs/templates/`).
2. Extract all paths matching the pattern `docs/templates/*.md` from that section.
3. For each extracted path, check whether the file exists on disk at `[project_root]/[path]`.
4. Skip this check entirely if no `docs/templates/*.md` pattern is found in CLAUDE.md — no finding is emitted.

**Scoring rule:**

- For each missing template path: emit a MEDIUM finding — "Template path referenced in CLAUDE.md does not exist on disk: [path]"
- Add each missing path to `required_actions.medium` in the FIX_MANIFEST with `type: create_file`, `target: [path]`, `reason: "Template path referenced in CLAUDE.md does not exist on disk"`
- One finding per missing path (multiple missing paths produce multiple separate findings)

---

### Dimension 2 — Memory (ai-context/)

**Objective**: Verify that the memory layer exists, has substantial content, and is coherent with the real code.

**Existence checks:**

| File                         | Minimum acceptable lines                        |
| ---------------------------- | ----------------------------------------------- |
| `ai-context/stack.md`        | > 30 lines                                      |
| `ai-context/architecture.md` | > 40 lines                                      |
| `ai-context/conventions.md`  | > 30 lines                                      |
| `ai-context/known-issues.md` | > 10 lines (can be brief if the project is new) |
| `ai-context/changelog-ai.md` | > 5 lines (at least one entry)                  |

**Content checks** (for each file that exists):

- **stack.md**: Does it mention the same versions as package.json? I look for the top-5 project dependencies and verify they are documented.
- **architecture.md**: Does it mention directories that actually exist in the project? I read the folder tree and cross-check.
- **conventions.md**: Do the documented conventions mention patterns used in the real code? I take 2-3 sample files and verify.
- **known-issues.md**: Does it have real content or is it an empty template? I search for phrases like "[To confirm]" or "[Empty]".
- **changelog-ai.md**: Does it have at least one entry with a date? I verify the format `## YYYY-MM-DD`.

**Note on location**: The path can be `ai-context/` (without docs/) or `docs/ai-context/`. I check both.

**Placeholder phrase detection (D2 additive check):**

While reading each `ai-context/*.md` file (already read for line-count and content checks), scan the full file content for the following placeholder phrases:

- `[To be filled]`, `[empty]`, `[TBD]`, `[placeholder]`, `[To confirm]`, `[Empty]` — case-insensitive match on bracket-enclosed variants (e.g., `[todo]` and `[TODO]` both match)
- `TODO` — plain text, case-sensitive (exact uppercase match)

**Scoring rule — placeholder detection:**

- For each `ai-context/*.md` file whose content contains one or more of the above phrases: emit a HIGH finding — "[filename] appears to contain unfilled placeholder content"
- Treat such a file as functionally empty even if it passes the line-count check (do not award content/coherence points for that file)
- Add the finding to `required_actions.high` in the FIX_MANIFEST with `type: update_file`, `target: [ai-context/filename]`, `reason: "File contains placeholder content and has not been filled in"`

**stack.md technology version count (D2 additive check):**

After reading `ai-context/stack.md` (already read for content checks), count the number of lines that contain a version-like string matching any of these patterns:

- `x.y` (e.g., `3.4`, `19.0`)
- `x.y.z` (e.g., `19.0.0`, `5.4.2`)
- `vX` where X is a digit (e.g., `v3`, `v21`)

**Scoring rule — version count:**

- If the count is fewer than 3: emit a MEDIUM finding — "stack.md lists fewer than 3 technologies with concrete versions — minimum is 3"
- Add to `required_actions.medium` in the FIX_MANIFEST with `type: update_file`, `target: ai-context/stack.md`, `reason: "stack.md lists fewer than 3 technologies with concrete versions — minimum is 3"`
- Skip this check if `stack.md` does not exist or contains placeholder content (already caught by the placeholder check above)

**Additional sub-checks — User documentation freshness:**

For each of the following files, apply identical logic:

- `ai-context/scenarios.md`
- `ai-context/quick-reference.md`

Logic per file:

1. If the file does NOT exist → emit LOW finding: `"[filename] missing — create via /project-onboard or manually following the template in ai-context/"`
2. If the file exists → read first 10 lines and search for `^> Last verified: (\d{4}-\d{2}-\d{2})$`
   - Field absent or malformed → emit LOW: `"Last verified field not found or malformed in [filename]"`
   - Field present and date ≤ 90 days from today → no finding
   - Field present and date > 90 days from today → emit LOW: `"[filename] stale ([N] days since last verification) — run /project-update to refresh"`

**Severity note**: All findings for these sub-checks are LOW (informational). They do NOT deduct from the D2 numeric score.

---

### Dimension 3 — SDD Orchestrator

**Objective**: Verify that the SDD cycle is fully operational in this project.

**Sub-checks:**

#### 3a. Global SDD skills (prerequisite for everything else)

I read whether the 8 files exist in `~/.claude/skills/`:

- `sdd-explore/SKILL.md`
- `sdd-propose/SKILL.md`
- `sdd-spec/SKILL.md`
- `sdd-design/SKILL.md`
- `sdd-tasks/SKILL.md`
- `sdd-apply/SKILL.md`
- `sdd-verify/SKILL.md`
- `sdd-archive/SKILL.md`

If any is missing → ❌ CRITICAL (SDD cannot function without the phases).

#### 3b. Engram availability

Check if Engram MCP is reachable (call `mem_context`):
- If reachable: active mode = `engram`. Log `INFO: project uses engram mode`.
- If not reachable: active mode = `none`. Log `WARNING: Engram not reachable — SDD artifacts will not persist`.

| Check                                                    | Severity                                         |
| -------------------------------------------------------- | ------------------------------------------------ |
| Engram MCP is reachable                                  | ⚠️ HIGH (SDD artifacts won't persist without it) |

#### 3c. CLAUDE.md mentions SDD

| Check                               | Severity |
| ----------------------------------- | -------- |
| Contains any `/sdd-*` command       | ⚠️ HIGH  |
| Has section explaining the SDD flow | ℹ️ LOW   |

#### 3d. Orphaned changes

I search engram for active SDD changes that appear stale (no activity in >14 days):
```
mem_search(query: "sdd/", project: "{project}")
```
Filter for changes with state artifacts whose `last_updated` is >14 days ago and that have no `archive-report`.

I list:

```
Orphaned changes detected:
  - change-name: last completed phase "tasks" (X days inactive)
```

#### 3e. Hook script existence (D3 additive check)

1. If `ROOT_SETTINGS_JSON_EXISTS=1`, read `settings.json` at project root.
2. If `DOTCLAUDE_SETTINGS_JSON_EXISTS=1`, read `.claude/settings.json`.
3. If `SETTINGS_LOCAL_JSON_EXISTS=1`, read `settings.local.json` at project root.
4. For each file read above, locate the `hooks` key in the JSON content and extract all script path values (strings inside hook event arrays or as direct values within the `hooks` object).
5. For each extracted script path, check whether the file exists on disk at `[project_root]/[path]`.
6. Skip this entire check (emit no finding) when no file that was read contains a `hooks` key.

**Scoring rule — hook script existence:**

- For each script path that does NOT exist on disk: emit a HIGH finding — "Hook script referenced in [filename] not found on disk: [path]"
- Add each missing script to `required_actions.high` in the FIX_MANIFEST with `type: create_file`, `target: [path]`, `reason: "Hook script referenced in [filename] not found on disk"`
- Emit no finding when no `hooks` key is present in any settings file

#### 3f. Active changes conflict detection (D3 additive check)

1. Search engram for all active SDD changes (those without an `archive-report` topic_key). List their design artifacts.
2. For each active change that has a design artifact: retrieve the design via `mem_get_observation` and locate the `## File Change Matrix` section (or equivalent table with a `File` column).
3. Extract all file paths from the `File` column of that table.
4. Normalize each extracted path: convert to lowercase and strip any leading `./` prefix.
5. Skip this entire step (emit no finding) if fewer than two active changes have a `design.md`.

**Scoring rule — conflict detection:**

- Compute the set intersection of normalized file paths across all active changes that have a `design.md`.
- For each file path that appears in two or more active changes: emit a MEDIUM finding — "Concurrent file modification conflict detected: [path] is targeted by both [change-A] and [change-B]"
- Add each conflicting path to `violations[]` in the FIX_MANIFEST (NOT to `required_actions`) with `rule: "D3-active-changes-conflict"`, `severity: "medium"`, and `file: [path]`
- If no overlapping paths exist after intersection, emit no finding

**Limitation note**: path normalization only handles `lowercase + strip leading ./`. Other format inconsistencies (e.g., absolute vs relative paths, different separators) are not caught.

---

### Dimension 4 — Skills Quality

**Objective**: Verify that skills are substantial and that the registry in CLAUDE.md is accurate.

**Checks:**

#### 4a. Registry vs disk (bidirectional)

- For each skill listed in CLAUDE.md → I verify that the file/directory exists in `.claude/skills/`
- For each file in `.claude/skills/` → I verify that it is listed in CLAUDE.md
- I report: skills in registry but not on disk / skills on disk but not in registry

#### 4b. Minimum content

For each skill file (`.md` or directory with `SKILL.md`):

- Does it have more than 30 lines? → If not, it is probably a stub
- **Format-aware structural check** (see `docs/format-types.md` for the authoritative contract):
  1. Parse YAML frontmatter block (content between the first `---` pair at the start of the file). Extract `format:` value. If no frontmatter or no `format:` key → treat as `procedural`.
  2. If `format:` value is not one of `procedural`, `reference`, `anti-pattern` → emit INFO finding: `"Unknown format value '[value]' in [skill-name] — defaulting to procedural check"` and treat as `procedural`.
  3. Apply the check for the resolved format:

| Resolved format                  | Required section               | Accepted headings (any one satisfies)         | Finding if absent                                                                                                          |
| -------------------------------- | ------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `procedural` (or absent/unknown) | Process section                | `## Process`                                  | MEDIUM: "procedural skill [name] missing ## Process section"                                                               |
| `reference`                      | Patterns section (one of)      | `## Patterns` OR `## Critical Patterns`       | MEDIUM: "reference skill [name] missing (## Patterns or ## Critical Patterns) or (## Examples or ## Code Examples) section" |
| `reference`                      | Examples section (one of)      | `## Examples` OR `## Code Examples`           | (same finding — emitted when skill lacks both a pattern section AND an examples section, or has one but not the other)    |
| `anti-pattern`                   | Anti-patterns section (one of) | `## Anti-patterns` OR `## Critical Patterns`  | MEDIUM: "anti-pattern skill [name] missing ## Anti-patterns or ## Critical Patterns section"                               |

> **Validation logic for `reference` format**: A reference skill passes D4b if it has **at least one** of `## Patterns`/`## Critical Patterns` AND **at least one** of `## Examples`/`## Code Examples`. Use regex alternation: `^## (Patterns|Critical Patterns)` and `^## (Examples|Code Examples)` (case-sensitive). Emit the MEDIUM finding only when either condition is unsatisfied.

4. Missing `**Triggers**` and missing `## Rules` remain MEDIUM findings for **all** format types (unchanged).
5. For a `reference` or `anti-pattern` skill: missing `## Process` is **not a finding**.

Add each missing-section finding to `required_actions.medium` in the FIX_MANIFEST with:

```
type: skill_quality_action
action_type: add_missing_section
target: [skill path]
missing_sections: ["[section heading]"]
```

#### 4c. Relevant global tech skills coverage (scored: 0–10 pts)

I read the project stack (package.json) and identify which global technology skills in `~/.claude/skills/` are applicable but not yet installed in the project:

| If project uses | Available global skill |
| --------------- | ---------------------- |
| React 18+       | `react-19/SKILL.md`    |
| Next.js 14+     | `nextjs-15/SKILL.md`   |
| TypeScript      | `typescript/SKILL.md`  |
| Zustand         | `zustand-5/SKILL.md`   |
| Tailwind        | `tailwind-4/SKILL.md`  |
| Zod             | `zod-4/SKILL.md`       |
| Playwright      | `playwright/SKILL.md`  |

**Scoring rubric:**

| Coverage                                                                          | Points |
| --------------------------------------------------------------------------------- | ------ |
| No relevant global skills detected in stack, OR all applicable ones already added | 10     |
| ≥ 75% of applicable global skills installed                                       | 8      |
| 50–74% installed                                                                  | 5      |
| 25–49% installed                                                                  | 2      |
| < 25% installed (relevant skills exist but none added)                            | 0      |

"Applicable" means: the project stack uses the technology AND a matching global skill exists in `~/.claude/skills/`. Projects with no matching global skills get full credit automatically.

**D4 maximum: 20 points** (4a+4b registry and content = 10 pts; 4c global skills coverage = 10 pts)

---

### Dimension 6 — Cross-reference Integrity

**Objective**: Everything referenced in the Claude configuration must exist on disk.

**Checks:**

| What I verify                     | Where I search for references                                          |
| --------------------------------- | ---------------------------------------------------------------------- |
| Docs referenced in CLAUDE.md      | Section `## Documentation` → `.claude/docs/`                           |
| Templates referenced in CLAUDE.md | Templates section → `.claude/templates/`                               |
| Paths mentioned in skills         | Scan of skills searching for paths (`/lib/`, `/domain/`, `pages/api/`) |
| Paths mentioned in ai-context/    | Verify that dirs documented in architecture.md exist                   |
| Skill files mentioned in commands | If a command imports or references a skill                             |

For each broken reference: I report the source file, approximate line, and the path that does not exist.

---

### Dimension 8 — Testing & Verification Integrity

**Objective**: Verify that the project requires and evidences real tests before archiving SDD changes.

**Checks:**

#### 8a. Project has testing configuration

| Check                                             | Severity  |
| ------------------------------------------------- | --------- |
| Project has test runner configured or detectable   | ⚠️ HIGH   |
| Has documented testing strategy (in ai-context/)   | ⚠️ MEDIUM |

#### 8b. Archived changes have verify-report

Search engram for archive-report artifacts and check whether corresponding verify-report artifacts exist:

- Does `verify-report` exist for each archived change? If not → ⚠️ HIGH
- Does it mention tool execution results? If not → ⚠️ HIGH

I report:

```
Archived changes without verify-report: [list]
```

#### 8c. Active changes have verification criteria defined

Search engram for active SDD changes (those with tasks but no archive-report):

- If it has `tasks` → does the task plan include verification criteria?
- If it has `design` → does the design define how the change will be tested?

---

### Dimension 7 — Architecture Compliance

**Objective**: Verify whether the project's architecture matches its documented baseline by reading the output of `/project-analyze`.

**Input**: `analysis-report.md` at the project root (produced by the `project-analyze` skill).

**Scoring table:**

| Condition                                     | Score | Severity | Message                                                   |
| --------------------------------------------- | ----- | -------- | --------------------------------------------------------- |
| `analysis-report.md` absent                   | 0/5   | CRITICAL | "Run /project-analyze first, then re-run /project-audit." |
| Present + `ai-context/architecture.md` absent | 2/5   | HIGH     | "No architecture baseline to compare against."            |
| Drift summary = `none`                        | 5/5   | OK       |                                                           |
| Drift summary = `minor`                       | 3/5   | MEDIUM   | List drift entries from `analysis-report.md`              |
| Drift summary = `significant`                 | 0/5   | HIGH     | List drift entries from `analysis-report.md`              |

**Staleness penalty (D7 additive scoring modifier):**

After computing the drift-based D7 score (using the scoring table above), apply the staleness penalty as follows:

1. This penalty applies ONLY when `ANALYSIS_REPORT_EXISTS=1` (i.e., the file exists). When the file is absent, D7 is already 0/5 — no further deduction.
2. Parse `ANALYSIS_REPORT_DATE` from Phase A. Compute the age in days: `current_audit_date − ANALYSIS_REPORT_DATE`.
3. Apply the deduction:
   - Age ≤ 30 days → no penalty; no staleness finding emitted
   - Age 31–60 days → deduct 1 point from the drift-based score (floor: 0); emit a staleness warning: "analysis-report.md is [N] days old (> 30 days) — staleness penalty applied"
   - Age > 60 days → deduct 2 points from the drift-based score (floor: 0); emit a staleness warning: "analysis-report.md is [N] days old (> 60 days) — staleness penalty applied"
4. The staleness penalty stacks with the drift penalty: a `minor` drift score of 3/5 with a 40-day-old report becomes 2/5. The combined score floor is 0 — never negative.

**Staleness scoring tiers:**

| Age of analysis-report.md | Staleness deduction |
| ------------------------- | ------------------- |
| ≤ 30 days                 | None                |
| 31–60 days                | −1 pt (floor: 0)    |
| > 60 days                 | −2 pts (floor: 0)   |

_Staleness penalty stacks with drift penalty; floor is 0._

**Drift entries**: When drift summary is `minor` or `significant`, read the `## Architecture Drift` section of `analysis-report.md` and list each entry in the D7 output block.

**FIX_MANIFEST rule**: D7 violations go in `violations[]` only — NOT in `required_actions`. The `/project-fix` skill does not auto-fix architecture drift.

---

### Dimension 9 — Project Skills Quality

**Objective**: Audit the project's local skills directory against quality criteria and the global skill catalog.

**D9-1. Skip condition**

Read `$LOCAL_SKILLS_DIR` from the Phase A output. Check whether `$LOCAL_SKILLS_DIR` exists in the target project.

If it does NOT exist:

```
No [value of $LOCAL_SKILLS_DIR] directory found — Dimension 9 skipped.
```

No score deduction. Do not add `skill_quality_actions` to FIX_MANIFEST.

If it exists, proceed with D9-2 through D9-5 for each subdirectory found.

**Note — global-config circular detection**: When auditing the global-config repo itself, `$LOCAL_SKILLS_DIR` resolves to `"skills"` (root level). In this case every subdirectory under `skills/` will have a matching counterpart in `~/.claude/skills/` because they are the same files deployed by `install.sh`. D9-2 duplicate detection will assign disposition `keep` for all of them — this is correct and expected behavior (they are the source of truth, not duplicates).

**D9-2. Duplicate detection**

For each subdirectory `<name>` under `.claude/skills/`:

- Check whether `~/.claude/skills/<name>/` exists (exact directory name match)
- If it exists → candidate disposition: `move-to-global` (if local differs from global) or `delete` (if identical)
- If the global catalog is unreadable → emit `Global catalog unreadable — duplicate check skipped` at INFO level; assign disposition `keep`

**D9-3. Structural completeness**

Read each local `.claude/skills/<name>/SKILL.md`. Apply the same format-aware check as D4b (see `docs/format-types.md` for the authoritative contract):

1. Parse YAML frontmatter block (content between the first `---` pair). Extract `format:` value. If absent → treat as `procedural`.
2. If `format:` value is unrecognized → emit INFO finding and treat as `procedural`.
3. Apply the format-to-required-section check:

| Resolved format                  | Required section               | Accepted headings (any one satisfies)        | Finding if absent |
| -------------------------------- | ------------------------------ | -------------------------------------------- | ----------------- |
| `procedural` (or absent/unknown) | Process section                | `## Process`                                 | record as missing |
| `reference`                      | Patterns section (one of)      | `## Patterns` OR `## Critical Patterns`      | record as missing |
| `reference`                      | Examples section (one of)      | `## Examples` OR `## Code Examples`          | record as missing |
| `anti-pattern`                   | Anti-patterns section (one of) | `## Anti-patterns` OR `## Critical Patterns` | record as missing |

4. Missing `**Triggers**` and `## Rules` are checked for **all** format types (unchanged).
5. For `reference` or `anti-pattern` skills: missing `## Process` is **not a finding**.

If any required section is absent:

- Record missing sections per skill
- Assign disposition: `update`
- Action: `add_missing_section`

If no `SKILL.md` exists in the directory:

- Record as `SKILL.md missing`
- Assign disposition: `update`
- Action: `add_missing_section`

**D9-4. Language compliance**

Apply the D4e language-compliance heuristic (defined in Dimension 4) to the body text of each local `SKILL.md` outside fenced code blocks.

If non-English prose is found:

- Disposition: `update`
- Action: `flag_language_violation`
- Severity: INFO only — no score deduction

**D9-5. Stack relevance**

Extract technology references from the trigger line and title of each local `SKILL.md`.

If a technology name is absent from BOTH `ai-context/stack.md` AND `package.json`/`pyproject.toml`:

- Disposition: `update`
- Action: `flag_irrelevant`
- Severity: INFO only

If neither stack source (`stack.md` nor `package.json`/`pyproject.toml`) is found:

```
Stack relevance check skipped — no stack source found
```

---

### Dimension 10 — Feature Docs Coverage

**Objective**: Detect feature/skill documentation gaps across the project using either config-driven or heuristic discovery, and report coverage per feature. Informational only — no score impact.

**Skip condition**: If no features are detected (neither config-driven nor heuristic) → emit INFO: 'No feature directories detected — Dimension 10 skipped.' No score impact.

**Phase A discovery extension**: This dimension reads the `FEATURE_DOCS_CONFIG_EXISTS` variable produced by the Phase A bash script (see Rule 8). If `FEATURE_DOCS_CONFIG_EXISTS=1`, use config-driven detection. If `0`, fall back to heuristic detection.

#### Config-driven detection

If a project `config.yaml` exists and contains a `feature_docs:` key:

- Read the `convention` field (`skill` | `markdown` | `mixed`)
- Read the `paths` list (directories to scan for feature docs)
- Read the `feature_detection` block: `strategy` (`directory` | `prefix` | `explicit`), `root` (root directory whose subdirs are treated as features), and `exclude` list

Use this configuration as the source of truth for feature names and doc locations.

#### Heuristic detection fallback

If no `feature_docs:` key is present in the project config, run the following heuristic algorithm:

```
heuristic_sources = []

# Source 1: non-SDD skills in $LOCAL_SKILLS_DIR
if $LOCAL_SKILLS_DIR exists:
    for each subdirectory name in $LOCAL_SKILLS_DIR:
        if name does NOT start with: sdd-, project-, memory-, skill-:
            add to heuristic_sources as type=skill

# Source 2: markdown files in docs/features/ or docs/modules/
if docs/features/ exists:
    add each *.md file as type=markdown, feature_name = filename without extension
if docs/modules/ exists:
    add each *.md file as type=markdown, feature_name = filename without extension

# Source 3: subdirs of src/features/, src/modules/, app/ with README.md
for each candidate_root in [src/features/, src/modules/, app/]:
    if candidate_root exists:
        for each subdirectory:
            if subdirectory/README.md exists:
                add as type=markdown, feature_name = subdirectory name

# Exclusion list — always skip these directory/feature names:
EXCLUDE = [shared, utils, common, lib, types, hooks, components]

if heuristic_sources is empty (after exclusions):
    emit INFO: "No feature directories detected — Dimension 10 skipped."
    skip all four checks
```

#### D10 checks (run per detected feature)

**D10-a Coverage**: Verify that each detected feature has a corresponding documentation file.

- If `convention=skill`: PASS (✅) if `$LOCAL_SKILLS_DIR/<feature_name>/SKILL.md` exists; FAIL (⚠️) otherwise
- If `convention=markdown`: PASS (✅) if at least one `.md` file in the configured paths references `feature_name`; FAIL (⚠️) otherwise
- If `convention=mixed`: PASS (✅) if either a skill or a markdown doc is found; FAIL (⚠️) otherwise

**D10-b Structural Quality**: Verify that the found documentation has proper structure.

- If doc is a `SKILL.md`: PASS (✅) if frontmatter (`---` block) present AND `**Triggers**`/`## Triggers` defined AND `## Process` section AND `## Rules` section; WARN (⚠️) if any of the above is missing
- If doc is a `.md` file (not SKILL.md): PASS (✅) if has `# title` (H1) AND at least one `## section` (H2); WARN (⚠️) if missing either; N/A if doc not found

**D10-c Code Freshness**: Scan the doc file for file path references and verify they still exist on disk.

- Read the doc file content
- Extract all path-like strings matching: `/src/[^\s]+`, `/lib/[^\s]+`, `/app/[^\s]+`
- For each extracted path: check if `[project_root][path]` exists on disk; if NOT found → flag as stale (⚠️)
- PASS (✅) if no stale paths found or no paths found in doc; N/A if doc not found

**D10-d Registry Alignment**: If doc is a SKILL.md in `.claude/skills/` → verify it appears in the CLAUDE.md Skills Registry section.

- Read CLAUDE.md (or `.claude/CLAUDE.md`)
- Check if `feature_name` appears in the Skills Registry section
- PASS (✅) if found; INFO (ℹ️) if not found (not a warning — projects may have features without skill entries by design); N/A if doc is not a SKILL.md

#### Output format

Emit a per-feature coverage table:

| Feature | Doc found | Structure OK | Fresh     | In Registry | Status   |
| ------- | --------- | ------------ | --------- | ----------- | -------- |
| [name]  | ✅/❌     | ✅/⚠️/N/A    | ✅/⚠️/N/A | ✅/ℹ️/N/A   | ✅/⚠️/❌ |

**Status column logic**: ✅ if all applicable checks pass; ⚠️ if any check warns; ❌ if D10-a (coverage) fails.

**FIX_MANIFEST rule**: D10 findings MUST NOT appear in `required_actions` or `skill_quality_actions` in the FIX_MANIFEST. /project-fix does not act on D10 findings.

---

### Dimension 11 — Internal Coherence

**Objective**: Validate that individual skill files and CLAUDE.md are internally self-consistent — numeric claims in headings match actual section counts, numbered sequences have no gaps or duplicates, and frontmatter descriptions agree with the body. Informational only — no score impact.

**Skip condition**: If `$LOCAL_SKILLS_DIR` does not exist as a directory AND no root `CLAUDE.md` exists → emit INFO: `'No auditable files found — Dimension 11 skipped.'` No score impact.

**Scope**: All `SKILL.md` files under `$LOCAL_SKILLS_DIR` (emitted by the Phase A script) plus the root `CLAUDE.md` (if it exists).

**Tool constraint**: D11 uses only Read, Glob, and Grep tools for file analysis. No Bash calls.

#### D11-a Count Consistency

Extract numeric claims from headings (lines starting with `#`) and blockquote lines (lines starting with `>`) using the pattern:

```
CLAIM_PATTERN = /(\d+)\s+(Dimensions?|Steps?|Rules?|Phases?|Checks?|Sub-checks?)/i
```

For each claim found:

- Identify the keyword (e.g., "Dimensions", "Steps")
- Count matching sections in the body: heading lines containing the same keyword (case-insensitive)
- If declared count ≠ actual count → finding with severity INFO

Do NOT match numeric references inside code blocks, examples, or body prose — only headings and blockquote lines.

#### D11-b Section Numbering Continuity

Match numbered section patterns in H2/H3/H4 headings:

```
SEQUENCE_PATTERNS:
  - /^#{2,3}\s+.*Step\s+(\d+)/im     → Step sequences
  - /^#{2,3}\s+.*Dimension\s+(\d+)/im → Dimension sequences
  - /^#{2,3}\s+.*Phase\s+(\d+)/im     → Phase sequences
  - /^#{2,4}\s+.*D(\d+)/m             → D-prefixed sequences (D1, D2, ...)
```

For each pattern:

- Collect all matched numbers, sort ascending
- **Gap**: a number N is missing where min..max is not contiguous
- **Duplicate**: a number appears more than once
- Report only if the sequence has ≥ 2 members (single item = no sequence to validate)
- Finding severity: INFO

#### D11-c Frontmatter-Body Alignment

- Parse YAML frontmatter (between first pair of `---` markers)
- Extract the `description` field
- If `description` contains a numeric claim (reuse `CLAIM_PATTERN`) → verify that claim against the body using the same logic as D11-a
- If mismatch → finding with severity INFO
- If no frontmatter or no `description` field → skip this check for that file

**FIX_MANIFEST rule**: D11 findings go in `violations[]` only with severity `info`. Rule names: `D11-count-consistency`, `D11-numbering-continuity`, `D11-frontmatter-body`. D11 findings MUST NOT appear in `required_actions` or `skill_quality_actions`. /project-fix does not act on D11 findings.

---

### Dimension 12 — ADR Coverage

**Objective**: Audit the health and completeness of the ADR (Architecture Decision Record) system when the project references `docs/adr/`. Informational only — no impact on the 100-point score.

**Activation condition**: Read CLAUDE.md (or `.claude/CLAUDE.md`). Check whether the string `docs/adr/` appears anywhere in the content.

- If `docs/adr/` is NOT found in CLAUDE.md → emit INFO: "ADR Coverage check skipped — docs/adr/ not referenced in CLAUDE.md" and skip all sub-checks below. No findings are added to the FIX_MANIFEST.
- If `docs/adr/` IS found in CLAUDE.md → proceed with the following checks.

**D12-1. README existence check:**

- Use `ADR_README_EXISTS` from Phase A output.
- If `ADR_README_EXISTS=0`: emit a HIGH finding — "CLAUDE.md references docs/adr/ but docs/adr/README.md is missing"
- Add to `required_actions.high` in the FIX_MANIFEST with `type: create_file`, `target: docs/adr/README.md`, `reason: "CLAUDE.md references docs/adr/ but docs/adr/README.md is missing"`

**D12-2. Per-ADR Status field scan:**

1. Use Glob to list all files matching `docs/adr/NNN-*.md` (where NNN is a 3-digit prefix, e.g., `001-`, `002-`).
2. If no ADR files are found (only README.md or directory empty): emit INFO — "docs/adr/ contains no ADR files yet". No score impact.
3. For each matched ADR file:
   - Read the file content.
   - Search for a `## Status` section (line starting with `## Status`) OR a frontmatter `status:` field.
   - If neither is found: emit a MEDIUM finding — "ADR file [filename] is missing a valid status field"
   - Add to `required_actions.medium` in the FIX_MANIFEST with `type: update_file`, `target: [docs/adr/filename]`, `reason: "ADR file is missing a valid status field"`
   - Valid status values: `accepted`, `deprecated`, `superseded`. If a status field IS found, record its value for the output table; do not validate the value (custom statuses are allowed).

**FIX_MANIFEST rule**: D12 HIGH findings go in `required_actions.high` (actionable by /project-fix). D12 MEDIUM findings go in `required_actions.medium`. D12 INFO findings go in `violations[]` with severity `info`. D12 does NOT reduce the base 100-point score.

---

### Dimension 13 — Spec Coverage

**Objective**: Audit the health of the spec layer — verify that spec artifacts in engram have valid path references. Informational only — no impact on the 100-point score.

**Activation condition**: Engram is reachable AND `mem_search(query: "sdd/", project: "{project}")` returns spec artifacts.

- If Engram is not reachable OR no spec artifacts found → emit INFO: "Spec Coverage check skipped — no spec artifacts found in engram" and skip all sub-checks. No findings are added to the FIX_MANIFEST.
- If condition is met → proceed with the following checks.

**D13-1. Per-spec path reference scan:**

1. For each `spec.md` that exists (found in D13-1):
   - Read the file content.
   - Extract all path-like references: strings that look like file paths (contain `/` and no spaces, not inside URLs, not in fenced code block headers). Look for patterns like `src/[path]`, `lib/[path]`, `[dir]/[file].[ext]`.
   - For each extracted path, check whether the file or directory exists at `[project_root]/[path]`.
   - If a referenced path does NOT exist: emit an INFO finding — "Spec artifact references a path that no longer exists: [path]"
   - Add to `violations[]` in the FIX_MANIFEST with `rule: "D13-stale-path-reference"`, `severity: "info"`, `file: "engram spec artifact"`
2. INFO findings for stale paths are NOT added to `required_actions` — they are advisory only.

**FIX_MANIFEST rule**: D13 MEDIUM findings (missing spec.md) go in `required_actions.medium` (actionable by /project-fix). D13 INFO findings (stale path references) go in `violations[]` only. D13 does NOT reduce the base 100-point score.

---

### Dimension 14 — Budget Compliance (Informational — no score impact)

This dimension runs on every project-audit invocation. It reports character counts against governance budgets defined in ADR-041.

**Check 1 — CLAUDE.md budget:**
1. Read `CLAUDE.md` at project root; count characters
2. Determine project type:
   - IF project is detected as global-config (install.sh + sync.sh exist): global budget = 20,000 chars
   - ELSE: project budget = 5,000 chars
3. IF character count > budget:
   → Add INFO finding: `"CLAUDE.md is [N] chars ([N-budget] over [budget] budget). Consider extracting content to skills (ADR-041)."`
4. IF character count <= budget:
   → Add INFO finding: `"CLAUDE.md budget OK: [N]/[budget] chars."`

Findings are appended to `audit-report.md` in a `## Budget Compliance` section. They do NOT affect any audit score dimension.

---

## Report Format

The report is saved in `.claude/audit-report.md` with this exact structure:

`````markdown
# Audit Report — [Project Name]

Generated: [YYYY-MM-DD HH:MM]
Score: [XX/100]
SDD Ready: [YES|NO|PARTIAL]

---

## FIX_MANIFEST

<!-- This block is consumed by /project-fix — DO NOT modify manually -->

```yaml
score: [XX]
sdd_ready: [true|false|partial]
generated_at: "[timestamp]"
project_root: "[absolute path]"

required_actions:
  critical:
    - id: "[unique-id]"
      type: "[create_file|update_file|create_dir|add_registry_entry|install_skill]"
      target: "[path or element]"
      reason: "[why it is necessary]"
      template: "[template_name if applicable]"
  high:
    - id: "[unique-id]"
      type: "..."
      target: "..."
      reason: "..."
  medium:
    - ...
  low:
    - ...

missing_global_skills:
  - "[skill-name]"

orphaned_changes:
  - name: "[name]"
    last_phase: "[phase]"
    days_inactive: [N]

violations:
  - file: "[path]"
    line: [N]
    rule: "[violated rule]"
    severity: "[critical|high|medium]"

skill_quality_actions:
  - id: "D9-<skill-name>-<action-type>"
    skill_name: "<name>"
    local_path: ".claude/skills/<name>/SKILL.md"
    global_counterpart: "~/.claude/skills/<name>/SKILL.md" # only for duplicates
    action_type: "delete_duplicate|add_missing_section|flag_irrelevant|flag_language"
    disposition: "delete|move-to-global|update|keep"
    missing_sections: ["## Rules", "## Process"] # only for add_missing_section
    detail: "<human-readable reason>"
    severity: "info|warning"
```

---

## Executive Summary

[3-5 lines describing the general state of the project from the Claude/SDD perspective]

---

## Score: [XX]/100

| Dimension                               | Points  | Max     | Status   |
| --------------------------------------- | ------- | ------- | -------- |
| CLAUDE.md complete and accurate         | [X]     | 20      | ✅/⚠️/❌ |
| Memory initialized                      | [X]     | 15      | ✅/⚠️/❌ |
| Memory with substantial content         | [X]     | 10      | ✅/⚠️/❌ |
| SDD Orchestrator operational            | [X]     | 20      | ✅/⚠️/❌ |
| Skills registry complete and functional | [X]     | 20      | ✅/⚠️/❌ |
| Cross-references valid                  | [X]     | 5       | ✅/⚠️/❌ |
| Architecture compliance                 | [X]     | 5       | ✅/⚠️/❌ |
| Testing & Verification integrity        | [X]     | 5       | ✅/⚠️/❌ |
| Project Skills Quality                  | N/A     | N/A     | ✅/ℹ️/—  |
| Feature Docs Coverage                   | N/A     | N/A     | ✅/ℹ️/—  |
| Internal Coherence                      | N/A     | N/A     | ✅/ℹ️/—  |
| ADR Coverage                            | N/A     | N/A     | ✅/ℹ️/—  |
| Spec Coverage                           | N/A     | N/A     | ✅/ℹ️/—  |
| Budget Compliance                       | N/A     | N/A     | ✅/ℹ️/—  |
| **TOTAL**                               | **[X]** | **100** |          |

**SDD Readiness**: [FULL / PARTIAL / NOT CONFIGURED]

- FULL: Engram reachable, CLAUDE.md mentions /sdd-*, global skills present
- PARTIAL: Some SDD elements present but incomplete
- NOT CONFIGURED: Engram not reachable and no SDD references in CLAUDE.md

---

## Dimension 1 — CLAUDE.md [OK|WARNING|CRITICAL]

| Check                                                                    | Status   | Detail                   |
| ------------------------------------------------------------------------ | -------- | ------------------------ |
| Exists `.claude/CLAUDE.md` (or root `CLAUDE.md` for global-config repos) | ✅/❌    |                          |
| Has >50 lines                                                            | ✅/❌    | [X] lines                |
| Stack documented                                                         | ✅/⚠️/❌ |                          |
| Stack vs package.json                                                    | ✅/⚠️/❌ | [specific discrepancies] |
| Has Architecture section                                                 | ✅/⚠️/❌ |                          |
| Skills registry present                                                  | ✅/⚠️/❌ |                          |
| Mentions SDD (/sdd-\*)                                                   | ✅/⚠️/❌ |                          |

**Stack Discrepancies:**
[List each discrepancy: "Declares React 18, actual ^19.0.0"]

**Template path verification:**
| Template path | Exists |
|--------------|--------|
| docs/templates/prd-template.md | ✅/❌ |
| docs/templates/adr-template.md | ✅/❌ |
[or: "No docs/templates/*.md paths found in CLAUDE.md — check skipped"]

---

## Dimension 2 — Memory [OK|WARNING|CRITICAL]

| File            | Exists | Lines | Content  | Coherence |
| --------------- | ------ | ----- | -------- | --------- |
| stack.md        | ✅/❌  | [N]   | ✅/⚠️/❌ | ✅/⚠️/❌  |
| architecture.md | ✅/❌  | [N]   | ✅/⚠️/❌ | ✅/⚠️/❌  |
| conventions.md  | ✅/❌  | [N]   | ✅/⚠️/❌ | ✅/⚠️/❌  |
| known-issues.md | ✅/❌  | [N]   | ✅/⚠️/❌ | ✅/⚠️/❌  |
| changelog-ai.md | ✅/❌  | [N]   | ✅/⚠️/❌ | N/A       |

**Coherence issues detected:**
[List specific issues with file + what is outdated]

**Placeholder phrase detection:**
| File | Phrase found | Severity |
|------|-------------|----------|
| stack.md | "[To be filled]" | ⚠️ HIGH |
[or: "No placeholder phrases detected"]

**stack.md technology count**: [N] version entries detected (minimum: 3) — ✅/⚠️

---

## Dimension 3 — SDD Orchestrator [OK|WARNING|CRITICAL]

**Global SDD Skills:**
| Skill | Exists |
|-------|--------|
| sdd-explore | ✅/❌ |
| sdd-propose | ✅/❌ |
| sdd-spec | ✅/❌ |
| sdd-design | ✅/❌ |
| sdd-tasks | ✅/❌ |
| sdd-apply | ✅/❌ |
| sdd-verify | ✅/❌ |
| sdd-archive | ✅/❌ |

**Engram availability:**
| Check | Status |
|-------|--------|
| Engram MCP reachable | ✅/❌ |

**CLAUDE.md mentions SDD:** ✅/❌

**Orphaned changes:** [none | list]

**Hook script existence:**
| Hook event | Script path | Exists |
|-----------|-------------|--------|
| [event] | [path] | ✅/❌ |
[or: "No hooks key found in settings files — check skipped"]

**Active changes — file conflict detection:**
| File | Change A | Change B |
|------|----------|----------|
| [path] | [change-name] | [change-name] |
[or: "No conflicts detected"]
[or: "Fewer than two active changes have design.md — check skipped"]

---

## Dimension 4 — Skills [OK|WARNING|CRITICAL]

**Skills in registry but not on disk:**
[list or "none"]

**Skills on disk but not in registry:**
[list or "none"]

**Skills with insufficient content (<30 lines):**
[list or "none"]

**Recommended global tech skills not installed:**
[list with install command: /skill-add name]

---

## Dimension 6 — Cross-references [OK|WARNING|CRITICAL]

**Broken references:**
| Source file | Reference | Problem |
|----------------|-----------|---------|
[list or "none"]

---

## Dimension 7 — Architecture Compliance [OK|WARNING|CRITICAL]

Analysis report found: YES/NO
Last analyzed: [date or N/A]
Report age: [N days | N/A]
Architecture drift status: [none|minor|significant|N/A]
Staleness penalty: [none | −1 pt (report is [N] days old, > 30 days) | −2 pts (report is [N] days old, > 60 days)]

Drift entries: (when drift is present)
| File/Pattern | Expected | Found |
|---|---|---|
| [entry] | [expected] | [found] |

---

## Dimension 8 — Testing & Verification [OK|WARNING|CRITICAL]

**Project has test runner:** ✅/❌

**Archived changes without verify-report:**
[list or "none"]

**Archived changes with empty verify-report.md (without [x]):**
[list or "none"]

**Verify rules are executable:** ✅/⚠️/❌

---

## Dimension 9 — Project Skills Quality [OK|INFO|SKIPPED]

**Local skills directory**: [value of $LOCAL_SKILLS_DIR] — [N skills found | not found — skipped]

| Skill        | Duplicate of global | Structural complete     | Language OK       | Stack relevant            | Disposition                       |
| ------------ | ------------------- | ----------------------- | ----------------- | ------------------------- | --------------------------------- |
| [skill-name] | ⚠️ YES / ❌ NO      | ✅ / ⚠️ (missing: list) | ✅ / ℹ️ violation | ✅ / ℹ️ flag / ℹ️ UNKNOWN | keep/update/delete/move-to-global |

**Skills with missing structural sections:**
[list or "none"]

**Language violations (INFO — manual fix required):**
[list or "none"]

**Stack relevance issues (INFO):**
[list or "none"]

_Note: Dimension 9 does not affect the score in this iteration. Findings are informational unless action_type is `delete_duplicate`._

---

## Dimension 10 — Feature Docs Coverage [OK|INFO|SKIPPED]

**Detection mode**: configured | heuristic | skipped
**Features detected**: [N] ([list of names])

| Feature | Doc found | Structure OK | Fresh     | In Registry | Status   |
| ------- | --------- | ------------ | --------- | ----------- | -------- |
| [name]  | ✅/❌     | ✅/⚠️/N/A    | ✅/⚠️/N/A | ✅/ℹ️/N/A   | ✅/⚠️/❌ |

_D10 findings are informational only — they do not affect the score and are not auto-fixed by /project-fix._

---

## Dimension 11 — Internal Coherence [OK|INFO|SKIPPED]

**Skills scanned**: [N] from $LOCAL_SKILLS_DIR

| Skill        | Count OK | Numbering OK | Frontmatter OK | Findings            |
| ------------ | -------- | ------------ | -------------- | ------------------- |
| [skill-name] | ✅/⚠️    | ✅/⚠️        | ✅/⚠️/N/A      | [detail or "clean"] |

**Inconsistencies found**: [N] across [M] skills (or "None — all skills internally coherent")

_D11 findings are informational only — they do not affect the score and are not auto-fixed by /project-fix._

---

## Dimension 12 — ADR Coverage [OK|INFO|SKIPPED]

**Condition**: CLAUDE.md references docs/adr/ — YES/NO
**ADR README exists**: ✅/❌
**ADRs scanned**: [N]

| ADR              | Status field found | Status value                       | Finding                         |
| ---------------- | ------------------ | ---------------------------------- | ------------------------------- |
| [001-example.md] | ✅/❌              | [accepted/deprecated/superseded/—] | clean/Missing ## Status section |

[or: "ADR Coverage check skipped — docs/adr/ not referenced in CLAUDE.md"]
[or: "docs/adr/ contains no ADR files yet"]

_D12 findings are informational only — no score impact._

---

## Dimension 13 — Spec Coverage [OK|INFO|SKIPPED]

**Condition**: Engram reachable and spec artifacts found — YES/NO
**Domains detected**: [list of domain names]

| Domain | spec.md found | Stale paths | Status   |
| ------ | ------------- | ----------- | -------- |
| [name] | ✅/❌         | [N]         | ✅/⚠️/❌ |

[or: "Spec Coverage check skipped — no spec artifacts found in engram"]

_D13 findings are informational only — no score impact._

---

## Budget Compliance [INFO]

**Project type**: agent-config (20,000 char global budget) | other project (5,000 char project budget)

**CLAUDE.md character count**: [N] chars — [OK: N/budget | OVER: N chars over budget]

_Budget Compliance findings are informational only — no score impact. See ADR-041 for budget governance details._

---

## Required Actions

### Critical (block SDD):

1. [concrete action] → run `/project-fix` or manually: [instruction]

### High (degrade quality):

1. [concrete action]

### Medium:

1. [concrete action]

### Low (optional improvements):

1. [concrete action]

---

_To implement these corrections: run `/project-fix`_
_This report was generated by `/project-audit` — do not modify the FIX_MANIFEST block manually_
`````

---

## Detailed Scoring

| Dimension                  | Criterion                                                                                                                                                                                                                       | Max points |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| **CLAUDE.md**              | Exists + complete structure + accurate stack + SDD refs                                                                                                                                                                         | 20         |
| **Memory — existence**     | All 5 files exist                                                                                                                                                                                                               | 15         |
| **Memory — quality**       | Substantial content + coherent with code                                                                                                                                                                                        | 10         |
| **SDD Orchestrator**       | Global skills + Engram availability + CLAUDE.md refs                                                                                                                                                                             | 20         |
| **Skills**                 | Registry accuracy + content depth = 10 pts; global tech skills coverage (D4c) = 10 pts                                                                                                                                          | 20         |
| **Cross-references**       | No broken references                                                                                                                                                                                                            | 5          |
| **Architecture**           | No critical violations in samples                                                                                                                                                                                               | 5          |
| **Testing & Verification** | config.yaml has testing block + archived changes have verify-report.md                                                                                                                                                          | 5          |
| **Project Skills Quality** | Informational only — no score deduction in iteration 1. Flags duplicates, structural gaps, language violations, stack relevance issues.                                                                                         | N/A        |
| **Feature Docs Coverage**  | Informational only — no score deduction. Detects feature/skill documentation gaps.                                                                                                                                              | N/A        |
| **Internal Coherence**     | Informational only — no score deduction. Validates count claims, section numbering, and frontmatter consistency within individual skill files.                                                                                  | N/A        |
| **ADR Coverage**           | Informational only — no score deduction. Activated when CLAUDE.md references docs/adr/. Verifies README.md exists and each ADR file has a status field. HIGH/MEDIUM findings are actionable by /project-fix.                    | N/A        |
| **Spec Coverage**          | Informational only — no score deduction. Activated when engram has spec artifacts. Verifies spec path references are valid on disk. MEDIUM findings are actionable by /project-fix. | N/A        |
| **Budget Compliance**      | Informational only — no score deduction. Reports CLAUDE.md character count against ADR-041 governance budgets (20k global / 5k project). | N/A        |

**Interpretation:**

- 90-100: SDD fully operational, excellent maintenance
- 75-89: Ready to use SDD, minor improvements pending
- 50-74: SDD partially configured, needs `/project-fix`
- <50: Requires complete setup

---

## Rules

1. **I always read real files** — I never assume the content of a file
2. **I run in a subagent** with read tools — never in main context
3. **I always save the report** in `.claude/audit-report.md` before presenting to the user
4. **The FIX_MANIFEST is valid YAML** — I verify that the block is parseable
5. **I never modify anything** — this skill is 100% read-only
6. **If I cannot read a file**, I report it as ❌ with the exact error, I do not assume it does not exist
7. **When finished**, I notify the user: "Report saved in `.claude/audit-report.md`. To implement the corrections: `/project-fix`"
8. **All shell-based discovery MUST be consolidated into a single Bash script call (Phase A). Maximum 3 Bash calls per audit run. Never issue individual `ls`, `grep`, `wc -l`, or `find` calls per dimension.**
9. **Compatibility behavior must be explicit** — if a legacy or repo-specific structure is accepted, the skill documents it as compatibility policy rather than leaving it implicit in a dimension.

   Use the following reference script template for Phase A discovery:

   ```sh
   #!/usr/bin/env bash
   # project-audit discovery — Phase A
   # Usage: bash <(echo "$SCRIPT") [project_root]
   PROJECT="${1:-.}"
   f() { [ -f "$PROJECT/$1" ] && echo 1 || echo 0; }
   d() { [ -d "$PROJECT/$1" ] && echo 1 || echo 0; }
   lc() { [ -f "$PROJECT/$1" ] && wc -l < "$PROJECT/$1" || echo 0; }

   echo "CLAUDE_MD_EXISTS=$(f .claude/CLAUDE.md)"
   echo "ROOT_CLAUDE_MD_EXISTS=$(f CLAUDE.md)"
   echo "ENGRAM_REACHABLE=<check via mem_context>"
   echo "INSTALL_SH_EXISTS=$(f install.sh)"
   echo "SYNC_SH_EXISTS=$(f sync.sh)"

   # Global-config detection for LOCAL_SKILLS_DIR
   if [ "$INSTALL_SH_EXISTS" = "1" ] && [ "$SYNC_SH_EXISTS" = "1" ]; then
     LOCAL_SKILLS_DIR="skills"
   elif [ -d "$PROJECT/skills/_shared" ]; then
     LOCAL_SKILLS_DIR="skills"
   else
     LOCAL_SKILLS_DIR=".claude/skills"
   fi
   echo "LOCAL_SKILLS_DIR=$LOCAL_SKILLS_DIR"

   echo "STACK_MD_EXISTS=$(f ai-context/stack.md)"
   echo "ARCH_MD_EXISTS=$(f ai-context/architecture.md)"
   echo "CONV_MD_EXISTS=$(f ai-context/conventions.md)"
   echo "ISSUES_MD_EXISTS=$(f ai-context/known-issues.md)"
   echo "CHANGELOG_MD_EXISTS=$(f ai-context/changelog-ai.md)"
   echo "CLAUDE_MD_LINES=$(lc CLAUDE.md)"
   echo "STACK_MD_LINES=$(lc ai-context/stack.md)"

   # Orphaned changes — detected via engram search for stale SDD state artifacts
   ORPHANED="<detected via mem_search for sdd/*/state artifacts older than 14 days>"
   fi
   echo "ORPHANED_CHANGES=${ORPHANED:-NONE}"

   # SDD phase skills present
   SDD_COUNT=0
   for phase in explore propose spec design tasks apply verify archive; do
     [ -f "$HOME/.claude/skills/sdd-$phase/SKILL.md" ] && SDD_COUNT=$((SDD_COUNT+1))
   done
   echo "SDD_SKILLS_PRESENT=$SDD_COUNT"
   echo "FEATURE_DOCS_CONFIG_EXISTS=<check config.yaml at project root if it exists>"
   echo "ANALYSIS_REPORT_EXISTS=$(f analysis-report.md)"
   echo "ANALYSIS_REPORT_DATE=$(head -5 "$PROJECT/analysis-report.md" 2>/dev/null | grep 'Last analyzed:' | awk '{print $3}' || echo '')"
   echo "ROOT_SETTINGS_JSON_EXISTS=$(f settings.json)"
   echo "DOTCLAUDE_SETTINGS_JSON_EXISTS=$(f .claude/settings.json)"
   echo "SETTINGS_LOCAL_JSON_EXISTS=$(f settings.local.json)"
   echo "ADR_DIR_EXISTS=$(d docs/adr)"
   echo "ADR_README_EXISTS=$(f docs/adr/README.md)"
   echo "ENGRAM_HAS_SPECS=<check via mem_search for sdd/*/spec artifacts>"
   ```

   **Output key schema** (each key is a `key=value` line in stdout):
   - `CLAUDE_MD_EXISTS` — 1 if `.claude/CLAUDE.md` exists, 0 if absent
   - `ROOT_CLAUDE_MD_EXISTS` — 1 if root `CLAUDE.md` exists, 0 if absent
   - `ENGRAM_REACHABLE` — 1 if Engram MCP is reachable, 0 if not
   - `INSTALL_SH_EXISTS` — 1 if `install.sh` exists at project root, 0 if absent
   - `SYNC_SH_EXISTS` — 1 if `sync.sh` exists at project root, 0 if absent
   - `LOCAL_SKILLS_DIR` — string: `"skills"` (global-config detected via Condition A or B) or `".claude/skills"` (standard project)
   - `STACK_MD_EXISTS` — 1 if `ai-context/stack.md` exists, 0 if absent
   - `ARCH_MD_EXISTS` — 1 if `ai-context/architecture.md` exists, 0 if absent
   - `CONV_MD_EXISTS` — 1 if `ai-context/conventions.md` exists, 0 if absent
   - `ISSUES_MD_EXISTS` — 1 if `ai-context/known-issues.md` exists, 0 if absent
   - `CHANGELOG_MD_EXISTS` — 1 if `ai-context/changelog-ai.md` exists, 0 if absent
   - `CLAUDE_MD_LINES` — integer line count of root `CLAUDE.md` (0 if absent)
   - `STACK_MD_LINES` — integer line count of `ai-context/stack.md` (0 if absent)
   - `ORPHANED_CHANGES` — comma-separated names of orphaned change dirs, or `NONE`
   - `SDD_SKILLS_PRESENT` — integer count of present `~/.claude/skills/sdd-*/SKILL.md` files (0–8)
   - `FEATURE_DOCS_CONFIG_EXISTS` — 1 if project config.yaml contains a `feature_docs:` key, 0 if absent
   - `ANALYSIS_REPORT_EXISTS` — 1 if `analysis-report.md` exists at project root, 0 if absent
   - `ANALYSIS_REPORT_DATE` — ISO date string from the `Last analyzed:` field of `analysis-report.md`, or empty string if absent
   - `ROOT_SETTINGS_JSON_EXISTS` — 1 if `settings.json` exists at project root, 0 if absent
   - `DOTCLAUDE_SETTINGS_JSON_EXISTS` — 1 if `.claude/settings.json` exists, 0 if absent
   - `SETTINGS_LOCAL_JSON_EXISTS` — 1 if `settings.local.json` exists at project root, 0 if absent
   - `ADR_DIR_EXISTS` — 1 if `docs/adr/` directory exists, 0 if absent
   - `ADR_README_EXISTS` — 1 if `docs/adr/README.md` exists, 0 if absent
   - `ENGRAM_HAS_SPECS` — 1 if engram contains spec artifacts for this project, 0 if absent

   **Legacy commands/ detection (Phase A post-script check):**

   After running the Phase A script, check whether `.claude/commands/` exists in the project root:

   ```
   if [ -d "$PROJECT/.claude/commands" ]; then
     emit LOW finding: "Legacy .claude/commands/ directory detected — migrate to .claude/skills/ following the official Claude Code standard."
   fi
   ```

   - Severity: LOW (informational)
   - Score penalty: none
   - FIX_MANIFEST entry: none (do NOT add a `required_actions` entry for this finding)

### Phase A extension — analysis-report.md check

After the Phase A Bash batch completes, the following two variables are available for use by Dimension 7 in Phase B:

- `ANALYSIS_REPORT_EXISTS` — 1 if `analysis-report.md` exists at the project root, 0 if absent
- `ANALYSIS_REPORT_DATE` — ISO date string from the `Last analyzed:` field, or empty string if absent

**Important constraints:**

- `project-audit` does NOT invoke `project-analyze` automatically. `analysis-report.md` is treated as external input produced by a prior `/project-analyze` run.
- D7 in Phase B reads `ANALYSIS_REPORT_EXISTS` and `ANALYSIS_REPORT_DATE` to compute its score and staleness warning.
- These two variables are added to the existing Phase A Bash script template — no additional Bash call is introduced. Total Bash calls per audit run remain ≤ 3.

```

```
