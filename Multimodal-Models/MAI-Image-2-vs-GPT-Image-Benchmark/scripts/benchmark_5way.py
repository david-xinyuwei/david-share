"""
5-Way Image Generation Benchmark: MAI-Image-2 vs MAI-Image-2e vs GPT-Image-1.5 (low/medium/high)
Author: Xinyu Wei (魏新宇)
Date: 2026-04-19

API Sources:
  MAI: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python
  GPT: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e

Fairness: warmup + alternating order + symmetric wait + 2 rounds
"""
import csv
import json
import base64
import time
import subprocess
import sys
import math
import requests
from pathlib import Path
from datetime import datetime

# === Config ===
CSV_PATH = Path(__file__).parent.parent / "微软2个接口测试(Surreal).csv"

# MAI endpoint — source: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai
MAI_URL = "https://<your-mai-resource>.services.ai.azure.com/mai/v1/images/generations"

# GPT endpoint — source: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e
GPT_URL = "https://<your-openai-resource>.openai.azure.com/openai/deployments/<your-gpt-deployment>/images/generations?api-version=2025-04-01-preview"
GPT_API_KEY = "<your-api-key>"

# Output
OUT_BASE = Path(__file__).parent.parent / "5way-benchmark"
RESULTS_JSON = OUT_BASE / "5way_benchmark_results.json"

# 5 groups
GROUPS = [
    {"id": "mai-image-2",         "type": "mai", "model": "MAI-Image-2",  "quality": None},
    {"id": "mai-image-2e",        "type": "mai", "model": "MAI-Image-2e", "quality": None},
    {"id": "gpt-image-1.5-low",   "type": "gpt", "model": None,          "quality": "low"},
    {"id": "gpt-image-1.5-medium","type": "gpt", "model": None,          "quality": "medium"},
    {"id": "gpt-image-1.5-high",  "type": "gpt", "model": None,          "quality": "high"},
]

INTER_CALL_WAIT = 5  # seconds between each API call (symmetric)


def get_entra_token():
    """Get Entra ID token for MAI endpoint."""
    if sys.platform == "win32":
        result = subprocess.run(
            ['cmd', '/c', 'az', 'account', 'get-access-token',
             '--resource', 'https://cognitiveservices.azure.com',
             '--query', 'accessToken', '-o', 'tsv'],
            capture_output=True, text=True, timeout=30
        )
    else:
        result = subprocess.run(
            ['az', 'account', 'get-access-token',
             '--resource', 'https://cognitiveservices.azure.com',
             '--query', 'accessToken', '-o', 'tsv'],
            capture_output=True, text=True, timeout=30
        )
    return result.stdout.strip()


