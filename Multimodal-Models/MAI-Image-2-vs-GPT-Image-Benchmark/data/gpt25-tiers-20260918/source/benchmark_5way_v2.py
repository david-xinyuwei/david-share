"""
5-Way Benchmark V2: Latency + Token Usage
Author: Xinyu Wei (魏新宇)
Date: 2026-04-19

Changes from V1:
  - Records token usage from API responses (MAI: num_output_tokens, GPT: usage.*)
  - Saves images per round (r1/ and r2/ subdirectories, no overwrite)

API Sources:
  MAI: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python
  GPT: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e
"""
import argparse
import hashlib
import os
import platform
import struct
import csv, json, base64, time, subprocess, sys, math, requests
from pathlib import Path
from datetime import datetime, timezone

CSV_PATH = Path(__file__).parent.parent / "prompts.csv"

# MAI endpoint — source: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai
MAI_URL = os.environ.get("MAI_ENDPOINT", "https://<your-mai-resource>.services.ai.azure.com").rstrip("/") + "/mai/v1/images/generations"
MAI_API_KEY = os.environ.get("AZURE_API_KEY")

# GPT endpoint — source: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e
GPT_ENDPOINT = os.environ.get("GPT_ENDPOINT", "https://<your-openai-resource>.openai.azure.com").rstrip("/")
GPT_DEPLOYMENT = os.environ.get("GPT_DEPLOYMENT", "<your-gpt-deployment>")
GPT_API_VERSION = os.environ.get("GPT_API_VERSION", "2025-04-01-preview")
GPT_URL = f"{GPT_ENDPOINT}/openai/deployments/{GPT_DEPLOYMENT}/images/generations?api-version={GPT_API_VERSION}"
GPT_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")


def gpt_url(deployment=None):
    """Per-deployment generations URL; a group without a model falls back to GPT_DEPLOYMENT."""
    return f"{GPT_ENDPOINT}/openai/deployments/{deployment or GPT_DEPLOYMENT}/images/generations?api-version={GPT_API_VERSION}"

OUT_BASE = Path(__file__).parent.parent / "5way-benchmark-v2"
RESULTS_JSON = OUT_BASE / "5way_v2_results.json"

GROUPS = [
    {"id": "mai-image-2",         "type": "mai", "model": "MAI-Image-2",  "quality": None},
    {"id": "mai-image-2e",        "type": "mai", "model": "MAI-Image-2e", "quality": None},
    {"id": "gpt-image-1.5-low",   "type": "gpt", "model": None,          "quality": "low"},
    {"id": "gpt-image-1.5-medium","type": "gpt", "model": None,          "quality": "medium"},
    {"id": "gpt-image-1.5-high",  "type": "gpt", "model": None,          "quality": "high"},
]
QUALITY_ALIASES = {
    # Pinned to the three tiers gpt-image-2 supports; published archives reproduce with this token,
    # so its meaning must not widen when a newer model adds tiers.
    "all": ("low", "medium", "high"),
    # gpt-image-2.5-flare / -sunburst additionally accept these three (verified 2026-09-18).
    "all25": ("low", "medium", "high", "xhigh", "max", "auto"),
}
# Single source for both the actual call and the recorded configuration, so the archived metadata
# cannot drift from what the client really allowed.
MAI_REQUEST_TIMEOUT = 180
GPT_REQUEST_TIMEOUT = 900


def model_version_for(prefix, deployment):
    """Model version for one deployment.

    A run may interleave deployments of different vintages behind a single credential prefix
    (gpt-image-2 is 2026-04-21 while gpt-image-2.5-* is 2026-09-08), so a per-deployment map
    takes precedence over the single-value variable used when a run has one deployment.
    """
    overrides = os.environ.get(prefix + "_MODEL_VERSIONS")
    if overrides and deployment:
        try:
            mapped = json.loads(overrides).get(deployment)
        except json.JSONDecodeError:
            mapped = None
        if mapped:
            return mapped
    return os.environ.get(prefix + "_MODEL_VERSION")


