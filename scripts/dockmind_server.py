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
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from yolo_core import DEFAULT_MODEL, DEFAULT_PROMPTS, detect_with_yolo


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / ".dockmind-runtime"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
MAX_BODY_BYTES = 24 * 1024 * 1024


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()
DEFAULT_GEMINI_MODELS = ("gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite")
GEMINI_MODELS = tuple(
    model.strip()
    for model in os.environ.get("GEMINI_MODEL", ",".join(DEFAULT_GEMINI_MODELS)).split(",")
    if model.strip()
)


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

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/config":
            self._json({
                "gemini": bool(os.environ.get("GEMINI_API_KEY")),
                "vertex": bool(os.environ.get("GOOGLE_CLOUD_ACCESS_TOKEN") and (
                    os.environ.get("GOOGLE_CLOUD_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
                )),
                "shisa": bool(os.environ.get("SHISA_API_KEY") or os.environ.get("SHISA_API_URL")),
                "crustdata": bool(os.environ.get("CRUSTDATA_API_KEY")),
                "gbrain": bool(os.environ.get("GBRAIN_ENABLED")),
            })
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/detect":
            self._handle_detect()
            return
        if path == "/api/analyze-cargo":
            self._handle_analyze_cargo()
            return
        if path == "/api/agent-skill":
            self._handle_agent_skill()
            return
        if path == "/api/voice-command":
            self._handle_voice_command()
            return
        if path == "/api/crustdata":
            self._handle_crustdata()
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid content length")

        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            raise ValueError("image payload too large")

        return json.loads(self.rfile.read(content_length).decode("utf-8"))

    def _handle_detect(self) -> None:
        try:
            payload = self._read_json_body()
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        try:
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

    def _handle_analyze_cargo(self) -> None:
        try:
            payload = self._read_json_body()
            detections = payload.get("detections") or []
            prompt = str(payload.get("prompt") or "")
            route = payload.get("route") or ["Osaka", "Kyoto", "Nagoya"]
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        try:
            cargo = _gemini_cargo_manifest(detections, prompt, route)
            self._json({"source": "gemini", "cargo": cargo})
        except Exception as exc:  # noqa: BLE001 - local demo should keep working.
            cargo = _local_cargo_manifest(detections, prompt, route)
            self._json({"source": "local", "warning": str(exc), "cargo": cargo})

    def _handle_agent_skill(self) -> None:
        try:
            payload = self._read_json_body()
            plan = payload["plan"]
            kind = str(payload.get("kind") or "loader")
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        try:
            skill = _gemini_agent_skill(kind, plan)
            self._json({"source": "gemini", "skill": skill})
        except Exception as exc:  # noqa: BLE001
            self._json({"source": "local", "warning": str(exc), "skill": _local_agent_skill(kind, plan)})

    def _handle_voice_command(self) -> None:
        try:
            payload = self._read_json_body()
            transcript = str(payload.get("transcript") or "")
            plan = payload.get("plan") or {}
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        try:
            command = _gemini_voice_command(transcript, plan)
            self._json({"source": "gemini", "command": command})
        except Exception as exc:  # noqa: BLE001
            self._json({"source": "local", "warning": str(exc), "command": _local_voice_command(transcript)})

    def _handle_crustdata(self) -> None:
        try:
            payload = self._read_json_body()
        except Exception as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        api_key = os.environ.get("CRUSTDATA_API_KEY")
        if not api_key:
            self._json({"error": "CRUSTDATA_API_KEY is not configured"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return

        # Crustdata is optional enrichment for demo data. The endpoint can be
        # overridden without code changes as their API account shape varies.
        endpoint = os.environ.get("CRUSTDATA_API_URL", "https://api.crustdata.com/screener/company")
        try:
            req = Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urlopen(req, timeout=12) as response:  # noqa: S310 - user-configured API endpoint.
                data = json.loads(response.read().decode("utf-8"))
            self._json({"source": "crustdata", "data": data})
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            self._json({"source": "crustdata", "error": str(exc)}, HTTPStatus.BAD_GATEWAY)


def _gemini_text(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    access_token = os.environ.get("GOOGLE_CLOUD_ACCESS_TOKEN")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_REGION") or os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1"

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    timeout = int(os.environ.get("AGENT_BUILDER_TIMEOUT_MS", "15000")) / 1000
    errors: list[str] = []

    if not api_key and not (access_token and project):
        raise RuntimeError("Neither GEMINI_API_KEY nor Google Cloud Vertex credentials are configured")

    if api_key:
        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                return _post_gemini_json(url, body, {"Content-Type": "application/json"}, timeout, f"Gemini API {model}")
            except Exception as exc:  # noqa: BLE001 - try the next configured model/provider.
                errors.append(str(exc))

    if access_token and project:
        for model in GEMINI_MODELS:
            url = (
                f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}"
                f"/publishers/google/models/{model}:generateContent"
            )
            try:
                return _post_gemini_json(
                    url,
                    body,
                    {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
                    timeout,
                    f"Vertex {model}",
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

    raise RuntimeError("Gemini failed for configured models: " + " | ".join(errors))


def _post_gemini_json(url: str, body: dict, headers: dict[str, str], timeout: float, label: str) -> str:
    req = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as response:  # noqa: S310
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:240]
        raise RuntimeError(f"{label}: HTTP {exc.code} {detail}") from exc

    candidates = data.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    text = "".join(str(part.get("text", "")) for part in parts)
    if not text:
        raise RuntimeError(f"{label}: returned no text")
    return text


def _json_from_model(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    return json.loads(stripped)


def _gemini_cargo_manifest(detections: list[dict], prompt: str, route: list[str]) -> list[dict]:
    text = _gemini_text(
        "You are DockMind, an AI logistics planner. Convert real YOLO cargo detections "
        "into a plausible cargo manifest for truck loading. Use the detection geometry "
        "as evidence; do not invent more boxes than detections. Return ONLY JSON: "
        "{\"cargo\":[{\"id\":\"BOX-01\",\"label\":\"...\",\"length\":80,\"width\":50,"
        "\"height\":45,\"weight\":22,\"stop\":\"Kyoto\",\"tags\":[\"fragile\"]}]}.\n"
        f"Route choices: {route}\n"
        f"Planner prompt: {prompt}\n"
        f"Detections: {json.dumps(detections, ensure_ascii=False)}"
    )
    data = _json_from_model(text)
    return _normalize_cargo_list(data.get("cargo", []), detections, route)


def _gemini_agent_skill(kind: str, plan: dict) -> str:
    text = _gemini_text(
        "Create a gstack-compatible SKILL.md for a DockMind logistics agent. "
        "Return JSON only: {\"skill\":\"...markdown...\"}. The skill must include "
        "frontmatter name/description, goal, inputs, steps, safety checks, and done criteria. "
        f"Agent kind: {kind}\nPlan JSON: {json.dumps(plan, ensure_ascii=False)}"
    )
    data = _json_from_model(text)
    skill = str(data.get("skill") or "")
    if not skill:
        raise RuntimeError("Gemini returned no skill")
    return skill


def _gemini_voice_command(transcript: str, plan: dict) -> dict:
    text = _gemini_text(
        "Parse a warehouse voice command for DockMind. Return JSON only with keys: "
        "intent (detect|analyze|optimize|set_truck|generate_agent|unknown), "
        "truckId (smallVan|fourTon|reefer|null), spokenResponse, role (loader|driver|ops|customer|agent|null). "
        f"Transcript: {transcript}\nCurrent plan metrics: {json.dumps(plan.get('metrics', {}), ensure_ascii=False)}"
    )
    data = _json_from_model(text)
    return {
        "intent": str(data.get("intent") or "unknown"),
        "truckId": data.get("truckId"),
        "role": data.get("role"),
        "spokenResponse": str(data.get("spokenResponse") or "Command parsed."),
    }


def _normalize_cargo_list(cargo: list[dict], detections: list[dict], route: list[str]) -> list[dict]:
    normalized: list[dict] = []
    for index, item in enumerate(cargo[:12]):
        detection = detections[index] if index < len(detections) else {}
        stop = item.get("stop") if item.get("stop") in route else route[min(len(route) - 1, 1 + (index % max(1, len(route) - 1)))]
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        normalized.append({
            "id": str(item.get("id") or detection.get("id") or f"BOX-{index + 1:02d}")[:18],
            "label": str(item.get("label") or detection.get("label") or "Detected cargo")[:48],
            "length": _bounded_int(item.get("length"), 45, 140, 70),
            "width": _bounded_int(item.get("width"), 35, 95, 50),
            "height": _bounded_int(item.get("height"), 32, 95, 45),
            "weight": _bounded_int(item.get("weight"), 8, 140, 24),
            "stop": stop,
            "tags": [str(tag).lower() for tag in tags if str(tag).lower() in {"cold", "fragile", "heavy"}],
        })
    if normalized:
        return normalized
    return _local_cargo_manifest(detections, "", route)


def _bounded_int(value: Any, low: int, high: int, fallback: int) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = fallback
    return max(low, min(high, parsed))


def _local_cargo_manifest(detections: list[dict], prompt: str, route: list[str]) -> list[dict]:
    prompt_lower = prompt.lower()
    usable = detections[:12]
    cargo = []
    for index, detection in enumerate(usable):
        tags: list[str] = []
        if ("cold" in prompt_lower or "frozen" in prompt_lower or "medical" in prompt_lower) and index % 4 == 0:
            tags.append("cold")
        if ("fragile" in prompt_lower or "electronics" in prompt_lower) and index % 3 == 1:
            tags.append("fragile")
        if ("machine" in prompt_lower or "heavy" in prompt_lower) and index == 0:
            tags.append("heavy")
        w = float(detection.get("w") or 12)
        h = float(detection.get("h") or 12)
        cargo.append({
            "id": detection.get("id") or f"BOX-{index + 1:02d}",
            "label": "Detected cargo box",
            "length": round(max(45, min(130, 42 + w * 1.7))),
            "width": round(max(35, min(90, 30 + h * 1.4))),
            "height": round(max(32, min(90, 28 + ((w * h) ** 0.5) * 1.1))),
            "weight": round(max(10, min(120, 10 + (w * h / 22)))),
            "stop": route[min(len(route) - 1, 1 + (index % max(1, len(route) - 1)))],
            "tags": tags,
        })
    return cargo


def _local_agent_skill(kind: str, plan: dict) -> str:
    placements = plan.get("placements") or []
    warnings = plan.get("warnings") or []
    steps = "\n".join(
        f"{index + 1}. Move {item.get('id')} to x={item.get('x')}cm, y={item.get('y')}cm. Stop: {item.get('stop')}."
        for index, item in enumerate(placements)
    )
    checks = "\n".join(f"- {item.get('title')}: {item.get('body')}" for item in warnings)
    return f"""---
name: dockmind-{kind}-agent
description: Execute DockMind truck loading plan for the {kind} role.
---

# DockMind {kind.title()} Agent Skill

## Goal
Turn the current DockMind load plan into safe, ordered warehouse action.

## Inputs
- DockMind plan JSON
- Cargo detections
- Truck preset

## Steps
{steps}

## Safety Checks
{checks}

## Done Criteria
- Cargo is loaded in the rendered order.
- Open exceptions are confirmed by ops before departure.
"""


def _local_voice_command(transcript: str) -> dict:
    text = transcript.lower()
    if "camera" in text or "detect" in text or "scan" in text:
        return {"intent": "detect", "truckId": None, "role": None, "spokenResponse": "Scanning cargo now."}
    if "analyze" in text or "manifest" in text:
        return {"intent": "analyze", "truckId": None, "role": None, "spokenResponse": "Analyzing detected cargo."}
    if "optimize" in text or "plan" in text:
        return {"intent": "optimize", "truckId": None, "role": None, "spokenResponse": "Optimizing the load plan."}
    if "refrigerated" in text or "reefer" in text:
        return {"intent": "set_truck", "truckId": "reefer", "role": None, "spokenResponse": "Switching to refrigerated truck."}
    if "van" in text:
        return {"intent": "set_truck", "truckId": "smallVan", "role": None, "spokenResponse": "Switching to small van."}
    if "agent" in text or "skill" in text:
        return {"intent": "generate_agent", "truckId": None, "role": "loader", "spokenResponse": "Generating the loader skill."}
    return {"intent": "unknown", "truckId": None, "role": None, "spokenResponse": "I did not catch a DockMind command."}


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
