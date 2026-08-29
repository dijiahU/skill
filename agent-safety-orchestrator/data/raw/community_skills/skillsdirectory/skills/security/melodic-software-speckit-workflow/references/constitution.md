# Constitution Guide

Patterns and examples for project constitution files.

## Purpose

The constitution file (`.constitution.md`) establishes project-wide principles, constraints, and standards that guide ALL specifications and implementations. It serves as the foundational document that ensures consistency across features.

## File Location

```text
<project-root>/
└── .constitution.md
```

The constitution lives at the project root, visible to all development activities.

## Constitution Sections

### Core Principles

Fundamental development principles the team follows.

```markdown
## Core Principles

### Code Quality
- All code must pass linting before commit
- Test coverage minimum: 80%
- No TODO comments in production code

### Architecture
- Follow vertical slice architecture
- Prefer composition over inheritance
- Keep dependencies explicit and minimal

### Collaboration
- All changes require code review
- Documentation updates with code changes
- Clear commit messages following conventional commits
```

### Technical Constraints

Hard constraints that must be respected.

```markdown
## Technical Constraints

### Platform
- Runtime: .NET 9+
- Database: PostgreSQL 16+
- Cache: Redis 7+

### Dependencies
- No deprecated packages allowed
- Security updates within 2 weeks
- License: MIT, Apache 2.0, BSD only

### Performance
- API response time: < 200ms (p95)
- Memory per request: < 50MB
- Database queries per request: < 5
```

### Quality Standards

Standards that define "done" for all work.

```markdown
## Quality Standards

### Testing
- Unit tests for all business logic
- Integration tests for all API endpoints
- E2E tests for critical user journeys

### Documentation
- API documentation via OpenAPI
- Architecture Decision Records for significant decisions
- README updates for new features

### Security
- OWASP Top 10 compliance
- No secrets in code or logs
- Input validation on all external data
```

### Non-Functional Requirements

Cross-cutting requirements that apply everywhere.

```markdown
## Non-Functional Requirements

### Performance
- Page load time: < 3 seconds
- Time to interactive: < 5 seconds
- API throughput: > 1000 req/sec

### Reliability
- Uptime: 99.9%
- Recovery time: < 15 minutes
- Data loss tolerance: 0

### Scalability
- Support 10x current load
- Horizontal scaling only
- Stateless services

### Accessibility
- WCAG 2.1 AA compliance
- Keyboard navigation
- Screen reader support
```

### Team Conventions

Agreed-upon practices for the team.

```markdown
## Team Conventions

### Naming
- Use PascalCase for types
- Use camelCase for members
- Use kebab-case for files

### Git Workflow
- Feature branches from main
- Squash merge to main
- Release branches for deployments

### Code Review
- 1 approval minimum
- Author cannot approve own code
- Address all comments before merge
```

## Complete Example

```markdown
# Project Constitution

## Overview

This constitution establishes the principles, constraints, and standards
that govern all development on this project.

**Last Updated:** 2025-01-15
**Version:** 1.2

## Core Principles

### Simplicity First
- Prefer simple solutions over complex ones
- Add complexity only when proven necessary
- Refactor toward simplicity

### Test-Driven Development
- Write tests before implementation
- Tests document expected behavior
- Failing tests are acceptable; failing builds are not

### Continuous Improvement
- Retrospect on every feature
- Update constitution when patterns emerge
- Pay down technical debt regularly

## Technical Constraints

### Runtime Environment
- .NET 9.0 or later
- PostgreSQL 16.x
- Redis 7.x for caching
- RabbitMQ 3.x for messaging

### Deployment
- Container-based (Docker)
- Kubernetes orchestration
- Blue-green deployments
- Infrastructure as Code (Pulumi)

### Third-Party Services
- Authentication: Azure AD B2C
- Payments: Stripe
- Email: SendGrid
- Monitoring: OpenTelemetry + Grafana

## Quality Standards

### Code Quality
- All code passes static analysis (no warnings)
- Cyclomatic complexity < 10 per method
- Method length < 30 lines
- Class length < 300 lines

### Test Coverage
- Minimum 80% line coverage
- 100% coverage on critical paths
- No untested public API

### Documentation
- XML docs for all public APIs
- README for each module
- ADR for significant decisions

## Non-Functional Requirements

### Performance
| Metric | Target |
| --- | --- |
| API p50 latency | < 50ms |
| API p95 latency | < 200ms |
| API p99 latency | < 500ms |
| Throughput | > 1000 req/sec |

### Reliability
| Metric | Target |
| --- | --- |
| Availability | 99.95% |
| MTTR | < 30 minutes |
| RTO | < 1 hour |
| RPO | < 5 minutes |

### Security
- All data encrypted at rest (AES-256)
- All data encrypted in transit (TLS 1.3)
- PII handling per GDPR
- Security scan on every build

## Team Conventions

### Branch Naming
- `feature/<ticket-id>-<description>`
- `bugfix/<ticket-id>-<description>`
- `hotfix/<ticket-id>-<description>`

### Commit Messages
Follow Conventional Commits:
- `feat:` for features
- `fix:` for bug fixes
- `docs:` for documentation
- `refactor:` for refactoring
- `test:` for tests
- `chore:` for maintenance

### Code Review
- Reviewers assigned within 4 hours
- Review completed within 24 hours
- All comments addressed before merge
- CI must pass before merge

## Change Log

| Version | Date | Changes |
| --- | --- | --- |
| 1.2 | 2025-01-15 | Added security section |
| 1.1 | 2024-11-01 | Updated performance targets |
| 1.0 | 2024-06-15 | Initial constitution |
```

## Validation Checklist

Before considering the constitution complete:

- [ ] All sections have meaningful content
- [ ] Principles are actionable, not vague
- [ ] Constraints are specific and measurable
- [ ] Standards have clear pass/fail criteria
- [ ] NFRs have quantified targets
- [ ] Conventions are documented clearly
- [ ] Version and date are current
- [ ] Team has reviewed and approved

## When to Update

Update the constitution when:

1. **New patterns emerge** - Repeated decisions should become principles
2. **Technical constraints change** - New dependencies, platforms, or limits
3. **Team grows or changes** - Conventions may need clarification
4. **Major incidents occur** - Add constraints to prevent recurrence
5. **Quarterly review** - Regular maintenance and cleanup

## Anti-Patterns

### Too Vague

```markdown
## Principles
- Write good code
- Test everything
- Be professional
```

**Fix:** Be specific and actionable.

### Too Strict

```markdown
## Constraints
- All methods must be < 5 lines
- All classes must have exactly 1 method
- No dependencies allowed
```

**Fix:** Set realistic limits that enable productivity.

### Outdated

```markdown
## Constraints
- Use .NET Framework 4.5
- Deploy to Windows Server 2008
```

**Fix:** Review and update regularly.

### No Measurable Criteria

```markdown
## NFRs
- System should be fast
- System should be reliable
- System should be secure
```

**Fix:** Add specific, measurable targets.
