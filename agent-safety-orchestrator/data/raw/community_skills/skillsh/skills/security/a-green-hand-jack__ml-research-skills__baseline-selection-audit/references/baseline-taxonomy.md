# Baseline Taxonomy

Classify each candidate by role before deciding whether it must be run.

## Roles

`direct-competitor`
: Solves the same problem with a method that could make the proposed method look incremental.

`strongest-current-method`
: Best or near-best reported empirical method under the relevant benchmark, even if conceptually different.

`standard-benchmark-baseline`
: Official or commonly expected baseline for the dataset, task, metric, or community.

`classic-baseline`
: Older, simple, or highly cited method that gives historical context and guards against overclaiming.

`nearest-previous-method`
: The most similar predecessor, previous version, or method component being modified.

`ablation-baseline`
: The proposed method with one component removed, simplified, or replaced.

`control-baseline`
: Trivial, random, no-method, matched-parameter, matched-compute, or frozen control that tests confounds.

`oracle-or-upper-bound`
: Uses information not available to a deployed method, but establishes a ceiling or diagnostic reference.

`resource-matched-baseline`
: A comparison equalized by compute, FLOPs, parameters, wall-clock, data, or number of function evaluations.

`domain-required-baseline`
: A method expected by the target domain or venue even if it is not the closest paper.

`citation-only`
: Must be discussed or cited, but not run as an experiment because it addresses a different claim.

`not-comparable`
: Related but invalid as a direct comparison under the current task, data, metric, or resource setting.

## Requirement Levels

`must-have`
: Omission creates a likely major or fatal reviewer objection.

`should-have`
: Adds meaningful confidence or blocks a plausible reviewer objection, but can be omitted with a good reason.

`optional`
: Useful context, appendix material, or low-risk addition.

`not-comparable`
: Do not run as a direct comparison; explain why if readers may expect it.

`citation-only`
: Include in related work or positioning, not in the main result table.

## Candidate Table

```markdown
| Candidate | Role | Requirement | Why reviewers expect it | Comparison form | Source/status |
|---|---|---|---|---|---|
```

## Exclusion Reasons

Use concrete exclusion reasons:

- different task
- different data or extra supervision
- incompatible metric
- incompatible resource regime
- no faithful reproduction path
- unavailable code and too expensive to reimplement
- superseded by a stronger baseline
- addresses only motivation or theory
- evaluates a different claim

Avoid vague exclusions like "not relevant" unless the mismatch is stated.
