"""
GPT-Image-1.5 vs MAI-Image-2 Fair Comparison Test
Author: Xinyu Wei (魏新宇)

Uses identical prompts from CSV to ensure fair comparison.
7-Dimension Alignment:
  1. Prompt: identical (from CSV)
  2. Resolution: 1024x1024
  3. Count: 11 prompts
  4. Network: same machine
  5. Time window: same day
  6. Response format: b64_json
  7. Model: the only variable (gpt-image-1.5)
"""
import csv
import json
import base64
import time
import requests
from pathlib import Path

# Configuration - gpt-image-1.5 uses standard Azure OpenAI API with Key Auth
API_KEY = "<your-api-key>"
RESOURCE_NAME = "<your-resource-name>"
DEPLOYMENT_NAME = "gpt-image-1-5"
API_VERSION = "2025-04-01-preview"

BASE_URL = f"https://{RESOURCE_NAME}.openai.azure.com"
API_PATH = f"/openai/deployments/{DEPLOYMENT_NAME}/images/generations"

OUTPUT_DIR = Path(__file__).parent.parent / "GPT-Image-1.5-Test-Result" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_PATH = Path(__file__).parent.parent / "微软2个接口测试(Surreal).csv"


def generate_image(prompt, filename, size="1024x1024"):
    """Call gpt-image-1.5 via Azure OpenAI images/generations API."""
    url = f"{BASE_URL}{API_PATH}?api-version={API_VERSION}"
    payload = {
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": "high",
    }
    headers = {
        "Content-Type": "application/json",
        "api-key": API_KEY,
    }

    short = prompt[:80] + ('...' if len(prompt) > 80 else '')
    print(f"\n  {short}", flush=True)

    try:
        start = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=300)
        elapsed = time.time() - start

        if response.status_code == 200:
            result = response.json()
            data_list = result.get("data", [])
            if data_list and "b64_json" in data_list[0]:
                img_bytes = base64.b64decode(data_list[0]["b64_json"])
                out_path = OUTPUT_DIR / filename
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                kb = len(img_bytes) / 1024
                print(f"  OK {elapsed:.1f}s {kb:.0f}KB -> {filename}", flush=True)
                return True, elapsed, len(img_bytes)
            elif data_list and "url" in data_list[0]:
                img_url = data_list[0]["url"]
                img_resp = requests.get(img_url, timeout=60)
                if img_resp.status_code == 200:
                    out_path = OUTPUT_DIR / filename
                    with open(out_path, "wb") as f:
                        f.write(img_resp.content)
                    kb = len(img_resp.content) / 1024
                    print(f"  OK {elapsed:.1f}s {kb:.0f}KB -> {filename}", flush=True)
                    return True, elapsed, len(img_resp.content)
            else:
                print(f"  Unexpected response: {json.dumps(result, indent=2)[:300]}", flush=True)
        elif response.status_code == 429:
            retry_after = response.headers.get("retry-after", "60")
            print(f"  RATE LIMITED (retry-after: {retry_after}s)", flush=True)
            return "rate_limited", elapsed, 0
        else:
            try:
                err = response.json()
                print(f"  FAIL {response.status_code}: {json.dumps(err)[:300]}", flush=True)
            except Exception:
                print(f"  FAIL {response.status_code}: {response.text[:300]}", flush=True)
    except requests.exceptions.Timeout:
        print("  TIMEOUT (300s)", flush=True)
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}", flush=True)

    return False, 0, 0


def main():
    print("=" * 60, flush=True)
    print("GPT-Image-1.5 Fair Comparison Test", flush=True)
    print(f"Endpoint: {BASE_URL}", flush=True)
    print(f"Deployment: {DEPLOYMENT_NAME}", flush=True)
    print(f"API Version: {API_VERSION}", flush=True)
    print(f"Auth: Key-based", flush=True)
    print(f"Resolution: 1024x1024", flush=True)
    print("=" * 60, flush=True)

    # Read prompts from CSV
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        prompts = [row[0].strip() for row in reader if row and row[0].strip()]

    print(f"\nTotal: {len(prompts)} prompts from CSV", flush=True)
    print("=" * 60, flush=True)

    results = []
    for i, prompt in enumerate(prompts):
        fname = f"{i+1:02d}_test.png"
        print(f"\n[{i+1}/{len(prompts)}]", flush=True)

        success, elapsed, size = generate_image(prompt, fname)

        if success == "rate_limited":
            wait = 65
            print(f"\n--- Waiting {wait}s for rate limit reset ---", flush=True)
            time.sleep(wait)
            success, elapsed, size = generate_image(prompt, fname)

        results.append((i + 1, fname, success, elapsed, size))
        time.sleep(2)  # brief pause between requests

    # Summary
    print(flush=True)
    print("=" * 60, flush=True)
    print("RESULTS SUMMARY", flush=True)
    print("=" * 60, flush=True)

    total_time = 0
    for idx, fname, ok, t, sz in results:
        if ok is True:
            status = f"PASS {t:.1f}s {sz/1024:.0f}KB"
            total_time += t
        else:
            status = f"FAIL {t:.1f}s"
        print(f"  [{status:>20}] #{idx} {fname}", flush=True)

    passed = sum(1 for _, _, ok, _, _ in results if ok is True)
    avg_time = total_time / passed if passed > 0 else 0
    print(f"\nTotal: {passed}/{len(results)} passed", flush=True)
    print(f"Avg latency: {avg_time:.1f}s", flush=True)
    print(f"Output dir: {OUTPUT_DIR}", flush=True)


if __name__ == "__main__":
    main()
