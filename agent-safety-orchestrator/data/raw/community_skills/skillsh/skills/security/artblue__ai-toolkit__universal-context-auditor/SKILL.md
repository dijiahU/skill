---
name: universal-context-auditor
description: Universal AI config context auditor (CLAUDE.md, .cursorrules, etc.) based on 25+ primary sources. Optimizes fidelity × cache efficiency for any tech stack. No setup required - works with your existing files.
---

# Universal Context Auditor

**The "Context Auditor"** - evaluates AI configuration files against research-backed principles to maximize task success rate while minimizing cost and attention decay.

## What This Does

Audits your existing AI configuration files (CLAUDE\.md, .cursorrules, instructions.md, etc.) and provides:

- **Structural analysis** against LLM research (Stanford, UC Berkeley, Anthropic)
- **Fidelity scoring** - Will the AI reliably follow your rules?
- **Cache efficiency** - Is your config optimized for prompt caching?
- **Attention architecture** - Are critical rules in the right cognitive zones?
- **Actionable refactoring** - Concrete improvements using YOUR existing examples

## Prerequisites

**You need:** An existing AI configuration file with your project-specific conventions already documented.

**You don't need:** Tech stack detection, framework templates, or setup wizards.

This skill audits **structure and cognitive architecture**, not content specifics. It works with any tech stack because the underlying principles are universal.

## Core Principle

**Prioritize fidelity over aesthetics.** A verbose, redundant config that is 90% cached and 100% accurate is superior to a "clean" compressed config. The goal is not minimal tokens—it's maximal task success rate.

## The Audit Criteria

When auditing a file, evaluate against these four priorities:

### 1. **Fidelity Score** (Priority 1)

Will the AI reliably follow these rules?

- ✅ **Critical constraints in primacy zone** - First 2,000 tokens exploit the Primacy Effect (Liu et al., 2024 - "Lost in the Middle")
- ✅ **XML encapsulation for Claude** - Wrapping rules in `<architecture_rules>`, `<correctness_guards>` creates structural boundaries preventing context bleeding (Anthropic-optimized)
- ✅ **Correctness Guards present** - Version-specific syntax examples prevent hallucination to training data
- ❌ **Avoid indirection layers** - External references land in weak attention zone (middle of context)
- ❌ **No vague commands** - "Be thorough" triggers infinite tool loops (Thoroughness Anti-Pattern)

### 2. **Cache Efficiency** (Priority 2)

Will this stay static and cacheable?

- ✅ **Layer 1 (Anchor) is stable** - System prompt content should be prefix-anchored and rarely change
- ✅ **Under 2,000 tokens for cache activation** - This is the threshold for Anthropic's prompt caching, not a compression target
- ❌ **Frequent churn invalidates cache** - Don't put session-specific or rapidly-changing data in config files
- ❌ **Dynamic references break caching** - Importing frequently-updated files kills cache benefits

### 3. **Attention Architecture** (Priority 3)

Where do instructions land in the context hierarchy?

**The Stratified Stack:**

- **Layer 1 (Anchor / System Prompt):** Identity, safety rails, core project standards → CLAUDE\.md (primacy zone)
- **Layer 2 (Skills):** Specialized procedures invoked occasionally (e.g., "Security Audit", release workflow) → .claude/skills/ (dynamic injection)
- **Layer 3 (MCP Tools):** Live data connections (Jira, GitHub) → Tool outputs (filtered/distilled)
- **Layer 4 (Use-Time Prompts):** Ad-hoc session-specific instructions → User messages (recency bias)

**Critical Rule:** Frequently-referenced material (used >50% of sessions) should stay in Layer 1, NOT be extracted to Layer 2.

### 4. **Task Success Rate** (Priority 4)

Does this reduce errors and improve output quality?

- ✅ **Redundancy improves comprehension** - "Write Everything Twice" (WET) is optimal for LLMs
- ✅ **Having same rule in 3 files > AI missing it once**
- ✅ **Verbose examples prevent version confusion** - Don't assume AI will browse URLs to verify syntax
- ❌ **DRY is wrong for LLMs** - Human code principles don't apply to probabilistic inference engines

## Refactoring Recommendations

The auditor suggests improvements based on these research-backed patterns:

### 1. **XML Encapsulation** (Claude-specific)

Wrap non-negotiable rules in XML tags for structural enforcement:

