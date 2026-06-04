"""
GuiGazer — Playwright Action Controller
=========================================
Translates high-level :class:`Action` decisions into concrete Playwright
browser interactions (click, type, scroll) and provides screenshot capture.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from loguru import logger
from PIL import Image

from agent.reasoner import Action
from detector.model import Detection

if TYPE_CHECKING:
    from playwright.async_api import Page


class PlaywrightController:
    """Execute agent actions on a live Playwright browser page.

    Usage
    -----
    >>> ctrl = PlaywrightController()
    >>> ctrl.set_page(page)            # pass the Playwright Page object
    >>> done = await ctrl.execute(action, detections)
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page: Page | None = None
        logger.debug("PlaywrightController created")

    # ------------------------------------------------------------------
    # Configuration & Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize Playwright and launch the browser."""
        if self._page is not None:
            return
            
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=False)
        self._page = await self._browser.new_page()
        # Set a standard desktop viewport
        await self._page.set_viewport_size({"width": 1280, "height": 800})
        logger.info("Playwright standalone browser initialized")

    def set_page(self, page: Page) -> None:
        """Attach a pre-existing Playwright ``Page``."""
        self._page = page
        logger.info("PlaywrightController attached to existing page")

    async def cleanup(self) -> None:
        """Close the browser and stop Playwright."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Playwright resources cleaned up")

    async def navigate(self, url: str) -> None:
        """Navigate to a URL."""
        await self.initialize()
        await self._page.goto(url)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _require_page(self) -> Page:
        """Initialize browser if needed, return page."""
        await self.initialize()
        return self._page

    @staticmethod
    def _find_detection(
        element_id: int,
        detections: list[Detection],
    ) -> Detection | None:
        """Look up a detection by its ``element_id``."""
        for det in detections:
            if det.element_id == element_id:
                return det
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self,
        action: Action,
        detections: list[Detection],
    ) -> bool:
        """Execute an :class:`Action` on the current page.

        Parameters
        ----------
        action:
            The action chosen by the VLM reasoner.
        detections:
            Current set of detected UI elements (used to resolve
            ``element_id`` → pixel coordinates).

        Returns
        -------
        bool
            ``True`` if the task is deemed complete (``action == "done"``),
            ``False`` otherwise (more steps needed).
        """
        page = await self._require_page()

        # --- done -----------------------------------------------------------
        if action.action == "done":
            logger.info("Agent signalled DONE — {}", action.reasoning)
            return True

        # --- resolve target element -----------------------------------------
        det = self._find_detection(action.element_id, detections)
        if det is None:
            logger.warning(
                "element_id={} not found in {} detections — skipping action",
                action.element_id,
                len(detections),
            )
            return False

        cx, cy = det.center
        logger.info(
            "Executing {} on element {} ({}) at ({}, {}) — {}",
            action.action,
            det.element_id,
            det.class_name,
            cx,
            cy,
            action.reasoning[:60],
        )

        # --- click ----------------------------------------------------------
        if action.action == "click":
            await page.mouse.click(cx, cy)
            logger.debug("Clicked ({}, {})", cx, cy)

        # --- type -----------------------------------------------------------
        elif action.action == "type":
            await page.mouse.click(cx, cy)
            await page.keyboard.type(action.value, delay=50)
            logger.debug("Typed '{}' into element {}", action.value, det.element_id)

        # --- scroll ---------------------------------------------------------
        elif action.action == "scroll":
            await page.mouse.wheel(0, 300)
            logger.debug("Scrolled down 300 px")

        else:
            logger.warning("Unknown action '{}' — ignoring", action.action)

        return False

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    async def capture(self) -> Image.Image:
        """Take a full-page screenshot and return it as a PIL Image.

        Returns
        -------
        PIL.Image.Image
            The captured screenshot in RGB mode.
        """
        page = await self._require_page()
        raw_bytes: bytes = await page.screenshot(type="png")
        image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        logger.debug(
            "Captured screenshot {}×{}", image.width, image.height
        )
        return image
