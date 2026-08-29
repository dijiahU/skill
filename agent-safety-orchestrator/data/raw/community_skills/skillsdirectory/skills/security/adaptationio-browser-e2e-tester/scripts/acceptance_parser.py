"""
Acceptance Parser

Parses acceptance criteria into executable test steps.
"""

from dataclasses import dataclass
from typing import Any, Optional
import json
import re


@dataclass
class TestStep:
    """Single test step."""
    step: str
    action: str
    target: Optional[str] = None
    value: Optional[str] = None
    expected: Optional[str] = None
    timeout_ms: int = 5000


def parse_acceptance_criteria(criteria: list[dict]) -> list[TestStep]:
    """
    Parse acceptance criteria into test steps.

    Args:
        criteria: List of acceptance criteria dictionaries

    Returns:
        List of TestStep objects
    """
    steps = []

    for criterion in criteria:
        step = TestStep(
            step=criterion.get("step", ""),
            action=criterion.get("action", ""),
            target=criterion.get("target"),
            value=criterion.get("value"),
            expected=criterion.get("expected"),
            timeout_ms=criterion.get("timeout_ms", 5000)
        )
        steps.append(step)

    return steps


def parse_natural_language(description: str) -> list[TestStep]:
    """
    Parse natural language acceptance criteria into test steps.

    Args:
        description: Natural language description

    Returns:
        List of TestStep objects
    """
    steps = []
    lines = description.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        step = _parse_line(line)
        if step:
            steps.append(step)

    return steps


def _parse_line(line: str) -> Optional[TestStep]:
    """Parse a single line into a test step."""
    # Remove bullet points, numbers
    line = re.sub(r"^[\d\.\)\-\*\s]+", "", line).strip()

    # Pattern: click on [element]
    if match := re.search(r"click (?:on )?['\"]?([^'\"]+)['\"]?", line, re.I):
        return TestStep(
            step=line,
            action="click",
            target=match.group(1).strip()
        )

    # Pattern: type/enter [value] in/into [element]
    if match := re.search(r"(?:type|enter) ['\"]([^'\"]+)['\"] (?:in|into) ['\"]?([^'\"]+)['\"]?", line, re.I):
        return TestStep(
            step=line,
            action="fill",
            target=match.group(2).strip(),
            value=match.group(1)
        )

    # Pattern: fill [element] with [value]
    if match := re.search(r"fill ['\"]?([^'\"]+)['\"]? with ['\"]([^'\"]+)['\"]", line, re.I):
        return TestStep(
            step=line,
            action="fill",
            target=match.group(1).strip(),
            value=match.group(2)
        )

    # Pattern: navigate/go to [url]
    if match := re.search(r"(?:navigate|go) to ['\"]?([^'\"]+)['\"]?", line, re.I):
        return TestStep(
            step=line,
            action="goto",
            target=match.group(1).strip()
        )

    # Pattern: see/verify [text] on page
    if match := re.search(r"(?:see|verify|check|should see) ['\"]([^'\"]+)['\"]", line, re.I):
        return TestStep(
            step=line,
            action="assert_text",
            target="body",
            expected=match.group(1)
        )

    # Pattern: redirected to [url]
    if match := re.search(r"redirect(?:ed)? to ['\"]?([^'\"]+)['\"]?", line, re.I):
        return TestStep(
            step=line,
            action="assert_url",
            expected=match.group(1).strip()
        )

    # Pattern: wait for [element]
    if match := re.search(r"wait for ['\"]?([^'\"]+)['\"]?", line, re.I):
        return TestStep(
            step=line,
            action="wait",
            target=match.group(1).strip()
        )

    # Default: treat as assertion
    return TestStep(
        step=line,
        action="assert_visible",
        target="body"
    )


def parse_gherkin(gherkin: str) -> list[TestStep]:
    """
    Parse Gherkin-style acceptance criteria.

    Args:
        gherkin: Gherkin format string (Given/When/Then)

    Returns:
        List of TestStep objects
    """
    steps = []
    lines = gherkin.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remove Gherkin keywords
        for keyword in ["Given", "When", "Then", "And", "But"]:
            if line.startswith(keyword):
                line = line[len(keyword):].strip()
                break

        step = _parse_line(line)
        if step:
            steps.append(step)

    return steps


def validate_steps(steps: list[TestStep]) -> list[str]:
    """
    Validate test steps for common issues.

    Args:
        steps: List of test steps

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    for i, step in enumerate(steps):
        if not step.action:
            errors.append(f"Step {i+1}: Missing action")

        if step.action in ["click", "fill", "type", "wait"] and not step.target:
            errors.append(f"Step {i+1}: '{step.action}' requires target")

        if step.action in ["fill", "type"] and not step.value:
            errors.append(f"Step {i+1}: '{step.action}' requires value")

        if step.action in ["assert_url", "assert_text"] and not step.expected:
            errors.append(f"Step {i+1}: '{step.action}' requires expected value")

    return errors