```xml
<architecture_rules>
Core architectural constraints that must never be violated
</architecture_rules>

<correctness_guards>
Version-specific syntax examples (YOUR frameworks, YOUR versions)
</correctness_guards>

<agent_constraints>
Workflow boundaries: what the AI must never do and must always do before marking work complete
</agent_constraints>
```

**Note:** GPT and Gemini prefer Markdown hierarchy. Only use XML for Claude. Don't mix formats.

### 2. **Topological Prefix-Anchoring**

Structure for the Primacy Effect:

```
[TOP - First 2,000 tokens]
- Identity & agent constraints
- Architecture rules (non-negotiable)
- Correctness Guards (version-specific syntax)

[MIDDLE]
- Component patterns (reference to existing examples, not full documentation)
- Non-discoverable conventions only (syntax, APIs, framework differences)
- Testing requirements (what's mandatory, not how to structure)

[BOTTOM]
- Repository metadata
- PR checklist
- Skills/commands references
```

### 3. **Don't Extract for Aesthetics**

Test before extracting to skills:

- ❌ **DON'T extract:** Frequently-referenced material (npm commands used every session)
- ✅ **DO extract:** Specialized procedures invoked occasionally (release workflow, security audit)
- **Test:** "Will this be read on 50%+ of turns?" → Keep inline

**Why:** Indirection layers break caching, land instructions in weak attention zone, and cause "instruction fatigue."

### 4. **Correctness Guards Over Links**

Use "Golden Snippets" for version-specific syntax. The auditor will identify YOUR existing examples and suggest structural improvements:

**Example transformation:**
```markdown
<!-- Before: Buried in middle of file -->
We use React 19, so don't use forwardRef anymore.

<!-- After: Suggested placement -->
<correctness_guards>
**Version-Specific Syntax (Prevents Training Data Hallucination):**
- **React 19:** Use native `ref` prop NOT `React.forwardRef` wrapper
- **TypeScript 5.5:** Use `satisfies` operator for type narrowing NOT type assertions
</correctness_guards>
```

The auditor uses **your frameworks** and **your examples** - it just suggests better placement and emphasis.

### 5. **Prioritize Fidelity Over DRY**

Key principles:

- Verbose, redundant configs are GOOD if fully cached
- "Write Everything Twice" (WET) prevents attention decay
- A well-cached 2,000-token config > a compressed 800-token "clean" config
- If clean code habits make AI dumber, they're technical debt

### 6. **Discovery-First Architecture**

LLMs have powerful file exploration tools (Glob, Grep, Read). Optimize for signal-to-noise:

**Discoverable vs Non-Discoverable Material:**

- ❌ **DON'T include:** File structures, directory layouts, naming patterns visible via file exploration
- ✅ **DO include:** Non-obvious conventions, version-specific syntax, framework API differences
- **Test:** "Could an AI discover this with Read/Glob/Grep in 1-2 files?" → If yes, replace with reference to example
- **Exception:** Brief pointers to example locations are good ("See src/components/Button.tsx for patterns")

**Pattern Documentation Strategy:**

- **Point, don't duplicate** - "Reference existing patterns at X" not ASCII file trees
- **Signal over noise** - Every token should prevent an error or clarify non-obvious behavior
- **Examples over documentation** - "See how Button component handles this" > full explanation

**Test questions:**

1. Is this pattern visible in file structure? → Reference the file, don't duplicate
2. Is this non-obvious or version-specific? → Include explicitly
3. Could AI infer this from 1-2 examples? → Point to examples
4. Does this prevent training data hallucination? → Include with emphasis

## Audit Modes

### Single-File Mode (Default)

Audit the root `/CLAUDE.md` file only.

### Repo-Wide Mode

Audit all CLAUDE\.md files in the repository (root + nested in subfolders). Use this when:

- User requests "audit all CLAUDE\.md files"
- User mentions "nested" or "subfolder" CLAUDE\.md files
- User asks about combined token budget

**Combined Token Budget:** All CLAUDE\.md files together must stay under 2,000 tokens for optimal caching.

## Expected Workflow

### Single-File Mode

#### 1. Read the Target File

Use Read tool to examine the current CLAUDE\.md or config file.

#### 2. Calculate Metrics

Provide:

- **Token count** (estimate: ~4 chars per token for English)
- **Fidelity Score** (1-100): Will AI reliably follow rules?
- **Cache Efficiency** (1-100): Is it static and under 2,000 tokens?
- **Attention Architecture** (1-100): Are critical rules in primacy zone?
- **Task Success Projection** (1-100): Will this reduce errors?
- **Overall Score** (average of above)

