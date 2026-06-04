"""
GuiGazer — Synthetic GUI Dataset Generator
============================================
Generates synthetic GUI screenshots with realistic UI elements (buttons,
text inputs, checkboxes, toggles, dropdowns, links, icons, navigation bars,
cards, and text blocks) drawn via Pillow.  Bounding-box annotations are
saved in YOLO format alongside a ``data.yaml`` consumed by Ultralytics.

Usage::

    python -m detector.dataset          # generate 20 images + labels
    python -m detector.dataset --count 50
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from loguru import logger
from PIL import Image, ImageDraw, ImageFont

# Resolve project root so ``config`` is always importable.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import UI_CLASSES  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────

IMG_W, IMG_H = 640, 640  # YOLO default input size
DATASET_DIR = _PROJECT_ROOT / "datasets" / "gui_elements"

# Colour palette (light/dark themes)
_BG_COLORS = [(255, 255, 255), (245, 245, 245), (30, 30, 30), (18, 18, 18)]
_ACCENT_COLORS = [
    (59, 130, 246),   # blue
    (16, 185, 129),   # green
    (239, 68, 68),    # red
    (245, 158, 11),   # amber
    (139, 92, 246),   # purple
    (236, 72, 153),   # pink
    (14, 165, 233),   # sky
]
_TEXT_COLORS_LIGHT = [(33, 33, 33), (55, 55, 55), (80, 80, 80)]
_TEXT_COLORS_DARK = [(220, 220, 220), (200, 200, 200), (180, 180, 180)]

_BUTTON_LABELS = [
    "Submit", "Login", "Sign Up", "Cancel", "OK", "Next", "Back",
    "Save", "Delete", "Continue", "Send", "Apply", "Search", "Download",
    "Upload", "Confirm", "Reset", "Close", "Edit", "Add",
]
_INPUT_PLACEHOLDERS = [
    "Enter your name…", "Email address", "Search…", "Password",
    "Type here…", "Username", "Phone number", "https://",
]
_LINK_LABELS = [
    "Learn more", "Privacy Policy", "Terms of Service", "Forgot password?",
    "Contact us", "Help center", "Read more →", "View all",
]
_TEXT_SAMPLES = [
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
    "Welcome to GuiGazer, your AI-powered GUI automation tool.",
    "Please fill in the form below to create your account.",
    "Your changes have been saved successfully.",
    "Dashboard  |  Settings  |  Profile  |  Notifications",
]
_NAV_ITEMS = ["Home", "About", "Products", "Blog", "Contact"]


def _try_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a TrueType font, fall back to the built-in bitmap font."""
    for name in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ── Primitive drawers ─────────────────────────────────────────────────────────
# Each drawer returns the bbox as (x1, y1, x2, y2) in *pixel* coordinates.


