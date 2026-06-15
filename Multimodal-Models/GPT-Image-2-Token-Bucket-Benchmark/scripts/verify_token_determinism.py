#!/usr/bin/env python3
"""
GPT-Image-2 Token Determinism Verification
=============================================
Runs N diverse prompts at a fixed quality+size to verify that
output tokens are deterministic and prompt-independent.

Usage:
    export AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
    export AZURE_OPENAI_KEY="YOUR_KEY"
    python verify_token_determinism.py

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

DEFAULT_PROMPTS = [
    "Chrome kimono maiden surrounded by metallic flowers, cinematic lighting",
    "A portal into a mythical forest on the wall of a small messy bedroom",
    "A tiny astronaut hatching from an egg on the moon",
    "Cute fluffy creature fantasy, dreamlike, surrealism, trending on artstation",
    "A hidden cenote in a lush jungle with crystalline turquoise waters",
    "A charming girl with silver pixie-cut hair working on holographic interface",
    "Universe, LSD, Fractal Worlds, Giant Eyes",
    "Close up render of a mythical creature made of spiraling fractals",
    "An angry cat playing drums",
    "A monkey playing music in a jazz club",
    "Watercolor painting of Venice canals at sunset with gondolas",
]


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
        "prompt": prompt,
        "output_tokens": usage.get("output_tokens"),
        "input_tokens": usage.get("input_tokens"),
        "latency_s": round(elapsed, 1),
    }, img_bytes


def main():
    parser = argparse.ArgumentParser(
        description="Verify GPT-Image-2 output tokens are prompt-independent"
    )
    parser.add_argument("--endpoint", default=os.environ.get("AZURE_OPENAI_ENDPOINT", ""))
    parser.add_argument("--key", default=os.environ.get("AZURE_OPENAI_KEY", ""))
    parser.add_argument("--deployment", default="gpt-image-2")
    parser.add_argument("--api-version", default="2025-04-01-preview")
    parser.add_argument("--quality", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--output-dir", default="output_determinism")
    parser.add_argument("--wait", type=int, default=5, help="Seconds between requests")
    args = parser.parse_args()

    if not args.endpoint or not args.key:
        print("ERROR: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    results = []

    print(f"\nToken Determinism Test — {datetime.now().isoformat()}")
    print(f"Fixed: quality={args.quality}, size={args.size}")
    print(f"Prompts: {len(DEFAULT_PROMPTS)}\n")
    print(f"{'#':>2s} | {'OutTok':>6s} | {'InTok':>5s} | {'Latency':>7s} | Prompt")
    print("-" * 80)

    for i, prompt in enumerate(DEFAULT_PROMPTS, 1):
        try:
            result, img_bytes = generate_image(
                args.endpoint, args.key, args.deployment,
                prompt, args.quality, args.size, args.api_version,
            )
            results.append(result)
            if img_bytes:
                fname = f"{i:02d}_{args.quality}.png"
                with open(os.path.join(args.output_dir, fname), "wb") as f:
                    f.write(img_bytes)
            print(
                f"{i:2d} | {result['output_tokens']:6d} | {result['input_tokens']:5d} | "
                f"{result['latency_s']:6.1f}s | {prompt[:50]}"
            )
        except Exception as e:
            print(f"{i:2d} | ERROR: {e}")
            results.append({"prompt": prompt, "error": str(e)})
        if i < len(DEFAULT_PROMPTS):
            time.sleep(args.wait)

    # Verify determinism
    tokens = [r["output_tokens"] for r in results if "output_tokens" in r]
    unique = set(tokens)
    print(f"\n{'='*80}")
    if len(unique) == 1:
        print(f"PASS: All {len(tokens)} prompts returned {unique.pop()} output tokens.")
        print("Output tokens are DETERMINISTIC and PROMPT-INDEPENDENT.")
    else:
        print(f"FAIL: Found {len(unique)} different token counts: {unique}")
        print("Output tokens may vary — investigate further.")

    latencies = [r["latency_s"] for r in results if "latency_s" in r]
    if latencies:
        avg = sum(latencies) / len(latencies)
        print(f"Latency: avg={avg:.1f}s, min={min(latencies):.1f}s, max={max(latencies):.1f}s")

    # Save
    outfile = os.path.join(args.output_dir, "determinism_results.json")
    with open(outfile, "w") as f:
        json.dump({
            "date": datetime.now().isoformat(),
            "quality": args.quality, "size": args.size,
            "results": results,
        }, f, indent=2)
    print(f"Saved to {outfile}")


if __name__ == "__main__":
    main()
