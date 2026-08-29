---
name: code-review-assistant
description: Performs structured code review on a diff or file set, producing inline comments with severity levels and a summary. Checks correctness, error handling, security, and maintainability — in that priority order. Use when reviewing a pull request, when the user asks for a code review, when preparing code for merge, or when a second opinion is needed on a change.
license: Apache-2.0
metadata:
  category: "code-quality"
  suite: "general-secure-coding-agent-skills"
  version: "0.2.0"
  related: "code-smell-detector, code-refactoring-assistant, technical-debt-analyzer"
---

# Code Review Assistant

Review code as a senior engineer would: find the bug that will page someone at 3am, not the missing semicolon. Every comment should be one the author couldn't have found with a linter.

## Priority order — always review in this sequence

Stop after any tier that produces a **Blocking** finding. There is no value in reporting naming nits on code that deletes the wrong rows.

1. **Correctness** — does it do what the PR says it does?
2. **Error & edge-case handling** — what happens at empty / null / max / concurrent?
3. **Security** — untrusted input, authz, secrets, injection
4. **Performance** — only for hot paths; O(n²) in a loop over user records is a bug, in a 5-element config list it isn't
5. **Maintainability** — naming, structure, duplication, tests
6. **Style** — only if the project has no formatter; otherwise skip entirely

## Step 1 — Understand before you judge

Read in this order:

1. **PR title + description.** This is the contract. Everything else is checked against it.
2. **Test changes.** Tests encode what the author *thinks* the code does. Mismatch between test names and PR description = first red flag.
3. **The diff itself.** Now you know what to look for.

If the PR description is empty or says "misc fixes" — your first comment is asking for a description. You cannot review intent you don't know.

## Step 2 — Correctness pass

For every changed function, hold the stated intent (from the PR description) against the implementation. Specific checks:

- **Off-by-one at boundaries.** `<` vs `<=`, `len-1` vs `len`, slice end-exclusive vs inclusive. If you see a loop boundary change in the diff, verify against one concrete example.
- **Negation logic.** `if (!isValid || !isEnabled)` — expand De Morgan's in your head and verify the truth table is what the author meant.
- **Early returns + cleanup.** New `return` in the middle of a function that previously had a single exit → does it skip a `close()` / `unlock()` / `commit()` that used to run?
- **State mutation ordering.** If the diff reorders two writes to shared state, what reads them? If the diff adds a write before an existing read of the same field, is the old read still correct?
- **Async/await:** Missing `await` on a promise-returning call is a silent future bug. Every call to an `async` function should be awaited, explicitly `void`ed, or collected for `Promise.all`.

## Step 3 — Error & edge-case pass

For each changed function, walk the inputs:

| Input shape        | Ask                                                          |
| ------------------ | ------------------------------------------------------------ |
| Collection / array | What if it's empty? What if it has one element?              |
| Optional / nullable| Is it checked before first deref? Is there a *test* for the null path? |
| String             | Empty string? Whitespace-only? Longer than the DB column?    |
| Number             | Zero? Negative? Larger than the downstream type can hold?    |
| External call      | What if it throws? Times out? Returns a shape you don't expect? |
| Map / dict lookup  | What if the key is absent?                                   |

**Catch blocks deserve extra scrutiny.** A `catch` that just logs and continues turns a loud failure into a silent data corruption. Ask: *is the system in a valid state after this catch runs?* If not → Blocking.

## Step 4 — Security pass

Not a full audit — just the things a reviewer spots in a diff:

- Any string concatenation that feeds a query, shell command, HTML, or URL → does untrusted input reach it?
- Any new `exec`, `eval`, `system`, `child_process`, `subprocess`, `Runtime.exec`
- Any new endpoint or handler → where's the authz check? Is it before or after the first data access?
- Any literal that looks like a credential → even in tests, even commented out
- Deserialization of external input (`pickle.loads`, `yaml.load`, `ObjectInputStream`, `unserialize`)

For anything beyond a spot check, defer: "→ run `static-vulnerability-detector` on this path before merge."

