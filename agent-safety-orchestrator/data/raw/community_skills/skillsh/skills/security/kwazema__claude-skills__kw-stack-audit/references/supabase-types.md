# Supabase Types — Schema Drift Audit

**Only applies if the project uses Supabase.** Detect by looking for `@supabase/supabase-js` in `package.json`. If not found, mark as N/A and skip.

## Step 1 — Detect GenTypes

- Look for the generated types file: `src/integrations/supabase/types.ts` or similar
  (also `src/types/supabase.ts`, `src/lib/database.types.ts`).
- If not found: report that GenTypes are not configured and recommend `supabase gen types typescript`.

## Step 2 — Detect manual types that duplicate the DB

- Read files in `src/types/` (or the project's types folder).
- For each interface/type that appears to represent a DB table, check if the equivalent
  table exists in the GenTypes file.
- If duplication found: report which manual interfaces replicate existing tables.

## Step 3 — Measure the impact

- Count `as any` specifically in `src/services/` files — that's where schema drift
  manifests most strongly.
- Look for patterns like `(variable as any).field` that indicate untyped fields.

## Report

> Found N manual interfaces in src/types/ that replicate DB tables already
> covered by Supabase GenTypes. This causes schema drift: when a field is added
> to the DB and types are regenerated, the manual interfaces don't update
> and force `as any`.
>
> Recommended pattern — derive types directly from the generated schema:
>
> ```typescript
> import type { Database } from '@/integrations/supabase/types';
> type Tables = Database['public']['Tables'];
> export type Employee = Tables['employees']['Row'];
> export type EmployeeInsert = Tables['employees']['Insert'];
> ```

**Do not apply changes automatically in this section.** This is a migration that requires
manual review file by file. Only report the gap and propose the pattern.

## Apply workflow

1. Show a concrete example from the project: manual interface vs GenType equivalent.
2. Show the migration pattern (helper file with derived type aliases).
3. Warn that migration is manual and file-by-file.
4. Do not apply automatically — create the helper file and document what to migrate.
