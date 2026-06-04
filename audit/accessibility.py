"""
GuiGazer — WCAG Accessibility Checker
======================================
Analyses annotated screenshots against WCAG 2.1 guidelines:

* **Contrast**: luminance ratio of dominant foreground / background colours.
* **Touch-targets**: minimum 44 × 44 px for interactive elements.
* **Labels**: every ``Text Input`` should have a nearby ``Text Block`` label.

All thresholds are pulled from ``config.settings`` so they can be tuned via
environment variables without touching code.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from loguru import logger
from PIL import Image

from config import settings

# ── interactive classes that must meet touch-target requirements ──────────
_INTERACTIVE_CLASSES: set[str] = {
    "Button",
    "Text Input",
    "Checkbox",
    "Toggle",
    "Dropdown",
    "Link",
}


# ── colour / luminance helpers ───────────────────────────────────────────
def _relative_luminance(rgb: np.ndarray) -> float:
    """Compute WCAG 2.1 *relative luminance* for an sRGB colour (0-255).

    Formula: https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
    """
    srgb = rgb / 255.0
    linear = np.where(srgb <= 0.03928, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2])


def _dominant_two_colors(region: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the two most dominant colours in an image region using k-means.

    Uses a simple two-centre k-means (3 iterations) on the pixel cloud.
    Falls back to darkest / lightest pixels when the region is too small.
    """
    pixels = region.reshape(-1, 3).astype(np.float64)

    if len(pixels) < 2:
        colour = pixels[0] if len(pixels) == 1 else np.array([0.0, 0.0, 0.0])
        return colour, colour

    # ── seed centres: darkest & lightest pixel by brightness ─────────
    brightness = pixels.sum(axis=1)
    c1 = pixels[brightness.argmin()].copy()
    c2 = pixels[brightness.argmax()].copy()

    for _ in range(3):
        d1 = np.linalg.norm(pixels - c1, axis=1)
        d2 = np.linalg.norm(pixels - c2, axis=1)
        mask = d1 <= d2
        if mask.any():
            c1 = pixels[mask].mean(axis=0)
        if (~mask).any():
            c2 = pixels[~mask].mean(axis=0)

    return c1, c2


def _contrast_ratio(l1: float, l2: float) -> float:
    """WCAG contrast ratio, always ≥ 1.0."""
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ── public API ───────────────────────────────────────────────────────────

def check_contrast(image: Image.Image, detections: list) -> list[dict]:
    """Evaluate contrast ratio for every detected element.

    Parameters
    ----------
    image:
        The full screenshot as a PIL Image (RGB).
    detections:
        List of detection dicts, each having at least
        ``id``, ``class_name``, ``bbox`` (x1, y1, x2, y2).

    Returns
    -------
    list[dict]
        One record per detection with keys:
        ``element_id``, ``class_name``, ``contrast_ratio``,
        ``passes_aa``, ``passes_aaa``.
    """
    img_array = np.array(image.convert("RGB"))
    h, w = img_array.shape[:2]
    results: list[dict] = []

    for det in detections:
        x1, y1, x2, y2 = (int(v) for v in det["bbox"])
        # clamp to image bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        region = img_array[y1:y2, x1:x2]
        if region.size == 0:
            logger.warning("Empty region for element {}", det.get("id"))
            results.append(
                {
                    "element_id": det.get("id"),
                    "class_name": det.get("class_name", ""),
                    "contrast_ratio": 1.0,
                    "passes_aa": False,
                    "passes_aaa": False,
                }
            )
            continue

        c1, c2 = _dominant_two_colors(region)
        lum1 = _relative_luminance(c1)
        lum2 = _relative_luminance(c2)
        ratio = round(_contrast_ratio(lum1, lum2), 2)

        results.append(
            {
                "element_id": det.get("id"),
                "class_name": det.get("class_name", ""),
                "contrast_ratio": ratio,
                "passes_aa": ratio >= settings.wcag_contrast_aa,
                "passes_aaa": ratio >= settings.wcag_contrast_aaa,
            }
        )
        logger.debug(
            "Contrast {}: ratio={:.2f}  AA={} AAA={}",
            det.get("id"),
            ratio,
            results[-1]["passes_aa"],
            results[-1]["passes_aaa"],
        )

    return results


