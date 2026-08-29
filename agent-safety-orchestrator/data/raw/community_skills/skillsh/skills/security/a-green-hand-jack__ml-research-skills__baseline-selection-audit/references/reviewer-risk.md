# Reviewer Risk

Translate baseline issues into likely reviewer objections.

## Common Attacks

`missing-direct-competitor`
: "The paper does not compare against the most relevant prior work."

`missing-sota`
: "The method is not compared to current strong baselines, so the empirical claim is unsupported."

`weak-baseline`
: "Baselines are old, under-tuned, or not representative."

`unfair-compute`
: "The proposed method uses more compute, parameters, data, or tuning."

`unfair-protocol`
: "Comparisons use different splits, metrics, decoding, preprocessing, or evaluation scripts."

`missing-ablation`
: "The paper does not show which component causes the gain."

`missing-control`
: "The improvement could come from data, model size, training recipe, or evaluation artifact."

`overbroad-claim`
: "The claim is broader than the comparison set supports."

`non-reproducible-baseline`
: "The baseline implementation is unclear or not reproducible."

`appendix-burying`
: "Important comparisons are hidden in the appendix or omitted from the main table."

## Severity

`fatal`
: Likely rejection unless resolved or claim is substantially narrowed.

`major`
: Strong negative point; can lower score significantly.

`medium`
: Must answer clearly; may be acceptable with good justification.

`minor`
: Improve clarity or polish, low decision impact.

## Mitigation Types

- `run`: add the baseline experiment
- `matched-run`: run a compute/parameter/data-matched comparison
- `ablate`: add a component or control ablation
- `cite`: discuss and position without experiment
- `justify-exclusion`: explain why direct comparison is invalid
- `narrow-claim`: reduce claim scope to supported setting
- `appendix`: add lower-priority baseline outside main table
- `accept-risk`: explicitly accept residual risk when cost exceeds value

## Risk Table

```markdown
| Baseline issue | Reviewer attack | Severity | Mitigation | Owner/action |
|---|---|---|---|---|
```

Write attacks in realistic reviewer language. The goal is to make the risk obvious enough that the project can act on it.
