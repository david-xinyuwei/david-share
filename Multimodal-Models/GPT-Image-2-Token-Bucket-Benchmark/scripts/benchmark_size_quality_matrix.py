#!/usr/bin/env python3
"""
GPT-Image-2 Size × Quality Token Matrix
==========================================
Tests all 9 combinations of size and quality to build a complete
output token mapping table. Saves images and records token/latency data.

Usage:
    export AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
    export AZURE_OPENAI_KEY="YOUR_KEY"
    python benchmark_size_quality_matrix.py

Author: Xinyu Wei
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("Install: pip install requests")
    sys.exit(1)


def generate_image(endpoint, api_key, deployment, prompt, quality, size,
                   api_version="2025-04-01-preview"):
    url = (
        f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        f"/images/generations?api-version={api_version}"
    )
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    body = {"prompt": prompt, "quality": quality, "size": size, "n": 1}

    start = time.time()
    resp = requests.post(url, headers=headers, json=body, timeout=300)
    elapsed = time.time() - start
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})

    img_bytes = None
    if data.get("data") and data["data"][0].get("b64_json"):
        img_bytes = base64.b64decode(data["data"][0]["b64_json"])

    return {
        "size": size,
        "quality": quality,
        "output_tokens": usage.get("output_tokens"),
        "input_tokens": usage.get("input_tokens"),
        "latency_s": round(elapsed, 1),
        "image_bytes": len(img_bytes) if img_bytes else 0,
    }, img_bytes


def main():
    parser = argparse.ArgumentParser(
        description="GPT-Image-2 Size x Quality Token Matrix"
    )
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""))
    parser.add_argument("--key", default=os.environ.get("AZURE_OPENAI_KEY", ""))
    parser.add_argument("--deployment", default="gpt-image-2")
    parser.add_argument("--api-version", default="2025-04-01-preview")
    parser.add_argument("--output-dir", default="output_matrix")
    parser.add_argument("--prompt", default="A golden retriever puppy in a sunlit meadow")
    parser.add_argument("--wait", type=int, default=5, help="Seconds between requests")
    args = parser.parse_args()

    if not args.endpoint or not args.key:
        print("ERROR: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    sizes = ["1024x1024", "1024x1536", "1536x1024"]
    qualities = ["low", "medium", "high"]
    results = []
    total = len(sizes) * len(qualities)
    i = 0

    print(f"\nSize x Quality Token Matrix — {datetime.now().isoformat()}")
    print(f"Prompt: \"{args.prompt}\"")
    print(f"Tests: {total} ({len(sizes)} sizes x {len(qualities)} qualities)\n")
    print(f"{'Size':12s} | {'Quality':7s} | {'OutTok':>6s} | {'InTok':>5s} | {'Latency':>7s}")
    print("-" * 50)

    for size in sizes:
        for quality in qualities:
            i += 1
            try:
                result, img_bytes = generate_image(
                    args.endpoint, args.key, args.deployment,
                    args.prompt, quality, size, args.api_version,
                )
                results.append(result)
                if img_bytes:
                    fname = f"{size}_{quality}.png"
                    with open(os.path.join(args.output_dir, fname), "wb") as f:
                        f.write(img_bytes)
                print(
                    f"{size:12s} | {quality:7s} | {result['output_tokens']:6d} | "
                    f"{result['input_tokens']:5d} | {result['latency_s']:6.1f}s"
                )
            except Exception as e:
                print(f"{size:12s} | {quality:7s} | ERROR: {e}")
                results.append({"size": size, "quality": quality, "error": str(e)})
            if i < total:
                time.sleep(args.wait)

    # Summary matrix
    print(f"\n{'='*50}")
    print("Output Token Matrix:")
    print(f"{'Size':12s} | {'low':>6s} | {'medium':>6s} | {'high':>6s}")
    print("-" * 40)
    for size in sizes:
        row = []
        for q in qualities:
            match = [r for r in results if r.get("size") == size and r.get("quality") == q]
            row.append(str(match[0].get("output_tokens", "ERR")) if match else "ERR")
        print(f"{size:12s} | {row[0]:>6s} | {row[1]:>6s} | {row[2]:>6s}")

    # Save
    outfile = os.path.join(args.output_dir, "size_quality_matrix.json")
    with open(outfile, "w") as f:
        json.dump({"date": datetime.now().isoformat(), "prompt": args.prompt, "results": results}, f, indent=2)
    print(f"\nSaved to {outfile}")


if __name__ == "__main__":
    main()
