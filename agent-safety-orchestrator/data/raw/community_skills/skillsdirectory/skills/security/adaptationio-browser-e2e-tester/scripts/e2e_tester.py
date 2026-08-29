"""
E2E Tester

Core browser-based end-to-end testing for feature verification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json
import asyncio


@dataclass
class TestStep:
    """Single test step."""
    step: str
    action: str
    target: Optional[str] = None
    value: Optional[str] = None
    expected: Optional[str] = None
    timeout_ms: int = 5000


@dataclass
class TestResult:
    """Result of a single test run."""
    feature_id: str
    passed: bool
    duration_ms: int
    steps_executed: int
    steps_passed: int
    failures: list[str] = field(default_factory=list)
    screenshots: list[Path] = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TestSuiteResult:
    """Result of running all tests."""
    total: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    results: list[TestResult] = field(default_factory=list)


class E2ETester:
    """
    Browser-based E2E tester for feature verification.

    Responsibilities:
    - Load acceptance criteria from feature list
    - Execute browser-based tests
    - Capture failures with screenshots
    - Report results for progress tracking
    """

    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.browser = None
        self.base_url = "http://localhost:3000"
        self.screenshot_dir = self.project_dir / ".claude" / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def test_feature(self, feature_id: str) -> TestResult:
        """
        Test a single feature.

        Args:
            feature_id: Feature to test

        Returns:
            TestResult with pass/fail and details
        """
        from .browser_controller import BrowserController
        from .acceptance_parser import parse_acceptance_criteria

        start_time = datetime.now()
        failures = []
        screenshots = []
        steps_executed = 0
        steps_passed = 0

        # Load feature acceptance criteria
        criteria = await self._load_feature_criteria(feature_id)
        if not criteria:
            return TestResult(
                feature_id=feature_id,
                passed=False,
                duration_ms=0,
                steps_executed=0,
                steps_passed=0,
                failures=["No acceptance criteria found"]
            )

        # Parse into test steps
        steps = parse_acceptance_criteria(criteria)

        # Initialize browser
        browser = BrowserController(self.base_url)
        await browser.start()

        try:
            for step in steps:
                steps_executed += 1
                try:
                    await browser.execute_step(step)
                    steps_passed += 1
                except Exception as e:
                    failures.append(f"Step '{step.step}' failed: {str(e)}")
                    # Capture screenshot on failure
                    screenshot = await browser.capture_screenshot(
                        self.screenshot_dir / f"{feature_id}-{steps_executed}.png"
                    )
                    screenshots.append(screenshot)
                    break  # Stop on first failure

        finally:
            await browser.stop()

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        passed = len(failures) == 0

        return TestResult(
            feature_id=feature_id,
            passed=passed,
            duration_ms=duration_ms,
            steps_executed=steps_executed,
            steps_passed=steps_passed,
            failures=failures,
            screenshots=screenshots
        )

    async def test_all_features(self) -> TestSuiteResult:
        """
        Test all incomplete features.

        Returns:
            TestSuiteResult with aggregate results
        """
        start_time = datetime.now()
        results = []
        passed = 0
        failed = 0
        skipped = 0

        # Load feature list
        features = await self._load_features()

        for feature in features:
            if feature.get("passes", False):
                skipped += 1
                continue

            result = await self.test_feature(feature["id"])
            results.append(result)

            if result.passed:
                passed += 1
            else:
                failed += 1

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return TestSuiteResult(
            total=len(features),
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_ms=duration_ms,
            results=results
        )

    async def verify_feature(self, feature_id: str) -> bool:
        """
        Quick verification that a feature passes.

        Args:
            feature_id: Feature to verify

        Returns:
            True if passes, False otherwise
        """
        result = await self.test_feature(feature_id)
        return result.passed

    async def _load_features(self) -> list[dict]:
        """Load feature list from file."""
        feature_file = self.project_dir / "feature_list.json"
        if not feature_file.exists():
            return []
        return json.loads(feature_file.read_text())

    async def _load_feature_criteria(self, feature_id: str) -> Optional[dict]:
        """Load acceptance criteria for a feature."""
        features = await self._load_features()
        for feature in features:
            if feature["id"] == feature_id:
                return feature.get("acceptance_criteria", [])
        return None

    def set_base_url(self, url: str) -> None:
        """Set base URL for tests."""
        self.base_url = url


async def run_e2e_tests(project_dir: Path) -> TestSuiteResult:
    """
    Convenience function to run all E2E tests.

    Args:
        project_dir: Project directory

    Returns:
        TestSuiteResult
    """
    tester = E2ETester(project_dir)
    return await tester.test_all_features()
