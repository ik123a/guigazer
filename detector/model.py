"""
GuiGazer — YOLOv8 GUI Element Detector
=======================================
Wraps an Ultralytics YOLOv8 model for detecting UI elements in screenshots.
Supports loading fine-tuned weights with automatic fallback to a pretrained
``yolov8n.pt`` checkpoint.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import PIL.Image
from loguru import logger
from ultralytics import YOLO

# Resolve project root so ``config`` is always importable.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import UI_CLASSES, settings  # noqa: E402


# ── Detection dataclass ──────────────────────────────────────────────────────


@dataclass
class Detection:
    """A single detected UI element.

    Attributes
    ----------
    bbox : tuple[int, int, int, int]
        Bounding box as ``(x1, y1, x2, y2)`` in pixel coordinates.
    class_name : str
        Predicted UI class label (e.g., ``"Button"``, ``"Text Input"``).
    confidence : float
        Model confidence score in ``[0, 1]``.
    element_id : int
        Sequential identifier assigned during detection (0-based).
    """

    bbox: tuple[int, int, int, int]
    class_name: str
    confidence: float
    element_id: int

    # ── convenience helpers ───────────────────────────────────────────────

    @property
    def center(self) -> tuple[int, int]:
        """Return the ``(cx, cy)`` center of the bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]

    @property
    def area(self) -> int:
        return self.width * self.height

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary."""
        return {
            "element_id": self.element_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox": list(self.bbox),
        }


# ── GUIDetector ──────────────────────────────────────────────────────────────


class GUIDetector:
    """YOLOv8-based GUI element detector.

    Parameters
    ----------
    model_path : str | Path | None
        Path to fine-tuned weights.  Falls back to ``yolov8n.pt`` (COCO
        pretrained) when the file does not exist or is ``None``.
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        resolved = Path(model_path) if model_path else Path(settings.detector_model_path)

        if resolved.exists():
            logger.info("Loading fine-tuned model from {}", resolved)
            self.model = YOLO(str(resolved))
        else:
            logger.warning(
                "Model path '{}' not found — falling back to pretrained yolov8n.pt",
                resolved,
            )
            self.model = YOLO("yolov8n.pt")

        self._class_names: list[str] = UI_CLASSES
        logger.info(
            "GUIDetector initialised  |  {} UI classes  |  conf={}  |  iou={}",
            len(self._class_names),
            settings.detector_confidence,
            settings.detector_iou_threshold,
        )

    # ── inference ─────────────────────────────────────────────────────────

    def detect(self, image: PIL.Image.Image) -> list[Detection]:
        """Run inference on a single PIL image.

        Returns
        -------
        list[Detection]
            Detections that survive the configured confidence & NMS
            thresholds.
        """
        results = self.model.predict(
            source=image,
            conf=settings.detector_confidence,
            iou=settings.detector_iou_threshold,
            verbose=False,
        )

        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for idx, box in enumerate(boxes):
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())

                # Map class id → human-readable name
                if cls_id < len(self._class_names):
                    class_name = self._class_names[cls_id]
                else:
                    class_name = result.names.get(cls_id, f"class_{cls_id}")

                detections.append(
                    Detection(
                        bbox=(int(x1), int(y1), int(x2), int(y2)),
                        class_name=class_name,
                        confidence=round(conf, 4),
                        element_id=idx,
                    )
                )

        logger.info("Detected {} UI elements", len(detections))
        return detections

    # ── export ────────────────────────────────────────────────────────────

    def export_onnx(self, path: str) -> None:
        """Export the loaded model to ONNX format.

        Parameters
        ----------
        path : str
            Destination file path (e.g. ``"model.onnx"``).
        """
        logger.info("Exporting model to ONNX → {}", path)
        export_path = self.model.export(format="onnx", imgsz=640)
        exported = Path(str(export_path))
        target = Path(path)
        if exported.exists() and exported != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            exported.rename(target)
        logger.success("ONNX export complete: {}", target)
