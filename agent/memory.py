"""
GuiGazer — Short-Term Action Memory
=====================================
Maintains a bounded history of agent actions so the VLM can reference
what it has already tried and avoid loops or repeated mistakes.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from loguru import logger

from agent.reasoner import Action


class ActionMemory:
    """Rolling window of recent agent actions.

    Parameters
    ----------
    max_size : int
        Maximum number of steps to retain.  Oldest entries are dropped
        once the limit is exceeded.
    """

    def __init__(self, max_size: int = 20) -> None:
        self._max_size = max_size
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(
        self,
        step: int,
        action: Action,
        screenshot_path: Optional[str] = None,
    ) -> None:
        """Append a completed step to the history.

        Parameters
        ----------
        step:
            1-based step number.
        action:
            The :class:`Action` that was executed.
        screenshot_path:
            Optional filesystem path where the annotated screenshot was saved.
        """
        entry = {
            "step": step,
            "element_id": action.element_id,
            "action": action.action,
            "value": action.value,
            "reasoning": action.reasoning,
            "screenshot_path": screenshot_path,
        }
        self._history.append(entry)

        # Trim oldest entries if over capacity
        if len(self._history) > self._max_size:
            dropped = len(self._history) - self._max_size
            self._history = self._history[dropped:]
            logger.debug("ActionMemory trimmed {} oldest entries", dropped)

        logger.debug(
            "ActionMemory recorded step {} — {} element {}",
            step,
            action.action,
            action.element_id,
        )

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def get_history_text(self) -> str:
        """Format the history as human-readable text for VLM context.

        Example output::

            Step 1: Clicked element 3 (Button) — "Navigate to settings"
            Step 2: Typed "admin" into element 7 (Text Input) — "Enter username"
        """
        lines: list[str] = []
        for h in self._history:
            act = h["action"]
            eid = h["element_id"]
            reason = h.get("reasoning", "")

            if act == "click":
                desc = f"Clicked element {eid}"
            elif act == "type":
                desc = f"Typed \"{h.get('value', '')}\" into element {eid}"
            elif act == "scroll":
                desc = "Scrolled down"
            elif act == "done":
                desc = "Marked task as done"
            else:
                desc = f"{act} element {eid}"

            lines.append(f"Step {h['step']}: {desc} — \"{reason}\"")

        return "\n".join(lines)

    def to_list(self) -> list[dict]:
        """Return the raw history as a list of dicts (JSON-serialisable)."""
        return list(self._history)

    def clear(self) -> None:
        """Reset the memory to empty."""
        self._history.clear()
        logger.debug("ActionMemory cleared")

    def __len__(self) -> int:
        return len(self._history)

    def __repr__(self) -> str:
        return f"ActionMemory(size={len(self._history)}, max={self._max_size})"
