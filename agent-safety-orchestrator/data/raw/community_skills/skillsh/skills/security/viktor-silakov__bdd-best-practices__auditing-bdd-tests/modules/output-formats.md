# Output Formats Module

Available output formats and their usage.

## 1. ASCII Dashboard (Terminal)

Always output in terminal for immediate feedback.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                       BDD TEST SOLUTION REPORT                               ║
║  Repository: {name} | Stack: {stack}                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  OVERALL GRADE: {X}     SCORE: {XX}/100     {delta}                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. Executable Gherkin      {bar} {score}/100                                ║
║  2. Step Definitions        {bar} {score}/100                                ║
║  ...                                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

Progress bar: `████████░░` = 80/100 (10 chars, each = 10%)

## 2. Issue List Format

```
🔴 CRITICAL ({N})
──────────────────────────────────────────────────────────────────────
[C1] {Aspect}: {Issue}
     Evidence: {paths/snippets}
     Impact: {why it matters}
     Effort: Low/Medium/High
```

Every issue MUST have evidence (file path, pattern, or example).

## 3. JSON Report

Save to `.bddready/history/reports/{REPORT_ID}.json`:

```json
{
  "report_id": "2026-01-24_162500",
  "date": "2026-01-24",
  "repo_name": "example-repo",
  "overall": { "score": 68, "grade": "C" },
  "aspects": [...],
  "issues": [...],
  "issue_counts": { "critical": 2, "warning": 5, "info": 3 }
}
```

## 4. HTML Report

Generate using: `node scripts/render-html.mjs <input.json> <output.html>`

Template location: `templates/report.html`

## 5. Markdown Report

Save to `.bddready/history/reports/{REPORT_ID}.md`

Use the example format from `examples/BDD-TEST-SOLUTION-REPORT-EXAMPLE.md`.

## File Structure

```
.bddready/
├── history/
│   ├── index.json          # History index for delta
│   └── reports/
│       ├── {REPORT_ID}.md
│       ├── {REPORT_ID}.html
│       └── {REPORT_ID}.json
```
