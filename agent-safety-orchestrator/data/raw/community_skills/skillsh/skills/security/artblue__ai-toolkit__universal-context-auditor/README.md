# Universal Context Auditor

A research-backed skill for auditing AI configuration files.

Optimizes your CLAUDE\.md, .cursorrules, or any AI instruction files for maximum task success rate while minimizing token waste and cache misses. The skill was created with Claude as the primary beneficiary, but many of the auditor enhancements should apply to other agents.

## Quick Start

### Installation

**Option 1: Using Skills.sh (Recommended)**
```bash
npx skills add ArtBlue/AI-toolkit/skills
```

**Option 2: Copy to Your Project**

```bash
# Create skills directory if it doesn't exist
mkdir -p .claude/skills
# Download from GitHub
curl -L https://github.com/ArtBlue/AI-toolkit/archive/main.tar.gz | \
  tar xz -C .claude/skills/
```

### Usage (explicit)

```bash
# Audit your root CLAUDE.md
/universal-context-auditor

# Audit all CLAUDE.md files in your repo
/universal-context-auditor --repo-wide

# Audit a specific file
/universal-context-auditor --file path/to/instructions.md
```

### Usage (implied)

Some LLMs will automatically pick up and use the skill if they infer you're trying to do what the specific skill is meant to do. For these, you should simply be able to use them using natural language by prompting something like this:

```bash
Audit the context file CLAUDE.md
```

## What You Get

### Immediate Audit Report

```
Token Count: 1,847 tokens
Fidelity Score: 72/100
Cache Efficiency: 85/100
Attention Architecture: 68/100
Task Success Projection: 75/100
Overall Score: 75/100
```

### Actionable Recommendations

- **Structural improvements** (move critical rules to primacy zone)
- **Cache optimization** (identify dynamic content breaking caching)
- **Correctness guards** (suggest better placement for version-specific syntax)
- **Discovery-first analysis** (remove file trees, keep non-obvious conventions)
- **Token efficiency** (eliminate waste without sacrificing fidelity)

### Before/After Refactoring

The auditor shows:
- What to change and why
- Projected metric improvements
- Token count reduction (if applicable)
- Concrete refactored sections

## Prerequisites

**You need:**
- An existing AI configuration file (CLAUDE\.md, .cursorrules, etc.). If you don't have one, have Claude Code create one doing `/init` 
- Your project-specific conventions already documented

**You don't need:**
- Tech stack detection
- Framework templates
- Setup wizards
- Pre-configuration
- Plus Claude Code's `/init` should create those by consuming your repo.

**Works with any tech stack** because the underlying principles are universal.

## How It Works

### 1. Reads Your Existing File(s)

The skill examines your current configuration without assuming anything about your tech stack.

### 2. Evaluates Structure Against Research

Based on 25+ primary sources including:
- Liu et al. (2024) - "Lost in the Middle" (Primacy Effect)
- Anthropic - Prompt caching optimization
- Stanford/UC Berkeley - LLM attention patterns

### 3. Scores Four Dimensions

- **Fidelity** - Will AI reliably follow your rules?
- **Cache Efficiency** - Is content static and under 2K tokens?
- **Attention Architecture** - Are critical rules in primacy zone?
- **Task Success Rate** - Does structure reduce errors?

### 4. Suggests Improvements Using YOUR Examples

The auditor doesn't prescribe what to include—it evaluates how you've structured what you already documented.

**Example transformation:**
```markdown
# Before (your file)
We use React 19. Don't use forwardRef.

# After (suggested)
<correctness_guards>
- **React 19:** Use native `ref` NOT `forwardRef` wrapper
</correctness_guards>
```

Uses **your frameworks**, **your examples**, just better placed and emphasized.

## Key Principles

### 1. Fidelity > Aesthetics

A verbose, redundant config that is 90% cached and 100% accurate > a "clean" compressed config.

### 2. WET > DRY for LLMs

