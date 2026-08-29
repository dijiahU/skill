# E2E Test Patterns Reference

## Overview

This document describes common E2E testing patterns used for feature verification.

## Pattern Categories

### 1. Page Object Pattern

Encapsulate page interactions in reusable objects:

```python
class LoginPage:
    def __init__(self, page):
        self.page = page
        self.email_input = "#email"
        self.password_input = "#password"
        self.submit_button = "button[type=submit]"

    async def login(self, email: str, password: str):
        await self.page.fill(self.email_input, email)
        await self.page.fill(self.password_input, password)
        await self.page.click(self.submit_button)
```

### 2. Fixture Pattern

Setup consistent test state:

```python
@dataclass
class TestFixture:
    user: User
    project: Project
    cleanup: Callable

async def create_fixture() -> TestFixture:
    user = await create_test_user()
    project = await create_test_project(user)

    async def cleanup():
        await delete_project(project)
        await delete_user(user)

    return TestFixture(user, project, cleanup)
```

### 3. Action Chain Pattern

Chain multiple actions for complex flows:

```python
class ActionChain:
    def __init__(self, browser):
        self.browser = browser
        self.steps = []

    def goto(self, url):
        self.steps.append(("goto", url))
        return self

    def click(self, selector):
        self.steps.append(("click", selector))
        return self

    def fill(self, selector, value):
        self.steps.append(("fill", selector, value))
        return self

    async def execute(self):
        for step in self.steps:
            action = step[0]
            args = step[1:]
            await getattr(self.browser, action)(*args)
```

## Common Test Patterns

### Authentication Flow

```json
{
  "acceptance_criteria": [
    {"step": "Navigate to login", "action": "goto", "target": "/login"},
    {"step": "Enter email", "action": "fill", "target": "#email", "value": "test@example.com"},
    {"step": "Enter password", "action": "fill", "target": "#password", "value": "password123"},
    {"step": "Submit", "action": "click", "target": "button[type=submit]"},
    {"step": "Verify dashboard", "action": "assert_url", "expected": "/dashboard"}
  ]
}
```

### Form Submission Flow

```json
{
  "acceptance_criteria": [
    {"step": "Navigate to form", "action": "goto", "target": "/contact"},
    {"step": "Fill name", "action": "fill", "target": "#name", "value": "Test User"},
    {"step": "Fill email", "action": "fill", "target": "#email", "value": "test@example.com"},
    {"step": "Fill message", "action": "fill", "target": "#message", "value": "Hello"},
    {"step": "Submit", "action": "click", "target": "#submit"},
    {"step": "Verify success", "action": "assert_text", "target": ".success", "expected": "Thank you"}
  ]
}
```

### CRUD Operations

```json
{
  "acceptance_criteria": [
    {"step": "Navigate to list", "action": "goto", "target": "/items"},
    {"step": "Click create", "action": "click", "target": ".btn-create"},
    {"step": "Fill name", "action": "fill", "target": "#name", "value": "New Item"},
    {"step": "Save", "action": "click", "target": "#save"},
    {"step": "Verify created", "action": "assert_text", "target": ".item-list", "expected": "New Item"},
    {"step": "Click edit", "action": "click", "target": ".btn-edit"},
    {"step": "Update name", "action": "fill", "target": "#name", "value": "Updated Item"},
    {"step": "Save", "action": "click", "target": "#save"},
    {"step": "Verify updated", "action": "assert_text", "target": ".item-list", "expected": "Updated Item"}
  ]
}
```

## Best Practices

### 1. Selector Strategy

```python
# Prefer (most stable to least):
# 1. data-testid attributes
await page.click('[data-testid="submit-button"]')

# 2. Role-based selectors
await page.click('button:has-text("Submit")')

# 3. Semantic selectors
await page.click('button[type="submit"]')

# 4. CSS selectors (less stable)
await page.click('.btn-primary')

# 5. XPath (least preferred)
await page.click('//button[contains(@class, "submit")]')
```

### 2. Wait Strategies

```python
# Wait for element
await page.wait_for_selector("#content")

# Wait for navigation
await page.wait_for_url("**/dashboard")

# Wait for network idle
await page.wait_for_load_state("networkidle")

# Custom wait
await page.wait_for_function(
    "document.querySelector('#status').textContent === 'Ready'"
)
```

### 3. Error Handling

```python
async def safe_click(page, selector: str):
    try:
        await page.click(selector, timeout=5000)
        return True
    except TimeoutError:
        await page.screenshot(path=f"error-{selector}.png")
        return False
```

## Flaky Test Prevention

1. **Use explicit waits** instead of arbitrary delays
2. **Retry transient failures** with exponential backoff
3. **Isolate tests** - each test should be independent
4. **Clean state** before and after each test
5. **Use stable selectors** (data-testid, roles)
6. **Mock external services** for consistency
