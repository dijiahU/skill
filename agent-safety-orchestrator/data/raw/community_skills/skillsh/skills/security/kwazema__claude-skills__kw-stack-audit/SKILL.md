---
name: kw-stack-audit
description: >
  Audit frontend project quality configuration (TypeScript, formatter, Supabase types,
  library consistency, type safety in code, hardcoded constants/secrets, testing).
  Use when the user wants to review or improve a project's foundation, detect tooling
  tech debt, prepare a project for TDD, or bootstrap strict config from day one.
  Triggers: "stack audit", "audit", "audit project", "review stack", "strict TypeScript",
  "add Biome", "detect inconsistencies", "improve project base",
  "revisar el stack", "configurar TypeScript estricto", "anadir Biome",
  "detectar inconsistencias", "mejorar la base del proyecto".
  Presents findings first and waits for explicit approval before applying changes.
---

# Stack Audit

Interactive quality audit for frontend project stacks.
Analyzes, proposes, and applies changes **only with explicit user approval**.

## Philosophy

- Audit first, change later. Never apply changes without confirmation.
- Each block of changes is presented separately and approved individually.
- Respect existing project decisions (if Prettier is set up, don't propose Biome).
- Distinguish between new and existing projects: rule severity changes accordingly.
- Don't install testing: report the gap and document that it needs Superpowers (TDD-assisted development workflow).

---

## Pre-flight — detect context before starting

Before any analysis:

1. **Detect package manager:** look for `bun.lockb` → bun, `pnpm-lock.yaml` → pnpm,
   `package-lock.json` → npm. Use the correct one in all subsequent commands.

2. **Detect project maturity:**
   - Count `.tsx` and `.ts` files in `src/` (excluding `node_modules` and auto-generated types).
   - < 15 code files → **new project**. Severity: `error` for type rules.
   - >= 15 code files → **existing project**. Severity: `warn` for type rules (progressive migration).
   - Report: "Project detected as **new/existing** (N files in src/). Recommendations adjusted accordingly."

3. **Read CLAUDE.md** if it exists at the project root: it may contain conventions or constraints that affect recommendations.

---

## Phase 1: Analysis — read without touching anything

Inspect these files if they exist:

- `package.json` — dependencies, devDependencies, scripts
- `tsconfig.json` and `tsconfig.app.json` — compiler options
- `.eslintrc.*` or `eslint.config.*` — linting config
- `.prettierrc.*` or `biome.json` — formatter
- `vitest.config.*`, `jest.config.*` — test runner
- `.env`, `.env.example`, `.env.local` — environment variables

Also run these counts (grep with `output_mode: "count"` or equivalent):

- `as any` in `src/` → real type safety indicator
- `@ts-ignore` and `@ts-expect-error` in `src/` → type suppressions
- `// eslint-disable` and `// biome-ignore` in `src/` → linter suppressions
- `console.log` and `console.error` in `src/` → uncentralized logs

---

## Phase 2: Generate findings report

Present section by section. Read the corresponding reference file for detailed workflow:

### 2.1 TypeScript
Read `references/typescript.md` for the full TypeScript audit workflow including strict migration strategy.

### 2.2 Formatter and Linter
Read `references/formatter-linter.md` for Biome vs Prettier decision tree and recommended config.

### 2.3 Supabase Types — Schema Drift
Read `references/supabase-types.md` for GenTypes detection and migration pattern. Only applies if the project uses Supabase.

### 2.4 Library Consistency
Read `references/library-consistency.md` for duplicate/conflicting library detection across 8 categories.

### 2.5 Constants and Security
Read `references/security-constants.md` for hardcoded secrets, duplicate constants, and .env checks.

### 2.6 Testing

Detect current state:

- Look for `vitest`, `jest`, `@testing-library/react` in `package.json`.
- Look for `*.test.*` or `*.spec.*` files in `src/`.
- Look for a `test` script in `package.json`.

**If no runner installed:**

> No test runner configured. Superpowers (TDD-assisted development workflow) needs
> an installed runner for the RED-GREEN-REFACTOR cycle. For the Vite + React + TypeScript
> stack, the natural choice is Vitest + React Testing Library.
> This skill does not install testing — that decision should be made alongside
> Superpowers configuration.

**If runner exists but zero tests:**

> Runner installed but no test files found. The highest-value files to start with
> are pure utilities in `src/lib/` and services without UI dependencies.

**Do not install or configure anything related to testing.** Report only.

---

## Phase 3: Executive summary

After the full analysis, show a summary table:

```
Area                  Status           Proposed action
-------------------------------------------------------------------
TypeScript config     [status]         Enable strict (+ flags)
Real type safety      [status] (N any) Reduce as any (N occurrences)
Formatter             [status]         Install Biome / already configured
Supabase types        [status]         Migrate to GenTypes derivation
Library consistency   [status]         Standardize duplicates
Constants/security    [status]         Centralize / move to .env
Testing               [status]         (pending with Superpowers)
```

Then ask:

> Which area would you like to start with? We can go one at a time.
> I'll show you the exact changes before applying anything.

---

## Phase 4: Apply changes (only with approval)

For each approved area, read the corresponding reference file for the detailed apply workflow. General principle: show the exact diff before every change, wait for confirmation, then apply.

---

## General rules

- Never run install without showing the exact command to the user first.
- Never modify files without showing the diff first.
- If a section has no issues, report it explicitly as a pass so the user knows it was checked.
- If CLAUDE.md exists, respect the conventions it defines.
- Don't propose changes to auto-generated files (Supabase types, shadcn/ui components).
- When reporting `as any` metrics, exclude auto-generated files and `node_modules`.
