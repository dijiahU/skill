# MCP Configuration Audit Framework

**Architecture:** This framework provides scoring criteria and query guides. **All validation rules are fetched from official documentation via docs-management skill** - this file contains NO duplicated official content.

## 🚨 MANDATORY: Use docs-management BEFORE Any Finding

> **ABSOLUTE REQUIREMENT - NEVER SKIP THIS STEP:**
>
> Before flagging ANY finding about MCP configuration, server entries, or transport types:
>
> 1. **INVOKE** `docs-management` skill with query: `".mcp.json" "MCP configuration" "mcpServers" example`
> 2. **READ** the official documentation examples
> 3. **VERIFY** your finding matches what official docs show
> 4. **IF UNCERTAIN** → Do NOT flag. Ask for clarification instead.
>
> **Flagging findings without verifying against official docs = AUDIT FAILURE**

### Verification Checkpoint

Before including ANY finding in your audit report:

- [ ] Did I invoke docs-management for this topic?
- [ ] Did I read the official example/schema?
- [ ] Does my finding contradict official documentation?
- [ ] Did I run `claude mcp list` first to verify actual state? ← **CLI-FIRST IS MANDATORY**

**If you cannot verify against official docs, mark finding as UNVERIFIED and do not deduct points.**

## How Audits Work

1. **Auditor loads** `mcp-integration` skill
2. **Skill delegates** to `docs-management` for official rules
3. **Official docs provide** the actual validation criteria
4. **This framework provides** scoring weights and thresholds

## External Technology Validation

**CRITICAL:** Before flagging any finding related to external technologies, validate with MCP servers.

For complete validation guidance, see: `../../shared-references/external-tech-validation.md`

**Quick Reference:**

- .NET/Azure: microsoft-learn + perplexity (REQUIRED)
- npm/PyPI: context7 + perplexity
- Version claims: perplexity ALWAYS
- MCP unavailable: Flag as UNVERIFIED

## Documentation Query Guide

Before auditing, query `docs-management` skill for these topics:

| Category | Query Keywords | What to Fetch |
| --- | --- | --- |
| Broad Coverage | `MCP servers` | General MCP documentation - start here |
| Configuration Structure | `MCP configuration .mcp.json mcpServers schema` | Valid file structure |
| Server Entries | `MCP server configuration mcpServers command args` | Server entry format |
| Transport Types | `MCP transport stdio http sse streamable` | Valid transport options |
| Authentication | `MCP authentication OAuth headers env secrets` | Auth configuration |
| Scopes | `MCP scopes project user installation mcp` | Scope locations |
| Environment Variables | `MCP environment env expansion secrets variables` | Env var patterns |
| Server Discovery | `claude mcp list mcp get server` | CLI-based discovery |
| Permissions | `MCP permissions tool access allow deny` | Permission patterns |

**CRITICAL:** The auditor MUST query docs-management and use the returned official documentation as the source of truth for validation rules.

## 🚨 Required docs-management Queries Per Category

**MANDATORY:** Execute these queries BEFORE scoring each category:

| Category | Required Query | What to Verify |
| --- | --- | --- |
| Broad Coverage | `MCP servers` | Start here for general context |
| Configuration | `MCP configuration .mcp.json mcpServers schema structure` | Valid structure, required fields |
| Server Entries | `MCP server mcpServers command args env configuration` | Server entry format, required fields |
| Transport | `MCP transport stdio http sse streamable types` | Valid transport types |
| Scopes | `MCP scopes mcp installation project user plugin` | Valid file locations |
| Authentication | `MCP authentication OAuth env secrets headers` | Auth configuration patterns |
| Permissions | `MCP permissions tool access allow deny rules` | Permission configuration |

### Query Execution Protocol

1. **Before each category** → Run the required query
2. **Read returned docs** → Find the relevant example/table
3. **Compare your finding** → Does it match official docs?
4. **If mismatch** → Your finding is WRONG, not the MCP config
5. **If uncertain** → Do NOT deduct points, mark as NEEDS-VERIFICATION

## Extensive Validation Requirements

**CRITICAL:** Before flagging ANY finding, you MUST:

1. **Query docs-management EXTENSIVELY** - Use multiple keyword combinations
2. **Read the FULL official documentation** - Not just snippets
3. **Check for optional vs required fields** - Query: `"optional" "required" {topic}`
4. **Verify default behaviors** - Query: `"default" {topic}`
5. **Distinguish official vs repo-specific rules** - Only official rules are errors; repo-specific are suggestions
6. **Verify configuration paths** - Query: `"MCP configuration" "file locations" scope`