INTER_CALL_WAIT = 5
# Every deployment used here is provisioned at 2 requests/minute; fast models would otherwise
# trip the client's own quota on the third consecutive tier and record a 429 that says nothing
# about the service.
RATE_PACING = {"max_requests": 2, "window_seconds": 60}
PACING_HISTORY = {}
LAST_PACING_WAIT = 0.0
REQUEST_CONTEXT = {}
LAST_ATTEMPTS = []
RUN_RECORD = {}
RESUME = False
WARMUP_ONLY = False


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def checkpoint(state):
    RUN_RECORD["state"] = state
    RUN_RECORD["updated_at_utc"] = utc_now()
    RUN_RECORD["process_id"] = os.getpid()
    write_json(RESULTS_JSON, RUN_RECORD)


def record_attempt(record):
    LAST_ATTEMPTS.append(record)
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    with (OUT_BASE / "attempts.jsonl").open("a", encoding="utf-8") as attempt_file:
        attempt_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        attempt_file.flush()


def safe_error(error):
    message = str(error)
    for key in (MAI_API_KEY, GPT_API_KEY):
        if key:
            message = message.replace(key, "[redacted]")
    from urllib.parse import urlsplit
    for url in (MAI_URL, GPT_URL):
        hostname = urlsplit(url).hostname
        if hostname:
            message = message.replace(hostname, "[resource]")
    return message

def get_entra_token():
    if MAI_API_KEY or all(group["type"] == "gpt" for group in GROUPS):
        return None
    if sys.platform == "win32":
        r = subprocess.run(['cmd','/c','az','account','get-access-token','--resource','https://cognitiveservices.azure.com','--query','accessToken','-o','tsv'], capture_output=True, text=True, timeout=30)
    else:
        r = subprocess.run(['az','account','get-access-token','--resource','https://cognitiveservices.azure.com','--query','accessToken','-o','tsv'], capture_output=True, text=True, timeout=30)
    return r.stdout.strip()

def archive_image_response(result, sample_id, attempt):
    data = result.get("data", [])
    if len(data) != 1 or "b64_json" not in data[0]:
        raise ValueError("HTTP 200 response did not contain exactly one base64 image")
    image = base64.b64decode(data[0]["b64_json"], validate=True)
    if image[:8] != b"\x89PNG\r\n\x1a\n" or len(image) < 24:
        raise ValueError("Response is not a valid PNG header")
    dimensions = struct.unpack(">II", image[16:24])
    if dimensions != (1024, 1024):
        raise ValueError(f"Unexpected image dimensions: {dimensions}")
    metadata = {key: value for key, value in result.items() if key != "data"}
    metadata["data"] = [{key: value for key, value in item.items() if key != "b64_json"}
                        for item in data]
    metadata["archival_note"] = "b64_json omitted; decoded image is archived separately."
    response_name = f"{sample_id}-a{attempt}.json"
    write_json(OUT_BASE / "responses" / response_name, metadata)
    return image, {"ok": True, "image_sha256": hashlib.sha256(image).hexdigest(),
                   "image_bytes": len(image), "width": dimensions[0], "height": dimensions[1],
                   "response_metadata": "responses/" + response_name}

