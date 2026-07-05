#!/usr/bin/env python3
"""DockMind local server with YOLO detection endpoint."""

from __future__ import annotations

import base64
import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import time_ns
from urllib.parse import urlparse

from yolo_core import DEFAULT_MODEL, DEFAULT_PROMPTS, detect_with_yolo


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / ".dockmind-runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
MAX_BODY_BYTES = 24 * 1024 * 1024


def _extension_for_data_url(header: str) -> str:
    if "image/png" in header:
        return ".png"
    if "image/webp" in header:
        return ".webp"
    if "image/heic" in header or "image/heif" in header:
        return ".heic"
    return ".jpg"


class DockMindHandler(SimpleHTTPRequestHandler):
    server_version = "DockMindYOLO/0.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/detect":
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        self._handle_detect()

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_detect(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json({"error": "invalid content length"}, HTTPStatus.BAD_REQUEST)
            return

        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self._json({"error": "image payload too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            image_data = payload["imageData"]
            header, encoded = image_data.split(",", 1)
            if not header.startswith("data:image/"):
                raise ValueError("imageData must be a data:image URL")
            image_bytes = base64.b64decode(encoded, validate=True)
        except Exception as exc:  # noqa: BLE001 - return client-friendly API errors.
            self._json({"error": f"invalid image payload: {exc}"}, HTTPStatus.BAD_REQUEST)
            return

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        image_path = UPLOAD_DIR / f"upload-{time_ns()}{_extension_for_data_url(header)}"
        image_path.write_bytes(image_bytes)

        model = str(payload.get("model") or os.environ.get("DOCKMIND_YOLO_MODEL") or DEFAULT_MODEL)
        prompts = payload.get("prompts") or DEFAULT_PROMPTS
        confidence = float(payload.get("confidence") or os.environ.get("DOCKMIND_YOLO_CONF") or 0.06)

        try:
            result = detect_with_yolo(image_path, model_name=model, prompts=list(prompts), confidence=confidence)
        except ModuleNotFoundError as exc:
            self._json({
                "error": f"YOLO dependency missing: {exc.name}",
                "install": "python3.12 -m venv .venv-yolo && .venv-yolo/bin/python -m pip install ultralytics",
            }, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        except Exception as exc:  # noqa: BLE001 - expose concise local demo failure.
            self._json({
                "error": f"YOLO detection failed: {exc.__class__.__name__}: {exc}",
                "model": model,
                "prompts": prompts,
            }, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        result["image"] = str(image_path.relative_to(ROOT))
        self._json(result)


def main() -> None:
    port = int(os.environ.get("PORT", "4173"))
    server = ThreadingHTTPServer(("", port), DockMindHandler)
    print(f"DockMind YOLO server: http://127.0.0.1:{port}")
    print(f"YOLO model: {os.environ.get('DOCKMIND_YOLO_MODEL', DEFAULT_MODEL)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDockMind YOLO server stopped")


if __name__ == "__main__":
    main()
