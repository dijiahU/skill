---
name: skill-prescan
description: Pre-scan a SKILL.md locally before publishing to ClawHub. Simulates the ClawScan security review using the same prompt and evaluation criteria as the real scanner. Use when you want to check if your skill will pass ClawHub's security review before uploading.
homepage: https://github.com/openclaw/clawhub
metadata: {"openclaw": {"emoji": "🔍"}}
---

# skill-prescan

Pre-scan your SKILL.md locally before publishing to ClawHub. This tool simulates the ClawScan security review using the same system prompt and evaluation criteria as the real ClawHub scanner, allowing you to iterate on your skill documentation until it passes.

## When to Use

- Before publishing a new skill to ClawHub
- After modifying a skill that previously failed the security review
- To understand why ClawHub flagged your skill as "suspicious"
- To iterate locally without consuming publish attempts

## Requirements

- Python 3.8+
- An OpenAI API key (or any OpenAI-compatible API)

## Usage

```bash
# Basic scan (uses OPENAI_API_KEY env var)
python3 {baseDir}/scripts/scan.py path/to/SKILL.md

# Specify API key and model
python3 {baseDir}/scripts/scan.py path/to/SKILL.md --api-key sk-xxx --model gpt-5.5

# Use a custom OpenAI-compatible endpoint
python3 {baseDir}/scripts/scan.py path/to/SKILL.md --base-url https://your-gateway.com --model gpt-5.5

# Use Anthropic Claude
python3 {baseDir}/scripts/scan.py path/to/SKILL.md --provider anthropic --api-key sk-ant-xxx

# Run multiple times to check consistency
python3 {baseDir}/scripts/scan.py path/to/SKILL.md --runs 3

# Output raw JSON
python3 {baseDir}/scripts/scan.py path/to/SKILL.md --json
```

## Model Selection

The real ClawHub scanner uses **gpt-5.5** with `reasoning.effort: "xhigh"`. For the most accurate local simulation, use gpt-5.5 via any OpenAI-compatible endpoint (default).

| Provider | Flag | Models | Accuracy vs ClawHub |
|----------|------|--------|-------------------|
| OpenAI-compatible | `--provider openai` (default) | gpt-5.5, gpt-5, gpt-5.1 | Closest to real results |
| Anthropic | `--provider anthropic` | claude-sonnet-4-6, claude-opus-4-6 | More lenient |

Note: the real scanner uses the Responses API with extended reasoning, which is not available through Chat Completions. Local results may be slightly more lenient than production.

## Understanding Results

### Verdicts

- **benign** — Your skill should pass ClawHub's review and be searchable.
- **suspicious** — Your skill will be flagged and hidden from search. Review the concerns.
- **malicious** — Your skill will be blocked entirely.

### Findings

Each finding has a status:
- **note** — Purpose-aligned behavior that users should be aware of. Notes alone should NOT trigger suspicious.
- **concern** — Behavior the scanner considers overbroad, unbounded, or insufficiently disclosed. One or more concerns trigger suspicious.

### Key Rule from ClawHub's Scanner

> "A coherent skill with only purpose-aligned notes should remain benign with clear user guidance."

If your skill gets suspicious with 0 concerns (only notes), it means the scanner thinks the combination of notes is "overbroad." This is harder to fix via documentation alone.

## Writing Effective Safety Documentation

1. **Disclose all capabilities explicitly** — the scanner flags hidden or undisclosed behavior.
2. **Bound high-impact actions** — document user approval mechanisms, scope limits, reversibility, and containment.
3. **State structural limitations** — explicitly list what the tool cannot do.
4. **Use neutral framing** — describe behaviors factually rather than defensively.
5. **Be specific about data flows** — describe what is transmitted, to where, and what boundaries apply.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | API key for the LLM service | (required) |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible API | `https://api.openai.com` |
| `SCAN_MODEL` | Model to use for scanning | `gpt-5.5` |
| `SCAN_PROVIDER` | Provider: `openai` or `anthropic` | `openai` |

## How It Works

The scanner sends your SKILL.md content to an LLM with the exact same system prompt that ClawHub's ClawScan uses (extracted from the [open-source ClawHub repository](https://github.com/openclaw/clawhub/blob/main/convex/lib/securityPrompt.ts)). The LLM evaluates your skill across multiple security dimensions and returns a verdict.

## Limitations

- Local scan uses Chat Completions API; ClawHub uses Responses API with `reasoning.effort: "xhigh"` which may produce stricter results.
- ClawHub also runs a VirusTotal scan separately — this tool only simulates the LLM (ClawScan) portion.
- Results may vary between runs due to LLM temperature (default 1.0 on the real scanner).
- The scanner prompt may be updated by ClawHub at any time — check the source repo for the latest version.
