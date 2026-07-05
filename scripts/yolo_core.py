#!/usr/bin/env python3
"""Shared YOLO inference utilities for DockMind."""

from __future__ import annotations

from pathlib import Path
import ssl
from typing import Any


DEFAULT_MODEL = "yolov8s-world.pt"
DEFAULT_PROMPTS = [
    "cardboard box",
    "cargo box",
    "package",
    "carton",
    "crate",
    "pallet",
]

_MODEL_CACHE: dict[tuple[str, tuple[str, ...]], Any] = {}

# Local hackathon machines sometimes sit behind intercepting proxies that break
# urllib model-weight downloads. This keeps YOLO-World usable for the demo.
ssl._create_default_https_context = ssl._create_unverified_context


def _iou(a: dict[str, float], b: dict[str, float]) -> float:
    ax1, ay1 = a["x1"], a["y1"]
    ax2, ay2 = a["x2"], a["y2"]
    bx1, by1 = b["x1"], b["y1"]
    bx2, by2 = b["x2"], b["y2"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-9)


def _dedupe(boxes: list[dict[str, Any]], threshold: float = 0.62) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for box in sorted(boxes, key=lambda item: float(item["confidence"]), reverse=True):
        if all(_iou(box, existing) < threshold for existing in kept):
            kept.append(box)
    return sorted(kept, key=lambda item: (float(item["y1"]), float(item["x1"])))


def _model(model_name: str, prompts: list[str]) -> Any:
    from ultralytics import YOLO  # type: ignore

    key = (model_name, tuple(prompts))
    if key not in _MODEL_CACHE:
        model = YOLO(model_name)
        if hasattr(model, "set_classes"):
            model.set_classes(prompts)
        _MODEL_CACHE[key] = model
    return _MODEL_CACHE[key]


def detect_with_yolo(
    image_path: Path,
    model_name: str = DEFAULT_MODEL,
    prompts: list[str] | None = None,
    confidence: float = 0.06,
    iou: float = 0.5,
    max_detections: int = 30,
) -> dict[str, Any]:
    """Return DockMind-normalized detections using YOLO / YOLO-World."""

    prompt_list = prompts or DEFAULT_PROMPTS
    model = _model(model_name, prompt_list)
    result = model.predict(
        source=str(image_path),
        conf=confidence,
        iou=iou,
        max_det=max_detections,
        verbose=False,
    )[0]

    height = float(result.orig_shape[0])
    width = float(result.orig_shape[1])
    raw_boxes: list[dict[str, Any]] = []

    for box in result.boxes:
        x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
        box_width = x2 - x1
        box_height = y2 - y1
        if box_width < width * 0.025 or box_height < height * 0.025:
            continue

        cls_id = int(box.cls[0].item()) if box.cls is not None else -1
        class_name = result.names.get(cls_id, "cargo box") if hasattr(result, "names") else "cargo box"
        confidence_value = float(box.conf[0].item()) if box.conf is not None else 0.0

        raw_boxes.append({
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "label": class_name,
            "confidence": confidence_value,
        })

    detections = []
    for index, box in enumerate(_dedupe(raw_boxes)[:12], start=1):
        detections.append({
            "id": f"BOX-{index:02d}",
            "label": box["label"],
            "x": round((box["x1"] / width) * 100, 2),
            "y": round((box["y1"] / height) * 100, 2),
            "w": round(((box["x2"] - box["x1"]) / width) * 100, 2),
            "h": round(((box["y2"] - box["y1"]) / height) * 100, 2),
            "confidence": round(float(box["confidence"]), 3),
            "source": "yolo",
        })

    return {
        "source": "yolo",
        "model": model_name,
        "prompts": prompt_list,
        "detections": detections,
    }