### Repo-Wide Mode

#### 1. Discover All CLAUDE\.md Files

Use Glob to find all CLAUDE\.md files:

```
**/CLAUDE\.md
```

#### 2. Read All Files

Use Read tool for each discovered file.

#### 3. Calculate Aggregate Metrics

Provide:

- **Per-file token counts** (estimate)
- **Combined total tokens** (all files)
- **Budget status**: ✅ Under 2,000 tokens OR ⚠️ Exceeds threshold
- **Hierarchy check**: Do nested files extend or contradict root?
- **Redundancy check**: Flag excessive duplication (not beneficial WET)
- **Individual scores** for each file
- **Aggregate recommendations**

### Identify Issues — Single-File

**Anti-Patterns to Flag:**

- Frequently-used material extracted to skills (breaks caching)
- Critical rules buried mid-file (lost in the middle)
- No XML encapsulation for Claude (context bleeding)
- Missing Correctness Guards (version hallucination risk)
- Vague commands like "be thorough" (tool loop trigger)
- Over-compression sacrificing fidelity (Clean Code Tax)
- File structure ASCII art (discoverable via exploration)
- Documenting patterns instead of referencing examples
- Including obvious information in comments (e.g., "# Exports + types")
- Using generic examples not from the actual project tech stack

**Good Patterns to Recognize:**

- Verbose, redundant critical rules (WET is good)
- Static, prefix-anchored content <2,000 tokens
- XML-wrapped guardrails for Claude
- Version-specific syntax examples inline
- Frequently-used reference material kept inline
- "Reference existing patterns" guidance over full documentation
- Critical API differences prominently labeled (CRITICAL, prevents hallucination)
- Focus on non-discoverable, version-specific rules
- Examples from the actual project tech stack
- Token efficiency through discovery-first approach

### Identify Issues — Repo-Wide (Additional)

**Additional Anti-Patterns for Multi-File:**

- **Combined budget exceeded**: Total >2,000 tokens across all files
- **Contradictory rules**: Child file overrides parent constraints
- **Wasteful duplication**: Entire sections copy-pasted (not beneficial redundancy)
- **Hierarchy violations**: Child files redefine core architecture/identity
- **Orphaned context**: Nested file with no clear parent relationship

**Good Patterns for Multi-File:**

- **Root file (~1,200-1,500 tokens)**: Core rules, architecture, identity
- **Nested files (~100-300 tokens each)**: Package/domain-specific extensions
- **Clear hierarchy**: Child extends parent, doesn't contradict
- **Targeted redundancy**: Critical rules repeated where needed (WET)
- **Combined total <2,000 tokens**: Maintains cache efficiency

### Propose Refactored Version

**Single-File Structure:**

1. **Summary of changes** with justification
2. **Before/After token counts**
3. **Projected improvement in metrics**
4. **Refactored content** (if significant changes needed)

**Repo-Wide Structure:**

1. **Executive Summary**: Combined token budget status
2. **Per-File Analysis**: Token counts, scores, issues
3. **Hierarchy Report**: Parent-child relationships, conflicts
4. **Redundancy Map**: Beneficial vs wasteful duplication
5. **Recommendations**: Which files to trim, what to consolidate
6. **Projected Outcomes**: Before/After total tokens, cache efficiency

**Critical:** Don't optimize for "looks clean to humans" - optimize for "AI follows rules and stays cached."

**Token Budget Strategy (Repo-Wide):**

- Root CLAUDE\.md: ~1,200-1,500 tokens (core rules, architecture, identity)
- Package-level nested files: ~100-300 tokens each (domain-specific extensions)
- Combined total: <2,000 tokens for cache activation
- Headroom target: 30-40% under threshold for future growth

## Final Checklist

### Single-File Mode

Before finalizing recommendations:

- [ ] Fidelity > Token count (verbose is OK if cached)
- [ ] Critical rules in first 2,000 tokens (primacy zone)
- [ ] XML encapsulation for Claude (structural boundaries)
- [ ] Correctness Guards for version-specific syntax
- [ ] No extraction of frequently-used reference material
- [ ] Static content for cache efficiency
- [ ] WET over DRY (redundancy is good for LLMs)

### Repo-Wide Mode

Additional checks:

