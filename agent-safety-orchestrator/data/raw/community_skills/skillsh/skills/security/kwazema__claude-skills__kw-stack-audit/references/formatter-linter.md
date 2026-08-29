# Formatter and Linter Audit

## Findings

Detect current state:

- If `biome.json` exists → formatter already configured, report version and active rules.
- If `.prettierrc.*` exists → formatter already configured, don't propose switching to Biome.
- If ESLint exists without formatter → report formatting gap.
- If nothing exists → report complete gap.

**If no formatter**, ask the user:

> No formatter configured. Do you prefer Biome (replaces ESLint + Prettier in one,
> faster) or Prettier (more familiar, compatible with existing ESLint)?

**If user chooses Biome AND ESLint exists**, manage the transition:

1. List installed ESLint packages (eslint, plugins, configs).
2. Identify custom ESLint rules that have Biome equivalents.
3. Identify rules without equivalents (if any, warn before migrating).
4. Propose: uninstall ESLint packages + delete config + install Biome.
5. Show the full list of packages to uninstall.

## Recommended Biome config

Use as base (do NOT depend on `npx biome init`):

For **new** projects (severity: error):

```jsonc
{
  "organizeImports": { "enabled": true },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "suspicious": {
        "noExplicitAny": "error"
      },
      "correctness": {
        "noUnusedVariables": "error",
        "noUnusedImports": "error",
        "useExhaustiveDependencies": "warn"
      },
      "style": {
        "noNonNullAssertion": "warn"
      }
    }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "single",
      "semicolons": "always",
      "trailingCommas": "all"
    }
  },
  "files": {
    "ignore": ["dist", "node_modules"]
  }
}
```

For **existing** projects: change `noExplicitAny` to `"warn"` and `noUnusedVariables` to `"warn"`.

If the project has auto-generated files (like Supabase types), add their path to `files.ignore`.

## Apply workflow

1. If ESLint exists, show list of packages to uninstall and config to delete.
2. Show package to install: `@biomejs/biome`.
3. Show the full `biome.json` that will be created (adjusted to project maturity).
4. Show scripts to add/modify in `package.json`:
   ```json
   "lint": "biome check .",
   "lint:fix": "biome check --fix .",
   "format": "biome format --write ."
   ```
5. Wait for confirmation.
6. Run installation, create config, update scripts, remove ESLint if applicable.
7. Ask whether to run the formatter on existing code.
