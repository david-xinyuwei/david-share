"""
the assistant Migration Benchmark — Streaming Mode
Measures REAL TTFT (time to first SSE token) and E2E latency
reasoning_effort=none for 5.4 models
"""
import time, json, statistics, sys, re
from datetime import datetime
import requests

KEY_EUS2 = open("/tmp/key_eus2.txt").read().strip()
ENDPOINT = "https://<your-endpoint>.openai.azure.com"
API_VERSION = "2025-04-01-preview"
RUNS = 3
MODELS = ["gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4-nano"]

SCENARIOS = [
    {"id":"1a","feat":"Next Move","name":"Intent Classification","system":"You are the assistant. Classify intent into: [device_setup, troubleshoot, purchase, information, calendar, communication]. Reply with ONLY the label.","user":"I just got my new ThinkPad and need Wi-Fi setup","max":10},
    {"id":"2a","feat":"Chat Mode","name":"Device Q&A","system":"You are the assistant. Be concise and helpful.","user":"How do I extend battery life on my ThinkPad? Getting only 6 hours.","max":80},
    {"id":"3a","feat":"Write For Me","name":"Email Draft","system":"You are the assistant. Draft a professional email. Be concise.","user":"Write a short email to IT requesting a second monitor for presentations.","max":120},
    {"id":"4a","feat":"Live Mode","name":"Quick Response","system":"You are the assistant in Live Mode. Ultra brief, 1-2 sentences max.","user":"What was our APAC revenue last quarter?","max":30},
    {"id":"5a","feat":"Catch Me Up","name":"Activity Summary","system":"You are the assistant. Summarize with bullet points.","user":"Summarize: Phone: 3 missed calls, 12 emails (2 urgent from CFO). Laptop: 5 unsaved files, Teams meeting tomorrow 9am. Tablet: PDF annotation half-done.","max":120},
    {"id":"6a","feat":"Pay Attention","name":"Meeting Summary","system":"You are the assistant. Output: 1) Key decisions 2) Action items 3) Next steps.","user":"Meeting: Q2 roadmap, prioritize the assistant mobile Android launch June. Budget $2M for 3 ML engineers. MVP April 15, beta May 1. Sarah: job descriptions by Friday. Mark: the organization API integration.","max":150},
    {"id":"7a","feat":"Bing Grounding","name":"Web Q&A","system":"You are the assistant with web search. Answer using your knowledge.","user":"What's the latest ThinkPad X1 Carbon Gen 13 pricing in the US?","max":80},
]

def call_streaming(model, scenario):
    url = f"{ENDPOINT}/openai/deployments/{model}/chat/completions?api-version={API_VERSION}"
    headers = {"api-key": KEY_EUS2, "Content-Type": "application/json"}
    body = {
        "messages": [
            {"role": "system", "content": scenario["system"]},
            {"role": "user", "content": scenario["user"]}
        ],
        "max_completion_tokens": scenario["max"],
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if "5.4" in model:
        body["reasoning_effort"] = "none"

    t0 = time.time()
    ttft = None
    tokens_received = 0
    content_parts = []
    usage_data = {}

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30, stream=True)
        if resp.status_code != 200:
            return {"ok": False, "error": resp.text[:100], "status": resp.status_code}

        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if not line_str.startswith("data: "):
                continue
            data_str = line_str[6:]
            if data_str == "[DONE]":
                break

            try:
                chunk = json.loads(data_str)
            except:
                continue

            # TTFT: first chunk with content
            if chunk.get("choices") and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content")
                if content and ttft is None:
                    ttft = time.time() - t0
                if content:
                    content_parts.append(content)
                    tokens_received += 1

            # Usage in last chunk
            if chunk.get("usage"):
                usage_data = chunk["usage"]

        e2e = time.time() - t0
        if ttft is None:
            ttft = e2e

        completion_tokens = usage_data.get("completion_tokens", tokens_received)
        reasoning = 0
        if usage_data.get("completion_tokens_details"):
            reasoning = usage_data["completion_tokens_details"].get("reasoning_tokens", 0)

        tps = completion_tokens / e2e if e2e > 0 else 0

        return {
            "ok": True,
            "ttft": round(ttft, 3),
            "e2e": round(e2e, 3),
            "completion_tokens": completion_tokens,
            "reasoning_tokens": reasoning,
            "tps": round(tps, 1),
            "content": "".join(content_parts)[:80],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:80]}

