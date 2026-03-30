#!/usr/bin/env python3
"""
the organization Model Migration Benchmark
gpt-4o-mini vs gpt-5.4-mini vs gpt-5.4-nano

Scenarios based on 6 core AI assistant features:
1. Next Move — Intent classification, proactive suggestions
2. Chat Mode — Multi-turn conversation, device Q&A
3. Write For Me — Document continuation, email draft
4. Live Mode — Real-time quick response (TTFT critical!)
5. Catch Me Up — Cross-device activity summary
6. Pay Attention — Meeting transcription summary + action items

Plus: Bing Grounding integration scenarios (Chris's #1 pain point)

Author: Xinyu Wei (魏新宇)
"""
import time, json, statistics, sys, os
from datetime import datetime
import requests

# Keys
KEY_EUS2 = open("/tmp/key_eus2.txt").read().strip()
KEY_SWE  = open("/tmp/key_swe.txt").read().strip()
KEY_SEA  = open("/tmp/key_sea.txt").read().strip()

REGIONS = {
    "eastus2": ("https://<your-endpoint>.openai.azure.com", KEY_EUS2),
    "swedencentral": ("https://admin-m3n3cb54-swedencentral.openai.azure.com", KEY_SWE),
    "southeastasia": ("https://aoai-southeastasia-<your-project>.openai.azure.com", KEY_SEA),
}

API_VERSION = "2025-04-01-preview"
RUNS = 3

# ═══ the assistant Scenarios (based on CES PPT + Chris's real usage) ═══

SCENARIOS = [
    # --- 1. Next Move: Intent Classification (proactive suggestions) ---
    {
        "id": "1a",
        "feature": "Next Move",
        "name": "Intent Classification - Device Setup",
        "system": "You are the assistant, the organization's personal AI assistant. Classify the user's intent into one of: [device_setup, troubleshoot, purchase, information, calendar, communication]. Respond with ONLY the intent label.",
        "user": "I just got my new ThinkPad X1 Carbon and need to get it connected to my office Wi-Fi",
        "max_tokens": 10,
        "latency_target": "< 0.5s",
    },
    {
        "id": "1b",
        "feature": "Next Move",
        "name": "Intent Classification - Schedule",
        "system": "You are the assistant, the organization's personal AI assistant. Classify the user's intent into one of: [device_setup, troubleshoot, purchase, information, calendar, communication]. Respond with ONLY the intent label.",
        "user": "What's my schedule for tomorrow? I think I have a meeting with the Shanghai team",
        "max_tokens": 10,
        "latency_target": "< 0.5s",
    },

    # --- 2. Chat Mode: Conversational Q&A ---
    {
        "id": "2a",
        "feature": "Chat Mode",
        "name": "Device Knowledge Q&A",
        "system": "You are the assistant, the organization's cross-device AI assistant. Answer questions about products and user's devices. Be concise and helpful.",
        "user": "How do I extend the battery life on my ThinkPad? I'm getting only 6 hours but it's supposed to last 10.",
        "max_tokens": 80,
        "latency_target": "< 2s",
    },
    {
        "id": "2b",
        "feature": "Chat Mode",
        "name": "Multi-turn Follow-up",
        "system": "You are the assistant, the organization's AI assistant. The user previously asked about VPN setup. Continue the conversation naturally.",
        "user": "I followed the steps you gave me but it's still showing 'connection timeout'. The error code is VPN-ERR-4012.",
        "max_tokens": 100,
        "latency_target": "< 2s",
    },

    # --- 3. Write For Me: Content Generation ---
    {
        "id": "3a",
        "feature": "Write For Me",
        "name": "Email Draft - IT Request",
        "system": "You are the assistant, helping the user draft a professional email. Match the user's tone and be concise.",
        "user": "Write a short email to IT requesting a second monitor for my home office setup. Mention I need it for the upcoming quarterly review presentations.",
        "max_tokens": 120,
        "latency_target": "< 3s",
    },
    {
        "id": "3b",
        "feature": "Write For Me",
        "name": "Document Continuation",
        "system": "You are the assistant, helping the user continue a document. Write in the same style and tone.",
        "user": "Continue this paragraph: 'The Q3 results showed a 15% increase in customer satisfaction scores across APAC markets. Key drivers included'",
        "max_tokens": 80,
        "latency_target": "< 2s",
    },

    # --- 4. Live Mode: Real-time Quick Response (TTFT critical!) ---
    {
        "id": "4a",
        "feature": "Live Mode",
        "name": "Quick Response - Presentation Help",
        "system": "You are the assistant in Live Mode. The user is giving a presentation RIGHT NOW. Give extremely brief, instant answers. No more than 1-2 sentences.",
        "user": "What was our APAC revenue last quarter?",
        "max_tokens": 30,
        "latency_target": "< 1s ⚡",
    },
    {
        "id": "4b",
        "feature": "Live Mode",
        "name": "Quick Response - Translation",
        "system": "You are the assistant in Live Mode. Translate instantly. No explanation, just the translation.",
        "user": "Translate to Mandarin: 'We expect to close this deal by end of March'",
        "max_tokens": 30,
        "latency_target": "< 1s ⚡",
    },

    # --- 5. Catch Me Up: Activity Summary ---
    {
        "id": "5a",
        "feature": "Catch Me Up",
        "name": "Cross-device Activity Summary",
        "system": "You are the assistant. Summarize the user's recent activities across devices. Be structured: use bullet points for key items, highlight action items.",
        "user": "Summarize: [Phone] 3 missed calls from John, 12 new emails (2 urgent from CFO about budget), WeChat message from Shanghai team. [Laptop] VS Code session with 5 unsaved files, Teams meeting invite for tomorrow 9am. [Tablet] PDF annotation on 'Q4 Strategy' doc half-finished.",
        "max_tokens": 120,
        "latency_target": "< 3s",
    },

    # --- 6. Pay Attention: Meeting Summary ---
    {
        "id": "6a",
        "feature": "Pay Attention",
        "name": "Meeting Summary + Action Items",
        "system": "You are the assistant. Summarize the meeting transcript. Output: 1) Key decisions, 2) Action items with owners, 3) Next steps. Be structured and concise.",
        "user": "Meeting notes: Discussed Q2 product roadmap. Decision: prioritize the assistant mobile app for Android launch in June. Budget: approved $2M for 3 new ML engineers. Timeline: MVP by April 15, beta by May 1. Action: Sarah to draft job descriptions by Friday. Mark to coordinate with the organization team on API integration. Next review meeting in 2 weeks. Risk: GPU availability for fine-tuning may delay training phase.",
        "max_tokens": 150,
        "latency_target": "< 3s",
    },

    # --- 7. Bing Grounding Simulation (Chris's pain point: 700ms+ per search) ---
    {
        "id": "7a",
        "feature": "Bing Grounding",
        "name": "Web-grounded Q&A (simulated)",
        "system": "You are the assistant with web search capability. Answer using your knowledge. In production, this would use Bing Search for grounding. Cite sources if possible.",
        "user": "What's the latest ThinkPad X1 Carbon Gen 13 pricing and availability in the US?",
        "max_tokens": 80,
        "latency_target": "< 2s (+ 700ms Bing)",
    },
]

