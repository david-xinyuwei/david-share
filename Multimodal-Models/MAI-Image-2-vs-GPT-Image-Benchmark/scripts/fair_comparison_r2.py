"""
MAI-Image-2 vs GPT-Image-1.5 Fair Comparison Test (Round 2)
Author: Xinyu Wei (魏新宇)

Unified script - both models tested with IDENTICAL parameters:
  - Resolution: 1024x1024
  - Quality: high (explicitly set)
  - Response format: b64_json
  - Prompts: same 11 from CSV
"""
import csv
import json
import base64
import time
import subprocess
import requests
from pathlib import Path

# === Config ===
API_KEY = "<your-api-key>"
CSV_PATH = Path(__file__).parent.parent / "微软2个接口测试(Surreal).csv"

# GPT-Image-1.5
GPT_URL = "https://<your-resource-name>.openai.azure.com/openai/deployments/gpt-image-1-5/images/generations?api-version=2025-04-01-preview"
GPT_HEADERS = {"Content-Type": "application/json", "api-key": API_KEY}
GPT_OUT = Path(__file__).parent.parent / "GPT-Image-1.5-Test-Result" / "outputs_r2"
GPT_OUT.mkdir(parents=True, exist_ok=True)

# MAI-Image-2 (Entra auth)
MAI_URL = "https://<your-mai-resource>.services.ai.azure.com/mai/v1/images/generations"
MAI_OUT = Path(__file__).parent.parent / "MAI2-Test-Result" / "outputs_r2"
MAI_OUT.mkdir(parents=True, exist_ok=True)


def get_entra_token():
    return subprocess.check_output([
        'az', 'account', 'get-access-token',
        '--resource', 'https://cognitiveservices.azure.com',
        '--query', 'accessToken', '-o', 'tsv'
    ]).decode().strip()


def generate_gpt(prompt, filename):
    payload = {"prompt": prompt, "n": 1, "size": "1024x1024", "quality": "high"}
    try:
        start = time.time()
        r = requests.post(GPT_URL, headers=GPT_HEADERS, json=payload, timeout=300)
        elapsed = time.time() - start
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data and "b64_json" in data[0]:
                img = base64.b64decode(data[0]["b64_json"])
                (GPT_OUT / filename).write_bytes(img)
                return True, elapsed, len(img)
        elif r.status_code == 429:
            retry = r.headers.get("retry-after", "60")
            print(f"    GPT RATE LIMITED (retry-after: {retry}s)", flush=True)
            time.sleep(min(int(retry) + 5, 70))
            return generate_gpt(prompt, filename)
        else:
            print(f"    GPT FAIL {r.status_code}: {r.text[:150]}", flush=True)
    except Exception as e:
        print(f"    GPT ERROR: {e}", flush=True)
    return False, 0, 0


def generate_mai(prompt, filename, token):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"model": "MAI-Image-2", "prompt": prompt, "width": 1024, "height": 1024, "quality": "high"}
    try:
        start = time.time()
        r = requests.post(MAI_URL, headers=headers, json=payload, timeout=300)
        elapsed = time.time() - start
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data and "b64_json" in data[0]:
                img = base64.b64decode(data[0]["b64_json"])
                (MAI_OUT / filename).write_bytes(img)
                return True, elapsed, len(img)
        elif r.status_code == 429:
            print(f"    MAI RATE LIMITED", flush=True)
            time.sleep(65)
            return generate_mai(prompt, filename, token)
        else:
            print(f"    MAI FAIL {r.status_code}: {r.text[:150]}", flush=True)
    except Exception as e:
        print(f"    MAI ERROR: {e}", flush=True)
    return False, 0, 0


def main():
    print("=" * 70, flush=True)
    print("MAI-Image-2 vs GPT-Image-1.5 Fair Comparison (Round 2)", flush=True)
    print("Unified params: 1024x1024, quality=high, b64_json", flush=True)
    print("=" * 70, flush=True)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        prompts = [row[0].strip() for row in reader if row and row[0].strip()]

    print(f"Prompts: {len(prompts)}", flush=True)
    token = get_entra_token()
    print("Entra token acquired", flush=True)
    print("=" * 70, flush=True)

    mai_results = []
    gpt_results = []

    for i, prompt in enumerate(prompts):
        fname = f"{i+1:02d}_test.png"
        short = prompt[:70] + ("..." if len(prompt) > 70 else "")
        print(f"\n[{i+1}/{len(prompts)}] {short}", flush=True)

        # MAI first
        ok, t, sz = generate_mai(prompt, fname, token)
        mai_results.append((i+1, fname, ok, t, sz))
        print(f"  MAI: {'OK' if ok else 'FAIL'} {t:.1f}s {sz/1024:.0f}KB", flush=True)

        time.sleep(2)

        # GPT second
        ok, t, sz = generate_gpt(prompt, fname)
        gpt_results.append((i+1, fname, ok, t, sz))
        print(f"  GPT: {'OK' if ok else 'FAIL'} {t:.1f}s {sz/1024:.0f}KB", flush=True)

        time.sleep(2)

    # Summary
    print(flush=True)
    print("=" * 70, flush=True)
    print("RESULTS SUMMARY (quality=high, 1024x1024)", flush=True)
    print("=" * 70, flush=True)
    print(f"{'#':>3} {'Prompt':<25} {'MAI Time':>10} {'MAI KB':>8} {'GPT Time':>10} {'GPT KB':>8} {'Ratio':>7}", flush=True)
    print("-" * 70, flush=True)

    mai_total_t = gpt_total_t = 0
    mai_total_sz = gpt_total_sz = 0
    mai_pass = gpt_pass = 0

    for m, g in zip(mai_results, gpt_results):
        idx = m[0]
        short = prompts[idx-1][:22] + "..." if len(prompts[idx-1]) > 22 else prompts[idx-1]
        mt = m[3]; msz = m[4]/1024; gt = g[3]; gsz = g[4]/1024
        ratio = f"{gt/mt:.1f}x" if mt > 0 and gt > 0 else "N/A"
        print(f"{idx:>3} {short:<25} {mt:>9.1f}s {msz:>7.0f} {gt:>9.1f}s {gsz:>7.0f} {ratio:>7}", flush=True)
        if m[2]: mai_pass += 1; mai_total_t += mt; mai_total_sz += msz
        if g[2]: gpt_pass += 1; gpt_total_t += gt; gpt_total_sz += gsz

    print("-" * 70, flush=True)
    mai_avg = mai_total_t / mai_pass if mai_pass > 0 else 0
    gpt_avg = gpt_total_t / gpt_pass if gpt_pass > 0 else 0
    ratio = f"{gpt_avg/mai_avg:.1f}x" if mai_avg > 0 and gpt_avg > 0 else "N/A"
    print(f"AVG {'':25} {mai_avg:>9.1f}s {mai_total_sz/mai_pass:>7.0f} {gpt_avg:>9.1f}s {gpt_total_sz/gpt_pass:>7.0f} {ratio:>7}", flush=True)
    print(f"\nMAI: {mai_pass}/{len(mai_results)} passed | GPT: {gpt_pass}/{len(gpt_results)} passed", flush=True)


if __name__ == "__main__":
    main()
