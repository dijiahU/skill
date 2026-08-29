# Example Audits

These examples are **constructed illustrations**, not case studies from real projects. They exist to:

- Show what a before/after audit looks like in practice
- Demonstrate how the auditing principles apply across different tech stacks
- Give readers a feel for the output format before running the skill themselves

## What these examples are

Each example shows a deliberately weak "Before" CLAUDE.md — one that is vague, has a discoverable file tree, and lacks correctness guards — and an "After" version that applies the audit criteria from SKILL.md. The before/after transformations, scores, and metrics are constructed to make the principles concrete. They are not derived from any specific team or codebase.

## What these examples are not

- Real measurements from real projects
- A guarantee of what your results will look like
- A template to copy directly (the "After" reflects the fictional project's stack, not yours)

## A note on token counts

Token counts throughout these examples are estimates. The general conversion rules:

| Content type | Characters per token |
|---|---|
| English prose | ~4 |
| Mixed prose + code | ~3–3.5 |
| Dense code (brackets, indentation, generics) | ~2–3 |

Since the "After" versions are code-heavy, their actual token counts are likely **higher** than the estimates shown — the ~4 chars/token rule understates cost for code. Verify with a tokenizer before relying on specific numbers.

## Seeing actual results

The only way to get real results is to run the skill on your own config file:

```bash
/universal-context-auditor
```

The skill reads your actual CLAUDE.md, applies the same criteria shown in these examples, and produces recommendations grounded in your tech stack and your existing examples — not a fictional one.

## Available examples

| File | Stack |
|------|-------|
| [typescript-react.md](typescript-react.md) | React 19 + TypeScript 5.5 component library |
| [go-microservices.md](go-microservices.md) | Go 1.22 gRPC microservice |
| [python-django.md](python-django.md) | Django 5.0 + DRF REST API |
| [rust-tokio.md](rust-tokio.md) | Rust 2024 + Tokio async web server |
