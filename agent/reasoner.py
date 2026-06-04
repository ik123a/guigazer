"""
GuiGazer — Vision LLM Reasoner
===============================
Sends annotated screenshots to an NVIDIA NIM vision model (OpenAI-compatible)
and parses the structured JSON response into an :class:`Action` dataclass.
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass

from loguru import logger
from openai import AsyncOpenAI
from PIL import Image

from config import settings

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class Action:
    """A single agent action decided by the vision LLM.

    Attributes
    ----------
    element_id : int
        The annotated element number to interact with (``-1`` for *done*).
    action : str
        One of ``"click"``, ``"type"``, ``"scroll"``, ``"done"``.
    value : str
        Text to type when ``action == "type"``; empty string otherwise.
    reasoning : str
        Brief natural-language explanation from the model.
    """

    element_id: int
    action: str
    value: str
    reasoning: str


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a GUI automation agent. You see a screenshot with numbered UI "
    "elements. Given the user task, decide which element to interact with. "
    'Respond ONLY with JSON: {"element_id": int, "action": '
    '"click"|"type"|"scroll"|"done", "value": "text to type if action is '
    'type, else empty", "reasoning": "brief explanation"}.'
)

# ---------------------------------------------------------------------------
# Reasoner
# ---------------------------------------------------------------------------


class VisionReasoner:
    """Wraps an NVIDIA NIM vision-language model for GUI decision-making."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.nvidia_vlm_base_url,
            api_key=settings.nvidia_api_key,
        )
        self._model = settings.nvidia_vlm_model
        logger.info(
            "VisionReasoner initialised — model={}, base_url={}",
            self._model,
            settings.nvidia_vlm_base_url,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _image_to_data_url(image: Image.Image) -> str:
        """Encode a PIL image as a base64 ``data:`` URL (JPEG)."""
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{b64}"

    @staticmethod
    def _parse_action(raw: str) -> Action:
        """Extract a JSON object from the model response text.

        The model *should* return pure JSON, but occasionally wraps it in
        markdown fences (````json … ````).  We strip those before parsing.
        """
        text = raw.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]  # remove opening fence line
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        data = json.loads(text)
        return Action(
            element_id=int(data.get("element_id", -1)),
            action=str(data.get("action", "done")),
            value=str(data.get("value", "")),
            reasoning=str(data.get("reasoning", "")),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def decide(
        self,
        annotated_image: Image.Image,
        task: str,
        history: list[dict],
    ) -> Action:
        """Ask the VLM what to do next.

        Parameters
        ----------
        annotated_image:
            The screenshot with Set-of-Mark annotations.
        task:
            The high-level user goal (e.g. *"Book a flight to Tokyo"*).
        history:
            Previous actions serialised as dicts (for context).

        Returns
        -------
        Action
            The parsed next action.  On any failure a *done* action with an
            error reasoning string is returned so the loop can exit cleanly.
        """
        image_url = self._image_to_data_url(annotated_image)

        # Build history context string
        history_text = ""
        if history:
            history_text = "\n\nPrevious actions:\n" + "\n".join(
                f"- Step {h.get('step', '?')}: {h.get('action', '?')} "
                f"element {h.get('element_id', '?')} — {h.get('reasoning', '')}"
                for h in history
            )

        user_content: list[dict] = [
            {
                "type": "text",
                "text": f"Task: {task}{history_text}",
            },
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            },
        ]

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_tokens=256,
            )

            raw_text = response.choices[0].message.content or ""
            logger.debug("VLM raw response: {}", raw_text[:300])

            action = self._parse_action(raw_text)
            logger.info(
                "VLM decided: action={}, element_id={}, reasoning={}",
                action.action,
                action.element_id,
                action.reasoning[:80],
            )
            return action

        except json.JSONDecodeError as exc:
            logger.error("Failed to parse VLM JSON: {}", exc)
            return Action(
                element_id=-1,
                action="done",
                value="",
                reasoning=f"JSON parse error: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("VLM request failed: {}", exc)
            return Action(
                element_id=-1,
                action="done",
                value="",
                reasoning=f"VLM error: {exc}",
            )
