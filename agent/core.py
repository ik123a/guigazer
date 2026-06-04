"""
GuiGazer — Core Agent Loop
============================
Orchestrates the full perception → reasoning → action cycle:

1. **Capture** a browser screenshot.
2. **Detect** UI elements with the YOLOv8 detector.
3. **Annotate** the screenshot with Set-of-Mark labels.
4. **Reason** about the next action via the vision LLM.
5. **Execute** the action on the live page.
6. Repeat until the task is done or the step budget is exhausted.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, Protocol

from loguru import logger
from PIL import Image

from agent.annotator import annotate_screenshot
from agent.controller import PlaywrightController
from agent.memory import ActionMemory
from agent.reasoner import Action, VisionReasoner
from config import settings
from detector.model import Detection

# ---------------------------------------------------------------------------
# Type alias for the step callback
# ---------------------------------------------------------------------------

StepCallback = Optional[Callable[[dict[str, Any]], Coroutine[Any, Any, None]]]

# ---------------------------------------------------------------------------
# Detector protocol (duck-typing so we don't hard-depend on the concrete class)
# ---------------------------------------------------------------------------


class DetectorProtocol(Protocol):
    """Minimal interface a detector must satisfy."""

    def detect(self, image: Image.Image) -> list[Detection]: ...


# ---------------------------------------------------------------------------
# Screenshots directory
# ---------------------------------------------------------------------------

_SCREENSHOTS_DIR = Path("screenshots")


def _ensure_screenshots_dir() -> Path:
    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return _SCREENSHOTS_DIR


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class GuiGazerAgent:
    """High-level agent that loops through perceive → think → act.

    Parameters
    ----------
    detector:
        Any object implementing :pymethod:`detect(Image) -> list[Detection]`.
    reasoner:
        A :class:`VisionReasoner` for VLM-based decision-making.
    controller:
        A :class:`PlaywrightController` for browser interaction.
    """

    def __init__(
        self,
        detector: DetectorProtocol,
        reasoner: VisionReasoner,
        controller: PlaywrightController,
    ) -> None:
        self.detector = detector
        self.reasoner = reasoner
        self.controller = controller
        self.memory = ActionMemory(max_size=20)
        logger.info("GuiGazerAgent initialised")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run_task(
        self,
        task: str,
        url: str = "",
        callback: StepCallback = None,
    ) -> dict[str, Any]:
        """Execute a multi-step GUI task.

        Parameters
        ----------
        task:
            Natural-language description of the goal.
        url:
            Starting URL to navigate to before beginning the task.
        callback:
            Optional async callable invoked after each step with a dict
            containing ``step``, ``action``, ``detections_count``, and
            ``screenshot_path``.

        Returns
        -------
        dict
            Summary with keys ``task``, ``steps_taken``, ``completed``,
            and ``history``.
        """
        self.memory.clear()
        screenshots_dir = _ensure_screenshots_dir()
        completed = False
        step = 0

        # Navigate to URL if provided
        if url:
            logger.info("Navigating to starting URL: {}", url)
            await self.controller.navigate(url)
            await asyncio.sleep(1)  # Wait for page load

        logger.info("=== Starting task: '{}' (max {} steps) ===", task, settings.max_agent_steps)

        for step in range(1, settings.max_agent_steps + 1):
            t0 = time.perf_counter()

            # 1. Capture -------------------------------------------------------
            screenshot = await self.controller.capture()

            # 2. Detect --------------------------------------------------------
            detections: list[Detection] = self.detector.detect(screenshot)
            logger.info("Step {}: detected {} UI elements", step, len(detections))

            # 3. Annotate ------------------------------------------------------
            annotated = annotate_screenshot(screenshot, detections)

            # Save annotated screenshot
            screenshot_path = str(screenshots_dir / f"step_{step}.png")
            annotated.save(screenshot_path)
            logger.debug("Saved annotated screenshot → {}", screenshot_path)

            # 4. Reason --------------------------------------------------------
            action: Action = await self.reasoner.decide(
                annotated_image=annotated,
                task=task,
                history=self.memory.to_list(),
            )

            # 5. Record in memory
            self.memory.add(step=step, action=action, screenshot_path=screenshot_path)

            # 6. Execute -------------------------------------------------------
            completed = await self.controller.execute(action, detections)

            elapsed = time.perf_counter() - t0
            logger.info(
                "Step {} complete in {:.2f}s — action={}, element={}, done={}",
                step,
                elapsed,
                action.action,
                action.element_id,
                completed,
            )

            # 7. Callback ------------------------------------------------------
            if callback is not None:
                step_data = {
                    "step": step,
                    "action": action.action,
                    "element_id": action.element_id,
                    "value": action.value,
                    "reasoning": action.reasoning,
                    "detections_count": len(detections),
                    "screenshot_path": screenshot_path,
                    "elapsed_seconds": round(elapsed, 3),
                    "completed": completed,
                }
                await callback(step_data)

            if completed:
                logger.info("Task completed at step {}", step)
                break

            # Pace the loop
            if settings.action_delay_ms > 0:
                await asyncio.sleep(settings.action_delay_ms / 1000.0)

        if not completed:
            logger.warning(
                "Task NOT completed after {} steps (budget exhausted)", step
            )

        summary = {
            "task": task,
            "steps_taken": step,
            "completed": completed,
            "history": self.memory.to_list(),
        }
        return summary

    # ------------------------------------------------------------------
    # Accessibility audit (stub — delegates to a future audit module)
    # ------------------------------------------------------------------

    async def run_accessibility_audit(self, url: str = "") -> dict[str, Any]:
        """Capture the current page and run a full WCAG accessibility audit.

        Parameters
        ----------
        url:
            URL to navigate to before auditing.

        Returns
        -------
        dict
            Audit results with summary scores and detailed check results.
        """
        # Navigate if URL provided
        if url:
            logger.info("Navigating to audit target: {}", url)
            await self.controller.navigate(url)
            await asyncio.sleep(1)

        screenshot = await self.controller.capture()
        detections: list[Detection] = self.detector.detect(screenshot)
        annotated = annotate_screenshot(screenshot, detections)

        # Save audit screenshot
        screenshots_dir = _ensure_screenshots_dir()
        audit_path = str(screenshots_dir / "audit.png")
        annotated.save(audit_path)

        logger.info(
            "Accessibility audit captured {} elements → {}",
            len(detections),
            audit_path,
        )

        # Run full WCAG audit
        try:
            from audit.accessibility import run_full_audit
            audit_result = run_full_audit(screenshot, detections)
        except ImportError:
            logger.warning("Audit module not available, returning basic results")
            audit_result = {
                "summary": {"total_elements": len(detections), "overall_score": 0},
                "details": {},
            }

        audit_result["screenshot_path"] = audit_path
        audit_result["detections"] = [d.to_dict() for d in detections]
        return audit_result