**If official documentation does not explicitly prohibit something, do NOT flag it as an error.**

**If you cannot find documentation supporting your finding, the finding is INVALID.**

## Audit Scoring Rubric

This scoring rubric is used by the `mcp-auditor` agent for formal audits.

### Category Scores

| Category | Points | Description |
| --- | --- | --- |
| Configuration Structure | 25 | Valid JSON, required fields present |
| Server Entries | 25 | Valid server configurations, proper format |
| Transport Config | 20 | Valid transport types, correct settings |
| Authentication | 15 | Proper auth setup, no exposed secrets |
| Scope Compliance | 15 | Appropriate scope (project/user/plugin) |

The maximum possible score is **Total: 100 points**.

### Scoring Details

**Note:** Pass conditions are validated against official documentation fetched via docs-management. The criteria below describe WHAT to check, not the specific rules (which come from docs).

#### Configuration Structure (25 points)

| Criterion | Points | Validation Source |
| --- | --- | --- |
| Valid JSON syntax | 10 | Syntax check |
| Required top-level structure | 10 | Query: ".mcp.json schema" |
| No unknown fields | 5 | Query: "MCP configuration options" |

#### Server Entries (25 points)

| Criterion | Points | Validation Source |
| --- | --- | --- |
| Valid server names | 8 | Query: "MCP server naming" |
| Required server fields | 10 | Query: "mcpServers configuration" |
| Valid command/args | 7 | Query: "MCP server command" |

#### Transport Config (20 points)

| Criterion | Points | Validation Source |
| --- | --- | --- |
| Valid transport type | 10 | Query: "MCP transport types" |
| Correct transport settings | 10 | Query: specific transport documentation |

#### Authentication (15 points)

| Criterion | Points | Validation Source |
| --- | --- | --- |
| No hardcoded secrets | 8 | Security check |
| Proper auth configuration | 4 | Query: "MCP authentication" |
| Env var usage for secrets | 3 | Best practice check |

#### Scope Compliance (15 points)

| Criterion | Points | Validation Source |
| --- | --- | --- |
| Correct file location | 8 | Query: "MCP scopes", "mcp installation scopes" |
| Appropriate server scope | 7 | Analysis: servers match intended scope |

### Thresholds

| Score Range | Result |
| --- | --- |
| 85-100 | **PASS** |
| 70-84 | **PASS WITH WARNINGS** |
| Below 70 | **FAIL** |

### Automatic Failures

Regardless of score, an MCP configuration **automatically fails** if:

- Invalid JSON syntax
- Contains exposed secrets (API keys, tokens, passwords)
- References non-existent commands/scripts
- Uses completely invalid transport types

## MCP Configuration Discovery

### CRITICAL: CLI-First Discovery (MANDATORY)

**ALWAYS run `claude mcp list` FIRST** before searching for configuration files. This provides ground truth from the actual running system.

```bash
# Step 1: Get authoritative list of configured servers
claude mcp list

# Step 2: Get details on specific server (shows scope and config)
claude mcp get <server-name>
```

The CLI output shows:

- All configured servers (regardless of which file they're in)
- Scope (User config, Project config, etc.)
- Connection status
- Transport type and configuration

**Why CLI First:**

- File locations can change between Claude Code versions
- Some configs may be in unexpected locations
- CLI is the source of truth for what's actually running

### Configuration File Locations

**Query docs-management:** `"MCP configuration" "mcp installation scopes" "file locations"`

File locations come from official documentation. Do NOT hardcode paths - always verify current locations via docs-management.

**ALWAYS use CLI discovery first** (`claude mcp list`) to get ground truth, then cross-reference with official documentation for file locations.

## Repository-Specific Standards

These standards are specific to this repository and NOT from official Claude Code documentation:

| Standard | Value | Rationale |
| --- | --- | --- |
| Env var for secrets | Always use `${ENV_VAR}` | Security |
| Server naming | Descriptive, lowercase | Consistency |
| Local servers | Prefer stdio transport | Simplicity |

## What This Framework Does NOT Contain

This file intentionally excludes:

- **Specific configuration schema** - Fetch from docs-management
- **Valid transport type list** - Fetch from docs-management
- **Authentication options** - Fetch from docs-management
- **Any content that exists in official documentation**

---

**Last Updated:** 2025-12-25
**Architecture:** Query-based audit framework (no duplicated official content)
**Update:** Added MANDATORY docs-management enforcement section
