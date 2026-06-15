"""
5-Way Benchmark V2: Latency + Token Usage + Cost Analysis
Author: Xinyu Wei (魏新宇)
Date: 2026-04-19

Changes from V1:
  - Records token usage from API responses (MAI: num_output_tokens, GPT: usage.*)
  - Saves images per round (r1/ and r2/ subdirectories, no overwrite)
  - Calculates per-image cost

API Sources:
  MAI: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python
  GPT: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e
"""
import csv, json, base64, time, subprocess, sys, math, requests
from pathlib import Path
from datetime import datetime

CSV_PATH = Path(__file__).parent.parent / "微软2个接口测试(Surreal).csv"

# MAI endpoint — source: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai
MAI_URL = "https://<your-mai-resource>.services.ai.azure.com/mai/v1/images/generations"

# GPT endpoint — source: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e
GPT_URL = "https://<your-openai-resource>.openai.azure.com/openai/deployments/<your-gpt-deployment>/images/generations?api-version=2025-04-01-preview"
GPT_API_KEY = "<your-api-key>"

OUT_BASE = Path(__file__).parent.parent / "5way-benchmark-v2"
RESULTS_JSON = OUT_BASE / "5way_v2_results.json"

GROUPS = [
    {"id": "mai-image-2",         "type": "mai", "model": "MAI-Image-2",  "quality": None,     "price_out": 33.0},
    {"id": "mai-image-2e",        "type": "mai", "model": "MAI-Image-2e", "quality": None,     "price_out": 19.5},
    {"id": "gpt-image-1.5-low",   "type": "gpt", "model": None,          "quality": "low",    "price_out": 32.0},
    {"id": "gpt-image-1.5-medium","type": "gpt", "model": None,          "quality": "medium", "price_out": 32.0},
    {"id": "gpt-image-1.5-high",  "type": "gpt", "model": None,          "quality": "high",   "price_out": 32.0},
]
INTER_CALL_WAIT = 5

def get_entra_token():
    if sys.platform == "win32":
        r = subprocess.run(['cmd','/c','az','account','get-access-token','--resource','https://cognitiveservices.azure.com','--query','accessToken','-o','tsv'], capture_output=True, text=True, timeout=30)
    else:
        r = subprocess.run(['az','account','get-access-token','--resource','https://cognitiveservices.azure.com','--query','accessToken','-o','tsv'], capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

def generate_mai(model_name, prompt, token, max_retries=3):
    """MAI API — only 4 params: model, prompt, width, height
    Source: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai"""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"model": model_name, "prompt": prompt, "width": 1024, "height": 1024}
    for attempt in range(max_retries):
        try:
            start = time.time()
            r = requests.post(MAI_URL, headers=headers, json=payload, timeout=180)
            elapsed = time.time() - start
            if r.status_code == 200:
                result = r.json()
                data = result.get("data", [])
                if data and "b64_json" in data[0]:
                    img = base64.b64decode(data[0]["b64_json"])
                    token_info = {"num_output_tokens": result.get("num_output_tokens")}
                    return True, elapsed, img, token_info
            elif r.status_code == 429:
                time.sleep(min(int(r.headers.get("retry-after", "65")) + 5, 75)); continue
            else:
                print(f"      FAIL {r.status_code}: {r.text[:200]}", flush=True)
                if attempt < max_retries - 1: time.sleep(10); continue
        except Exception as e:
            print(f"      ERROR: {e}", flush=True)
            if attempt < max_retries - 1: time.sleep(10); continue
    return False, 0, None, {}

