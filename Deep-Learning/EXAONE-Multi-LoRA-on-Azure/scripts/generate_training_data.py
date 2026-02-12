#!/usr/bin/env python3
"""
Generate expanded training data for EXAONE Multi-LoRA domains using Azure OpenAI.
Outputs ShareGPT-format JSONL files (80 samples per domain).

Author: Xinyu Wei
"""

import json
import os
import sys
import time
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", "<your-azure-openai-endpoint>"),
    api_key=os.environ.get("AZURE_OPENAI_API_KEY", "<your-azure-openai-api-key>"),
    api_version="2025-01-01-preview"
)

MODEL = os.environ.get("AZURE_OPENAI_MODEL", "gpt-4.1")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

DOMAINS = {
    "customer_support": {
        "file": "customer_support_train.jsonl",
        "system": "You are a training data generator. You MUST return a JSON object with exactly one key \"items\" containing an array of Q&A pairs.",
        "prompt": """Generate exactly {count} unique customer support conversation pairs.

CRITICAL: Return a JSON object in this EXACT format:
{{"items": [{{"q": "customer question", "a": "agent response"}}, {{"q": "...", "a": "..."}}, ...]}}

The "items" array MUST contain exactly {count} objects, each with "q" and "a" keys.

Topic coverage: orders, shipping, returns, refunds, billing, account issues, product questions, complaints, warranty, loyalty programs, payment methods, subscriptions, gift cards, tech support, delivery issues.
- Customer questions: natural and authentic (angry, confused, polite, urgent)
- Agent responses: professional, empathetic, structured (markdown bullets/steps), 150-400 words, specific details (ticket numbers, timelines)
- Mix simple and complex scenarios, escalations, edge cases
- All in English"""
    },
    "medical_qa": {
        "file": "medical_qa_train.jsonl",
        "system": "You are a training data generator. You MUST return a JSON object with exactly one key \"items\" containing an array of Q&A pairs.",
        "prompt": """Generate exactly {count} unique medical Q&A conversation pairs.

CRITICAL: Return a JSON object in this EXACT format:
{{"items": [{{"q": "medical question", "a": "professional response"}}, {{"q": "...", "a": "..."}}, ...]}}

The "items" array MUST contain exactly {count} objects, each with "q" and "a" keys.

Topic coverage: symptoms, diagnostics, treatments, medications, procedures, anatomy, pathology, pharmacology, emergency medicine, preventive care, mental health, pediatrics, geriatrics, lab interpretation, imaging.
- Questions: range from simple patient queries to complex clinical scenarios
- Responses: clinically accurate, proper medical terminology with explanations, 200-500 words
- Include diagnostic criteria, treatment protocols, differential diagnoses
- Structured formatting (bold headers, bullet points)
- Include disclaimers where appropriate
- All in English"""
    },
    "code_assistant": {
        "file": "code_assistant_train.jsonl",
        "system": "You are a training data generator. You MUST return a JSON object with exactly one key \"items\" containing an array of Q&A pairs.",
        "prompt": """Generate exactly {count} unique programming Q&A conversation pairs.

CRITICAL: Return a JSON object in this EXACT format:
{{"items": [{{"q": "developer question", "a": "assistant response with code"}}, {{"q": "...", "a": "..."}}, ...]}}

The "items" array MUST contain exactly {count} objects, each with "q" and "a" keys.

Topic coverage: algorithms, data structures, design patterns, web dev, APIs, databases, testing, debugging, performance, concurrency, security, DevOps, cloud, ML basics.
- Languages: primarily Python, also TypeScript, Go, Rust, SQL, Bash
- Responses MUST include working code blocks
- Code with docstrings, type hints, comments, 200-600 words including code
- Include complexity analysis, best practices, anti-patterns
- All in English"""
    },
    "legal_korean": {
        "file": "legal_korean_train.jsonl",
        "system": "You are a training data generator. You MUST return a JSON object with exactly one key \"items\" containing an array of Q&A pairs. ALL content in Korean.",
        "prompt": """Generate exactly {count} unique Korean legal Q&A conversation pairs.

CRITICAL: Return a JSON object in this EXACT format:
{{"items": [{{"q": "질문 (Korean)", "a": "답변 (Korean)"}}, {{"q": "...", "a": "..."}}, ...]}}

The "items" array MUST contain exactly {count} objects, each with "q" and "a" keys.
ALL content must be in Korean (한국어).

Topic coverage: 근로기준법, 민법, 상법, 형법, 부동산법, 가족법, 소비자보호법, 개인정보보호법, 지식재산권, 세법, 행정법, 임대차보호법, 전자상거래법.
- Reference specific Korean law articles (제X조), court precedents (대법원 판례)
- Include practical advice, legal citations, procedures, deadlines, penalties
- Proper Korean legal terminology, 200-500 words, structured formatting
- Mix simple citizen questions and complex legal scenarios"""
    }
}