def check_touch_targets(
    detections: list,
    min_size: int | None = None,
) -> list[dict]:
    """Verify interactive elements meet minimum touch-target dimensions.

    Parameters
    ----------
    detections:
        List of detection dicts (``id``, ``class_name``, ``bbox``).
    min_size:
        Override for the minimum pixel size (default from ``settings``).

    Returns
    -------
    list[dict]
        Records with ``element_id``, ``class_name``, ``width``, ``height``,
        ``passes``.
    """
    min_px = min_size if min_size is not None else settings.min_touch_target_px
    results: list[dict] = []

    for det in detections:
        cls = det.get("class_name", "")
        if cls not in _INTERACTIVE_CLASSES:
            continue

        x1, y1, x2, y2 = (int(v) for v in det["bbox"])
        w = x2 - x1
        h = y2 - y1
        passes = w >= min_px and h >= min_px

        results.append(
            {
                "element_id": det.get("id"),
                "class_name": cls,
                "width": w,
                "height": h,
                "passes": passes,
            }
        )
        if not passes:
            logger.debug(
                "Touch-target FAIL {}: {}×{} < {}px",
                det.get("id"),
                w,
                h,
                min_px,
            )

    return results


def check_labels(detections: list, proximity_px: int = 50) -> list[dict]:
    """Check that every ``Text Input`` has a nearby ``Text Block`` label.

    A ``Text Block`` is considered a label when its bottom-right corner is
    within *proximity_px* pixels above **or** to the left of the input's
    top-left corner.

    Parameters
    ----------
    detections:
        Detection dicts (``id``, ``class_name``, ``bbox``,
        optionally ``text``).
    proximity_px:
        Maximum gap in pixels to consider a text block as a label.

    Returns
    -------
    list[dict]
        Records with ``element_id``, ``has_label``, ``label_text``.
    """
    inputs = [d for d in detections if d.get("class_name") == "Text Input"]
    labels = [d for d in detections if d.get("class_name") == "Text Block"]

    results: list[dict] = []
    for inp in inputs:
        ix1, iy1, _, _ = (int(v) for v in inp["bbox"])
        best_label: Optional[str] = None

        for lbl in labels:
            lx1, ly1, lx2, ly2 = (int(v) for v in lbl["bbox"])

            # label above: its bottom edge is above input, horizontally overlapping
            above = (ly2 <= iy1) and (iy1 - ly2 <= proximity_px) and (lx1 <= ix1)
            # label to the left: its right edge is left of input, vertically close
            left = (lx2 <= ix1) and (ix1 - lx2 <= proximity_px) and (abs(ly1 - iy1) <= proximity_px)

            if above or left:
                best_label = lbl.get("text")
                break

        results.append(
            {
                "element_id": inp.get("id"),
                "has_label": best_label is not None,
                "label_text": best_label,
            }
        )

    return results


def run_full_audit(
    image: Image.Image,
    detections: list,
) -> dict:
    """Run all accessibility checks and return a consolidated report.

    Returns
    -------
    dict
        ``summary`` with totals + ``overall_score`` (0-100) and
        ``details`` with per-check lists.
    """
    logger.info("Running full accessibility audit on {} detections", len(detections))

    contrast = check_contrast(image, detections)
    touch = check_touch_targets(detections)
    labels = check_labels(detections)

    contrast_issues = sum(1 for c in contrast if not c["passes_aa"])
    touch_issues = sum(1 for t in touch if not t["passes"])
    label_issues = sum(1 for l in labels if not l["has_label"])
    total = len(detections)

    total_checks = len(contrast) + len(touch) + len(labels)
    total_passes = (
        sum(1 for c in contrast if c["passes_aa"])
        + sum(1 for t in touch if t["passes"])
        + sum(1 for l in labels if l["has_label"])
    )
    score = round(total_passes / total_checks * 100) if total_checks else 100

    summary = {
        "total_elements": total,
        "contrast_issues": contrast_issues,
        "touch_target_issues": touch_issues,
        "label_issues": label_issues,
        "overall_score": score,
    }

    logger.info(
        "Audit complete — score={}/100  contrast_issues={}  touch_issues={}  label_issues={}",
        score,
        contrast_issues,
        touch_issues,
        label_issues,
    )

    return {
        "summary": summary,
        "details": {
            "contrast": contrast,
            "touch_targets": touch,
            "labels": labels,
        },
    }
