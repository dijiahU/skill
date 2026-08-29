# kw-stack-audit

Comprehensive quality audit for frontend project stacks. Checks TypeScript config, formatter, Supabase types, library consistency, hardcoded secrets, and testing setup.

## Install

```bash
npx skills add kwazema/claude-skills --skill kw-stack-audit
```

## What it does

- Audits TypeScript strictness and proposes a phased migration strategy
- Detects missing or misconfigured formatters (Biome/Prettier/ESLint)
- Finds Supabase schema drift from manual types duplicating GenTypes
- Identifies conflicting libraries (duplicate toast, date, icon, state libs)
- Scans for hardcoded secrets, URLs, and duplicate constants
- Reports testing gaps without installing anything

## Example

> "Run a stack audit on this project"

Claude will analyze your project config, show a findings report per area, and propose changes one by one — nothing is applied without your approval.

## Triggers

`stack audit`, `audit`, `audit project`, `review stack`, `strict TypeScript`, `add Biome`, `detect inconsistencies`

Also: `revisar el stack`, `configurar TypeScript estricto`, `detectar inconsistencias`

See [SKILL.md](./SKILL.md) for the full workflow.
