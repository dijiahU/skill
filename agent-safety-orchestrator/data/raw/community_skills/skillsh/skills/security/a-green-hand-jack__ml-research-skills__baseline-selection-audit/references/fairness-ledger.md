# Fairness Ledger

Use this ledger for every `must-have` and `should-have` baseline.

## Fairness Dimensions

`data`
: Same dataset, split, filtering, augmentation, pretraining corpus, and extra-data policy.

`model-capacity`
: Parameters, architecture family, context length, feature extractor, backbone, or training tokens.

`compute`
: Training FLOPs, wall-clock, hardware, epochs, number of updates, batch size, memory, and inference budget.

`tuning`
: Hyperparameter search space, number of trials, early stopping, validation access, and author effort.

`protocol`
: Benchmark rules, train/val/test split, data leakage checks, checkpoint selection, and official evaluation script.

`metric`
: Same metric definition, averaging, confidence interval, significance test, sampling temperature, decoding strategy, or NFE.

`implementation`
: Official code, faithful reimplementation, public checkpoint, version, commit, and known reproduction gap.

`reporting`
: Same units, same table placement, same seeds, same resource accounting, same failure reporting.

## Ledger Table

```markdown
| Baseline | Data | Capacity | Compute | Tuning | Protocol | Metric | Implementation | Verdict |
|---|---|---|---|---|---|---|---|---|
```

Verdicts:

- `fair`
- `fair-with-caveat`
- `needs-matched-run`
- `not-directly-comparable`
- `unverified`
- `blocked`

## Tuning Budget Ledger

```markdown
| Method | Search space | Trials | Selection metric | Compute budget | Notes |
|---|---|---|---|---|---|
```

If the proposed method receives more tuning than baselines, say so and mitigate with matched tuning, sensitivity analysis, or a narrowed claim.

## Compute-Normalized Reporting

When raw performance is not enough, add:

- performance vs training FLOPs
- performance vs inference FLOPs
- performance vs wall-clock
- speed-quality Pareto curve
- number of forward passes or function evaluations
- memory or latency
- parameter-matched and compute-matched rows

## Incompatibility Handling

If a baseline cannot be made fair:

1. state the mismatch
2. decide whether it is still useful as citation-only context
3. narrow the claim if necessary
4. document the limitation in paper text or appendix
5. add an action if reproduction may become possible later
