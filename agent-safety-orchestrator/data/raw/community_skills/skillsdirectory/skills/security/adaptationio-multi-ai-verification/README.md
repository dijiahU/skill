# Multi-AI Verification

Multi-layer quality assurance with 5-layer verification pyramid (95% automated → 0% automated). Independent verification, LLM-as-judge, Agent-as-a-Judge patterns. Score 0-100 with ≥90 threshold.

## Quick Start

```
Use multi-ai-verification for [code/implementation]
```

Runs all 5 verification layers.

## The 5-Layer Pyramid

```
    Layer 5: Quality Scoring
    (LLM-as-judge, 0-20% automated, 60-120m)
         /\
    Layer 4: Integration
    (E2E, System, 20-30% automated, 45-90m)
      /    \
 Layer 3: Visual
 (UI, a11y, 30-50% automated, 30-90m)
    /      \
Layer 2: Functional
(Tests, Coverage, 60-80% automated, 30-60m)
  /          \
Layer 1: Rules
(Linting, Types, 95% automated, 15-30m)
```

**Principle**: Fail fast at automated layers before expensive LLM evaluation

## The 5 Operations

**Operation 1: Rules-Based** (95% automated, 15-30m)
- Linting, type checking, schema validation, SAST security

**Operation 2: Functional** (60-80% automated, 30-60m)
- Test execution, coverage validation, example checking

**Operation 3: Visual** (30-50% automated, 30-90m)
- Screenshots, visual diff, accessibility, responsive design

**Operation 4: Integration** (20-30% automated, 45-90m)
- E2E workflows, API integration, data flow validation

**Operation 5: Quality Scoring** (0-20% automated, 60-120m)
- LLM-as-judge, Agent-as-a-Judge, 0-100 scoring

## Quality Gates (All Must Pass)

```
✅ Gate 1: Rules Pass (no critical issues)
✅ Gate 2: Tests Pass + Coverage ≥80%
✅ Gate 3: Visual OK (no critical UI issues)
✅ Gate 4: Integration OK (E2E works)
✅ Gate 5: Quality ≥90/100

→ PRODUCTION APPROVED
```

## Key Features

- ✅ **5-layer verification** (automated base → judgment apex)
- ✅ **Independent verification** (separate from impl/testing)
- ✅ **Quality scoring** (0-100, 5 dimensions × 20 points)
- ✅ **Agent-as-a-Judge** (tool access, can verify claims)
- ✅ **Multi-agent ensemble** (3-5 agents voting)
- ✅ **100% actionable feedback** (What/Where/Why/How/Priority)
- ✅ **Security verification** (OWASP, SAST, vulnerabilities)

## Quality Scoring (0-100)

**5 Dimensions** (20 points each):
- Correctness (/20) - Logic, edge cases, security
- Functionality (/20) - Requirements met, works
- Quality (/20) - Maintainability, best practices
- Integration (/20) - Components work together
- Security (/20) - Vulnerabilities, compliance

**Threshold**: ≥90 for production approval

## Integration

- Called by: multi-ai-implementation (Step 6)
- Verifies: Code from multi-ai-implementation
- Verifies: Tests from multi-ai-testing
- Final gate: Before commit/deployment

## Cost Controls

- Budget: $70/month ($50 LLM-judge + $20 ensemble)
- Caching: 24h for same code
- Fast-path: Skip Layer 5 for <50 line changes
- Ensemble: Only for critical features

---

**Validated by**: Claude + Gemini + Codex
**Research**: 50+ sources on verification and QA
**Status**: Production-ready
