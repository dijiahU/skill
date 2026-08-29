# Multi-AI Testing

Test-driven development with independent verification to prevent test gaming. Achieve ≥80% coverage (gate) / ≥95% (target) through TDD, test generation, and AI-powered edge case discovery.

## Quick Start

```
Use multi-ai-testing TDD workflow for [feature]
```

Follow workflows in SKILL.md.

## The 4 Workflows

```
1. TDD               → Test-first development (1-3h)
   Test → Fail → Implement → Pass → Verify

2. TEST GENERATION  → Comprehensive test creation (30-90m)
   Unit + Integration + E2E + Property + Edge Cases

3. COVERAGE         → Validate and improve (30-60m)
   Measure → Gaps → Generate → Re-measure

4. INDEPENDENT      → Prevent gaming (45-90m)
   Separate verifier → Ensemble → Score → Feedback
```

## Key Features

- ✅ **Prevents test gaming** (separate test/impl agents)
- ✅ **TDD enforced** (tests first, confirm fail, then implement)
- ✅ **95% coverage achievable** (AI edge case discovery)
- ✅ **Property-based testing** (invariant validation)
- ✅ **Independent verification** (multi-agent ensemble)
- ✅ **Self-healing tests** (adapt to code changes)
- ✅ **Non-deterministic evaluation** (scoring, not binary)

## Quality Guarantees

- ✅ Coverage: ≥80% gate, ≥95% achievable
- ✅ Test quality: Independent verification ≥90/100
- ✅ No gaming: Separate agents enforced
- ✅ Edge cases: AI-discovered combinations
- ✅ Maintenance: 80% reduction through self-healing

## Integration

- Called by: multi-ai-implementation (TDD in Step 3)
- Calls: multi-ai-verification (test quality check)
- Standalone: Can generate tests independently

## Coverage Targets

- **Gate (must pass)**: ≥80% line coverage
- **Target (desired)**: ≥95% line coverage
- **Stretch**: 100% with mutation testing

---

**Validated by**: Claude + Gemini + Codex
**Research**: 50+ sources on TDD and agentic testing
**Status**: Production-ready
