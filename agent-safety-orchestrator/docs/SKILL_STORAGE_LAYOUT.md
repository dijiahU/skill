# Skill Storage Layout

This repository stores fetched upstream skills under `data/raw`.

## Directory Pattern

Use this path pattern for fetched official skills:

```text
data/raw/official_skills/<provider>/<collection>/<category>/<skill-name>/
```

Use this path pattern for fetched community marketplace skills:

```text
data/raw/community_skills/<marketplace>/<collection>/<category>/<skill-name>/
```

Use this path pattern for fetched MCP server metadata (registry-style sources that publish capabilities **not** as `SKILL.md`):

```text
data/raw/mcp_servers/<registry>/<category>/<server-slug>/
```

Use this path pattern for taxonomy / standards / practice-guide reference material (used to build the attack-surface taxonomy, **not** to enter the atomic skill library):

```text
data/raw/references/<source>/<category>/<doc-slug>/
```

Field meanings:

- `<provider>`: upstream organization or vendor, for example `openai`.
- `<marketplace>`: community marketplace identifier, for example `clawhub` or `skillsh`. For aggregator indexes that are themselves a single GitHub repository, use the repo's directory name (e.g. `agent-skills-directory`).
- `<registry>`: MCP server registry identifier, for example `modelcontextprotocol-registry`, `smithery`, `glama`, `mcp-so`, `pulsemcp`. Use lowercase + hyphens.
- `<source>` (under `references/`): origin of the reference, for example `owasp`, `snyk`, `slowmist`. Use lowercase + hyphens.
- `<doc-slug>` (under `references/`): document identifier, for example `agentic-top-10` or `practice-guide-v1`. Use lowercase + hyphens.
- `<collection>`: upstream skill collection, normalized without a leading dot. For example, OpenAI `skills/.curated/...` becomes `curated`. When a marketplace has no native collection concept, use `skills`.
- `<category>`: local topical bucket, for example `security`.
- `<skill-name>` / `<server-slug>`: upstream skill / server directory name. For ids with a provider prefix (e.g. `github/security-review`, `kloudle/cloud-security-scanner`), flatten to `<owner>__<name>`.

The contents inside each `<skill-name>/` directory should remain upstream-identical. Do not rename or rewrite internal files such as `SKILL.md`, `LICENSE.txt`, `references/`, `scripts/`, or `agents/`.

For `mcp_servers/` entries, each `<server-slug>/` directory contains a `metadata.json` with the full upstream record (server name, description, repo URL, tools list, license, etc.) plus any auxiliary files the registry exposes (e.g. `README.md`). MCP servers are not `SKILL.md` artifacts — `metadata.json` is the canonical representation.

For `references/` entries, each `<doc-slug>/` directory contains the upstream document (e.g. the markdown / PDF as published) plus a `metadata.json` capturing source URL, version / publication date, and license. References do **not** enter the atomic skill library; they feed the attack-surface taxonomy and risk dimensions used by Module 1.4 (semantic alignment) and Module 3 (Safety Router phase mapping).

## Current Layout

```text
data/raw/official_skills/
└── openai/
    └── curated/
        └── security/
            ├── security-best-practices/
            ├── security-ownership-map/
            └── security-threat-model/

data/raw/community_skills/
├── agent-skills-directory/
│   └── skills/
│       └── security/
│           └── <provider>__<skill-name>/
├── clawhub/
│   └── skills/
│       └── security/
│           └── <clawhub-skill-slug>/
├── skillsdirectory/
│   └── skills/
│       └── security/
│           └── <skillsdirectory-slug>/
└── skillsh/
    └── skills/
        └── security/
            └── <source>__<skill-id>/

data/raw/mcp_servers/
├── modelcontextprotocol-registry/security/<owner>__<name>/
├── smithery/security/<owner>__<name>/
├── glama/security/<owner>__<name>/
├── mcp-so/security/<owner>__<name>/
└── pulsemcp/security/<slug>/

data/raw/references/
├── owasp/security/agentic-ai-threats/
├── owasp/security/llm-top-10/
├── nist/security/ai-rmf-genai-profile/
├── nist/security/ai-100-2-adversarial-ml/
├── mitre/security/atlas/                              # ATLAS.yaml + tactics.yaml
├── modelcontextprotocol/security/security-best-practices/
├── anthropic/security/responsible-scaling-policy/
├── lakera/security/guide-to-prompt-injection/
├── slowmist/security/openclaw-security-practice-guide/
├── prompt-security/security/clawsec-overview/
└── useai-pro/security/openclaw-skills-security/
```

