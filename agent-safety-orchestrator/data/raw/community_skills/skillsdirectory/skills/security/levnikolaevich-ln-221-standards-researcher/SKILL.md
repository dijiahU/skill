---
name: ln-221-standards-researcher
description: Research standards/patterns via MCP Ref. Generates Standards Research for Story Technical Notes subsection. Reusable worker.
---

# Standards Researcher (Worker)

This skill researches industry standards and architectural patterns using MCP Ref to generate Standards Research for Story Technical Notes.

## When to Use This Skill

This skill should be used when:
- Need to research standards and patterns BEFORE Story generation (ensures tasks follow industry best practices)
- Epic Technical Notes mention specific standards requiring documentation (OAuth, OpenAPI, WebSocket)
- Prevent situations where tasks use outdated patterns or violate RFC compliance
- Reusable for ANY skill requiring standards research (ln-220-story-coordinator, ln-310-story-decomposer, ln-350-story-test-planner)

**Who calls this skill:**
- **ln-220-story-coordinator** (Phase 3) - research for Story creation
- **ln-310-story-decomposer** (optional) - research for complex Stories
- **ln-350-story-test-planner** (optional) - research for test task planning
- **Manual** - user can invoke directly for Epic/Story research

## How It Works

The skill follows a 5-phase workflow focused on standards and architectural patterns.

Phases: Identify → Ref Research → Existing Guides → Standards Research

### Phase 1: Identify Libraries

**Objective**: Parse Epic/Story for libraries and technology keywords.

**Process**:
1. **Read Epic/Story description** (provided as input)
   - Parse Epic Technical Notes for mentioned libraries/frameworks
   - Parse Epic Scope In for technology keywords (authentication, rate limiting, payments, etc.)
   - Identify Story domain from Epic goal statement (e.g., "Add rate limiting" → domain = "rate limiting")

2. **Extract library list**:
   - Primary libraries (explicitly mentioned)
   - Inferred libraries (e.g., "REST API" → FastAPI, "caching" → Redis)
   - Filter out well-known libraries with stable APIs (e.g., requests, urllib3)

3. **Determine Story domain**:
   - Extract from Epic goal or Story title
   - Examples: rate limiting, authentication, payment processing, file upload

**Output**: Library list (3-5 libraries max) + Story domain

**Skip conditions**:
- NO libraries mentioned in Epic → Output empty Research Summary
- Trivial CRUD operation with well-known libraries → Output empty Research Summary
- Epic explicitly states "research not needed" → Skip

---

### Phase 2: MCP Ref Research

**Objective**: Get industry standards and architectural patterns.

**Process:**
1. **Focus on standards/RFCs:**
   - Call `mcp__Ref__ref_search_documentation(query="[story_domain] RFC standard specification")`
   - Extract: RFC/spec references (OAuth 2.0 RFC 6749, OpenAPI 3.0, WebSocket RFC 6455)

2. **Focus on architectural patterns:**
   - Call `mcp__Ref__ref_search_documentation(query="[story_domain] architectural patterns best practices")`
   - Extract: Middleware, Dependency Injection, Decorator pattern

**Output:** Standards compliance table + Architectural patterns list

---

### Phase 3: MCP Ref Research

**Objective**: Get industry standards and best practices.

**Process**:
1. **FOR EACH library + Story domain** combination:
   - Call `mcp__Ref__ref_search_documentation(query="[library] [domain] best practices 2025")`
   - Call `mcp__Ref__ref_search_documentation(query="[domain] industry standards RFC")`

2. **Extract from results**:
   - **Industry standards** (RFC/spec references: OAuth 2.0, REST API, OpenAPI 3.0, WebSocket)
   - **Common patterns** (do/don't examples, anti-patterns to avoid)
   - **Integration approaches** (middleware, dependency injection, decorators)
   - **Security considerations** (OWASP compliance, vulnerability mitigation)
   - **Best practices URLs** (link to authoritative sources)

3. **Store results** for Research Summary compilation

**Output**: Standards compliance table (RFC/Standard name, how to comply) + Best practices list

---

### Phase 4: Scan Existing Guides

**Objective**: Find relevant pattern guides in docs/guides/ directory.

**Process**:
1. **Scan guides directory**:
   - Use `Glob` to find `docs/guides/*.md`
   - Read guide filenames

2. **Match guides to Story domain**:
   - Match keywords (e.g., rate limiting guide for rate limiting Story)
   - Fuzzy match (e.g., "authentication" matches "auth.md", "oauth.md")

3. **Collect guide paths** for linking in Technical Notes

**Output**: Existing guides list (relative paths from project root)

---

### Phase 5: Generate Standards Research

**Objective**: Compile research results into Standards Research for Story Technical Notes subsection.

**Process:**

Generate Standards Research in Markdown format:

```markdown
## Standards Research

**Standards compliance:**
- [Standard/RFC name]: [how Story should comply - brief description]
  - Example: "OAuth 2.0 (RFC 6749): Use authorization code flow with PKCE for public clients"

**Architectural patterns:**
- [Pattern name]: [when to use, why relevant for Story domain]
  - Example: "Middleware pattern: Intercept requests for authentication before reaching endpoints"

**Existing guides:**
- [guide_path.md](guide_path.md) - [brief guide description]
```

**Return Standards Research** to calling skill (ln-220, ln-310, ln-350)

**Output:** Standards Research (Markdown string) for insertion into Story Technical Notes subsection

**Important notes:**
- Focus on STANDARDS and PATTERNS only (no library details - libraries researched at Task level)
- Prefer official docs and RFC standards over blog posts
- If Standards Research is empty (no standards/patterns) → Return "No standards research needed"
- Standards Research will be inserted in EVERY Story's Technical Notes (Standards Research subsection)

---

## Integration with Ecosystem

**Called by:**
- **ln-220-story-coordinator** (Phase 2) - research for ALL Stories in Epic
- **ln-310-story-decomposer** (optional) - research for complex technical Stories
- **ln-350-story-test-planner** (optional) - research for test infrastructure

**Dependencies:**
- MCP Ref (ref_search_documentation) - industry standards and patterns
- Glob (scan docs/guides/)

**Input parameters (from calling skill):**
- `epic_description` (string) - Epic Technical Notes + Scope In + Goal
- `story_domain` (string, optional) - Story domain (e.g., "rate limiting")

**Output format:**
- Markdown string (Standards Research for Technical Notes subsection)
- Format: Standards + Patterns (libraries researched at Task level)

---

## Time-Box and Performance

**Time-box:** 15-20 minutes maximum per Epic

**Performance:**
- Research is done ONCE per Epic
- Results reused for all Stories (5-10 Stories benefit from single research)
- Parallel MCP calls when possible (Context7 + Ref)

**Token efficiency:**
- Context7: max 3000 tokens per library
- Total: ~10,000 tokens for typical Epic (3-4 libraries)

---

## References

**Tools:**
- `mcp__Ref__ref_search_documentation()` - Search best practices and standards
- `Glob` - Scan docs/guides/ directory

**Templates:**
- [research_guidelines.md](references/research_guidelines.md) - Research quality guidelines (official docs > blog posts, prefer LTS versions)

---

**Version:** 2.0.0 (BREAKING: Renamed to ln-221-standards-researcher, removed research_level parameter, simplified to standards/patterns only)
**Last Updated:** 2025-11-20