def generate_mai(model_name, prompt, token, max_retries=3, *, web_grounding=None):
    """Generate an MAI image, optionally controlling web grounding at fixed aspect ratio."""
    headers = {"Content-Type": "application/json"}
    if MAI_API_KEY:
        headers["api-key"] = MAI_API_KEY
    else:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"model": model_name, "prompt": prompt, "width": 1024, "height": 1024}
    if web_grounding is not None:
        if not isinstance(web_grounding, bool):
            raise ValueError("web_grounding must be a boolean or omitted")
        payload.update({"web_grounding": web_grounding, "auto_aspect_ratio": False})
    LAST_ATTEMPTS.clear()
    for attempt in range(max_retries):
        attempt_record = {**REQUEST_CONTEXT, "attempt": attempt + 1, "started_at_utc": utc_now(),
                          "request": payload, "ok": False}
        try:
            start = time.time()
            r = requests.post(MAI_URL, headers=headers, json=payload, timeout=MAI_REQUEST_TIMEOUT)
            elapsed = time.time() - start
            attempt_record.update({"http_status": r.status_code, "request_seconds": elapsed,
                                   "response_received_at_utc": utc_now(),
                                   "response_body_sha256": hashlib.sha256(r.content).hexdigest(),
                                   "headers": {name: r.headers[name] for name in
                                               ("apim-request-id", "x-request-id", "x-ms-request-id",
                                                "date", "retry-after", "x-ratelimit-remaining-requests")
                                               if name in r.headers}})
            if r.status_code == 200:
                result = r.json()
                img, image_record = archive_image_response(
                    result, REQUEST_CONTEXT.get("sample_id", model_name), attempt + 1)
                attempt_record.update(image_record)
                token_info = {"num_output_tokens": result.get("num_output_tokens"),
                              "usage": result.get("usage")}
                return True, elapsed, img, token_info
            elif r.status_code == 429:
                wait_seconds = min(int(r.headers.get("retry-after", "65")) + 5, 75)
                attempt_record["retry_wait_seconds"] = wait_seconds
                print(f"      HTTP 429; waiting {wait_seconds}s", flush=True)
                time.sleep(wait_seconds); continue
            else:
                attempt_record["error"] = safe_error(r.text)[:2000]
                print(f"      FAIL {r.status_code}: {safe_error(r.text)[:200]}", flush=True)
                if attempt < max_retries - 1: time.sleep(10); continue
        except Exception as e:
            attempt_record["error"] = type(e).__name__
            attempt_record["exception_type"] = type(e).__name__
            attempt_record.setdefault("request_seconds", time.time() - start)
            print(f"      ERROR: {type(e).__name__}", flush=True)
            if attempt < max_retries - 1: time.sleep(10); continue
        finally:
            attempt_record["finished_at_utc"] = utc_now()
            record_attempt(attempt_record)
    return False, 0, None, {}