"Write Everything Twice" prevents attention decay in probabilistic systems. Human code principles don't apply to LLMs.

### 3. Discovery-First Architecture

Don't document what AI can discover via Glob/Grep/Read. Document non-obvious conventions and version-specific syntax.

### 4. Primacy Zone Optimization

First 2,000 tokens have highest attention weight. Put critical rules there.

### 5. Cache = Speed + Cost Savings

Content under 2,000 tokens gets cached by Anthropic. Keep config static and under threshold.

## Common Improvements Suggested

### ✅ Structural Optimization

**Before:**
```markdown
# My Project

[Long file tree]
[Random rules scattered]
[Critical syntax buried at line 150]
```

**After:**
```markdown
<architecture_rules>
[Non-negotiable constraints]
</architecture_rules>

<correctness_guards>
[Version-specific syntax - prevents hallucination]
</correctness_guards>

## Patterns
[References to examples, not full docs]
```

### ✅ Correctness Guards

**Before:**
```markdown
Use the new API. The old one is deprecated.
```

**After:**
```markdown
<correctness_guards>
- **Library v2.0:** Use `newMethod()` NOT `oldMethod()` (removed in v2.0)
</correctness_guards>
```

### ✅ Discovery-First

**Before:**
```markdown
## File Structure
src/
  components/
    Button/
      Button.tsx
      Button.test.tsx
      Button.stories.tsx
    Input/
      Input.tsx
      ...
```

**After:**
```markdown
## Component Patterns
See src/components/Button/ for standard structure
```

**Saves:** ~200 tokens, improves signal-to-noise ratio

### ✅ Removing Vague Commands

**Before:**
```markdown
- Write good tests
- Be thorough with error handling
- Make it production-ready
```

**After:**
```markdown
## Testing Requirements
- All features require unit tests (see tests/Button.test.tsx)
- Visual regression via Percy for CSS changes
- Integration tests for multi-component flows
```

## Customization (Optional)

While the skill works out of the box, you can customize it for deeper domain knowledge.

### Add Framework-Specific Checks

Edit `SKILL.md` to add your recurring issues:

```markdown
**Additional Anti-Patterns for [Your Framework]:**
- Missing dependency injection setup (Spring Boot)
- Incorrect async/await patterns (JavaScript)
- Not using context managers (Python)
```

### Adjust Scoring Weights

If certain metrics matter more:

```markdown
**Custom Scoring:**
- Fidelity Score: 40% (default: 25%)
- Cache Efficiency: 30% (default: 25%)
- Attention Architecture: 20% (default: 25%)
- Task Success Rate: 10% (default: 25%)
```

### Add Tech-Stack Specific Validation

```markdown
**Go-Specific Checks:**
- [ ] Error handling uses errors.Is/As (not ==)
- [ ] Contexts passed explicitly (not in structs)
- [ ] Interfaces kept small (1-3 methods)
```

## Example Audits

See the `examples/` directory for before/after audits across different tech stacks:

- [**Python/Django**](examples/python-django.md) - Django 5.0, Python 3.12
- [**TypeScript/React**](examples/typescript-react.md) - React 19, TypeScript 5.5
- [**Go/Microservices**](examples/go-microservices.md) - Go 1.22, gRPC
- [**Rust/Tokio**](examples/rust-tokio.md) - Rust 2024, async patterns

Each example shows:
- Original CLAUDE\.md (typical for that stack)
- Audit scores and findings
- Refactored version
- Token savings and fidelity improvements

## Multi-File Repos

For monorepos or projects with nested CLAUDE\.md files:

```bash
/universal-context-auditor --repo-wide
```

