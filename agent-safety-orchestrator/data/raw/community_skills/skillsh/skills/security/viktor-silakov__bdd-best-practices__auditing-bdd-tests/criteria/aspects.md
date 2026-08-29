# BDD Test Solution — Aspect Criteria (0/5/10)

Used by the `auditing-bdd-tests` skill.

Each criterion is scored strictly on the **0 / 5 / 10** scale.

**Rule:** if "generally ok" but lacks provability/determinism/reproducibility — it's **5**, not **10**.

## Contents
- [Aspect 1: Executable Gherkin (16%)](#aspect-1-executable-gherkin-16)
- [Aspect 2: Step Definitions Quality (14%)](#aspect-2-step-definitions-quality-14)
- [Aspect 3: Test Architecture (14%)](#aspect-3-test-architecture-14)
- [Aspect 4: Selector Strategy (12%)](#aspect-4-selector-strategy-12)
- [Aspect 5: Waiting & Flake Resistance (14%)](#aspect-5-waiting--flake-resistance-14)
- [Aspect 6: Data & Environment (10%)](#aspect-6-data--environment-10)
- [Aspect 7: CI, Reporting & Artifacts (10%)](#aspect-7-ci-reporting--artifacts-10)
- [Aspect 8: AI-Agent Operability (10%)](#aspect-8-ai-agent-operability-10)

---

## Aspect 1: Executable Gherkin (16%)

**Max: 120 points (12 criteria)**

| # | Criterion | 0 | 5 | 10 |
|---|-----------|---|---|-----|
| 1.1 | Scenario names | vague/duplicated | mostly clear | clear, intent-first |
| 1.2 | Step atomicity | multi-action steps | mixed | 1 action = 1 step |
| 1.3 | Assertions explicit | hidden in When/And | partial | all in Then |
| 1.4 | Observability | “works” language | some concrete | fully verifiable outcomes |
| 1.5 | Background usage | abused/shared state | occasional | only stable preconditions |
| 1.6 | Scenario length | >12 steps common | mixed | focused (≤8–10) |
| 1.7 | Tags taxonomy | none/chaos | basic @smoke/@regression | consistent, documented |
| 1.8 | Traceability IDs | none | partial | stable IDs (JIRA/TC) |
| 1.9 | Data in feature | hardcoded everywhere | some aliases | aliases/factories pattern |
| 1.10 | Device variants | hidden branching | some tags | explicit scenarios per device |
| 1.11 | Reuse without coupling | copy-paste | some reuse | reusable steps without hidden state |
| 1.12 | Business language | UI-implementation text | mixed | business intent + observable checks |

---

## Aspect 2: Step Definitions Quality (14%)

**Max: 120 points (12 criteria)**

| # | Criterion | 0 | 5 | 10 |
|---|-----------|---|---|-----|
| 2.1 | “Thin steps” | complex logic | some helpers | wiring only |
| 2.2 | Branching | lots of if/else | occasional | no hidden branching |
| 2.3 | Loops/retries | inside steps | mixed | moved to utils/fixtures |
| 2.4 | Hidden expects | common | some | none |
| 2.5 | Error clarity | swallowed errors | ok | actionable messages |
| 2.6 | Naming & grouping | inconsistent | ok | by domain/feature |
| 2.7 | Duplication | many near-duplicates | some | single canonical steps |
| 2.8 | Parameter hygiene | regex soup | mixed | clear parameter types |
| 2.9 | Side effects | implicit state | some | explicit state in scenario |
| 2.10 | Timeouts | random per-step | mixed | centralized policy |
| 2.11 | Logging | none/noisy | partial | structured + useful |
| 2.12 | Discoverability | hard to find step impl | ok | clear mapping & index |

---

## Aspect 3: Test Architecture (14%)

**Max: 100 points (10 criteria)**

| # | Criterion | 0 | 5 | 10 |
|---|-----------|---|---|-----|
| 3.1 | Layering | steps do everything | mixed | steps→fixtures→utils |
| 3.2 | Page objects | none or god-POM | partial | focused POM/components |
| 3.3 | Fixtures design | ad-hoc globals | some | typed fixtures, scoped |
| 3.4 | Reuse boundaries | random helpers | ok | clear public API |
| 3.5 | Config centralization | scattered | partial | single config surface |
| 3.6 | Test isolation | order-dependent | mixed | isolated by design |
| 3.7 | Parallel safety | breaks in parallel | mixed | parallel-safe patterns |
| 3.8 | File sizes | mega files common | some | small modules (≤300–500 LOC) |
| 3.9 | Utilities quality | copy-paste | ok | composable utils |
| 3.10 | Documentation | none | basic | “how to write tests” doc |

---

## Aspect 4: Selector Strategy (12%)

**Max: 140 points (14 criteria)**

Playwright recommends **prioritizing user-facing attributes** and **semantic locators** that reflect how users and assistive technology perceive the page.

**Locator Priority (best to worst):**
1. `getByRole()` — ARIA roles + accessible names (buttons, links, headings, etc.)
2. `getByLabel()` — form controls by associated label
3. `getByPlaceholder()` — inputs by placeholder text
4. `getByText()` — non-interactive elements by visible text
5. `getByAltText()` — images by alt attribute
6. `getByTitle()` — elements by title attribute
7. `getByTestId()` — explicit test IDs (fallback for complex cases)
8. CSS/XPath — **avoid**; brittle, DOM-structure dependent

| # | Criterion | 0 | 5 | 10 |
|---|-----------|---|---|-----|
| 4.1 | Role-first locators | ignored | mixed | `getByRole()` as primary strategy |
| 4.2 | Semantic HTML usage | divs everywhere | some semantic tags | proper HTML5 semantics (button, nav, header, etc.) |
| 4.3 | ARIA attributes | missing/incorrect | partial | correct roles, labels, states |
| 4.4 | Label association | labels not linked | some | all inputs have associated labels |
| 4.5 | Test IDs (fallback) | none | scattered | consistent `data-testid` for edge cases |
| 4.6 | Forbidden selectors | common nth-child/css hashes | some | none; no brittle selectors |
| 4.7 | Central mapping | scattered | partial | single mapping/aliases for complex locators |
| 4.8 | Localization safety | hardcoded text everywhere | some i18n awareness | role-based or test-id resilient to locale |
| 4.9 | Accessible names | missing/generic | partial | descriptive accessible names for all interactive elements |
| 4.10 | ARIA states usage | ignored | partial | `expanded`, `checked`, `selected` states tested where applicable |
| 4.11 | Consistency | many selector styles | some | team-wide selector conventions |
| 4.12 | Debuggability | hard to trace | ok | named locators, clear aliases |
| 4.13 | Component selectors | none | partial | component-level locator strategy |
| 4.14 | Drift handling | constant breakage | mixed | single-point-of-update pattern |

**Why semantic/a11y-first matters for AI agents:**
- AI agents understand page structure through roles and accessible names
- Semantic selectors are self-documenting and intent-revealing
- Tests become accessibility audits by default
- Locators survive refactoring if semantics stay consistent

---

## Aspect 5: Waiting & Flake Resistance (14%)

**Max: 120 points (12 criteria)**

| # | Criterion | 0 | 5 | 10 |
|---|-----------|---|---|-----|
| 5.1 | Arbitrary sleeps | common | occasional | none |
| 5.2 | Condition waits | none | partial | condition-first everywhere |
| 5.3 | Network sync | ignored | mixed | deterministic endpoints waits |
| 5.4 | Animation handling | flaky | mixed | stabilized (disable/await) |
| 5.5 | Timeouts | random | partial | policy-driven |
| 5.6 | Retries | used as crutch | some | root-cause focus |
| 5.7 | Shared state | common | some | isolated setup/teardown |
| 5.8 | Test data flake | non-deterministic | mixed | deterministic generation |
| 5.9 | Env stability | unknown | partial | documented + controlled |
| 5.10 | Flaky tracking | none | manual | tracked + triaged |
| 5.11 | Deterministic assertions | “eventually” vague | mixed | stable assertions |
| 5.12 | Concurrency | race-prone | mixed | safe parallel runs |

---

## Aspect 6: Data & Environment (10%)

**Max: 80 points (8 criteria)**

| # | Criterion | 0 | 5 | 10 |
|---|-----------|---|---|-----|
| 6.1 | Test data factories | hardcoded | partial | factories/generators |
| 6.2 | Cleanup strategy | none | partial | reliable cleanup/reset |
| 6.3 | Secrets handling | hardcoded | env but messy | clean .env + CI secrets |
| 6.4 | Environments | ad-hoc | some docs | clear env matrix |
| 6.5 | Feature flags | random | partial | controlled flags |
| 6.6 | Time control | flakey time | partial | freeze/mask when needed |
| 6.7 | External deps | unstable | mixed | mocked/contracted |
| 6.8 | Data ownership | shared accounts | mixed | isolated accounts/tenants |

---

## Aspect 7: CI, Reporting & Artifacts (10%)

**Max: 80 points (8 criteria)**

| # | Criterion | 0 | 5 | 10 |
|---|-----------|---|---|-----|
| 7.1 | CI execution | none | basic | reliable pipelines |
| 7.2 | Sharding/parallel | none | partial | optimized CI runtime |
| 7.3 | Tag-based runs | none | smoke only | robust matrix (smoke/regression) |
| 7.4 | Artifacts | none | screenshots only | trace/video/html reports |
| 7.5 | Failure triage | manual | partial | standardized triage process |
| 7.6 | Reporting | raw logs | basic report | rich report (HTML/JUnit) |
| 7.7 | Flaky quarantine | none | manual | policy + tooling |
| 7.8 | Deterministic CI env | unknown | mixed | pinned deps, stable browser |

---

## Aspect 8: AI-Agent Operability (10%)

**Max: 130 points (13 criteria)**

AI agents perceive web pages through **semantic structure, accessibility attributes, and visible text** — just like assistive technology. Tests that follow a11y best practices are inherently AI-agent friendly.

| # | Criterion | 0 | 5 | 10 |
|---|-----------|---|---|-----|
| 8.1 | Semantic targeting | "click div" | mixed | role-based element identification |
| 8.2 | Accessible names | generic/missing | partial | all interactive elements have descriptive names |
| 8.3 | User-visible behavior | tests implementation | mixed | tests what users see and interact with |
| 8.4 | No ambiguity | "click the thing" | mixed | explicit selectors with accessible names |
| 8.5 | No hidden state | lots of magic | some | all context visible in scenario |
| 8.6 | Deterministic runs | random/time based | mixed | same input = same output |
| 8.7 | Repo navigation | no map | basic | clear file structure docs |
| 8.8 | Conventions documented | none | partial | "how to add test" guide |
| 8.9 | Step catalog | none | partial | discoverable step index |
| 8.10 | Minimal cognitive load | complex patterns | mixed | consistent, predictable patterns |
| 8.11 | Safe automation | destructive steps | mixed | clear constraints/guards |
| 8.12 | A11y as test foundation | ignored | partial | semantic HTML enables both a11y and AI testing |
| 8.13 | A11y testing integration | none | manual checks | automated @axe-core/playwright scans |

**Key insight:** An AI agent navigating a page is functionally similar to a screen reader user — both rely on:
- Semantic HTML structure (`<button>`, `<nav>`, `<main>`, not `<div onclick>`)
- ARIA roles and labels
- Accessible names that describe purpose
- Visible text that matches intent

**Recommendations for AI-agent readability:**
- Prefer `getByRole('button', { name: 'Submit' })` over `locator('.btn-primary')`
- Use descriptive accessible names: "Save changes" not "Submit"
- Ensure labels are programmatically associated with inputs
- Keep step language aligned with visible UI text
