#!/usr/bin/env python3
"""Smoke test an OpenAI-compatible VLM endpoint with one local image."""

from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


PROMPT = """Look at the product image and return only valid JSON with these keys:
category, dominant_colors, visible_text, image_observed, short_description.

Use image_observed=true only if you can actually inspect the image.
"""


def image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{payload}"


def extract_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def call_endpoint(base_url: str, model: str, image_path: Path, timeout: int) -> dict:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_to_data_url(image_path)}},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 256,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"},
        method="POST",
    )
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            data = json.loads(raw)
            text = data["choices"][0]["message"].get("content", "")
            parsed = extract_json(text)
            return {
                "status": "ok",
                "http_status": response.status,
                "latency_ms": elapsed_ms,
                "raw_text": text,
                "parsed_json": parsed,
                "schema_valid": parsed is not None,
                "image_observed": bool(parsed and parsed.get("image_observed") is True),
                "usage": data.get("usage"),
            }
    except urllib.error.HTTPError as error:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            "status": "http_error",
            "http_status": error.code,
            "latency_ms": elapsed_ms,
            "error": error.read().decode("utf-8", errors="replace")[:2000],
        }
    except Exception as error:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return {"status": "error", "latency_ms": elapsed_ms, "error": repr(error)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    image_path = Path(args.image)
    result = call_endpoint(args.base_url, args.model, image_path, args.timeout)
    result.update({"label": args.label, "model": args.model, "image": str(image_path)})

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()