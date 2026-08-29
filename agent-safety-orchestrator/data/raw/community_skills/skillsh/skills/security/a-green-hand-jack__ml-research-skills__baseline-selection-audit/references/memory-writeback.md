# Memory Writeback

Use this when the project has `research-project-memory` files.

## What to Write

Write durable baseline knowledge:

- required baselines and why
- excluded baselines and the reason
- fairness caveats
- tuning or compute budget decisions
- reviewer risks
- planned comparison evidence
- claim narrowing caused by infeasible or failed baselines

Do not store a full literature review. Link to the literature review or audit report instead.

## `memory/decision-log.md`

Add durable baseline decisions:

```markdown
## DEC-### - Baseline set for [claim]

- Date:
- Status: active / revised / superseded
- Certainty: verified / inferred / provisional
- Decision:
- Must-have baselines:
- Excluded baselines:
- Rationale:
- Revisit trigger:
```

## `memory/risk-board.md`

Add baseline risks:

```markdown
## RSK-### - Missing or unfair baseline: [baseline/family]

- Status: open
- Severity: fatal / major / medium / minor
- Certainty: verified / inferred / unverified
- Linked claims:
- Description:
- Mitigation:
- Owner / next skill:
```

## `memory/evidence-board.md`

Add planned evidence:

```markdown
## EVD-### - Baseline comparison: [method vs baseline]

- Status: planned
- Linked claims:
- Linked risks:
- Evidence type: baseline / ablation / control / matched-run
- Fairness constraints:
- Required because:
```

## `memory/action-board.md`

Add concrete actions:

```markdown
## ACT-### - Run or justify [baseline]

- Status: todo
- Type: experiment / implementation / citation / writing / decision
- Priority: high / medium / low
- Linked risks:
- Output expected:
- Exit condition:
```

## `memory/claim-board.md`

Update claims when baseline feasibility changes scope:

- `planned`: needs baseline evidence
- `active`: has enough baseline support to write
- `narrowed`: comparison set supports a smaller claim
- `revised`: baseline result changed the story
- `cut`: unsupported after baseline audit or results

## Component Memory

If the audit affects code, update relevant worktree `.agent/worktree-status.md` with:

- baseline implementation target
- fairness constraints
- linked claim/risk IDs
- exit condition

If the audit affects the paper, update `paper/.agent/` with:

- main table rows
- appendix comparisons
- excluded-baseline wording
- related-work or limitation notes

## Certainty Labels

Use:

- `verified`: checked against primary source, official code, or actual project results
- `user-stated`: supplied by the user
- `inferred`: reviewer-risk or fairness judgment
- `unverified`: baseline candidate not yet checked

Never mark a baseline as unnecessary only because it is inconvenient.
