"""Async Playwright worker for web UI automation and self-healing capture.

Provides:
  - Headless/headed Chromium execution of AtomicQEStep sequences
  - Real-time DOM snapshot capture upon selector failures
  - Screenshot capture for multimodal root-cause analysis (Muse Wonder / SAM 3.1)
  - Pre-inference vault desanitization (re-inserting local values for browser inputs)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.core.schemas import AtomicQEStep, StepVerdict


class PlaywrightWorker:
    """Dispatches atomic test steps to Playwright Chromium sessions."""

    def __init__(self, headless: bool = True, screenshot_dir: str = "screenshots") -> None:
        self.headless = headless
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def start(self) -> None:
        """Launch the Chromium browser instance."""
        if not self._playwright:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

    async def stop(self) -> None:
        """Tear down the browser context and process."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    async def execute_step(
        self,
        step: AtomicQEStep,
        vault_resolver: Optional[dict[str, str]] = None,
        timeout_ms: int = 4000,
    ) -> dict[str, any]:
        """Execute a single AtomicQEStep against the active page.

        Returns a dictionary with status, error, dom_snapshot, and screenshot_path.
        """
        if not self._page:
            await self.start()

        page = self._page
        action_lower = step.action.lower()
        selector = step.target_selector

        # Resolve tokens from local vault if provided
        input_value = step.input_value
        if input_value and vault_resolver and input_value in vault_resolver:
            input_value = vault_resolver[input_value]

        try:
            if "navigate" in action_lower or "open" in action_lower or selector.startswith("http"):
                url = selector if selector.startswith("http") else "http://localhost:8080"
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)

            elif input_value is not None or "fill" in action_lower or "type" in action_lower:
                val = input_value or ""
                await page.fill(selector, val, timeout=timeout_ms)

            elif "click" in action_lower or "submit" in action_lower:
                await page.click(selector, timeout=timeout_ms)

            # Optional post-action assertion
            if step.assertion:
                if "text=" in step.assertion:
                    expected_text = step.assertion.split("text=")[-1].strip("'\"")
                    content = await page.content()
                    if expected_text not in content:
                        raise AssertionError(f"Expected text '{expected_text}' not found on page.")

            return {
                "verdict": StepVerdict.PASS,
                "error": None,
                "dom_snapshot": None,
                "screenshot_path": None,
            }

        except Exception as exc:
            # Capture failure artifact for SAM 3.1 & Muse Wonder multimodal diagnosis
            screenshot_path = str(self.screenshot_dir / f"fail_{step.step_id}.png")
            try:
                await page.screenshot(path=screenshot_path)
            except Exception:
                screenshot_path = ""

            try:
                dom_snapshot = await page.content()
            except Exception:
                dom_snapshot = ""

            return {
                "verdict": StepVerdict.FAIL,
                "error": str(exc),
                "dom_snapshot": dom_snapshot,
                "screenshot_path": screenshot_path,
            }
