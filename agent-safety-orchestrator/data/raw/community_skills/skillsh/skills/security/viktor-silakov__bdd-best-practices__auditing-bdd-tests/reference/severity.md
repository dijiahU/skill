# Severity Classification (BDD Test Solution)

Used by the `auditing-bdd-tests` skill.

## Boundary Rules (Warning vs Info)

Classify as **WARNING** if any of the following are true:
- Impacts determinism, stability, or flake rate.
- Affects ≥20% of scenarios or ≥2 key feature areas.
- Requires structural refactor (architecture/locator strategy/policy) rather than a local fix.

Classify as **INFO** if all of the following are true:
- Does not affect deterministic execution.
- Local to a small scope (single feature or few scenarios).
- Can be fixed with localized edits without changing team-wide conventions.

If unsure, default to WARNING.

## 🔴 CRITICAL (blocks reliable execution)

Must be fixed first — otherwise tests/AI-agent work "by luck":

- Widespread `sleep`/`wait(…)` without conditions
- Unstable locators as the main strategy (generated classes, `nth-child`, deep CSS/XPath)
- **Non-semantic HTML** (`<div onclick>`, `<span class="link">`) blocking role-based locators
- **Missing accessible names** — interactive elements without labels or aria-label
- Hidden asserts inside `When/And` (impossible to read as specification)
- Steps with branching (`if/else` by device/state) instead of separate scenarios/tags
- Tests depend on order/shared state (shared accounts, shared data)
- No artifacts on failure (trace/video/screenshot) → flakes are not debuggable
- Step definitions contain retry/loops/try-catch that "swallow" errors

## 🟡 WARNING (hinders speed and maintainability)

AI and humans can work, but slowly/expensively:

- Long scenarios (>10–12 steps) and mega-steps
- Duplicate steps/locators in different places
- Timeouts/retries configured "by eye"
- No unified tag taxonomy (@smoke/@regression/@mobile…)
- Test data is hardcoded, no factories/generators
- No "how to write a new test" document
- **CSS/class-based locators** instead of `getByRole()` / `getByLabel()`
- **Form inputs without associated labels** — `getByLabel()` won't work
- **Hardcoded text in locators** — breaks on i18n/locale changes
- **Inconsistent locator styles** — mixed CSS, XPath, and semantic locators

## 🔵 INFO (optimizations)

Nice to have, but doesn't block:

- No step catalog (step index)
- No explicit "flaky policy" (when quarantine, when fix)
- Few "why" explain-paragraphs in complex places
- No "locator map" for key pages/components
- **Missing landmark regions** (`<nav>`, `<main>`, `<header>`) — nice for page structure
- **Generic accessible names** ("Submit" instead of "Submit order") — could be more descriptive
- **No a11y testing integration** — could catch semantic issues during tests
