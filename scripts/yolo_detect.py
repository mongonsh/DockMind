#!/usr/bin/env python3
"""DockMind YOLO-compatible detection wrapper."""

from __future__ import annotations

import argparse
import json
import pathlib

from yolo_core import DEFAULT_MODEL, DEFAULT_PROMPTS, detect_with_yolo


SAMPLE_DETECTIONS = [
    {"id": "FRZ-01", "label": "FRZ-01 90x60x55 42kg", "x": 9, "y": 15, "w": 25, "h": 27, "confidence": 0.91},
    {"id": "FRG-02", "label": "FRAGILE 70x50x45 18kg", "x": 35, "y": 22, "w": 21, "h": 24, "confidence": 0.88},
    {"id": "MCH-03", "label": "HEAVY 110x70x65 95kg", "x": 58, "y": 14, "w": 29, "h": 34, "confidence": 0.86},
    {"id": "MED-05", "label": "COLD FRAGILE 60x45x42", "x": 18, "y": 52, "w": 19, "h": 25, "confidence": 0.82},
    {"id": "RET-06", "label": "STOP: Kyoto 75x55x48", "x": 66, "y": 52, "w": 21, "h": 26, "confidence": 0.8},
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Warehouse image path")
    parser.add_argument("--out", required=True, help="Output DockMind detection JSON")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="YOLO model path/name")
    parser.add_argument("--prompt", action="append", default=[], help="Open-vocabulary YOLO prompt. Repeatable.")
    parser.add_argument("--conf", type=float, default=0.06, help="Detection confidence threshold")
    args = parser.parse_args()

    image_path = pathlib.Path(args.image)
    output_path = pathlib.Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source = "sample-fallback"
    try:
        result = detect_with_yolo(
            image_path,
            model_name=args.model,
            prompts=args.prompt or DEFAULT_PROMPTS,
            confidence=args.conf,
        )
        detections = result["detections"] or SAMPLE_DETECTIONS
        source = result["source"]
    except Exception as exc:  # noqa: BLE001 - demo fallback should catch install/model issues.
        detections = SAMPLE_DETECTIONS
        source = f"sample-fallback: {exc.__class__.__name__}"

    output_path.write_text(json.dumps({
        "source": source,
        "image": str(image_path),
        "detections": detections,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(detections)} detections to {output_path} ({source})")


if __name__ == "__main__":
    main()
