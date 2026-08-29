# Python/Django Example Audit

> **Illustrative example.** This before/after transformation is constructed to demonstrate the auditing principles — not taken from a real project. See the [examples README](README.md) for context, or run `/universal-context-auditor` on your own config to get actual results.

This example shows a typical Django project CLAUDE\.md before and after audit.

## Before: Original CLAUDE\.md

# Django E-commerce API

This is a Django-based REST API for an e-commerce platform.

## Tech Stack
- Python 3.12
- Django 5.0
- Django REST Framework 3.14
- PostgreSQL
- Redis for caching
- Celery for background tasks

## Project Structure
```
src/
  apps/
    products/
      models.py
      views.py
      serializers.py
      tests.py
    orders/
      models.py
      views.py
      serializers.py
      tests.py
    users/
      models.py
      views.py
      serializers.py
  config/
    settings/
      base.py
      development.py
      production.py
  manage.py
```

## Development Guidelines

1. Write good tests for all new features
2. Use type hints
3. Follow Django best practices
4. Be thorough with error handling
5. Don't use the old `url()` pattern, use `path()` instead
6. Make sure migrations are clean

## Code Style
- Black for formatting
- isort for imports
- flake8 for linting
- mypy for type checking

## Running Tests
```bash
python manage.py test
```
```

**Token count:** ~1,450 tokens (estimated)
**Estimated scores:**
- Fidelity: 48/100 (vague commands, critical syntax buried)
- Cache Efficiency: 75/100 (under 2K, but has discoverable content)
- Attention Architecture: 35/100 (no primacy zone optimization)
- Task Success Rate: 40/100 (lacks specificity)
- **Overall: 50/100**

## Audit Findings

### Issues Identified

1. **Missing Correctness Guards (Priority 1)**
   - Django 5.0 syntax mentioned but buried mid-file
   - No Python 3.12 specific patterns highlighted
   - Missing DRF serializer common mistakes

2. **Discoverable Information Bloat**
   - Full file tree (lines 8-25) discoverable via Glob
   - Tech stack list without context on WHY versions matter
   - Commands that are standard Django

3. **Vague Commands**
   - "Write good tests" - no specifics
   - "Follow Django best practices" - too generic
   - "Be thorough with error handling" - triggers tool loops

4. **No XML Encapsulation**
   - Critical rules not structurally separated
   - Context bleeding risk

5. **Critical Syntax Buried**
   - `path()` vs `url()` mentioned at line 18 (weak attention zone)
   - Should be in primacy zone with emphasis

## After: Refactored CLAUDE\.md

```markdown
<architecture_rules>
Django 5.0 + DRF 3.14 REST API
Python 3.12 with strict type hints (mypy --strict)
PostgreSQL primary DB + Redis cache layer
Celery for async tasks (broker: Redis)
</architecture_rules>

<correctness_guards>
**Version-Specific Syntax (Prevents Training Data Hallucination):**
- **Django 5.0:** Use `path()` in urls.py NOT `url()` (removed in Django 4.0)
- **Python 3.12:** Use `|` for unions (`str | None`) NOT `typing.Union[str, None]`
- **DRF Serializers:** Use `serializer.validated_data` NOT `serializer.data` before save
- **DRF ViewSets:** Use `get_queryset()` override NOT queryset attribute for dynamic filtering
- **Async Views:** Use `async def` + `sync_to_async` for ORM calls NOT blocking queries
- **Migrations:** Always use `python manage.py makemigrations --check` before commit
</correctness_guards>

<agent_constraints>
- Never commit without running tests + migration checks
- Always add type hints to new functions (mypy validates)
- Run `black . && isort .` before marking work complete
</agent_constraints>

## API Patterns

**Standard structure:** See `apps/products/` for reference implementation
- `models.py` - Django models with Meta, `__str__`, custom managers
- `serializers.py` - DRF serializers with validation methods
- `views.py` - ViewSets with permission_classes, filterset_class
- `tests.py` - pytest-django fixtures + APIClient tests


## Testing Requirements

- All new endpoints require API tests (see `apps/products/tests.py`)
- Use `pytest-django` fixtures, NOT Django TestCase classes
- Mock external services (Stripe, SendGrid) using `responses` library
- Minimum 80% coverage (enforced by CI)