def generate_mai(model_name, prompt, token, max_retries=3):
    """
    Call MAI image generation API.
    Source: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai
    Only 4 params: model, prompt, width, height. No quality/style/n.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "model": model_name,
        "prompt": prompt,
        "width": 1024,
        "height": 1024,
    }

    for attempt in range(max_retries):
        try:
            start = time.time()
            r = requests.post(MAI_URL, headers=headers, json=payload, timeout=180)
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json().get("data", [])
                if data and "b64_json" in data[0]:
                    img = base64.b64decode(data[0]["b64_json"])
                    return True, elapsed, img
            elif r.status_code == 429:
                retry_after = int(r.headers.get("retry-after", "65"))
                print(f"      429 RATE LIMITED (retry-after: {retry_after}s)", flush=True)
                time.sleep(min(retry_after + 5, 75))
                continue
            else:
                print(f"      FAIL {r.status_code}: {r.text[:200]}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue
        except Exception as e:
            print(f"      ERROR: {e}", flush=True)
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
    return False, 0, None


def generate_gpt(prompt, quality, max_retries=3):
    """
    Call GPT-Image-1.5 API.
    Source: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e
    Params: prompt, n, size, quality.
    """
    headers = {
        "Content-Type": "application/json",
        "api-key": GPT_API_KEY,
    }
    payload = {
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "quality": quality,
    }

    for attempt in range(max_retries):
        try:
            start = time.time()
            r = requests.post(GPT_URL, headers=headers, json=payload, timeout=300)
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json().get("data", [])
                if data and "b64_json" in data[0]:
                    img = base64.b64decode(data[0]["b64_json"])
                    return True, elapsed, img
            elif r.status_code == 429:
                retry_after = int(r.headers.get("retry-after", "60"))
                print(f"      429 RATE LIMITED (retry-after: {retry_after}s)", flush=True)
                time.sleep(min(retry_after + 5, 70))
                continue
            else:
                print(f"      FAIL {r.status_code}: {r.text[:200]}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(10)
                    continue
        except Exception as e:
            print(f"      ERROR: {e}", flush=True)
            if attempt < max_retries - 1:
                time.sleep(10)
                continue
    return False, 0, None


def call_group(group, prompt, token, out_dir, filename):
    """Call the appropriate API based on group type."""
    if group["type"] == "mai":
        ok, elapsed, img = generate_mai(group["model"], prompt, token)
    else:
        ok, elapsed, img = generate_gpt(prompt, group["quality"])

    size_bytes = 0
    if ok and img:
        out_path = out_dir / filename
        out_path.write_bytes(img)
        size_bytes = len(img)

    return ok, elapsed, size_bytes


def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 75, flush=True)
    print("5-Way Image Generation Benchmark", flush=True)
    print(f"Date: {timestamp}", flush=True)
    print(f"Groups: {len(GROUPS)} | Prompts: 11 | Rounds: 2", flush=True)
    print(f"MAI endpoint: {MAI_URL}", flush=True)
    print(f"GPT endpoint: {GPT_URL.split('?')[0]}", flush=True)
    print(f"Inter-call wait: {INTER_CALL_WAIT}s (symmetric)", flush=True)
    print("=" * 75, flush=True)

    # Load prompts
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        prompts = [row[0].strip() for row in reader if row and row[0].strip()]
    print(f"Loaded {len(prompts)} prompts", flush=True)

    # Create output dirs
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    group_dirs = {}
    for g in GROUPS:
        d = OUT_BASE / g["id"]
        d.mkdir(parents=True, exist_ok=True)
        group_dirs[g["id"]] = d

    token = get_entra_token()
    print(f"Entra token acquired", flush=True)

    # === WARMUP ===
    print("\n--- WARMUP (5 groups × 1 request, results discarded) ---", flush=True)
    warmup_prompt = "A simple blue circle on white background"
    for g in GROUPS:
        print(f"  Warmup: {g['id']}...", end="", flush=True)
        ok, t, _ = call_group(g, warmup_prompt, token, OUT_BASE, "warmup.png")
        print(f" {'OK' if ok else 'FAIL'} {t:.1f}s", flush=True)
        time.sleep(INTER_CALL_WAIT)
    print("--- WARMUP COMPLETE ---\n", flush=True)

    # === BENCHMARK ===
    all_data = []

    for round_num in range(1, 3):
        print(f"\n{'='*75}", flush=True)
        print(f"ROUND {round_num}/2", flush=True)
        print(f"{'='*75}", flush=True)

        # Reverse group order in round 2
        round_groups = GROUPS if round_num == 1 else list(reversed(GROUPS))
        order_label = "A→E" if round_num == 1 else "E→A"
        print(f"Group order: {order_label}", flush=True)

        for i, prompt in enumerate(prompts):
            short = prompt[:55] + ("..." if len(prompt) > 55 else "")
            print(f"\n  R{round_num}[{i+1}/{len(prompts)}] {short}", flush=True)

            fname = f"{i+1:02d}_test.png"

            for g in round_groups:
                gid = g["id"]
                print(f"    {gid}...", end="", flush=True)
                ok, elapsed, size_bytes = call_group(g, prompt, token, group_dirs[gid], fname)
                status = f"OK {elapsed:.1f}s {size_bytes/1024:.0f}KB" if ok else "FAIL"
                print(f" {status}", flush=True)

                all_data.append({
                    "round": round_num,
                    "prompt_idx": i + 1,
                    "prompt_short": short,
                    "group": gid,
                    "group_type": g["type"],
                    "quality": g.get("quality"),
                    "ok": ok,
                    "time": elapsed,
                    "size_bytes": size_bytes,
                })

                time.sleep(INTER_CALL_WAIT)

            # Refresh token every 3 prompts
            if (i + 1) % 3 == 0:
                token = get_entra_token()
                print(f"    Token refreshed", flush=True)

        token = get_entra_token()
        print(f"\n  Token refreshed for next round", flush=True)

    # === SUMMARY ===
    print(f"\n{'='*75}", flush=True)
    print("5-WAY BENCHMARK RESULTS", flush=True)
    print(f"{'='*75}", flush=True)

    # Per-group stats
    group_stats = {}
    for g in GROUPS:
        gid = g["id"]
        entries = [d for d in all_data if d["group"] == gid and d["ok"]]
        if entries:
            times = [d["time"] for d in entries]
            avg_t = sum(times) / len(times)
            std_t = math.sqrt(sum((x - avg_t)**2 for x in times) / len(times)) if len(times) > 1 else 0
            sizes = [d["size_bytes"] for d in entries]
            avg_sz = sum(sizes) / len(sizes)
            group_stats[gid] = {"avg": avg_t, "std": std_t, "avg_size": avg_sz, "n": len(entries), "pass": len(entries)}
        else:
            group_stats[gid] = {"avg": 0, "std": 0, "avg_size": 0, "n": 0, "pass": 0}

    print(f"\n{'Group':<28} {'Avg Time':>10} {'σ':>6} {'Avg Size':>10} {'Pass':>6}", flush=True)
    print("-" * 65, flush=True)
    for g in GROUPS:
        gid = g["id"]
        s = group_stats[gid]
        total = len([d for d in all_data if d["group"] == gid])
        print(f"{gid:<28} {s['avg']:>9.1f}s {s['std']:>5.1f} {s['avg_size']/1024:>9.0f}KB {s['pass']}/{total}", flush=True)

    # Per-prompt comparison
    print(f"\n{'#':>3} {'Prompt':<22} ", end="", flush=True)
    for g in GROUPS:
        print(f" {g['id'][:10]:>10}", end="", flush=True)
    print(flush=True)
    print("-" * 80, flush=True)

    for pidx in range(1, len(prompts) + 1):
        short_p = prompts[pidx-1][:19] + "..." if len(prompts[pidx-1]) > 19 else prompts[pidx-1]
        print(f"{pidx:>3} {short_p:<22} ", end="", flush=True)
        for g in GROUPS:
            entries = [d for d in all_data if d["group"] == g["id"] and d["prompt_idx"] == pidx and d["ok"]]
            if entries:
                avg = sum(d["time"] for d in entries) / len(entries)
                print(f" {avg:>9.1f}s", end="", flush=True)
            else:
                print(f" {'FAIL':>10}", end="", flush=True)
        print(flush=True)

    # Save results
    results = {
        "timestamp": timestamp,
        "config": {
            "groups": [g["id"] for g in GROUPS],
            "prompts": len(prompts),
            "rounds": 2,
            "resolution": "1024x1024",
            "inter_call_wait": INTER_CALL_WAIT,
            "warmup": True,
            "fairness": "warmup + reversed order in R2 + symmetric wait",
            "mai_api_source": "https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai",
            "gpt_api_source": "https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e",
        },
        "group_summary": group_stats,
        "raw_data": all_data,
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved: {RESULTS_JSON}", flush=True)
    print("BENCHMARK COMPLETE", flush=True)


if __name__ == "__main__":
    main()
