# CI/CD Integration Guide

Complete guide for integrating multi-AI code review into CI/CD pipelines.

## GitHub Actions

### Basic PR Review

```yaml
# .github/workflows/ai-review.yml
name: Multi-AI Code Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Get Changed Files
        id: changed-files
        uses: tj-actions/changed-files@v41
        with:
          files: |
            **/*.py
            **/*.js
            **/*.ts
            **/*.go

      - name: Claude Review
        if: steps.changed-files.outputs.any_changed == 'true'
        uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          model: claude-sonnet-4-5-20250929
          files: ${{ steps.changed-files.outputs.all_changed_files }}
          review_type: security,performance,maintainability

      - name: Post Review Comment
        uses: actions/github-script@v7
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          script: |
            const fs = require('fs');
            const review = fs.readFileSync('review-output.md', 'utf8');

            await github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: review
            });
```

### Multi-Model Review Pipeline

```yaml
# .github/workflows/multi-ai-review.yml
name: Multi-AI Review Pipeline
on: [pull_request]

jobs:
  security-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Security Scan
        id: security
        run: |
          # Claude for security focus
          curl -X POST https://api.anthropic.com/v1/messages \
            -H "x-api-key: ${{ secrets.ANTHROPIC_API_KEY }}" \
            -H "anthropic-version: 2023-06-01" \
            -d '{
              "model": "claude-sonnet-4-5-20250929",
              "max_tokens": 4096,
              "system": "You are a security specialist. Review code for vulnerabilities.",
              "messages": [{"role": "user", "content": "Review: '"$(cat src/*.py)"'"}]
            }' > security-review.json

      - name: Upload Security Results
        uses: actions/upload-artifact@v4
        with:
          name: security-review
          path: security-review.json

  performance-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Performance Analysis
        run: |
          # Gemini for performance (fast, large context)
          curl -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent" \
            -H "Content-Type: application/json" \
            -H "x-goog-api-key: ${{ secrets.GEMINI_API_KEY }}" \
            -d '{
              "contents": [{
                "parts": [{"text": "Analyze performance of: '"$(cat src/*.py)"'"}]
              }]
            }' > performance-review.json

      - name: Upload Performance Results
        uses: actions/upload-artifact@v4
        with:
          name: performance-review
          path: performance-review.json

  synthesize:
    needs: [security-review, performance-review]
    runs-on: ubuntu-latest
    steps:
      - name: Download All Reviews
        uses: actions/download-artifact@v4

      - name: Synthesize Findings
        run: |
          # Combine and deduplicate findings
          python3 << 'EOF'
          import json
          import os

          findings = []
          for review_file in ['security-review/security-review.json',
                              'performance-review/performance-review.json']:
              if os.path.exists(review_file):
                  with open(review_file) as f:
                      findings.append(json.load(f))

          # Generate summary (simplified)
          print("## Multi-AI Review Summary")
          print(f"Reviews analyzed: {len(findings)}")
          EOF

      - name: Post Summary
        uses: actions/github-script@v7
        with:
          script: |
            // Post combined summary to PR
```

### Quality Gate Enforcement

```yaml
# .github/workflows/quality-gate.yml
name: Quality Gate
on: [pull_request]

jobs:
  quality-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run AI Review
        id: review
        run: |
          # Run review and parse results
          # Output: CRITICAL_COUNT, HIGH_COUNT, SCORE

      - name: Check Quality Gate
        run: |
          CRITICAL=${{ steps.review.outputs.critical_count }}
          HIGH=${{ steps.review.outputs.high_count }}
          SCORE=${{ steps.review.outputs.score }}

          echo "Critical: $CRITICAL, High: $HIGH, Score: $SCORE"

          if [ "$CRITICAL" -gt 0 ]; then
            echo "::error::Quality gate failed: $CRITICAL critical issues"
            exit 1
          fi

          if [ "$HIGH" -gt 3 ]; then
            echo "::error::Quality gate failed: Too many high issues ($HIGH)"
            exit 1
          fi

          if [ "$SCORE" -lt 70 ]; then
            echo "::error::Quality gate failed: Score $SCORE < 70"
            exit 1
          fi

          echo "Quality gate passed!"
```

---

## GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - review
  - gate

ai-review:
  stage: review
  image: python:3.11
  script:
    - pip install anthropic
    - python scripts/run-ai-review.py
  artifacts:
    reports:
      codequality: review-report.json
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

quality-gate:
  stage: gate
  needs: [ai-review]
  script:
    - |
      CRITICAL=$(jq '.critical_count' review-report.json)
      if [ "$CRITICAL" -gt 0 ]; then
        echo "Blocked: Critical issues found"
        exit 1
      fi
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

---

## Pre-Commit Hooks

### Setup

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ai-security-scan
        name: AI Security Scan
        entry: python scripts/quick-security-scan.py
        language: python
        types: [python]
        stages: [commit]

      - id: ai-style-check
        name: AI Style Check
        entry: python scripts/style-check.py
        language: python
        types: [python]
        stages: [commit]
```

### Quick Scan Script

```python
#!/usr/bin/env python3
# scripts/quick-security-scan.py
import sys
import subprocess

def quick_scan(files):
    """Quick security scan before commit."""
    issues = []

    for file in files:
        with open(file) as f:
            content = f.read()

        # Check for common issues
        if 'eval(' in content:
            issues.append(f"{file}: eval() usage detected")
        if 'exec(' in content:
            issues.append(f"{file}: exec() usage detected")
        if 'password' in content.lower() and '=' in content:
            issues.append(f"{file}: Possible hardcoded password")

    if issues:
        print("Security issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(quick_scan(sys.argv[1:]))
```

---

## Branch Protection Rules

### GitHub Branch Protection

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "ai-review",
      "quality-gate"
    ]
  },
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

### CODEOWNERS Integration

```
# .github/CODEOWNERS
# Require AI review approval for security-sensitive files

/auth/ @security-team
/api/ @backend-team
*.sql @database-team
```

---

## Reporting Dashboard

### Metrics Collection

```python
# scripts/collect-metrics.py
import json
from datetime import datetime

def collect_review_metrics(review_result):
    """Collect metrics from AI review."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "pr_number": review_result.get("pr_number"),
        "critical_issues": review_result.get("critical_count", 0),
        "high_issues": review_result.get("high_count", 0),
        "medium_issues": review_result.get("medium_count", 0),
        "score": review_result.get("score", 0),
        "review_time_seconds": review_result.get("duration", 0),
        "false_positives": 0,  # Updated by human feedback
        "fixes_accepted": 0    # Updated after merge
    }

def update_dashboard(metrics):
    """Update metrics dashboard."""
    # Send to your metrics system (Datadog, Prometheus, etc.)
    pass
```

### Sample Dashboard Query

```sql
-- Weekly AI review effectiveness
SELECT
    DATE_TRUNC('week', timestamp) as week,
    AVG(score) as avg_score,
    SUM(critical_issues) as total_critical,
    AVG(false_positive_rate) as false_positive_rate,
    AVG(fix_acceptance_rate) as fix_acceptance
FROM ai_review_metrics
WHERE timestamp > NOW() - INTERVAL '90 days'
GROUP BY week
ORDER BY week DESC;
```