def call_model(endpoint, key, model, scenario):
    url = f"{endpoint}/openai/deployments/{model}/chat/completions?api-version={API_VERSION}"
    headers = {"api-key": key, "Content-Type": "application/json"}
    body = {
        "messages": [
            {"role": "system", "content": scenario["system"]},
            {"role": "user", "content": scenario["user"]}
        ],
        "max_completion_tokens": scenario["max_tokens"],
    }
    if "5." in model and "4o" not in model:
        body["reasoning_effort"] = "none"

    t0 = time.time()
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30, stream=True)
        # Measure TTFT (time to first byte)
        first_byte = None
        chunks = b""
        for chunk in resp.iter_content(chunk_size=64):
            if first_byte is None:
                first_byte = time.time()
            chunks += chunk
        total_time = time.time() - t0
        ttft = (first_byte - t0) if first_byte else total_time

        data = json.loads(chunks.decode("utf-8"))
        if resp.status_code == 200:
            usage = data.get("usage", {})
            content = data["choices"][0]["message"]["content"]
            completion_tokens = usage.get("completion_tokens", 0)
            reasoning = 0
            if usage.get("completion_tokens_details"):
                reasoning = usage["completion_tokens_details"].get("reasoning_tokens", 0)
            tps = completion_tokens / total_time if total_time > 0 else 0

            return {
                "ok": True, "latency": round(total_time, 3), "ttft": round(ttft, 3),
                "completion_tokens": completion_tokens, "reasoning_tokens": reasoning,
                "tps": round(tps, 1), "content": content[:100],
            }
        else:
            return {"ok": False, "latency": round(total_time, 3), "error": data.get("error", {}).get("message", "")[:80]}
    except Exception as e:
        return {"ok": False, "latency": round(time.time()-t0, 3), "error": str(e)[:80]}

MODELS = ["gpt-4o-mini", "gpt-5.4-mini", "gpt-5.4-nano"]

