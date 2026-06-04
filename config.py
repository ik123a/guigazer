"""
GuiGazer Configuration
======================
API keys, model settings, detection thresholds, and app-wide config.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # --- NVIDIA NIM Vision API ---
    nvidia_api_key: str = Field(default="", description="NVIDIA API key for NIM endpoints")
    nvidia_vlm_model: str = Field(
        default="meta/llama-3.2-90b-vision-instruct",
        description="NVIDIA NIM vision model for reasoning",
    )
    nvidia_vlm_base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="NVIDIA NIM API base URL",
    )

    # --- Fallback: OpenAI GPT-4V ---
    openai_api_key: str = Field(default="", description="OpenAI API key (fallback)")
    openai_vlm_model: str = Field(default="gpt-4o", description="OpenAI vision model")

    # --- YOLOv8 Detector ---
    detector_model_path: str = Field(
        default="detector/checkpoints/guigazer_yolov8n.pt",
        description="Path to fine-tuned YOLOv8 weights",
    )
    detector_confidence: float = Field(
        default=0.35,
        description="Minimum confidence threshold for detections",
    )
    detector_iou_threshold: float = Field(
        default=0.45,
        description="IoU threshold for NMS",
    )

    # --- Agent ---
    max_agent_steps: int = Field(default=15, description="Max steps per task")
    action_delay_ms: int = Field(
        default=500,
        description="Delay between agent actions in milliseconds",
    )

    # --- Accessibility ---
    wcag_contrast_aa: float = Field(default=4.5, description="WCAG AA contrast ratio")
    wcag_contrast_aaa: float = Field(default=7.0, description="WCAG AAA contrast ratio")
    min_touch_target_px: int = Field(default=44, description="Min touch target size (px)")

    # --- Server ---
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    log_level: str = Field(default="info")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()


# ---------------------------------------------------------------------------
# UI Element Classes for YOLOv8
# ---------------------------------------------------------------------------

UI_CLASSES = [
    "Button",
    "Text Input",
    "Checkbox",
    "Toggle",
    "Dropdown",
    "Link",
    "Icon",
    "Image",
    "Navigation Bar",
    "Modal",
    "Card",
    "Text Block",
]

CLASS_COLORS = {
    "Button":         (59, 130, 246),   # Blue
    "Text Input":     (16, 185, 129),   # Green
    "Checkbox":       (245, 158, 11),   # Amber
    "Toggle":         (236, 72, 153),   # Pink
    "Dropdown":       (139, 92, 246),   # Purple
    "Link":           (6, 182, 212),    # Cyan
    "Icon":           (251, 146, 60),   # Orange
    "Image":          (34, 197, 94),    # Emerald
    "Navigation Bar": (244, 63, 94),    # Rose
    "Modal":          (168, 85, 247),   # Violet
    "Card":           (100, 116, 139),  # Slate
    "Text Block":     (148, 163, 184),  # Gray
}
