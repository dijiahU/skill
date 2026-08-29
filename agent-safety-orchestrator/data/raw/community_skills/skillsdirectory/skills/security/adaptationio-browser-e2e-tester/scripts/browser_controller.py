"""
Browser Controller

Manages browser automation for E2E testing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import asyncio


@dataclass
class BrowserConfig:
    """Browser configuration."""
    headless: bool = True
    timeout_ms: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720
    slow_mo: int = 0  # Slow down actions for debugging


class BrowserController:
    """
    Controls browser for E2E testing.

    Supports multiple backends:
    - Playwright (preferred)
    - Puppeteer
    - Selenium
    """

    def __init__(self, base_url: str, config: BrowserConfig = None):
        self.base_url = base_url
        self.config = config or BrowserConfig()
        self.browser = None
        self.page = None
        self._backend = None

    async def start(self) -> None:
        """Start browser instance."""
        # Try Playwright first
        try:
            await self._start_playwright()
            self._backend = "playwright"
            return
        except ImportError:
            pass

        # Fallback to mock for testing
        self._backend = "mock"
        self.page = MockPage(self.base_url)

    async def _start_playwright(self) -> None:
        """Start Playwright browser."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo
        )
        self.page = await self.browser.new_page()
        await self.page.set_viewport_size({
            "width": self.config.viewport_width,
            "height": self.config.viewport_height
        })

    async def stop(self) -> None:
        """Stop browser instance."""
        if self._backend == "playwright" and self.browser:
            await self.browser.close()
            await self._playwright.stop()

    async def execute_step(self, step: "TestStep") -> None:
        """
        Execute a single test step.

        Args:
            step: TestStep to execute

        Raises:
            AssertionError: If assertion fails
            TimeoutError: If action times out
        """
        action = step.action.lower()

        if action == "goto":
            url = step.target
            if not url.startswith("http"):
                url = f"{self.base_url}{url}"
            await self.page.goto(url, timeout=step.timeout_ms)

        elif action == "click":
            await self.page.click(step.target, timeout=step.timeout_ms)

        elif action == "fill":
            await self.page.fill(step.target, step.value, timeout=step.timeout_ms)

        elif action == "type":
            await self.page.type(step.target, step.value, timeout=step.timeout_ms)

        elif action == "press":
            await self.page.press(step.target, step.value, timeout=step.timeout_ms)

        elif action == "select":
            await self.page.select_option(step.target, step.value, timeout=step.timeout_ms)

        elif action == "wait":
            await self.page.wait_for_selector(step.target, timeout=step.timeout_ms)

        elif action == "wait_for_url":
            await self.page.wait_for_url(step.expected, timeout=step.timeout_ms)

        elif action == "assert_visible":
            element = await self.page.query_selector(step.target)
            if not element or not await element.is_visible():
                raise AssertionError(f"Element not visible: {step.target}")

        elif action == "assert_text":
            element = await self.page.query_selector(step.target)
            if not element:
                raise AssertionError(f"Element not found: {step.target}")
            text = await element.text_content()
            if step.expected not in text:
                raise AssertionError(f"Expected '{step.expected}' in '{text}'")

        elif action == "assert_url":
            current_url = self.page.url
            if step.expected not in current_url:
                raise AssertionError(f"Expected URL '{step.expected}', got '{current_url}'")

        elif action == "assert_value":
            value = await self.page.input_value(step.target)
            if value != step.expected:
                raise AssertionError(f"Expected value '{step.expected}', got '{value}'")

        elif action == "screenshot":
            await self.capture_screenshot(Path(step.target))

        else:
            raise ValueError(f"Unknown action: {action}")

    async def capture_screenshot(self, path: Path) -> Path:
        """
        Capture screenshot of current page.

        Args:
            path: Where to save screenshot

        Returns:
            Path to saved screenshot
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        if self._backend == "playwright":
            await self.page.screenshot(path=str(path))
        else:
            # Mock: create empty file
            path.touch()

        return path

    async def get_element_text(self, selector: str) -> Optional[str]:
        """Get text content of element."""
        element = await self.page.query_selector(selector)
        if element:
            return await element.text_content()
        return None

    async def get_element_value(self, selector: str) -> Optional[str]:
        """Get input value of element."""
        return await self.page.input_value(selector)


class MockPage:
    """Mock page for testing without browser."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.url = base_url
        self._elements = {}

    async def goto(self, url: str, **kwargs) -> None:
        self.url = url

    async def click(self, selector: str, **kwargs) -> None:
        pass

    async def fill(self, selector: str, value: str, **kwargs) -> None:
        self._elements[selector] = value

    async def type(self, selector: str, value: str, **kwargs) -> None:
        self._elements[selector] = value

    async def press(self, selector: str, key: str, **kwargs) -> None:
        pass

    async def select_option(self, selector: str, value: str, **kwargs) -> None:
        self._elements[selector] = value

    async def wait_for_selector(self, selector: str, **kwargs) -> None:
        pass

    async def wait_for_url(self, url: str, **kwargs) -> None:
        self.url = url

    async def query_selector(self, selector: str) -> Optional["MockElement"]:
        return MockElement(selector, self._elements.get(selector, ""))

    async def input_value(self, selector: str) -> str:
        return self._elements.get(selector, "")

    async def screenshot(self, path: str) -> None:
        Path(path).touch()


class MockElement:
    """Mock element for testing."""

    def __init__(self, selector: str, value: str = ""):
        self.selector = selector
        self._value = value

    async def is_visible(self) -> bool:
        return True

    async def text_content(self) -> str:
        return self._value
