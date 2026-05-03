#!/usr/bin/env python3
"""
GPT-Image-2 Token Bucket Benchmark
====================================
Tests how the `quality` parameter affects output token count in GPT-Image-2.
Uses REST API directly for maximum compatibility.

Usage:
    export AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
    export AZURE_OPENAI_KEY="YOUR_KEY"
    python benchmark_gpt_image2.py --endpoint $AZURE_OPENAI_ENDPOINT --key $AZURE_OPENAI_KEY

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


def generate_image(endpoint, api_key, deployment, prompt, quality,
                   size="1024x1024", api_version="2025-04-01-preview"):
    """Generate one image via REST API and return metadata + image bytes."""
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
        "prompt": prompt,
        "quality": quality,
        "size": size,
        "latency_s": round(elapsed, 2),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "input_tokens_details": usage.get("input_tokens_details"),
        "background": data.get("background"),
        "output_format": data.get("output_format"),
        "image_bytes": len(img_bytes) if img_bytes else 0,
    }, img_bytes


def main():
    parser = argparse.ArgumentParser(
        description="GPT-Image-2 Token Bucket Benchmark"
    )
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        help="Azure OpenAI endpoint URL",
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("AZURE_OPENAI_KEY", ""),
        help="Azure OpenAI API key",
    )
    parser.add_argument("--deployment", default="gpt-image-2")
    parser.add_argument("--api-version", default="2025-04-01-preview")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--wait", type=int, default=10, help="Seconds between requests"
    )
    args = parser.parse_args()

    if not args.endpoint or not args.key:
        print("ERROR: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY env vars,")
        print("       or use --endpoint and --key arguments.")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    prompts = [
        "A simple red circle on white background",
        (
            "A photorealistic golden retriever puppy sitting in a sunlit meadow"
            " with wildflowers, shallow depth of field, professional photography"
        ),
    ]
    qualities = ["low", "medium", "high"]
    results = []
    total = len(prompts) * len(qualities)
    i = 0

    print(f"\nGPT-Image-2 Token Bucket Benchmark — {datetime.now().isoformat()}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Tests: {total} ({len(qualities)} qualities x {len(prompts)} prompts)\n")

    for prompt in prompts:
        tag = prompt[:40].replace(" ", "_").replace(",", "")
        for quality in qualities:
            i += 1
            print(f"[{i}/{total}] quality={quality:6s} | {prompt[:50]}...")

            try:
                result, img_bytes = generate_image(
                    args.endpoint, args.key, args.deployment,
                    prompt, quality, api_version=args.api_version,
                )
                results.append(result)

                if img_bytes:
                    fname = f"{tag}_{quality}.png"
                    path = os.path.join(args.output_dir, fname)
                    with open(path, "wb") as f:
                        f.write(img_bytes)

                print(
                    f"  OK {result['latency_s']:6.1f}s | "
                    f"output_tokens={result['output_tokens']} | "
                    f"{result['image_bytes']/1024:.0f}KB"
                )
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append({
                    "prompt": prompt, "quality": quality,
                    "error": str(e), "latency_s": 0,
                })

            if i < total:
                print(f"  waiting {args.wait}s...")
                time.sleep(args.wait)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY — output_tokens by quality:")
    print(f"{'='*60}")
    for q in qualities:
        q_results = [r for r in results if r.get("quality") == q and "error" not in r]
        tokens = [r["output_tokens"] for r in q_results]
        costs = [round(r["output_tokens"] * 30 / 1_000_000, 4) for r in q_results]
        print(f"  {q:6s} -> tokens={tokens}, cost/image=${costs}")

    # Save
    outfile = os.path.join(args.output_dir, "benchmark_results.json")
    with open(outfile, "w") as f:
        json.dump({
            "model": "gpt-image-2",
            "date": datetime.now().isoformat(),
            "api_version": args.api_version,
            "results": results,
        }, f, indent=2)
    print(f"\nSaved to {outfile}")


if __name__ == "__main__":
    main()
