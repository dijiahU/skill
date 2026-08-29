# TypeScript Audit

## Findings

**Critical disabled options** (check in tsconfig.json and tsconfig.app.json):

- `strict: false` or absent — "Does not enable any strict checks. Root cause of all type problems."
- `strictNullChecks: false` or absent — "TypeScript won't warn when something can be null. Primary source of runtime crashes with Supabase data."
- `noImplicitAny: false` or absent — "Allows implicit `any` in parameters and untyped variables."
- `noUnusedLocals: false` — "Allows dead variable accumulation without warning."
- `noUnusedParameters: false` — "Allows unused function parameters."

For each disabled option, explain in one line what concrete risk it carries.

**Real type safety metrics** (from Phase 1 counts):

- Report total `as any`, `@ts-ignore`, `@ts-expect-error`.
- List the 5 files with most occurrences.
- Example: "Found 176 uses of `as any` in src/. Most affected files: analyticsService.ts (46), rrhhService.ts (12), ..."

**Proposed changes:** show exact tsconfig diff.

## For existing projects — NEVER enable `strict: true` directly

Enabling strict at once in a project with existing code breaks everything. The skill must:

1. Report how many errors it would generate (`npx tsc --noEmit --strict 2>&1 | tail -1`).
2. Recommend the gradual phase strategy, in this order:
   - **Phase A:** `noUnusedLocals` + `noUnusedParameters` (dead code cleanup, low risk)
   - **Phase B:** `strictNullChecks` (highest real impact, prevents crashes with Supabase data)
   - **Phase C:** `noImplicitAny` (forces typing everything that is currently implicit `any`)
   - **Phase D:** `strict: true` (enables everything above + strictBindCallApply, strictFunctionTypes, etc.)
3. Ask the user:

> Enabling `strict` at once in this project would generate ~N TypeScript errors.
> The recommendation is to go phase by phase, enabling one flag at a time and
> fixing errors before moving to the next. Each phase is done in its own branch.
>
> Recommended order:
> 1. `noUnusedLocals` + `noUnusedParameters` (quick cleanup, low risk)
> 2. `strictNullChecks` (most valuable, prevents null crashes)
> 3. `noImplicitAny` (eliminates implicit any)
> 4. `strict: true` (enable everything once the above are clean)
>
> Want to start with phase 1, or prefer a different approach?

## For new projects

Propose directly `strict: true` + `noUncheckedIndexedAccess: true`.
No question — it's the only correct option from day one.

## Apply workflow

1. Show exact diff for `tsconfig.json` and `tsconfig.app.json`.
2. Wait for confirmation.
3. Apply changes.
4. Run `npx tsc --noEmit` to show how many errors it generates.
5. If existing project: ask whether to fix now or in a separate branch.
