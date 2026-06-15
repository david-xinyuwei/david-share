#!/usr/bin/env python3
"""
Test vLLM Multi-LoRA serving with domain-specific prompts.
Sends the same prompt to base model and each LoRA adapter,
comparing responses to demonstrate domain specialization.

Author: Xinyu Wei
"""
import json
import time
import requests
import sys

VLLM_URL = "http://localhost:8080/v1/chat/completions"
MODELS = [
    "/data/EXAONE-3.5-2.4B-Instruct",  # base model
    "medical",
    "legal",
    "customer_support",
    "code",
]

# Domain-specific test prompts
TEST_PROMPTS = {
    "medical": "What are the common symptoms and treatment options for Type 2 diabetes?",
    "legal": "What are the key differences between civil law and criminal law in South Korea?",
    "customer_support": "I ordered a product 2 weeks ago and it still hasn't arrived. What should I do?",
    "code": "Write a Python function that implements binary search on a sorted list.",
}


def query_model(model: str, prompt: str, max_tokens: int = 256) -> dict:
    """Send a chat completion request to vLLM."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    start = time.time()
    resp = requests.post(VLLM_URL, json=payload, timeout=60)
    elapsed = time.time() - start
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return {
        "model": model,
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "latency_s": round(elapsed, 3),
    }


def main():
    results = []
    print("=" * 80)
    print("EXAONE Multi-LoRA Serving Test")
    print("=" * 80)

    for domain, prompt in TEST_PROMPTS.items():
        print(f"\n{'=' * 80}")
        print(f"DOMAIN: {domain}")
        print(f"PROMPT: {prompt}")
        print("=" * 80)

        for model in MODELS:
            try:
                result = query_model(model, prompt)
                results.append({"domain": domain, **result})
                model_label = model.split("/")[-1] if "/" in model else model
                print(f"\n--- Model: {model_label} ({result['latency_s']}s, "
                      f"{result['completion_tokens']} tokens) ---")
                # Print first 300 chars of response
                text = result["content"]
                print(text[:300] + ("..." if len(text) > 300 else ""))
            except Exception as e:
                print(f"\n--- Model: {model} --- ERROR: {e}")

    # Summary table
    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Domain':<18} {'Model':<25} {'Tokens':>7} {'Latency':>8}")
    print("-" * 60)
    for r in results:
        model_label = r["model"].split("/")[-1] if "/" in r["model"] else r["model"]
        print(f"{r['domain']:<18} {model_label:<25} {r['completion_tokens']:>7} "
              f"{r['latency_s']:>7.3f}s")

    # Save results
    with open("/tmp/multi_lora_test_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to /tmp/multi_lora_test_results.json")


if __name__ == "__main__":
    main()
