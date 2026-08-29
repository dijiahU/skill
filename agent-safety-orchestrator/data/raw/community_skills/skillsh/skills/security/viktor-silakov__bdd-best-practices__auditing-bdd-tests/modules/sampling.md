# Sampling Module

Stratified sampling strategy for large repositories.

## When to Sample

- **Small repos (≤20 scenarios):** Analyze all — no sampling needed
- **Medium repos (21–100 scenarios):** Sample 30–50% or 25–40 scenarios
- **Large repos (100+ scenarios):** Sample 20–30% or max 50 scenarios

## Stratification Rules

1. **Build strata from:**
   - Tags: `@smoke` vs `@regression` vs `@wip`
   - Domains: `auth/`, `checkout/`, `profile/`
   - Age: new (last 30 days) vs legacy

2. **Quotas:**
   - At least 2 scenarios per stratum
   - At least 20% of total sample per stratum

3. **Mandatory picks (if history exists):**
   - Top 5 most flaky scenarios
   - Recently failed scenarios

4. **Cap by time budget:**
   - Quick audit: 15–25 scenarios
   - Standard audit: 25–40 scenarios
   - Deep audit: 40–60 scenarios

## Output Format

```
Sampling Strategy:
- Total scenarios: {N}
- Sample size: {M} ({percent}%)
- Strata: {list}
- Mandatory picks: {list or "none"}
```