def generate_gpt(prompt, quality, max_retries=3):
    """GPT API — source: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e"""
    headers = {"Content-Type": "application/json", "api-key": GPT_API_KEY}
    payload = {"prompt": prompt, "n": 1, "size": "1024x1024", "quality": quality}
    for attempt in range(max_retries):
        try:
            start = time.time()
            r = requests.post(GPT_URL, headers=headers, json=payload, timeout=300)
            elapsed = time.time() - start
            if r.status_code == 200:
                result = r.json()
                data = result.get("data", [])
                if data and "b64_json" in data[0]:
                    img = base64.b64decode(data[0]["b64_json"])
                    usage = result.get("usage", {})
                    token_info = {
                        "input_tokens": usage.get("input_tokens"),
                        "output_tokens": usage.get("output_tokens"),
                        "output_image_tokens": usage.get("output_tokens_details", {}).get("image_tokens"),
                        "output_text_tokens": usage.get("output_tokens_details", {}).get("text_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                    }
                    return True, elapsed, img, token_info
            elif r.status_code == 429:
                time.sleep(min(int(r.headers.get("retry-after", "60")) + 5, 70)); continue
            else:
                print(f"      FAIL {r.status_code}: {r.text[:200]}", flush=True)
                if attempt < max_retries - 1: time.sleep(10); continue
        except Exception as e:
            print(f"      ERROR: {e}", flush=True)
            if attempt < max_retries - 1: time.sleep(10); continue
    return False, 0, None, {}

def call_group(group, prompt, token):
    if group["type"] == "mai":
        return generate_mai(group["model"], prompt, token)
    else:
        return generate_gpt(prompt, group["quality"])

def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 75, flush=True)
    print("5-Way Benchmark V2 (Latency + Tokens + Cost)", flush=True)
    print(f"Date: {ts}", flush=True)
    print(f"Groups: {len(GROUPS)} | Prompts: 11 | Rounds: 2", flush=True)
    print("=" * 75, flush=True)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f); next(reader)
        prompts = [row[0].strip() for row in reader if row and row[0].strip()]
    print(f"Loaded {len(prompts)} prompts", flush=True)

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    # Create per-group per-round dirs
    for g in GROUPS:
        for rnd in ["r1", "r2"]:
            (OUT_BASE / g["id"] / rnd).mkdir(parents=True, exist_ok=True)

    token = get_entra_token()
    print(f"Token acquired", flush=True)

    # WARMUP
    print("\n--- WARMUP ---", flush=True)
    for g in GROUPS:
        print(f"  {g['id']}...", end="", flush=True)
        ok, t, _, ti = call_group(g, "blue circle", token)
        print(f" {'OK' if ok else 'FAIL'} {t:.1f}s", flush=True)
        time.sleep(INTER_CALL_WAIT)
    print("--- WARMUP DONE ---\n", flush=True)

    all_data = []
    for round_num in range(1, 3):
        rnd_label = f"r{round_num}"
        round_groups = GROUPS if round_num == 1 else list(reversed(GROUPS))
        print(f"\n{'='*75}\nROUND {round_num}/2 ({'A→E' if round_num==1 else 'E→A'})\n{'='*75}", flush=True)

        for i, prompt in enumerate(prompts):
            short = prompt[:55] + ("..." if len(prompt) > 55 else "")
            print(f"\n  R{round_num}[{i+1}/{len(prompts)}] {short}", flush=True)
            fname = f"{i+1:02d}_test.png"

            for g in round_groups:
                gid = g["id"]
                print(f"    {gid}...", end="", flush=True)
                ok, elapsed, img, token_info = call_group(g, prompt, token)
                size_bytes = 0
                if ok and img:
                    out_path = OUT_BASE / gid / rnd_label / fname
                    out_path.write_bytes(img)
                    size_bytes = len(img)

                # Calculate cost
                cost = None
                if g["type"] == "mai" and token_info.get("num_output_tokens"):
                    cost = token_info["num_output_tokens"] / 1_000_000 * g["price_out"]
                elif g["type"] == "gpt" and token_info.get("output_tokens"):
                    cost = token_info["output_tokens"] / 1_000_000 * g["price_out"]

                status = f"OK {elapsed:.1f}s {size_bytes/1024:.0f}KB"
                if token_info.get("output_tokens") or token_info.get("num_output_tokens"):
                    out_tok = token_info.get("output_tokens") or token_info.get("num_output_tokens")
                    status += f" tok={out_tok}"
                if cost is not None:
                    status += f" ${cost:.4f}"
                if not ok:
                    status = "FAIL"
                print(f" {status}", flush=True)

                all_data.append({
                    "round": round_num, "prompt_idx": i+1, "prompt_short": short,
                    "group": gid, "group_type": g["type"], "quality": g.get("quality"),
                    "ok": ok, "time": elapsed, "size_bytes": size_bytes,
                    "token_info": token_info, "cost_usd": cost,
                })
                time.sleep(INTER_CALL_WAIT)

            if (i+1) % 3 == 0:
                token = get_entra_token()
                print(f"    Token refreshed", flush=True)
        token = get_entra_token()

    # SUMMARY
    print(f"\n{'='*75}\nSUMMARY\n{'='*75}", flush=True)
    print(f"{'Group':<28} {'Latency':>8} {'OutTok':>8} {'Cost/img':>10} {'Pass':>6}", flush=True)
    print("-" * 65, flush=True)
    for g in GROUPS:
        entries = [d for d in all_data if d["group"]==g["id"] and d["ok"]]
        if entries:
            avg_t = sum(d["time"] for d in entries)/len(entries)
            costs = [d["cost_usd"] for d in entries if d["cost_usd"] is not None]
            avg_cost = sum(costs)/len(costs) if costs else None
            # output tokens
            if g["type"] == "gpt":
                toks = [d["token_info"].get("output_tokens",0) for d in entries if d["token_info"].get("output_tokens")]
            else:
                toks = [d["token_info"].get("num_output_tokens",0) for d in entries if d["token_info"].get("num_output_tokens")]
            avg_tok = sum(toks)/len(toks) if toks else None
            tok_str = f"{avg_tok:.0f}" if avg_tok else "N/A"
            cost_str = f"${avg_cost:.4f}" if avg_cost else "N/A"
            print(f"{g['id']:<28} {avg_t:>7.1f}s {tok_str:>8} {cost_str:>10} {len(entries)}/22", flush=True)

    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump({"timestamp": ts, "config": {"groups": [g["id"] for g in GROUPS], "rounds": 2, "resolution": "1024x1024", "inter_call_wait": INTER_CALL_WAIT}, "raw_data": all_data}, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {RESULTS_JSON}", flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