print("=" * 75)
print("  the assistant Migration Benchmark — STREAMING MODE (TTFT + E2E)")
print(f"  Models: {', '.join(MODELS)}")
print(f"  Region: East US 2  |  Stream: ON  |  reasoning_effort: none (5.4)")
print(f"  Time: {datetime.now():%Y-%m-%d %H:%M:%S}")
print("=" * 75)

all_results = {}

for model in MODELS:
    print(f"\n{'─'*65}")
    print(f"  {model}" + (" ⚠ SEA unavailable" if "5.4" in model else ""))
    print(f"{'─'*65}")
    print(f"  {'ID':4s} {'Feature':15s} {'Scenario':25s} | {'TTFT':>6s} {'E2E':>6s} {'TPS':>5s} {'Reason':>6s}")
    print(f"  {'─'*4} {'─'*15} {'─'*25} | {'─'*6} {'─'*6} {'─'*5} {'─'*6}")

    model_results = []
    for sc in SCENARIOS:
        runs = [call_streaming(model, sc) for _ in range(RUNS)]
        time.sleep(0.5)

        ok = [r for r in runs if r.get("ok")]
        if ok:
            avg_ttft = statistics.mean(r["ttft"] for r in ok)
            avg_e2e = statistics.mean(r["e2e"] for r in ok)
            avg_tps = statistics.mean(r["tps"] for r in ok)
            best = min(ok, key=lambda x: x["e2e"])
            reasoning = best["reasoning_tokens"]

            print(f"  {sc['id']:4s} {sc['feat']:15s} {sc['name']:25s} | {avg_ttft:>5.2f}s {avg_e2e:>5.2f}s {avg_tps:>4.0f} {reasoning:>5d}")
            model_results.append({
                "id": sc["id"], "feat": sc["feat"], "name": sc["name"],
                "ttft": round(avg_ttft, 3), "e2e": round(avg_e2e, 3),
                "tps": round(avg_tps, 1), "reasoning": reasoning, "tokens": best["completion_tokens"],
            })
        else:
            print(f"  {sc['id']:4s} {sc['feat']:15s} {sc['name']:25s} | FAILED")
            model_results.append({"id": sc["id"], "error": runs[0].get("error","?")[:40]})

    all_results[model] = model_results

# Summary
print(f"\n{'='*75}")
print("  COMPARISON (Streaming, East US 2)")
print(f"{'='*75}")
print(f"\n  {'':45s} | {'gpt-4o-mini':>12s} | {'gpt-5.4-mini':>12s} | {'gpt-5.4-nano':>12s}")
print(f"  {'':45s} | {'TTFT / E2E':>12s} | {'TTFT / E2E':>12s} | {'TTFT / E2E':>12s}")
print(f"  {'-'*45} | {'-'*12} | {'-'*12} | {'-'*12}")

for i, sc in enumerate(SCENARIOS):
    row = f"  {sc['feat']:15s} {sc['name'][:30]:30s} |"
    for model in MODELS:
        mr = all_results.get(model, [])
        if i < len(mr) and "ttft" in mr[i]:
            row += f" {mr[i]['ttft']:.2f}/{mr[i]['e2e']:.2f}s |"
        else:
            row += f"    {'N/A':>5s}   |"
    print(row)

# Averages
print(f"\n  {'AVG TTFT':45s} |", end="")
for m in MODELS:
    mr = all_results.get(m, [])
    vals = [r["ttft"] for r in mr if "ttft" in r]
    print(f" {statistics.mean(vals):>10.2f}s |" if vals else "   N/A      |", end="")
print()
print(f"  {'AVG E2E':45s} |", end="")
for m in MODELS:
    mr = all_results.get(m, [])
    vals = [r["e2e"] for r in mr if "e2e" in r]
    print(f" {statistics.mean(vals):>10.2f}s |" if vals else "   N/A      |", end="")
print()
print(f"  {'TOTAL REASONING TOKENS':45s} |", end="")
for m in MODELS:
    mr = all_results.get(m, [])
    total = sum(r.get("reasoning", 0) for r in mr)
    print(f" {total:>10d}  |", end="")
print()

with open("/tmp/benchmark_streaming_results.json", "w") as f:
    json.dump({"timestamp": datetime.now().isoformat(), "results": all_results}, f, indent=2)
print(f"\nSaved: /tmp/benchmark_streaming_results.json")
