# Discovery Module

Detailed instructions for Step 1 (Discovery) of the BDD audit.

## Auto-Detection Rules

Detect stack automatically from files:

| File Pattern | Stack Detection |
|--------------|-----------------|
| `playwright.config.*` | Playwright |
| `package.json` → `playwright-bdd` | playwright-bdd |
| `cucumber.js` / `cucumber.cjs` | cucumber-js |
| `*.feature` + `step_definitions/` | Generic BDD |

## Discovery Checklist

1. **Runner/Stack:** Playwright, playwright-bdd, cucumber-js, custom harness
2. **Entry points:** `playwright.config.*`, `cucumber.*`, `package.json` scripts, CI workflows
3. **BDD assets:** `features/**/*.feature`, step definitions, fixtures/utils, page objects
4. **Artifacts:** traces/videos/screenshots, reporters (HTML/JUnit/Allure)
5. **History:** check `.bddready/history/index.json` for delta calculation

## Repository Size Classification

Classify repository to determine workflow depth:

| Size | Feature Files | Scenarios | Workflow |
|------|--------------|-----------|----------|
| Small | 1–5 | 1–20 | Quick (skip sampling, simplified scoring) |
| Medium | 6–20 | 21–100 | Standard |
| Large | 21+ | 100+ | Full (stratified sampling, detailed roadmap) |

## Output Format

```
Target: {path}
Stack: {detected_stack} (confidence: high/medium/low)
Size: {small/medium/large} ({N} features, {M} scenarios)
History: {yes/no}
```
