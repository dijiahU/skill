"""
Test Reporter

Generates test reports from E2E test results.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import json


def generate_markdown_report(result: "TestSuiteResult", output_path: Path = None) -> str:
    """
    Generate Markdown test report.

    Args:
        result: TestSuiteResult from E2E tests
        output_path: Optional path to save report

    Returns:
        Markdown report string
    """
    lines = [
        "# E2E Test Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Duration**: {result.duration_ms}ms",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total | {result.total} |",
        f"| Passed | {result.passed} |",
        f"| Failed | {result.failed} |",
        f"| Skipped | {result.skipped} |",
        f"| Pass Rate | {result.passed / max(result.passed + result.failed, 1) * 100:.1f}% |",
        "",
    ]

    # Failed tests section
    failed_results = [r for r in result.results if not r.passed]
    if failed_results:
        lines.extend([
            "## Failed Tests",
            "",
        ])
        for r in failed_results:
            lines.extend([
                f"### {r.feature_id}",
                "",
                f"- **Duration**: {r.duration_ms}ms",
                f"- **Steps**: {r.steps_passed}/{r.steps_executed}",
                "",
                "**Failures**:",
                "",
            ])
            for failure in r.failures:
                lines.append(f"- {failure}")
            lines.append("")

            if r.screenshots:
                lines.append("**Screenshots**:")
                lines.append("")
                for screenshot in r.screenshots:
                    lines.append(f"- `{screenshot}`")
                lines.append("")

    # Passed tests section
    passed_results = [r for r in result.results if r.passed]
    if passed_results:
        lines.extend([
            "## Passed Tests",
            "",
            "| Feature | Duration | Steps |",
            "|---------|----------|-------|",
        ])
        for r in passed_results:
            lines.append(f"| {r.feature_id} | {r.duration_ms}ms | {r.steps_passed} |")
        lines.append("")

    report = "\n".join(lines)

    if output_path:
        output_path.write_text(report)

    return report


def generate_json_report(result: "TestSuiteResult", output_path: Path = None) -> dict:
    """
    Generate JSON test report.

    Args:
        result: TestSuiteResult from E2E tests
        output_path: Optional path to save report

    Returns:
        Report dictionary
    """
    report = {
        "generated": datetime.now().isoformat(),
        "summary": {
            "total": result.total,
            "passed": result.passed,
            "failed": result.failed,
            "skipped": result.skipped,
            "duration_ms": result.duration_ms,
            "pass_rate": result.passed / max(result.passed + result.failed, 1)
        },
        "results": [
            {
                "feature_id": r.feature_id,
                "passed": r.passed,
                "duration_ms": r.duration_ms,
                "steps_executed": r.steps_executed,
                "steps_passed": r.steps_passed,
                "failures": r.failures,
                "screenshots": [str(s) for s in r.screenshots],
                "timestamp": r.timestamp
            }
            for r in result.results
        ]
    }

    if output_path:
        output_path.write_text(json.dumps(report, indent=2))

    return report


def generate_junit_report(result: "TestSuiteResult", output_path: Path) -> str:
    """
    Generate JUnit XML report for CI integration.

    Args:
        result: TestSuiteResult from E2E tests
        output_path: Path to save report

    Returns:
        XML report string
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="e2e-tests" tests="{result.total}" '
        f'failures="{result.failed}" skipped="{result.skipped}" '
        f'time="{result.duration_ms / 1000}">',
    ]

    for r in result.results:
        lines.append(
            f'  <testcase name="{r.feature_id}" time="{r.duration_ms / 1000}">'
        )
        if not r.passed:
            for failure in r.failures:
                lines.append(f'    <failure message="{escape_xml(failure)}"/>')
        lines.append('  </testcase>')

    lines.append('</testsuite>')

    xml = "\n".join(lines)
    output_path.write_text(xml)
    return xml


def escape_xml(text: str) -> str:
    """Escape XML special characters."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def print_summary(result: "TestSuiteResult") -> None:
    """Print test summary to console."""
    total_tests = result.passed + result.failed
    pass_rate = result.passed / max(total_tests, 1) * 100

    print("\n" + "=" * 50)
    print("E2E TEST RESULTS")
    print("=" * 50)
    print(f"  Total:   {result.total}")
    print(f"  Passed:  {result.passed}")
    print(f"  Failed:  {result.failed}")
    print(f"  Skipped: {result.skipped}")
    print(f"  Rate:    {pass_rate:.1f}%")
    print(f"  Time:    {result.duration_ms}ms")
    print("=" * 50)

    if result.failed > 0:
        print("\nFailed Features:")
        for r in result.results:
            if not r.passed:
                print(f"  - {r.feature_id}")
                for failure in r.failures:
                    print(f"      {failure}")