- [ ] Combined token budget <2,000 tokens
- [ ] No contradictory rules between parent/child files
- [ ] Clear hierarchy (child extends, doesn't override)
- [ ] Beneficial redundancy only (not wasteful duplication)
- [ ] Nested files focused on domain-specific extensions
- [ ] Root file contains core architecture/identity (~1,200-1,500 tokens)
- [ ] Package files are lightweight supplements (~100-300 tokens each)

## Research Foundation

This auditor is built on 25+ primary sources including:

**LLM Cognitive Architecture:**
- Liu et al. (2024) - "Lost in the Middle: How Language Models Use Long Contexts"
- Anthropic - Attention distribution in transformer models
- UC Berkeley - Context window utilization patterns

**Prompt Engineering:**
- Anthropic - Prompt caching optimization
- Anthropic - XML tag effectiveness for Claude
- OpenAI - GPT-4 system message best practices

**Software Engineering for AI:**
- Microsoft Research - Code generation fidelity studies
- Google DeepMind - Agent reliability patterns
- Clean Code Tax principle (Khachatryan, 2025)


## Customization (Optional)

While this skill works out of the box, teams can customize it for deeper domain knowledge:

### 1. Add Framework-Specific Anti-Patterns

Edit the skill to recognize your recurring issues:

```markdown
**Additional Anti-Patterns for [Your Framework]:**
- [Specific pattern that causes issues in your codebase]
- [Common mistake with your tech stack]
```

### 2. Adjust Scoring Weights

If certain metrics matter more for your use case:

```markdown
**Custom Scoring:**
- Fidelity Score: 40% (default: 25%)
- Cache Efficiency: 30% (default: 25%)
- Attention Architecture: 20% (default: 25%)
- Task Success Rate: 10% (default: 25%)
```

### 3. Add Tech-Stack Specific Checks

For specialized frameworks:

```markdown
**[Your Framework] Specific Checks:**
- [ ] [Framework-specific requirement]
- [ ] [Version-specific validation]
```

## Example Transformations

### Before Audit

```markdown
# My Project

We use React 19 and TypeScript 5.5.

## File Structure
- src/
  - components/
    - Button/
    - Input/
  - utils/
  - hooks/

## Rules
- Use modern React patterns
- Write good tests
- Don't use forwardRef anymore
- Be thorough with error handling
```

### After Audit (Suggested)

```markdown
<architecture_rules>
React 19 + TypeScript 5.5 component library
</architecture_rules>

<correctness_guards>
**Version-Specific Syntax (Prevents Training Data Hallucination):**
- **React 19:** Use native `ref` prop NOT `React.forwardRef` wrapper
- **TypeScript 5.5:** Use `satisfies` operator NOT type assertions
</correctness_guards>

## Component Patterns

Follow existing structures:
- Button component: `src/components/Button/` (ref forwarding, variants)
- Form inputs: `src/components/Input/` (validation, accessibility)
- Custom hooks: `src/hooks/` (TypeScript generics, return type inference)

## Error Handling

- Use error boundaries for all async data-fetching components
- Return `Result<T, E>` types for fallible operations — do NOT swallow errors with empty catch blocks

## Testing Requirements

- All components require unit tests (Vitest + @testing-library/react)
- Visual regression via Chromatic for UI changes
- Integration tests for multi-component interactions

## Repository Metadata
[Discoverable file structure removed - use Glob to explore]
```

**Improvements:**
- ✅ XML encapsulation for critical rules
- ✅ Version-specific syntax in Correctness Guards (primacy zone)
- ✅ Removed discoverable file tree (reduces noise)
- ✅ Replaced vague "be thorough" with specific requirements
- ✅ Added concrete examples with file references
- ✅ Moved from generic to specific ("modern patterns" → actual syntax)

**Token count:** ~70 → ~236 tokens (intentionally larger — the "after" adds fidelity, not compression; see Core Principle)

## Usage

```bash
# Audit root CLAUDE.md
/universal-context-auditor

# Audit all CLAUDE.md files in repo
/universal-context-auditor --repo-wide

# Audit a specific file
/universal-context-auditor --file path/to/instructions.md
```

## Distribution

This skill is designed for:
- **Internal teams** - Standardize AI config quality across organization
- **Open source projects** - Improve contributor AI experience
- **Individual developers** - Optimize personal AI workflows
- **Tool builders** - Foundation for custom linters

**License:** MIT (See LICENSE file)
**Source:** Based on production use at eBay's evo-web monorepo
**Article:** "The Clean Code Tax: Why Your AI Context Files Are Wasting Tokens and Money"

---

**Made with ❤️ by engineers who learned the hard way that clean code principles don't apply to LLMs.**
