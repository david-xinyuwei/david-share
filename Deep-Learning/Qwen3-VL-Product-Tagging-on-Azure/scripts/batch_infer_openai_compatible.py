#!/usr/bin/env python3
"""Run a small image-tagging benchmark against a vLLM/SGLang OpenAI-compatible endpoint."""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path
from typing import Any

from openai import OpenAI


PROMPT = """Analyze this fashion product image and return only valid JSON with keys:
category, subcategory, colors, materials, patterns, style_tags, product_attributes, confidence.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, for example http://localhost:8000/v1")
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
    parser.add_argument("--input", required=True, help="Input JSONL with at least an image field.")
    parser.add_argument("--output", default="reports/baseline_predictions.jsonl")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    return parser.parse_args()


def image_to_data_url(path: str) -> str:
    image_path = Path(path)
    suffix = image_path.suffix.lower().lstrip(".") or "jpeg"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{payload}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_content(row: dict[str, Any]) -> list[dict[str, Any]]:
    title = row.get("title", "")
    description = row.get("description", "")
    category = row.get("category", "")
    text = f"{PROMPT}\nTitle: {title}\nDescription: {description}\nCategory hint: {category}"
    return [
        {"type": "image_url", "image_url": {"url": image_to_data_url(str(row["image"]))}},
        {"type": "text", "text": text},
    ]


def main() -> None:
    args = parse_args()
    client = OpenAI(base_url=args.base_url, api_key=args.api_key)
    rows = read_jsonl(Path(args.input))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as output_file:
        for index, row in enumerate(rows, start=1):
            started_at = time.perf_counter()
            response = client.chat.completions.create(
                model=args.model,
                messages=[{"role": "user", "content": build_content(row)}],
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
            elapsed = time.perf_counter() - started_at
            prediction = response.choices[0].message.content
            output_file.write(
                json.dumps(
                    {
                        "index": index,
                        "image": row.get("image"),
                        "prediction": prediction,
                        "latency_seconds": elapsed,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            print(f"{index}/{len(rows)} latency={elapsed:.3f}s")

    print(f"Wrote predictions to {output_path}")


if __name__ == "__main__":
    main()
