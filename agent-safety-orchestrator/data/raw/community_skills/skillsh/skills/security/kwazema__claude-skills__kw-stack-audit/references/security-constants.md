# Constants and Security Audit

## Hardcoded secrets and URLs

Search for patterns in `src/` (excluding `node_modules`, `dist`, auto-generated files):

- URLs: `https://` in strings (except comments and imports)
- Keys: patterns like `sk_`, `pk_`, `key=`, `secret`, `password`, `token` in strings
- Supabase URLs or anon keys outside `.env` or config files

If found: list file and line. Recommend moving to environment variables.

## Duplicate constants

- Search for definitions of the same constant in multiple files (pattern: `const NAME =`
  with the same value in more than one file).
- If detected: propose centralizing in `src/lib/constants.ts`.

## .env check

- If `.env` exists but not `.env.example`: report missing template.
- If `.env` is in `.gitignore`: good.
- If `.env` is NOT in `.gitignore`: report risk.

## Apply workflow

1. Show constants to centralize and their current locations.
2. Show proposed `src/lib/constants.ts` file.
3. Wait for confirmation.
4. Create the file and update imports.