def generate_batch(domain_key, domain_config, count=20, batch_num=1):
    """Generate a batch of training samples for a domain."""
    prompt = domain_config["prompt"].format(count=count)

    print(f"  [{domain_key}] Batch {batch_num}: Requesting {count} samples...", flush=True)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": domain_config["system"]},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9,
            max_tokens=16000,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # Extract items array from response
        items = []
        if isinstance(data, dict):
            if "items" in data and isinstance(data["items"], list):
                items = data["items"]
            else:
                for v in data.values():
                    if isinstance(v, list) and len(v) > 1:
                        items = v
                        break
                else:
                    if "q" in data and "a" in data:
                        items = [data]
        elif isinstance(data, list):
            items = data

        # Convert to ShareGPT format
        results = []
        for item in items:
            if isinstance(item, dict) and "q" in item and "a" in item:
                results.append({
                    "conversations": [
                        {"from": "human", "value": item["q"]},
                        {"from": "gpt", "value": item["a"]}
                    ]
                })

        print(f"    Got {len(results)} valid samples (tokens: {response.usage.total_tokens})", flush=True)
        return results

    except Exception as e:
        print(f"    ERROR: {e}", flush=True)
        return []


def main():
    target_per_domain = 80
    batch_size = 20

    print(f"=== Generating Training Data via Azure OpenAI ({MODEL}) ===", flush=True)
    print(f"Target: {target_per_domain} samples x {len(DOMAINS)} domains = {target_per_domain * len(DOMAINS)} total\n", flush=True)

    for domain_key, domain_config in DOMAINS.items():
        print(f"\n{'='*60}", flush=True)
        print(f"Domain: {domain_key}", flush=True)
        print(f"{'='*60}", flush=True)

        all_samples = []
        batch_num = 0

        while len(all_samples) < target_per_domain:
            batch_num += 1
            remaining = target_per_domain - len(all_samples)
            count = min(batch_size, remaining)

            samples = generate_batch(domain_key, domain_config, count=count, batch_num=batch_num)
            all_samples.extend(samples)

            if batch_num > 20:
                print(f"  WARNING: Exceeded max batches, stopping with {len(all_samples)} samples", flush=True)
                break

            time.sleep(1)

        all_samples = all_samples[:target_per_domain]

        output_path = os.path.join(DATA_DIR, domain_config["file"])
        with open(output_path, "w", encoding="utf-8") as f:
            for sample in all_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

        print(f"\n  ✅ {domain_key}: {len(all_samples)} samples → {output_path}", flush=True)

    # Summary
    print(f"\n{'='*60}", flush=True)
    print("=== SUMMARY ===", flush=True)
    print(f"{'='*60}", flush=True)
    for domain_key, domain_config in DOMAINS.items():
        path = os.path.join(DATA_DIR, domain_config["file"])
        if os.path.exists(path):
            with open(path, "r") as f:
                count = sum(1 for _ in f)
            size = os.path.getsize(path)
            print(f"  {domain_key}: {count} samples, {size/1024:.1f} KB", flush=True)


if __name__ == "__main__":
    main()