## Database Patterns

**Common mistakes to avoid:**
- ❌ `Model.objects.all()` in views (use pagination + select_related)
- ❌ N+1 queries (use `prefetch_related` for reverse FKs)
- ❌ Filtering in Python (use `.filter()` at DB level)

**Example:**
```python
# ❌ Bad
products = Product.objects.all()
products = [p for p in products if p.category_id == cat_id]

# ✅ Good
products = Product.objects.filter(category_id=cat_id).select_related('category')
```

## Async Task Patterns

- All Celery tasks in `apps/<app>/tasks.py`
- Use `@shared_task` decorator (not `@app.task`)
- Add `bind=True, max_retries=3` for error handling
- Always log task start/finish for debugging

## Environment Management

- Use `.env` for secrets (never commit)
- Settings split: `base.py` → `development.py` / `production.py`
- Required env vars validated in `config/settings/base.py` (KeyError if missing)

## Common Commands

```bash
# Development
python manage.py runserver
python manage.py shell_plus  # django-extensions

# Testing
pytest                       # All tests
pytest -k test_product      # Specific test
pytest --cov                # With coverage

# Pre-commit checks
black . && isort . && flake8 && mypy .
python manage.py makemigrations --check --dry-run
```
```

**Token count:** ~1,680 tokens (estimated)
**Projected scores:**
- Fidelity: 88/100 (XML guards, specific examples)
- Cache Efficiency: 80/100 (under 2K, minimal dynamic content)
- Attention Architecture: 85/100 (primacy zone optimized)
- Task Success Rate: 90/100 (specific, actionable guidance)
- **Overall: 86/100**

## Summary of Changes

### ✅ Improvements

1. **Added XML Encapsulation**
   - `<architecture_rules>` for foundational constraints
   - `<correctness_guards>` for version-specific syntax (primacy zone)
   - `<agent_constraints>` for workflow boundaries

2. **Removed Discoverable Content**
   - File tree removed (saves ~180 tokens)
   - Replaced with pointers to reference implementations
   - Kept only non-obvious structural conventions

3. **Specific > Generic**
   - "Write good tests" → Specific test requirements with examples
   - "Follow best practices" → Concrete anti-patterns with code examples
   - "Be thorough" → Removed (vague command)

4. **Correctness Guards in Primacy Zone**
   - Django 5.0 syntax at top (not buried)
   - Python 3.12 type hint syntax emphasized
   - DRF common mistakes highlighted

5. **Added Code Examples**
   - N+1 query anti-pattern with fix
   - Shows what NOT to do alongside correct approach
   - Uses actual project patterns

### 📊 Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Token count | 1,450 | 1,680 | +230 (beneficial redundancy) |
| Fidelity | 48/100 | 88/100 | +83% |
| Cache efficiency | 75/100 | 80/100 | +7% |
| Attention architecture | 35/100 | 85/100 | +143% |
| Task success rate | 40/100 | 90/100 | +125% |
| **Overall** | **50/100** | **86/100** | **+72%** |

### 🎯 Key Takeaways

1. **Token count increased, but fidelity improved dramatically** - The 230 additional tokens are beneficial redundancy (WET principle)
2. **Discoverable content removed** - File tree replaced with reference pointers (better signal-to-noise)
3. **Vague commands eliminated** - Every instruction is now specific and actionable
4. **Correctness Guards prevent hallucination** - AI won't revert to Django 3.x or Python 3.8 patterns from training data

## Real-World Impact

*These figures are illustrative estimates of the types of improvements this audit typically surfaces — not measurements from a specific project.*

**Before audit:**
- AI suggested `url()` in 23% of routing changes (deprecated in Django 4.0)
- Generic test suggestions without pytest-django context
- Repeated N+1 queries in generated viewsets

**After audit:**
- Zero instances of deprecated patterns
- Tests consistently use pytest fixtures and APIClient
- Generated code includes `select_related()` proactively

**Cost savings:**
- Cache hit rate: 15% → 82% (2K token threshold + static content)
- Average tokens per session: 2,400 → 1,900 (better scoped responses)
- Developer correction time: ~4 min/issue → ~30 sec/issue