## Current Inventory

| Provider / Marketplace | Tier | Path | Skill Count | Source | Filter |
| --- | --- | --- | --- | --- | --- |
| `openai` | official | `data/raw/official_skills/openai/curated/security/` | 3 | [openai/openai-cookbook](https://github.com/openai/openai-cookbook) curated security skills | hand-picked |
| `agent-skills-directory` | community | `data/raw/community_skills/agent-skills-directory/skills/security/` | 25 | [dmgrok/agent_skills_directory](https://github.com/dmgrok/agent_skills_directory) `exports/claude-skills.json` (929 skills, pinned by `commit_sha` in catalog) | upstream `category=security` (25) ∪ keyword regex (`SECURITY_PATTERNS`) |
| `clawhub` | community | `data/raw/community_skills/clawhub/skills/security/` | 598 | [clawhub.ai](https://clawhub.ai) `/api/v1` zip downloads | per-query keyword set + content filter |
| `skillsdirectory` | community | `data/raw/community_skills/skillsdirectory/skills/security/` | 1271 | [skillsdirectory.com](https://www.skillsdirectory.com) `/api/skills` (no auth) + `/api/skills/<slug>/download` zip | upstream `category=testing-security` (1272) → keyword regex (matches almost all due to upstream "Security-tested" branding) |
| `skillsh` | community | `data/raw/community_skills/skillsh/skills/security/` | 2901 | [skills.sh](https://skills.sh) search → GitHub raw downloads pinned to default branch | per-query keyword set + post-download content filter |
| `smithery` | mcp_servers | `data/raw/mcp_servers/smithery/security/` | 352 | [registry.smithery.ai](https://registry.smithery.ai) `/servers` listing + `/servers/<qn>` detail | 26 security keyword queries + content regex on name/description/homepage. **Note:** detail endpoint may 404 for stale ids; on patched script those save the listing record without detail rather than aborting. |
| `modelcontextprotocol-registry` | mcp_servers | `data/raw/mcp_servers/modelcontextprotocol-registry/security/` | 763 | [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) `/v0/servers` cursor-paginated | full-catalog walk + content regex on name/title/description/repo |
| `glama` | mcp_servers | `data/raw/mcp_servers/glama/security/` | 2366 | [glama.ai](https://glama.ai) `/api/mcp/v1/servers` cursor-paginated (search via `query=`) | 25 security keyword queries + content regex on name/description/repo/attributes |
| `mcp-so` | mcp_servers | `data/raw/mcp_servers/mcp-so/security/` | 18 | [mcp.so](https://mcp.so) sitemaps (3771 project URLs) + per-page RSC parsing | URL keyword pre-filter (default) → page fetch → content regex on title/og/README/tags. Use `--scan-all` to fetch every project page and reach broader recall. |
| `pulsemcp` | mcp_servers | `data/raw/mcp_servers/pulsemcp/security/` | 1926 | [api.pulsemcp.com](https://api.pulsemcp.com) `/v0beta/servers` server-driven `next` pagination | full-catalog walk (14k items) + content regex on name/slug/short_description |

### References Inventory

References are *not* counted as atomic-skill candidates. They live separately and feed taxonomy work.

| Source | Path | Doc Count | Notes |
| --- | --- | --- | --- |
| `owasp` | `data/raw/references/owasp/security/` | 2 | Agentic AI Threats; LLM Top 10 (2025) |
| `nist` | `data/raw/references/nist/security/` | 2 | AI 600-1 (GenAI RMF); AI 100-2 (Adversarial ML) |
| `mitre` | `data/raw/references/mitre/security/` | 1 | ATLAS — full data export (`ATLAS.yaml` + `tactics.yaml`) |
| `modelcontextprotocol` | `data/raw/references/modelcontextprotocol/security/` | 1 | MCP Spec Security Best Practices (2025-06-18) |
| `anthropic` | `data/raw/references/anthropic/security/` | 1 | Responsible Scaling Policy (2024-10-15) — Sentinel threshold precedent |
| `lakera` | `data/raw/references/lakera/security/` | 1 | Guide to Prompt Injection (vendor research) |
| `slowmist` | `data/raw/references/slowmist/security/` | 1 | OpenClaw Security Practice Guide (project book §1 example) |
| `prompt-security` | `data/raw/references/prompt-security/security/` | 1 | clawsec overview README |
| `useai-pro` | `data/raw/references/useai-pro/security/` | 1 | Curated security-first OpenClaw skills overview |
| **References total** | | **11** | ~5.7MB total |

To extend: edit `REFERENCES` at the top of `scripts/fetch_security_references.py` and re-run.

`Skill Count` is the number of fetched skill directories on disk and updates with each re-fetch. Run `find data/raw/community_skills/<marketplace> -mindepth 4 -maxdepth 4 -type d | wc -l` to recount.

## Repository Conventions

- Store official upstream artifacts in `data/raw/official_skills`, not `third_party`.
- Store community marketplace artifacts in `data/raw/community_skills`.
- Store MCP server metadata in `data/raw/mcp_servers`. Each server directory contains a `metadata.json`; this is **not** the SKILL.md format.
- Store taxonomy / standards / practice-guide reference material in `data/raw/references`. Do not mix with skill or MCP-server content; references feed taxonomy work, not the atomic skill library.
- Keep raw skill contents unchanged once fetched.
- Put transformed, distilled, audited, or derived outputs outside `data/raw`.
- Use `scripts/` for repeatable fetching and maintenance scripts.
- Use `reports/` for time-bound working outputs (audit notes, distillation summaries, etc.). Currently empty by convention — fetch runs do not persist run records here.

## Re-Fetch Commands

All fetch scripts are idempotent: destinations that already exist are skipped unless `--overwrite` is passed. Filtering happens at fetch time (security keyword regex is built into each script), and post-fetch auditing reads directly from the on-disk skill directories rather than from per-run manifests.

If you need a one-off run record (for diff or debugging), every fetch script accepts `--manifest <path>` to write a JSON summary; treat any such file as throwaway and delete it once the run is reviewed.

### OpenAI (official, curated)

```bash
python3 scripts/fetch_openai_security_skills.py --overwrite
```

To pin a specific upstream revision:

```bash
python3 scripts/fetch_openai_security_skills.py \
  --ref <commit-sha-or-tag> \
  --overwrite
```

### ClawHub (community marketplace)

ClawHub is a large community marketplace; inspect candidates first:

```bash
python3 scripts/fetch_clawhub_security_skills.py --dry-run
```

Then fetch all matched security candidates:

```bash
python3 scripts/fetch_clawhub_security_skills.py --overwrite
```

### skills.sh (community marketplace, GitHub-backed)

Requires a GitHub token (`gh auth login` or `GITHUB_TOKEN`), since the script downloads each skill directly from its source GitHub repo to bypass skills.sh's anonymous download limit (~60 req/hr).

```bash
gh auth login

python3 scripts/fetch_skillsh_security_skills.py --dry-run

python3 scripts/fetch_skillsh_security_skills.py \
  --workers 4 \
  --request-delay 0.3
```

### skillsdirectory.com (community marketplace)

Discovery uses the public `/api/skills` endpoint (no auth). The site groups testing and security under one upstream category (`testing-security`, 1272 skills); the keyword regex narrows that to the security subset. Use `--scan-all` to walk the full ~34k catalog when chasing security skills filed under other upstream categories.

```bash
python3 scripts/fetch_skillsdirectory_security_skills.py --dry-run

python3 scripts/fetch_skillsdirectory_security_skills.py \
  --workers 4 \
  --request-delay 0.25
```

### dmgrok/agent_skills_directory (community aggregator index)

The repo is a metadata index — it ships catalog exports listing every upstream skill with its source repo, `commit_sha`, and path. The script downloads `exports/claude-skills.json` (929 skills) and materializes each candidate from its pinned upstream commit. Requires a GitHub token.

```bash
gh auth login

python3 scripts/fetch_agent_skills_directory_security_skills.py --dry-run

python3 scripts/fetch_agent_skills_directory_security_skills.py --workers 4
```

To restrict to the upstream native `security` category (25 skills, narrowest):

```bash
python3 scripts/fetch_agent_skills_directory_security_skills.py \
  --upstream-category security \
  --workers 4 \
  --manifest reports/agent_skills_directory_security_skills_native_manifest_<YYYY-MM-DD>.json
```

### Common flags

- `--max-skills <n>` caps a run for testing; `--max-skills 0` (default) means no cap.
- `--overwrite` replaces existing destination directories (otherwise existing skills are skipped, supporting safe resume).
- `--no-content-filter` disables the keyword regex when the candidate set is already pre-filtered upstream.
