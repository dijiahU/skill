# Report Format

Red-team reports consolidate probe results across personas into a single assessment.

## Report Structure

```markdown
# Red-Team Report: <target>

**Date:** YYYY-MM-DD
**Surface:** docs | skills
**Personas tested:** N
**Scenarios:** N tested, N passed, N failed

## Overall Verdict: PASS | WARN | FAIL

## Per-Persona Results

### <persona-name> (<role>)

**Scenarios:** N/M passed
**Critical findings:** N

| Scenario | Verdict | Severity | Finding |
|----------|---------|----------|---------|
| ... | PASS/FAIL/PARTIAL | critical/significant/minor | ... |

### Detailed Findings

#### RT-YYYYMMDD-NNN: <finding title>

- **Persona:** <name>
- **Scenario:** <title>
- **Severity:** critical | significant | minor
- **Verdict:** PASS | FAIL | PARTIAL
- **Path taken:** entry_point -> file1:line -> file2:line -> ...
- **Finding:** <description>
- **Evidence:** <file:line reference>
- **Recommendation:** <actionable fix>

## Cross-Persona Findings

Findings reported by multiple personas (higher confidence):

| Finding | Personas | Confidence |
|---------|----------|------------|
| ... | panicked-sre, junior-engineer | high |

## Council Consolidation

Verdict from `/council --preset=red-team`: PASS | WARN | FAIL
<council summary>
```

## Finding -> schemas/finding.json Mapping

Red-team findings use the canonical finding schema with field mapping:

| Red-team field | Schema field | Encoding |
|---------------|-------------|----------|
| persona + finding type | `category` | `"red-team/<persona-name>"` |
| severity | `severity` | Direct: critical/significant/minor |
| finding description | `description` | Direct |
| file:line evidence | `location` | Direct |
| recommendation | `recommendation` | Direct |
| actionable fix | `fix` | Direct |
| navigation path | `ref` | Path taken as string |
| root cause | `why` | Why the finding matters |

## Verdict Rules

| Condition | Verdict |
|-----------|---------|
| Any persona has critical FAIL | **FAIL** |
| Mixed results, no critical FAILs | **WARN** |
| All personas pass all scenarios | **PASS** |

PASS with findings is valid -- it means "works but with friction."
