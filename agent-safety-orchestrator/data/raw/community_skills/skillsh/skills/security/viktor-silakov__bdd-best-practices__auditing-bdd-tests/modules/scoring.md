# Scoring Module

Score calculation formulas and grade boundaries.

## Aspect Weights

| # | Aspect | Weight |
|---|--------|--------|
| 1 | Executable Gherkin | 16% |
| 2 | Step Definitions Quality | 14% |
| 3 | Test Architecture | 14% |
| 4 | Selector Strategy | 12% |
| 5 | Waiting & Flake Resistance | 14% |
| 6 | Data & Environment | 10% |
| 7 | CI, Reporting & Artifacts | 10% |
| 8 | AI-Agent Operability | 10% |

## Calculation

```
Aspect Score = (Sum of criteria scores / Max possible) × 100
Overall Score = Σ(Aspect Score × Weight)
```

## Grade Boundaries

| Grade | Range | Interpretation |
|-------|-------|----------------|
| A | 90–100 | Excellent — ready for AI agents |
| B | 75–89 | Good — minor improvements needed |
| C | 60–74 | Fair — significant issues exist |
| D | 45–59 | Poor — major refactoring needed |
| F | 0–44 | Failing — fundamental problems |

## Quick Scoring (Small Repos)

For small repos, use simplified 3-level scoring per aspect:
- **Good (80+):** No significant issues found
- **Fair (50–79):** Some issues, but functional
- **Poor (<50):** Major issues blocking quality

## Delta Calculation

If history exists:
```
Delta = Current Score - Previous Score
Delta Direction: up (↑) / down (↓) / same (→)
```
