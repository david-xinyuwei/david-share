#!/usr/bin/env python3
"""
Qira Intent Classification Benchmark — Short Output Scenario
Tests whether gpt-5.4-nano is cheaper than gpt-4o-mini when output is minimal.
Uses 1066-token GUARDRAILS system prompt (triggers prompt caching) + max_tokens=30.
"""

import os, time, json, datetime
from openai import AzureOpenAI

AOAI_ENDPOINT = "https://<your-endpoint>.openai.azure.com"
AOAI_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "<your-api-key>")

GUARDRAILS = """
[GUARDRAILS — Qira AI Assistant Behavioral Framework v2.1]

Section 1: Identity & Persona
You are Qira, Lenovo's system-level cross-device AI assistant. You serve users across ThinkPad PCs, tablets, and Motorola phones. Maintain a professional, helpful, and concise communication style.

Section 2: Safety & Content Policy
Never generate harmful, hateful, violent, sexually explicit, or illegal content. Decline requests for malware, weapons, or dangerous activities. Redirect users to emergency services when life-threatening situations are detected.

Section 3: Privacy & Data Protection
Never request, store, or transmit personal identification numbers, passwords, financial account details, or health records. Do not reference previous conversation history unless explicitly provided in the current session.

Section 4: Accuracy & Hallucination Prevention
Only provide information you are confident about. When uncertain, clearly state limitations. Never fabricate citations, URLs, product specifications, or pricing. For real-time data, use Bing grounding.

Section 5: Brand & Product Guidelines
Represent Lenovo products accurately. Do not make comparative claims against competitors unless backed by published benchmarks. Always recommend consulting official Lenovo support for hardware issues.

Section 6: Response Format Standards
Keep responses concise and actionable. Use bullet points for lists exceeding 3 items. Include relevant disclaimers for medical, legal, or financial topics. Format code blocks with appropriate syntax highlighting.

Section 7: Multi-Device Context
Adapt response length and format to the device context. Shorter responses for phone interactions, detailed responses for PC sessions. Respect device-specific capabilities in recommendations.

Section 8: Escalation Protocol
For issues beyond your capability, provide Lenovo support contact information. For urgent device malfunctions, recommend immediate professional service. Never attempt to guide users through hardware repairs.

Section 9: Language & Localization
Respond in the user's language. Maintain cultural sensitivity across regions. Use metric or imperial units based on user locale. Adapt formality level to cultural norms.

Section 10: Session Management
Each conversation is independent. Do not assume continuity between sessions. Clearly acknowledge when context from the current session is being referenced.

Section 11: Tool Usage Guidelines
When using Bing search, perform exactly ONE search query. Do not refine or repeat searches. Use search results to provide current, factual information. Always cite the source of searched information.

Section 12: Compliance & Auditing
All responses must comply with applicable laws and regulations. Interactions may be logged for quality assurance. Maintain transparency about AI nature when directly asked.
"""

SYSTEM_MSG = "You are Qira, Lenovo's AI assistant. Classify the user's intent into exactly ONE category. Reply with ONLY the category name, nothing else.\n\nCategories: NextMove, ChatMode, WriteForMe, LiveMode, CatchMeUp, PayAttention, BingSearch, DeviceSupport, Unknown\n\n" + GUARDRAILS

INTENT_QUERIES = [
    "What's the weather like in Seattle right now?",
    "Help me write a professional email to my manager about taking PTO next week",
    "What are the latest ThinkPad X1 Carbon specs?",
    "Summarize what happened in my meetings today",
    "Can you fix my laptop's Bluetooth connection?",
    "What were the top AI news stories this week?",
    "Take notes during my next meeting",
    "How do I connect my Motorola phone to my ThinkPad?",
    "Draft a thank you note for my colleague",
    "What is the current stock price of Lenovo?",
]

MODELS = [
    {"name": "gpt-4o-mini", "deployment": "gpt-4o-mini"},
    {"name": "gpt-5.4-nano", "deployment": "gpt-5.4-nano"},
]

PRICING = {
    "gpt-4o-mini":  {"input": 0.15, "cached": 0.075, "output": 0.60},
    "gpt-5.4-nano": {"input": 0.20, "cached": 0.020, "output": 1.25},
}

