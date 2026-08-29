# Audit Report Template

## Filename Convention

Save the report at the project root as:

```
AUDIT-REPORT-YYYY-MM-DD.md
```

If a file with that name already exists, append an incrementing numeric suffix:

```
AUDIT-REPORT-YYYY-MM-DD-2.md
AUDIT-REPORT-YYYY-MM-DD-3.md
```

Use the current date at the time of report generation.

---

## Template

```markdown
# Audit Report — YYYY-MM-DD

## Summary

| Field               | Value                        |
|---------------------|------------------------------|
| **Scope**           | <files, directories, or modules audited> |
| **Categories**      | <comma-separated list of audit categories applied> |
| **Total findings**  | <N>                          |
| **Critical**        | <N>                          |
| **High**            | <N>                          |
| **Medium**          | <N>                          |
| **Low**             | <N>                          |

---

## Context & Intent

<Include the Intent Brief here using the structure from references/intent-discovery.md. Omit empty subsections. If no intent signals were discovered, write: "No documented intent signals were identified in the codebase.">

---

## Critical

### AUDIT-001 — <Short title>

| Field            | Value |
|------------------|-------|
| **Category**     | <category name> |
| **Location**     | `<file>:<line>` |
| **Severity**     | Critical |

**Description**

<Clear explanation of the finding. State what the code does and why it is problematic.>

**Impact**

<Concrete consequences: data loss, unauthorized access, service disruption, etc.>

**Recommendation**

<Specific, actionable fix. Include a code snippet when it clarifies the recommendation.>

---

## High

### AUDIT-NNN — <Short title>

| Field            | Value |
|------------------|-------|
| **Category**     | <category name> |
| **Location**     | `<file>:<line>` |
| **Severity**     | High |

**Description**

<...>

**Impact**

<...>

**Recommendation**

<...>

---

## Medium

### AUDIT-NNN — <Short title>

| Field            | Value |
|------------------|-------|
| **Category**     | <category name> |
| **Location**     | `<file>:<line>` |
| **Severity**     | Medium |

**Description**

<...>

**Impact**

<...>

**Recommendation**

<...>

---

## Low

### AUDIT-NNN — <Short title>

| Field            | Value |
|------------------|-------|
| **Category**     | <category name> |
| **Location**     | `<file>:<line>` |
| **Severity**     | Low |

**Description**

<...>

**Impact**

<...>

**Recommendation**

<...>
```

---

## Identifier Numbering

Assign `AUDIT-NNN` identifiers sequentially starting at `AUDIT-001`, ordered by severity (Critical first, then High, Medium, Low). Within the same severity level, order findings by category, then by file path.

---

## Multi-Location Findings

When a finding affects multiple locations (same root cause across files), use a comma-separated list in the Location field and list all locations in the Description:

```markdown
| **Location**     | `src/api/users.py:42`, `src/api/orders.py:87`, `src/api/products.py:31` |
```

For findings with many locations (>5), use the primary location in the field and list the full set in the Description body.

---

## Zero-Findings Report

When no issues are found, produce the full report structure with all counts set to 0. Replace each severity section body with:

```markdown
No issues found.
```

The "Context & Intent" section uses the fallback message: "No documented intent signals were identified in the codebase."