def generate_gpt(prompt, quality, deployment=None, max_retries=3):
    """GPT API — source: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e"""
    headers = {"Content-Type": "application/json", "api-key": GPT_API_KEY}
    payload = {"prompt": prompt, "n": 1, "size": "1024x1024", "quality": quality}
    url = gpt_url(deployment)
    LAST_ATTEMPTS.clear()
    for attempt in range(max_retries):
        attempt_record = {**REQUEST_CONTEXT, "attempt": attempt + 1, "started_at_utc": utc_now(),
                          "request": payload, "ok": False}
        try:
            start = time.time()
            # gpt-image-2.5-sunburst at quality=max measured 229s on a single request,
            # so the ceiling is well above the 300s that sufficed for low/medium/high.
            r = requests.post(url, headers=headers, json=payload, timeout=GPT_REQUEST_TIMEOUT)
            elapsed = time.time() - start
            attempt_record.update({"http_status": r.status_code, "request_seconds": elapsed,
                                   "response_received_at_utc": utc_now(),
                                   "response_body_sha256": hashlib.sha256(r.content).hexdigest(),
                                   "headers": {name: r.headers[name] for name in
                                               ("apim-request-id", "x-request-id", "x-ms-request-id",
                                                "date", "retry-after", "x-ratelimit-remaining-requests")
                                               if name in r.headers}})
            if r.status_code == 200:
                result = r.json()
                img, image_record = archive_image_response(
                    result, REQUEST_CONTEXT.get("sample_id", "gpt-" + quality), attempt + 1)
                attempt_record.update(image_record)
                usage = result.get("usage") or {}
                # quality=auto lets the service pick a tier per request, and it echoes the tier it
                # actually used. Without this the auto group's latency/token numbers are unreadable.
                service_quality = result.get("quality")
                attempt_record["service_quality"] = service_quality
                token_info = {
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "output_image_tokens": usage.get("output_tokens_details", {}).get("image_tokens"),
                    "output_text_tokens": usage.get("output_tokens_details", {}).get("text_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "usage": usage,
                    "requested_quality": quality,
                    "service_quality": service_quality,
                }
                return True, elapsed, img, token_info
            elif r.status_code == 429:
                wait_seconds = min(int(r.headers.get("retry-after", "60")) + 5, 70)
                attempt_record["retry_wait_seconds"] = wait_seconds
                print(f"      HTTP 429; waiting {wait_seconds}s", flush=True)
                time.sleep(wait_seconds); continue
            else:
                attempt_record["error"] = safe_error(r.text)[:2000]
                print(f"      FAIL {r.status_code}: {safe_error(r.text)[:200]}", flush=True)
                if attempt < max_retries - 1: time.sleep(10); continue
        except Exception as e:
            attempt_record["error"] = type(e).__name__
            attempt_record["exception_type"] = type(e).__name__
            attempt_record.setdefault("request_seconds", time.time() - start)
            print(f"      ERROR: {type(e).__name__}", flush=True)
            if attempt < max_retries - 1: time.sleep(10); continue
        finally:
            attempt_record["finished_at_utc"] = utc_now()
            record_attempt(attempt_record)
    return False, 0, None, {}

def pace(group):
    """Sleep just long enough to stay within RATE_PACING for this group's deployment; returns seconds waited."""
    global LAST_PACING_WAIT
    key = ("mai:" + str(group["model"])) if group["type"] == "mai" else ("gpt:" + str(group.get("model") or GPT_DEPLOYMENT))
    history = PACING_HISTORY.setdefault(key, [])
    now = time.monotonic()
    history[:] = [started for started in history if now - started < RATE_PACING["window_seconds"]]
    waited = 0.0
    if len(history) >= RATE_PACING["max_requests"]:
        waited = RATE_PACING["window_seconds"] - (now - history[0]) + 1.0
        print(f" pacing {waited:.0f}s", end="", flush=True)
        time.sleep(waited)
    history.append(time.monotonic())
    LAST_PACING_WAIT = waited
    return waited


def call_group(group, prompt, token):
    if group["type"] == "mai":
        return generate_mai(group["model"], prompt, token, web_grounding=group.get("web_grounding"))
    else:
        return generate_gpt(prompt, group["quality"], group.get("model"))

def main():
    if any(group["type"] == "mai" for group in GROUPS) and ("<" in MAI_URL or not MAI_URL.startswith("https://")):
        raise SystemExit("Set MAI_ENDPOINT to the resource origin before running.")
    if any(group["type"] == "gpt" for group in GROUPS):
        if "<" in GPT_ENDPOINT or not GPT_ENDPOINT.startswith("https://") or not GPT_API_KEY:
            raise SystemExit("Set GPT_ENDPOINT and AZURE_OPENAI_API_KEY before running.")
        if any(group["type"] == "gpt" and "<" in (group.get("model") or GPT_DEPLOYMENT) for group in GROUPS):
            raise SystemExit("Set GPT_DEPLOYMENT or pass --gpt-model before running.")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 75, flush=True)
    print("Image Benchmark (Latency + Tokens)", flush=True)
    print(f"Date: {ts}", flush=True)
    print(f"Groups: {len(GROUPS)} | Rounds: 2", flush=True)
    print("=" * 75, flush=True)

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f); next(reader)
        prompts = [row[0].strip() for row in reader if row and row[0].strip()]
    print(f"Loaded {len(prompts)} prompts", flush=True)

    OUT_BASE.mkdir(parents=True, exist_ok=True)
    group_configs = []
    for group in GROUPS:
        prefix = "MAI" if group["type"] == "mai" else "GPT"
        group_configs.append({
            "id": group["id"], "provider": group["type"], "model": group["model"],
            "quality": group["quality"],
            "model_version": model_version_for(prefix, group["model"]),
            "deployment_sku": os.environ.get(prefix + "_DEPLOYMENT_SKU"),
            "deployment_region": os.environ.get(prefix + "_DEPLOYMENT_REGION"),
            "request_rate_limit_per_minute": os.environ.get(prefix + "_RATE_LIMIT_RPM"),
            "auth": "api-key" if group["type"] == "gpt" or MAI_API_KEY else "Entra ID",
            "request_timeout_seconds": MAI_REQUEST_TIMEOUT if group["type"] == "mai" else GPT_REQUEST_TIMEOUT,
            "api_version": GPT_API_VERSION if group["type"] == "gpt" else None,
            "endpoint_fingerprint": hashlib.sha256(
                (MAI_URL if group["type"] == "mai" else gpt_url(group.get("model"))).encode("utf-8")).hexdigest(),
        })
        if "web_grounding" in group:
            group_configs[-1].update({"web_grounding": group["web_grounding"], "auto_aspect_ratio": False})
    config = {"groups": [group["id"] for group in GROUPS], "rounds": 2,
              "resolution": "1024x1024", "inter_call_wait": INTER_CALL_WAIT,
              "rate_pacing": dict(RATE_PACING),
              "prompts_sha256": hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(),
              "formal_sample_count": len(prompts) * len(GROUPS) * 2,
              "group_configurations": group_configs,
              "concurrency": 1, "max_attempts_per_sample": 3,
              "round_order": {"1": [group["id"] for group in GROUPS],
                              "2": [group["id"] for group in reversed(GROUPS)]},
              "latency_definition": "Successful requests.post duration, before JSON decode and file write.",
              "client_location": os.environ.get("BENCHMARK_CLIENT_LOCATION", "not recorded")}
    if RESULTS_JSON.exists():
        if not RESUME:
            raise SystemExit("Output already exists. Use --resume to continue without replacing results.")
        previous_run = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
        if previous_run["config"] != config:
            raise SystemExit("Resume configuration differs from the saved run.")
        if previous_run["script_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
            raise SystemExit("Resume script differs from the frozen run.")
        if previous_run["state"] == "COMPLETED":
            print("Run already complete; no API calls were made.", flush=True)
            return
        RUN_RECORD.update(previous_run)
        ts = RUN_RECORD["timestamp"]
    else:
        RUN_RECORD.update({"timestamp": ts, "started_at_utc": utc_now(), "config": config,
                           "environment": {"python": platform.python_version(), "platform": platform.platform(),
                                           "architecture": platform.machine(), "requests": requests.__version__},
                           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           "warmup": [], "raw_data": []})
    checkpoint("STARTING")
    # Create per-group per-round dirs
    for g in GROUPS:
        for rnd in ["r1", "r2"]:
            (OUT_BASE / g["id"] / rnd).mkdir(parents=True, exist_ok=True)

    token = get_entra_token()
    print("Authentication configured", flush=True)

    # WARMUP
    print("\n--- WARMUP ---", flush=True)
    for g in GROUPS:
        if any(item["group"] == g["id"] and item["ok"] for item in RUN_RECORD["warmup"]):
            continue
        REQUEST_CONTEXT.clear()
        REQUEST_CONTEXT.update({"sample_id": "warmup-" + g["id"], "phase": "warmup", "group": g["id"]})
        checkpoint("WARMUP")
        print(f"  {g['id']}...", end="", flush=True)
        pace(g)
        ok, t, warmup_image, ti = call_group(g, "blue circle", token)
        if ok and warmup_image:
            (OUT_BASE / ("warmup-" + g["id"] + ".png")).write_bytes(warmup_image)
        RUN_RECORD["warmup"].append({"group": g["id"], "ok": ok, "time": t, "token_info": ti,
                                     "attempt_count": len(LAST_ATTEMPTS), "ended_at_utc": utc_now()})
        checkpoint("WARMUP_PASSED" if ok else "WARMUP_FAILED")
        print(f" {'OK' if ok else 'FAIL'} {t:.1f}s", flush=True)
        if not ok:
            raise SystemExit("Warmup failed; formal samples were not started.")
        time.sleep(INTER_CALL_WAIT)
    print("--- WARMUP DONE ---\n", flush=True)
    if WARMUP_ONLY:
        checkpoint("WARMUP_PASSED")
        print("Warmup complete; resume without --warmup-only for the formal matrix.", flush=True)
        return

    all_data = RUN_RECORD["raw_data"]
    completed_samples = {(item["round"], item["prompt_idx"], item["group"]) for item in all_data}
    for round_num in range(1, 3):
        rnd_label = f"r{round_num}"
        round_groups = GROUPS if round_num == 1 else list(reversed(GROUPS))
        print(f"\n{'='*75}\nROUND {round_num}/2 ({'forward' if round_num==1 else 'reverse'})\n{'='*75}", flush=True)

        for i, prompt in enumerate(prompts):
            short = prompt[:55] + ("..." if len(prompt) > 55 else "")
            print(f"\n  R{round_num}[{i+1}/{len(prompts)}] {short}", flush=True)
            fname = f"{i+1:02d}_test.png"

            for g in round_groups:
                gid = g["id"]
                if (round_num, i + 1, gid) in completed_samples:
                    continue
                REQUEST_CONTEXT.clear()
                REQUEST_CONTEXT.update({"sample_id": f"{gid}-{rnd_label}-p{i + 1:02d}", "phase": "formal",
                                        "group": gid, "round": round_num, "prompt_idx": i + 1})
                RUN_RECORD["current_sample"] = dict(REQUEST_CONTEXT)
                checkpoint("RUNNING")
                print(f"    {gid}...", end="", flush=True)
                pace(g)
                sample_started_at = utc_now()
                sample_started = time.perf_counter()
                ok, elapsed, img, token_info = call_group(g, prompt, token)
                logical_seconds = time.perf_counter() - sample_started
                size_bytes = 0
                if ok and img:
                    out_path = OUT_BASE / gid / rnd_label / fname
                    out_path.write_bytes(img)
                    size_bytes = len(img)

                status = f"OK {elapsed:.1f}s {size_bytes/1024:.0f}KB"
                if token_info.get("output_tokens") or token_info.get("num_output_tokens"):
                    out_tok = token_info.get("output_tokens") or token_info.get("num_output_tokens")
                    status += f" tok={out_tok}"
                if not ok:
                    status = "FAIL"
                print(f" {status}", flush=True)

                all_data.append({
                    "round": round_num, "prompt_idx": i+1, "prompt_short": short,
                    "group": gid, "group_type": g["type"], "quality": g.get("quality"),
                    "ok": ok, "time": elapsed, "size_bytes": size_bytes,
                    "token_info": token_info,
                    "started_at_utc": sample_started_at, "ended_at_utc": utc_now(),
                    "logical_request_seconds": logical_seconds,
                    "pacing_wait_seconds": LAST_PACING_WAIT,
                    "attempt_count": len(LAST_ATTEMPTS),
                    "first_attempt_ok": LAST_ATTEMPTS[0]["ok"] if LAST_ATTEMPTS else None,
                    "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    "image": f"{gid}/{rnd_label}/{fname}" if ok else None,
                    "image_sha256": hashlib.sha256(img).hexdigest() if ok and img else None,
                })
                checkpoint("RUNNING")
                time.sleep(INTER_CALL_WAIT)

            if (i+1) % 3 == 0:
                token = get_entra_token()
                print("    Authentication refreshed", flush=True)
        token = get_entra_token()

    # SUMMARY
    print(f"\n{'='*75}\nSUMMARY\n{'='*75}", flush=True)
    print(f"{'Group':<28} {'Latency':>8} {'OutTok':>8} {'Pass':>6}", flush=True)
    print("-" * 65, flush=True)
    for g in GROUPS:
        entries = [d for d in all_data if d["group"]==g["id"] and d["ok"]]
        if entries:
            avg_t = sum(d["time"] for d in entries)/len(entries)
            # output tokens
            if g["type"] == "gpt":
                toks = [d["token_info"].get("output_tokens",0) for d in entries if d["token_info"].get("output_tokens")]
            else:
                toks = [d["token_info"].get("num_output_tokens",0) for d in entries if d["token_info"].get("num_output_tokens")]
            avg_tok = sum(toks)/len(toks) if toks else None
            tok_str = f"{avg_tok:.0f}" if avg_tok else "N/A"
            print(f"{g['id']:<28} {avg_t:>7.1f}s {tok_str:>8} {len(entries)}/{len(prompts) * 2}", flush=True)

    RUN_RECORD["ended_at_utc"] = utc_now()
    RUN_RECORD["current_sample"] = None
    checkpoint("COMPLETED" if all(item["ok"] for item in all_data) else "COMPLETED_WITH_FAILURES")
    print(f"\nSaved: {RESULTS_JSON}", flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the historical two-round image benchmark.")
    parser.add_argument("--mai-model", help="Select this MAI deployment; can be combined with --gpt-model.")
    parser.add_argument("--mai-web-grounding", choices=("off", "on", "both"),
                        help="Explicit MAI web grounding at fixed aspect ratio; omitted preserves the original request.")
    parser.add_argument("--prompts-csv", type=Path, help="Prompt CSV for an independent supplemental run.")
    parser.add_argument("--gpt-model", action="append",
                        help="Select this GPT image deployment; repeat the flag to interleave several deployments.")
    parser.add_argument("--gpt-quality", action="append",
                        choices=("low", "medium", "high", "xhigh", "max", "auto", "all", "all25"),
                        help="Quality tier; repeat the flag to combine tiers. "
                             "'all' stays low/medium/high (the tiers gpt-image-2 supports, used by "
                             "published archives); 'all25' adds xhigh/max/auto, which only "
                             "gpt-image-2.5-* accept. Default medium.")
    parser.add_argument("--output", type=Path, help="Directory for this independent measurement run.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without network calls.")
    parser.add_argument("--resume", action="store_true", help="Continue an interrupted run without rerunning recorded samples.")
    parser.add_argument("--warmup-only", action="store_true", help="Run the selected warmups; use --resume for formal samples later.")
    options = parser.parse_args()
    RESUME = options.resume
    WARMUP_ONLY = options.warmup_only
    if options.mai_web_grounding and not options.mai_model:
        parser.error("--mai-web-grounding requires --mai-model")
    if options.prompts_csv:
        CSV_PATH = options.prompts_csv.resolve()
    if options.mai_model or options.gpt_model:
        GROUPS = []
    if options.mai_model:
        if options.mai_web_grounding:
            grounding_modes = (False, True) if options.mai_web_grounding == "both" else (options.mai_web_grounding == "on",)
            GROUPS.extend({"id": options.mai_model.lower() + ("-web-on" if grounding_mode else "-web-off"),
                           "type": "mai", "model": options.mai_model, "quality": None,
                           "web_grounding": grounding_mode} for grounding_mode in grounding_modes)
        else:
            GROUPS.append({"id": options.mai_model.lower(), "type": "mai", "model": options.mai_model,
                           "quality": None})
    if options.gpt_model:
        qualities = []
        for token in options.gpt_quality or ["medium"]:
            for quality in QUALITY_ALIASES.get(token, (token,)):
                if quality not in qualities:
                    qualities.append(quality)
        GROUPS.extend({"id": f"{model.lower()}-{quality}", "type": "gpt",
                       "model": model, "quality": quality}
                      for model in options.gpt_model for quality in qualities)
    if options.output:
        OUT_BASE = options.output.resolve()
        RESULTS_JSON = OUT_BASE / "5way_v2_results.json"
    if options.dry_run:
        with CSV_PATH.open(encoding="utf-8-sig", newline="") as prompt_file:
            prompt_reader = csv.reader(prompt_file)
            next(prompt_reader)
            prompt_list = [row[0].strip() for row in prompt_reader if row and row[0].strip()]
        print(json.dumps({"status": "DRY_RUN", "groups": [group["id"] for group in GROUPS],
                          "quality": [group["quality"] for group in GROUPS],
                          "prompts": len(prompt_list), "rounds": 2,
                          "formal_samples": len(prompt_list) * len(GROUPS) * 2,
                          "warmup_requests": len(GROUPS), "resolution": "1024x1024",
                          "prompts_sha256": hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(),
                          "round_order": {"1": [group["id"] for group in GROUPS],
                                          "2": [group["id"] for group in reversed(GROUPS)]},
                          "inter_call_wait_seconds": INTER_CALL_WAIT, "network_calls": 0}))
    else:
        try:
            main()
        except KeyboardInterrupt:
            if RUN_RECORD:
                checkpoint("INTERRUPTED")
            raise SystemExit(130)