## Step 5 — Scope the maintainability pass

**Do not comment on code the PR didn't touch.** If a function was already 200 lines and the PR adds 3 lines to it, the 200-line problem is pre-existing tech debt, not this author's responsibility. At most: one summary-level comment suggesting a follow-up, never inline.

On code the PR *did* introduce:
- Is the new abstraction pulling its weight? A new interface with one implementer is a prediction, not a requirement. Ask what the second implementer would be.
- Is it tested? If the PR adds a branch with no corresponding test, say so — and say which specific case is missing.

## Severity levels

| Level          | Meaning                                               | Author's obligation      |
| -------------- | ----------------------------------------------------- | ------------------------ |
| **Blocking**   | Merge will cause a bug, security issue, or data loss  | Must fix before merge    |
| **Should-fix** | Will cause pain later; fix is clear and scoped        | Fix now or open a follow-up with a link |
| **Nit**        | Preference. Reasonable people disagree.               | Author's call. No re-review needed. |
| **Question**   | You don't understand; might be fine, might not        | Author answers; you decide severity from the answer |

**Do not mark something Blocking to win a style argument.** Blocking means "this will break production." If you're not confident it will, it's Should-fix at most.

## Output format

```
## Summary
Adds retry-with-backoff to the payment client.
1 blocking (retries non-idempotent POST), 1 should-fix, 2 nits.
Recommend addressing the blocking finding before approval.

## Findings

### src/payments/client.ts:45  [Blocking]
Retry wraps `POST /charges`. That endpoint is not idempotent — a
transient 503 after the charge succeeded server-side will retry and
double-charge the customer.
→ Either: pass an Idempotency-Key header and have the server dedupe,
or only retry on errors that guarantee the request never reached the
server (connection refused, DNS failure).

### src/payments/client.ts:52  [Should-fix]
Backoff is 2^attempt seconds, uncapped. Attempt 10 = 17 minutes.
→ Cap at 30s: `Math.min(2 ** attempt, 30)`.

### src/payments/client.ts:38  [Nit]
`let` could be `const` — `delayMs` is never reassigned.

### test/payments.test.ts:140  [Question]
This test asserts 3 retries, but I don't see where the max is
configured. Is it hardcoded or am I missing a fixture?
```

## Worked example

**Diff:**
```diff
  async function deleteUser(userId) {
-   const user = await db.users.findById(userId);
-   if (!user) throw new NotFoundError();
-   await db.users.delete(userId);
+   await db.users.delete(userId);
+   await cache.invalidate(`user:${userId}`);
  }
```

**Review:**

1. *Correctness:* The null check is gone. `db.users.delete(nonexistentId)` — what does it do? If it's a no-op that returns 0 rows affected, fine. If it throws, the error changed from `NotFoundError` to a DB error — API contract break. → **Question.**
2. *Error handling:* If `delete` succeeds but `cache.invalidate` throws, the user is gone from the DB but the cache still serves them. Next read is a ghost. → **Should-fix**: invalidate first, or catch-and-log the cache failure since the DB is source of truth.
3. *Ordering:* Actually — the ordering *is* the bug. Invalidate-then-delete has a race (another request repopulates the cache between the two), but delete-then-invalidate has the failure-mode above. Pick your poison, but document which one and why. → folds into the Should-fix.
4. Nothing Blocking — the change does what the PR says. Approve once the question is answered and the failure mode is acknowledged.

## Do not

- **Rewrite the PR in the review.** If you'd do it differently but the author's way works, that's a Nit or nothing.
- **Comment on style the formatter owns.** If the project runs prettier/black/gofmt, style comments are noise.
- **Approve with unresolved Blocking findings** "to unblock the author." That's what Should-fix is for.
- **Ask questions you can answer yourself in 30 seconds.** Read the surrounding code first.
- **Pile on.** If there are already 15 comments from another reviewer, add only what's new. Duplicate comments waste the author's time.
- **Block on test coverage percentage.** Block on *the specific untested case that matters*, and name it.
