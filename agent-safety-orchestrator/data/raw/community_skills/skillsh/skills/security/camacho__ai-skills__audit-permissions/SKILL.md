---
name: audit-permissions
description: Use when reviewing permission prompt frequency, optimizing the allow-list, or resetting the audit log. Triggers on "audit permissions", "permission report", "allow list", "reduce prompts", "what's getting prompted".
---

# Audit Permissions

Analyze permission audit logs and recommend allow-list changes. Wraps the TypeScript analyzer in ai-env.

## Args Routing

- **No args / empty**: run report (default)
- **Args contain "reset" or "clear"**: archive log and start fresh

## Report Mode (default)

### 1. Generate Report

```bash
node --import tsx /Users/patrickcamacho/projects/camacho/ai-env/src/tools/permission-analyzer.ts
```

Present the full markdown output to the user.

### 2. Recommended Allow Rules

If the section has entries:

1. Read `~/.claude/settings.json`, extract `permissions.allow` (default `[]`)
2. Compute new patterns not already present (case-sensitive exact match)
3. Show before/after diff of ONLY `permissions.allow`
4. Ask: "Apply these N safe rules to settings.json?" (plain text y/n — works on all surfaces)
5. If approved: merge, deduplicate, sort alphabetically, write back with 2-space indent
6. Never touch keys outside `permissions.allow`. Never touch `permissions.deny`.
7. Confirm what was added

### 3. Security Warnings

If present: show each pattern with flags and sample commands. Ask: "Add any of these despite the flags? (list numbers, or 'none')"

### 4. Suppressed Recommendations

List for awareness. Do NOT offer to add — these have danger-level flags.

### Done

Summarize: what was added, how many permission prompts should be reduced.

## Reset Mode

```bash
/Users/patrickcamacho/projects/camacho/ai-env/.claude/hooks/audit-permissions-reset.sh
```

Fresh log starts automatically on next tool call.

## Prerequisites

| Requirement | Check |
|---|---|
| ai-env repo | `/Users/patrickcamacho/projects/camacho/ai-env` exists (ai-env specific — other projects will see file-not-found errors) |
| Dependencies | `pnpm install` completed in ai-env |
| Audit hook | `permission-audit-log.sh` in `~/.claude/settings.json` PreToolUse |

## Troubleshooting

| Symptom | Fix |
|---|---|
| "No audit data found" | Hook not installed or no un-allowed prompts recorded yet |
| Analyzer crashes | Run `pnpm install` in ai-env repo |
| Stale recommendations | `/audit-permissions reset`, accumulate fresh data, re-run |
| settings.json parse error | Validate: `jq . ~/.claude/settings.json` |
