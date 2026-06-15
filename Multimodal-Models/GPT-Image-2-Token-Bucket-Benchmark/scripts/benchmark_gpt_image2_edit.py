#!/usr/bin/env python3
"""Benchmark GPT-Image-2 image edit API across quality levels.

Usage:
  export AZURE_OPENAI_ENDPOINT="https://<resource><your-resource>.openai.azure.com"
  export AZURE_OPENAI_KEY="<key>"
  python scripts/benchmark_gpt_image2_edit.py \
    --input-image images/matrix/1024x1024_medium.png \
    --prompt "Add cool sunglasses to the dog" \
    --output-dir images/edit_test
"""

import argparse
import base64
import csv
import os
import time

import requests


def run_edit(endpoint, api_key, deployment, api_version, image_path, prompt, quality, size):
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/images/edits"
        f"?api-version={api_version}"
    )
    with open(image_path, "rb") as f:
        files = [("image[]", (os.path.basename(image_path), f, "image/png"))]
        data = {
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": "1",
        }
        t0 = time.time()
        resp = requests.post(url, headers={"api-key": api_key}, files=files, data=data, timeout=420)
        latency = round(time.time() - t0, 1)
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    usage = payload.get("usage", {})
    image_bytes = base64.b64decode(payload["data"][0]["b64_json"])
    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "latency_s": latency,
        "img_kb": round(len(image_bytes) / 1024),
    }, image_bytes


def main():
    parser = argparse.ArgumentParser(description="Benchmark GPT-Image-2 edit API")
    parser.add_argument("--endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT", "https://<your-resource><your-resource>.openai.azure.com"))
    parser.add_argument("--api-key", default=os.getenv("AZURE_OPENAI_KEY", ""))
    parser.add_argument("--deployment", default="gpt-image-2")
    parser.add_argument("--api-version", default="2025-04-01-preview")
    parser.add_argument("--input-image", required=True)
    parser.add_argument("--prompt", default="Add cool sunglasses to the dog")
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--output-dir", default="images/edit_test")
    parser.add_argument("--csv", default="data/edit_quality_matrix.csv")
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("Set AZURE_OPENAI_KEY or pass --api-key")

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.csv), exist_ok=True)

    rows = []
    for quality in ["low", "medium", "high"]:
        result, image_bytes = run_edit(
            args.endpoint,
            args.api_key,
            args.deployment,
            args.api_version,
            args.input_image,
            args.prompt,
            quality,
            args.size,
        )
        output_path = os.path.join(args.output_dir, f"dog_sunglasses_{quality}.png")
        with open(output_path, "wb") as wf:
            wf.write(image_bytes)
        row = [quality, result["input_tokens"], result["output_tokens"], result["total_tokens"], result["latency_s"], result["img_kb"]]
        rows.append(row)
        print(f"{quality}: input={row[1]} output={row[2]} total={row[3]} latency={row[4]}s imgKB={row[5]}")

    with open(args.csv, "w", newline="") as cf:
        writer = csv.writer(cf)
        writer.writerow(["quality", "input_tokens", "output_tokens", "total_tokens", "latency_s", "imgKB"])
        writer.writerows(rows)
    print(f"Saved CSV: {args.csv}")


if __name__ == "__main__":
    main()