**Validates:**
- Combined token budget (<2,000 tokens total)
- Hierarchy (child extends parent, doesn't contradict)
- Redundancy (beneficial WET vs wasteful duplication)

**Typical structure:**
```
/CLAUDE.md                    (~1,200-1,500 tokens)
/packages/api/CLAUDE.md       (~150 tokens)
/packages/frontend/CLAUDE.md  (~200 tokens)
/packages/mobile/CLAUDE.md    (~180 tokens)
---
Total: ~1,730 tokens ✅
```

## Troubleshooting

### "Skill not found"

Ensure the skill is in one of these locations:
- `.claude/skills/universal-context-auditor/`
- `~/.claude/skills/universal-context-auditor/`

### "No CLAUDE\.md found"

Specify the file explicitly:
```bash
/universal-context-auditor --file .cursorrules
```

### "Scores are low, but I think my file is good"

Remember: The skill optimizes for **AI task success rate**, not human aesthetics. Low scores indicate:
- AI might miss critical rules (fidelity issue)
- Cache misses costing money (efficiency issue)
- Rules in weak attention zones (architecture issue)

If still unsure, do some testing with your current context file vs the optimized version.

## FAQ

### Does this work with .cursorrules, Codeium config, etc.?

Yes! While examples use CLAUDE\.md, the principles apply to any AI configuration file:
- `.cursorrules` (Cursor)
- `instructions.md` (generic)
- `.ai/config.md` (custom setups)
- Any file containing AI instructions

### Will this make my file longer?

Sometimes! If your file is over-compressed at the cost of fidelity, yes. But:
- Token efficiency through discovery-first approach often reduces size
- When it does add tokens, it's beneficial redundancy (WET principle)
- A 2,000-token config at 90% cache rate is cheaper than a 1,000-token config at 0% cache rate

### Does this work for GPT/Gemini, or just Claude?

**Core principles apply to all LLMs:**
- Primacy Effect (all transformers)
- Attention decay (all LLMs)
- Discovery-first (all with tool use)
- WET > DRY (all probabilistic systems)

**Claude-specific optimizations:**
- XML encapsulation (Claude)
- 2K token caching threshold (Anthropic)

For GPT/Gemini, the skill will recommend Markdown hierarchy instead of XML.

### Can I use this in CI/CD?

Absolutely! Example GitHub Action:

```yaml
name: Audit Context Files
on: [pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Context Auditor
        run: |
          claude-code run /universal-context-auditor --ci-mode
          # Exit 1 if score < 70
```

### How do I cite this in academic work?

```bibtex
@software{generic_context_auditor,
  title = {Universal Context Auditor: Research-Backed AI Configuration Auditor},
  author = {Khachatryan, Arthur},
  year = {2025},
  url = {https://github.com/[your-repo]/universal-context-auditor},
  note = {Based on 25+ primary sources including Liu et al. (2024), Anthropic prompt engineering research}
}
```

## Contributing

We welcome contributions! Areas of interest:

- **New real-world language/framework examples** (Julia, Elixir, Zig, etc.)
- **Research citations** (new LLM studies)
- **VSCode extension** (real-time linting)
- **Scoring improvements** (better heuristics)

## Acknowledgments

Built on research from:
- **Anthropic** - Prompt caching, XML tag effectiveness
- **Anthropic** - "Lost in the Middle" (Liu et al., 2024)
- **UC Berkeley** - Context window utilization patterns
- **Microsoft Research** - Code generation fidelity

Inspired by the "Clean Code Tax" article series.

## License

MIT License - See [LICENSE](LICENSE) file

## Links

- **Article:** [The $100,000 "Clean Code" Tax: Why Your Elegant AI Configs are Bleeding Capital](https://www.linkedin.com/pulse/100000-clean-code-tax-why-your-elegant-ai-configs-arthur-khachatryan-ktvmc)
- **Research:** [Full citation list](RESEARCH.md)
- **Examples:** [Tech stack audits](examples/)
- **Issues:** [GitHub Issues](https://github.com/ai-toolkit/issues)

---

**Made with ❤️ by engineers who learned that clean code principles don't apply to LLMs.**

**Star this repo if it saved you from context rot!** ⭐