def run_benchmark():
    client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version="2025-04-01-preview",
    )

    results = []
    iterations = 10  # per query
    warmup = 2

    for model_info in MODELS:
        model_name = model_info["name"]
        deployment = model_info["deployment"]
        print(f"\n{'='*60}")
        print(f"  Model: {model_name} (deployment: {deployment})")
        print(f"{'='*60}")

        for qi, query in enumerate(INTENT_QUERIES):
            for i in range(1, iterations + 1):
                is_warmup = i <= warmup
                prefix = "WU" if is_warmup else "  "

                t0 = time.time()
                ttft = None
                full_text = ""
                input_tokens = 0
                output_tokens = 0
                cached_tokens = 0

                try:
                    stream = client.responses.create(
                        model=deployment,
                        input=[
                            {"role": "system", "content": SYSTEM_MSG},
                            {"role": "user", "content": query},
                        ],
                        stream=True,
                        max_output_tokens=30,
                    )
                    for event in stream:
                        if ttft is None and hasattr(event, 'type') and event.type == 'response.output_text.delta':
                            ttft = time.time() - t0
                        if hasattr(event, 'type') and event.type == 'response.output_text.delta':
                            full_text += event.delta
                        if hasattr(event, 'type') and event.type == 'response.completed':
                            resp = event.response
                            if hasattr(resp, 'usage') and resp.usage:
                                input_tokens = resp.usage.input_tokens
                                output_tokens = resp.usage.output_tokens
                                if hasattr(resp.usage, 'input_tokens_details') and resp.usage.input_tokens_details:
                                    cached_tokens = getattr(resp.usage.input_tokens_details, 'cached_tokens', 0)
                except Exception as e:
                    print(f"  {prefix} q{qi} i{i} {model_name} ERROR: {e}")
                    continue

                e2e = time.time() - t0
                if ttft is None:
                    ttft = e2e

                rec = {
                    "model": model_name,
                    "query_idx": qi,
                    "query": query[:50],
                    "iter": i,
                    "warmup": is_warmup,
                    "ttft": round(ttft, 3),
                    "e2e": round(e2e, 3),
                    "response": full_text.strip(),
                    "len": len(full_text),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cached_tokens": cached_tokens,
                }
                results.append(rec)
                cache_pct = f"{cached_tokens/input_tokens*100:.0f}%" if input_tokens > 0 else "N/A"
                print(f"  {prefix} q{qi} i{i} {model_name:15s} TTFT={ttft:.2f}s in={input_tokens} out={output_tokens} cached={cache_pct} → \"{full_text.strip()[:30]}\"")

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY — Intent Classification (short output)")
    print(f"{'='*60}")

    for model_info in MODELS:
        mn = model_info["name"]
        recs = [r for r in results if r["model"] == mn and not r["warmup"]]
        if not recs:
            continue
        avg_in = sum(r["input_tokens"] for r in recs) / len(recs)
        avg_out = sum(r["output_tokens"] for r in recs) / len(recs)
        avg_cached = sum(r["cached_tokens"] for r in recs) / len(recs)
        avg_ttft = sum(r["ttft"] for r in recs) / len(recs)

        p = PRICING[mn]
        uncached_in = avg_in - avg_cached
        cost_per_req = (uncached_in * p["input"] + avg_cached * p["cached"] + avg_out * p["output"]) / 1_000_000
        monthly_1M = cost_per_req * 1_000_000

        cache_rate = avg_cached / avg_in * 100 if avg_in > 0 else 0
        print(f"\n  {mn}:")
        print(f"    Avg input tokens:  {avg_in:.0f} (cached: {avg_cached:.0f} = {cache_rate:.0f}%)")
        print(f"    Avg output tokens: {avg_out:.0f}")
        print(f"    Avg TTFT:          {avg_ttft:.2f}s")
        print(f"    Cost/request:      ${cost_per_req*1000:.4f} per 1K requests")
        print(f"    Monthly (100M req): ${monthly_1M*100:.0f}")

    # Save
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = f"outputs/benchmark_intent_classification_{ts}.json"
    with open(outfile, "w") as f:
        json.dump({"benchmark": "intent_classification", "timestamp": ts, "results": results}, f, indent=2)
    print(f"\nSaved: {outfile}")
    print("DONE.")

if __name__ == "__main__":
    run_benchmark()
