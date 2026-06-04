"""
GuiGazer — Set-of-Mark Annotator
=================================
Draws numbered, colour-coded markers on detected UI elements so the
vision-language model can reference them by ID.

Each element receives:
* A bounding-box outline in its class colour (from ``config.CLASS_COLORS``).
* A small filled circle at the top-left corner with the ``element_id``
  rendered in white text.
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont
from loguru import logger

from config import CLASS_COLORS
from detector.model import Detection

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MARKER_RADIUS: int = 12          # radius of the numbered circle
_FONT_SIZE: int = 14              # target font size for element IDs
_BOX_WIDTH: int = 2               # bounding-box outline thickness
_DEFAULT_COLOR: tuple[int, int, int] = (200, 200, 200)  # fallback grey


def _load_font(size: int = _FONT_SIZE) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a TrueType font; fall back to the built-in bitmap font."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            logger.debug("TrueType font unavailable — using default bitmap font")
            return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def annotate_screenshot(
    image: Image.Image,
    detections: list[Detection],
) -> Image.Image:
    """Draw numbered markers and bounding boxes on a screenshot.

    Parameters
    ----------
    image:
        The original (un-annotated) screenshot as a PIL Image.
    detections:
        List of :class:`Detection` objects to visualise.

    Returns
    -------
    PIL.Image.Image
        A *copy* of the input image with annotations drawn on top.
    """
    annotated = image.copy().convert("RGBA")
    overlay = Image.new("RGBA", annotated.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font()

    for det in detections:
        color = CLASS_COLORS.get(det.class_name, _DEFAULT_COLOR)
        x1, y1, x2, y2 = det.bbox

        # --- bounding-box outline -------------------------------------------
        draw.rectangle([x1, y1, x2, y2], outline=(*color, 220), width=_BOX_WIDTH)

        # --- numbered circle at top-left ------------------------------------
        cx = x1 + _MARKER_RADIUS
        cy = y1 + _MARKER_RADIUS
        draw.ellipse(
            [cx - _MARKER_RADIUS, cy - _MARKER_RADIUS,
             cx + _MARKER_RADIUS, cy + _MARKER_RADIUS],
            fill=(*color, 230),
        )

        # --- element ID text (white, centered in circle) --------------------
        label = str(det.element_id)
        bbox_text = draw.textbbox((0, 0), label, font=font)
        tw = bbox_text[2] - bbox_text[0]
        th = bbox_text[3] - bbox_text[1]
        draw.text(
            (cx - tw / 2, cy - th / 2),
            label,
            fill=(255, 255, 255, 255),
            font=font,
        )

    # Composite overlay onto original
    annotated = Image.alpha_composite(annotated, overlay)
    result = annotated.convert("RGB")

    logger.info("Annotated screenshot with {} element markers", len(detections))
    return result