print("=" * 75)
print("  the organization the assistant — Model Migration Benchmark (6 Features + Bing Grounding)")
print(f"  Models: {', '.join(MODELS)}")
print(f"  Scenarios: {len(SCENARIOS)} × {RUNS} runs")
print(f"  Time: {datetime.now():%Y-%m-%d %H:%M:%S}")
print("=" * 75)

# Use East US 2 as primary test region (lowest latency from our location)
endpoint, key = REGIONS["eastus2"]
all_results = {}

for model in MODELS:
    print(f"\n{'─'*60}")
    print(f"  Model: {model}")
    print(f"{'─'*60}")

    if "5.4" in model:
        # Check SEA availability
        print(f"  ⚠ Not available in Southeast Asia (Global Standard)")

    model_results = []
    for sc in SCENARIOS:
        runs = []
        for r in range(RUNS):
            result = call_model(endpoint, key, model, sc)
            runs.append(result)
            time.sleep(0.3)

        ok_runs = [r for r in runs if r.get("ok")]
        if ok_runs:
            avg_lat = statistics.mean(r["latency"] for r in ok_runs)
            avg_ttft = statistics.mean(r["ttft"] for r in ok_runs)
            avg_tps = statistics.mean(r["tps"] for r in ok_runs)
            best = min(ok_runs, key=lambda x: x["latency"])
            target = sc.get("latency_target", "")

            status = "✅" if avg_lat < 3 else "⚠️"
            print(f"  {sc['id']:4s} {sc['feature']:15s} {sc['name']:35s} | lat={avg_lat:.2f}s ttft={avg_ttft:.2f}s {avg_tps:.0f}t/s reason={best['reasoning_tokens']:>3d} | target: {target}")

            model_results.append({
                "id": sc["id"], "feature": sc["feature"], "name": sc["name"],
                "avg_latency": round(avg_lat, 3), "avg_ttft": round(avg_ttft, 3),
                "avg_tps": round(avg_tps, 1), "completion_tokens": best["completion_tokens"],
                "reasoning_tokens": best["reasoning_tokens"], "target": target,
            })
        else:
            err = runs[0].get("error", "?")[:50]
            print(f"  {sc['id']:4s} {sc['feature']:15s} {sc['name']:35s} | FAILED: {err}")
            model_results.append({"id": sc["id"], "feature": sc["feature"], "name": sc["name"], "error": err})

    all_results[model] = model_results

# ═══ Summary Table ═══
print(f"\n{'='*75}")
print("  COMPARISON SUMMARY (East US 2)")
print(f"{'='*75}")

print(f"\n  {'Feature':15s} {'Scenario':35s} | {'4o-mini':>8s} | {'5.4-mini':>8s} | {'5.4-nano':>8s} |")
print(f"  {'-'*15} {'-'*35} | {'-'*8} | {'-'*8} | {'-'*8} |")

for i, sc in enumerate(SCENARIOS):
    row = f"  {sc['feature']:15s} {sc['name'][:35]:35s} |"
    for model in MODELS:
        mr = all_results.get(model, [])
        if i < len(mr) and "avg_latency" in mr[i]:
            row += f" {mr[i]['avg_latency']:>6.2f}s |"
        else:
            row += f"   {'N/A':>4s} |"
    print(row)

# Averages
print(f"\n  {'AVERAGE':15s} {'':35s} |", end="")
for model in MODELS:
    mr = all_results.get(model, [])
    lats = [r["avg_latency"] for r in mr if "avg_latency" in r]
    if lats:
        print(f" {statistics.mean(lats):>6.2f}s |", end="")
    else:
        print(f"   {'N/A':>4s} |", end="")
print()

print(f"  {'AVG TTFT':15s} {'':35s} |", end="")
for model in MODELS:
    mr = all_results.get(model, [])
    ttfts = [r["avg_ttft"] for r in mr if "avg_ttft" in r]
    if ttfts:
        print(f" {statistics.mean(ttfts):>6.2f}s |", end="")
    else:
        print(f"   {'N/A':>4s} |", end="")
print()

print(f"  {'AVG TPS':15s} {'':35s} |", end="")
for model in MODELS:
    mr = all_results.get(model, [])
    tps_list = [r["avg_tps"] for r in mr if "avg_tps" in r]
    if tps_list:
        print(f" {statistics.mean(tps_list):>5.0f}t/s |", end="")
    else:
        print(f"   {'N/A':>4s} |", end="")
print()

# Save
output = {
    "timestamp": datetime.now().isoformat(),
    "region": "eastus2",
    "models": MODELS,
    "scenarios": [{k: v for k, v in sc.items() if k != "system"} for sc in SCENARIOS],
    "results": all_results,
}
outpath = "./outputs/benchmark_<your-project>_migration_20260323.json"
with open(outpath, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\nResults saved: {outpath}")