def _draw_button(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Rounded-rectangle button with centred text."""
    x1, y1, x2, y2 = region
    color = random.choice(_ACCENT_COLORS)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=color)
    label = random.choice(_BUTTON_LABELS)
    font = _try_font(max(12, (y2 - y1) // 2))
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x1 + ((x2 - x1) - tw) // 2
    ty = y1 + ((y2 - y1) - th) // 2
    draw.text((tx, ty), label, fill=(255, 255, 255), font=font)


def _draw_text_input(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Bordered text input field with placeholder text."""
    x1, y1, x2, y2 = region
    bg = (50, 50, 50) if dark else (255, 255, 255)
    border = (100, 100, 100) if dark else (200, 200, 200)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=6, fill=bg, outline=border, width=2)
    placeholder = random.choice(_INPUT_PLACEHOLDERS)
    font = _try_font(max(11, (y2 - y1) // 3))
    color = (120, 120, 120)
    draw.text((x1 + 10, y1 + (y2 - y1) // 4), placeholder, fill=color, font=font)


def _draw_checkbox(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Small square checkbox, optionally checked."""
    x1, y1, x2, y2 = region
    side = min(x2 - x1, y2 - y1)
    cx, cy = x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2
    bx1, by1 = cx - side // 2, cy - side // 2
    bx2, by2 = bx1 + side, by1 + side
    border = (180, 180, 180) if not dark else (120, 120, 120)
    draw.rectangle([bx1, by1, bx2, by2], outline=border, width=2)
    if random.random() > 0.4:
        accent = random.choice(_ACCENT_COLORS)
        draw.rectangle([bx1 + 3, by1 + 3, bx2 - 3, by2 - 3], fill=accent)
        draw.line([(bx1 + 5, cy), (cx - 2, by2 - 5), (bx2 - 4, by1 + 5)], fill=(255, 255, 255), width=2)


def _draw_toggle(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Pill-shaped toggle switch."""
    x1, y1, x2, y2 = region
    h = y2 - y1
    on = random.random() > 0.5
    bg = random.choice(_ACCENT_COLORS) if on else ((80, 80, 80) if dark else (200, 200, 200))
    draw.rounded_rectangle([x1, y1, x2, y2], radius=h // 2, fill=bg)
    circle_r = h // 2 - 3
    if on:
        cx = x2 - circle_r - 4
    else:
        cx = x1 + circle_r + 4
    cy = y1 + h // 2
    draw.ellipse([cx - circle_r, cy - circle_r, cx + circle_r, cy + circle_r], fill=(255, 255, 255))


def _draw_dropdown(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Dropdown selector with a down-arrow indicator."""
    x1, y1, x2, y2 = region
    bg = (50, 50, 50) if dark else (255, 255, 255)
    border = (100, 100, 100) if dark else (200, 200, 200)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=6, fill=bg, outline=border, width=2)
    font = _try_font(max(11, (y2 - y1) // 3))
    text_color = _TEXT_COLORS_DARK[0] if dark else _TEXT_COLORS_LIGHT[0]
    draw.text((x1 + 10, y1 + (y2 - y1) // 4), "Select option", fill=text_color, font=font)
    # Down arrow ▼
    ax = x2 - 20
    ay = y1 + (y2 - y1) // 2
    draw.polygon([(ax - 6, ay - 3), (ax + 6, ay - 3), (ax, ay + 5)], fill=text_color)


def _draw_link(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Underlined link text."""
    x1, y1, x2, y2 = region
    label = random.choice(_LINK_LABELS)
    font = _try_font(max(11, (y2 - y1) // 2))
    color = (59, 130, 246)
    draw.text((x1 + 4, y1 + (y2 - y1) // 4), label, fill=color, font=font)
    bbox = draw.textbbox((x1 + 4, y1 + (y2 - y1) // 4), label, font=font)
    draw.line([(bbox[0], bbox[3] + 1), (bbox[2], bbox[3] + 1)], fill=color, width=1)


def _draw_icon(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Simple geometric icon (circle or square with a symbol inside)."""
    x1, y1, x2, y2 = region
    side = min(x2 - x1, y2 - y1)
    cx, cy = x1 + (x2 - x1) // 2, y1 + (y2 - y1) // 2
    r = side // 2
    color = random.choice(_ACCENT_COLORS)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    # Inner symbol — small rectangle or cross
    inner = r // 2
    draw.rectangle([cx - inner, cy - 1, cx + inner, cy + 1], fill=(255, 255, 255))
    draw.rectangle([cx - 1, cy - inner, cx + 1, cy + inner], fill=(255, 255, 255))


def _draw_image_placeholder(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Grey rectangle with a mountain-icon indicating an image placeholder."""
    x1, y1, x2, y2 = region
    bg = (60, 60, 60) if dark else (230, 230, 230)
    draw.rectangle([x1, y1, x2, y2], fill=bg)
    # Mountain icon
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    s = min(x2 - x1, y2 - y1) // 4
    draw.polygon([(mx - s, my + s), (mx, my - s), (mx + s, my + s)], fill=(180, 180, 180) if not dark else (100, 100, 100))


def _draw_nav_bar(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Horizontal navigation bar with tab items."""
    x1, y1, x2, y2 = region
    bg = (35, 35, 35) if dark else (250, 250, 250)
    draw.rectangle([x1, y1, x2, y2], fill=bg)
    draw.line([(x1, y2), (x2, y2)], fill=(200, 200, 200) if not dark else (70, 70, 70), width=1)
    items = random.sample(_NAV_ITEMS, k=min(len(_NAV_ITEMS), random.randint(3, 5)))
    font = _try_font(max(11, (y2 - y1) // 3))
    spacing = (x2 - x1) // (len(items) + 1)
    text_color = _TEXT_COLORS_DARK[0] if dark else _TEXT_COLORS_LIGHT[0]
    for i, item in enumerate(items):
        tx = x1 + spacing * (i + 1) - 15
        ty = y1 + (y2 - y1) // 4
        draw.text((tx, ty), item, fill=text_color, font=font)


def _draw_modal(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Rounded card resembling a modal dialog."""
    x1, y1, x2, y2 = region
    bg = (45, 45, 45) if dark else (255, 255, 255)
    shadow = (0, 0, 0, 40)
    # Shadow
    draw.rounded_rectangle([x1 + 4, y1 + 4, x2 + 4, y2 + 4], radius=12, fill=(180, 180, 180))
    draw.rounded_rectangle([x1, y1, x2, y2], radius=12, fill=bg, outline=(200, 200, 200), width=1)
    # Title bar
    font = _try_font(max(12, (y2 - y1) // 8))
    text_color = _TEXT_COLORS_DARK[0] if dark else _TEXT_COLORS_LIGHT[0]
    draw.text((x1 + 16, y1 + 12), "Dialog Title", fill=text_color, font=font)
    # Close X
    draw.text((x2 - 24, y1 + 10), "✕", fill=(180, 80, 80), font=font)


def _draw_card(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Content card with header, body, and subtle border."""
    x1, y1, x2, y2 = region
    bg = (50, 50, 50) if dark else (255, 255, 255)
    border = (80, 80, 80) if dark else (220, 220, 220)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=10, fill=bg, outline=border, width=1)
    # Header stripe
    draw.rounded_rectangle([x1, y1, x2, y1 + (y2 - y1) // 4], radius=10, fill=random.choice(_ACCENT_COLORS))
    # Body text
    font = _try_font(max(10, (y2 - y1) // 10))
    text_color = _TEXT_COLORS_DARK[0] if dark else _TEXT_COLORS_LIGHT[0]
    draw.text((x1 + 12, y1 + (y2 - y1) // 3), "Card content…", fill=text_color, font=font)


def _draw_text_block(draw: ImageDraw.ImageDraw, region: tuple[int, int, int, int], dark: bool) -> None:
    """Multi-line paragraph text."""
    x1, y1, x2, y2 = region
    font = _try_font(max(10, (y2 - y1) // 6))
    text = random.choice(_TEXT_SAMPLES)
    text_color = _TEXT_COLORS_DARK[0] if dark else _TEXT_COLORS_LIGHT[0]
    draw.text((x1 + 6, y1 + 6), text, fill=text_color, font=font, width=x2 - x1 - 12)


# Mapping from class index → drawer function
_DRAWERS = {
    0: _draw_button,          # Button
    1: _draw_text_input,      # Text Input
    2: _draw_checkbox,        # Checkbox
    3: _draw_toggle,          # Toggle
    4: _draw_dropdown,        # Dropdown
    5: _draw_link,            # Link
    6: _draw_icon,            # Icon
    7: _draw_image_placeholder,  # Image
    8: _draw_nav_bar,         # Navigation Bar
    9: _draw_modal,           # Modal
    10: _draw_card,           # Card
    11: _draw_text_block,     # Text Block
}

# Approximate min/max sizes (w, h) for each element class
_SIZE_RANGES: dict[int, tuple[tuple[int, int], tuple[int, int]]] = {
    0:  ((80, 30), (200, 50)),     # Button
    1:  ((140, 30), (300, 45)),    # Text Input
    2:  ((20, 20), (30, 30)),      # Checkbox
    3:  ((44, 22), (60, 30)),      # Toggle
    4:  ((120, 30), (220, 45)),    # Dropdown
    5:  ((80, 18), (180, 28)),     # Link
    6:  ((24, 24), (40, 40)),      # Icon
    7:  ((100, 80), (260, 180)),   # Image
    8:  ((400, 36), (620, 52)),    # Navigation Bar
    9:  ((200, 140), (380, 260)),  # Modal
    10: ((160, 120), (300, 220)),  # Card
    11: ((180, 40), (400, 90)),    # Text Block
}


# ── Overlap helpers ───────────────────────────────────────────────────────────

def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Compute Intersection over Union for two boxes."""
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _place_element(
    cls_id: int,
    existing: list[tuple[int, int, int, int]],
    max_attempts: int = 40,
) -> tuple[int, int, int, int] | None:
    """Try to place an element without heavy overlap (IoU < 0.15)."""
    (min_w, min_h), (max_w, max_h) = _SIZE_RANGES[cls_id]
    for _ in range(max_attempts):
        w = random.randint(min_w, max_w)
        h = random.randint(min_h, max_h)
        x1 = random.randint(5, max(6, IMG_W - w - 5))
        y1 = random.randint(5, max(6, IMG_H - h - 5))
        x2, y2 = x1 + w, y1 + h
        box = (x1, y1, x2, y2)
        if all(_iou(box, e) < 0.15 for e in existing):
            return box
    return None


# ── Image generation ──────────────────────────────────────────────────────────


def _generate_image(index: int, images_dir: Path, labels_dir: Path) -> None:
    """Generate a single synthetic screenshot with YOLO annotations."""
    dark = random.random() > 0.5
    bg = random.choice(_BG_COLORS[2:] if dark else _BG_COLORS[:2])
    img = Image.new("RGB", (IMG_W, IMG_H), bg)
    draw = ImageDraw.Draw(img)

    # Decide how many elements (6-15 per image)
    num_elements = random.randint(6, 15)

    placed: list[tuple[int, int, int, int]] = []
    annotations: list[str] = []

    for _ in range(num_elements):
        cls_id = random.randint(0, len(UI_CLASSES) - 1)
        box = _place_element(cls_id, placed)
        if box is None:
            continue
        x1, y1, x2, y2 = box
        placed.append(box)

        # Draw the element
        drawer = _DRAWERS.get(cls_id)
        if drawer:
            drawer(draw, box, dark)

        # YOLO format: class_id  x_center  y_center  width  height  (all normalised)
        xc = ((x1 + x2) / 2) / IMG_W
        yc = ((y1 + y2) / 2) / IMG_H
        bw = (x2 - x1) / IMG_W
        bh = (y2 - y1) / IMG_H
        annotations.append(f"{cls_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")

    # Save image
    img_path = images_dir / f"gui_{index:04d}.png"
    img.save(img_path)

    # Save label
    lbl_path = labels_dir / f"gui_{index:04d}.txt"
    lbl_path.write_text("\n".join(annotations), encoding="utf-8")


# ── Public API ────────────────────────────────────────────────────────────────


def create_yolo_dataset_yaml(path: Path) -> Path:
    """Create a ``data.yaml`` file for YOLOv8 training.

    Parameters
    ----------
    path : Path
        Root directory of the dataset (should contain ``images/`` and
        ``labels/`` sub-directories, each with ``train/`` and ``val/``).

    Returns
    -------
    Path
        Absolute path to the generated ``data.yaml``.
    """
    yaml_path = path / "data.yaml"
    names_block = "\n".join(f"  {i}: {name}" for i, name in enumerate(UI_CLASSES))
    content = (
        f"path: {path.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"\n"
        f"nc: {len(UI_CLASSES)}\n"
        f"names:\n{names_block}\n"
    )
    yaml_path.write_text(content, encoding="utf-8")
    logger.info("Created data.yaml → {}", yaml_path)
    return yaml_path


def download_rico_sample(count: int = 20) -> Path:
    """Generate *count* synthetic GUI screenshots with YOLO annotations.

    Since the full RICO dataset is very large, this function synthesises
    realistic-looking GUI screenshots using Pillow and saves them alongside
    YOLO-format label files.

    The dataset is split 80/20 into ``train`` and ``val`` sets.

    Parameters
    ----------
    count : int
        Total number of images to generate (default 20).

    Returns
    -------
    Path
        Root directory of the generated dataset.
    """
    base = DATASET_DIR
    train_imgs = base / "images" / "train"
    train_lbls = base / "labels" / "train"
    val_imgs = base / "images" / "val"
    val_lbls = base / "labels" / "val"

    for d in (train_imgs, train_lbls, val_imgs, val_lbls):
        d.mkdir(parents=True, exist_ok=True)

    split_idx = int(count * 0.8)  # 80 % train

    logger.info("Generating {} synthetic GUI screenshots …", count)
    for i in range(count):
        if i < split_idx:
            _generate_image(i, train_imgs, train_lbls)
        else:
            _generate_image(i, val_imgs, val_lbls)

    logger.success(
        "Dataset ready — {} train / {} val  →  {}",
        split_idx,
        count - split_idx,
        base,
    )

    # Write data.yaml
    create_yolo_dataset_yaml(base)
    return base


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic GUI dataset")
    parser.add_argument("--count", type=int, default=20, help="Number of images to generate")
    args = parser.parse_args()
    download_rico_sample(count=args.count)
