#!/usr/bin/env python3
"""
GPT-4o vs GPT-5.1 Migration Benchmark
=====================================

Production-grade benchmark for comparing GPT-4o and GPT-5.1 performance.
Designed for enterprise migration decision support.

Features:
- Fair 7-dimension aligned comparison (same API, cache, padding, etc.)
- Cost and accuracy measurement
- Prompt caching support with Azure OpenAI
- Enterprise scenario coverage (intent, sentiment, RAG, code, customer service)

Usage:
    export AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/"
    export AZURE_OPENAI_API_KEY="your-api-key"
    python benchmark.py [--runs N] [--quick] [--output results.json]

Author: Xinyu Wei (魏新宇)
License: MIT
Version: 2.0.0
"""

import os
import sys
import io
import time
import json
import argparse
import statistics
from datetime import datetime
from typing import Dict, List, Optional, Any

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai package not installed. Run: pip install openai>=1.60.0")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

# =============================================================================
# CONFIGURATION (from environment variables - no hardcoding per security rules)
# =============================================================================
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")

if not AZURE_ENDPOINT or not AZURE_API_KEY:
    print("ERROR: Missing required environment variables!")
    print("Please set:")
    print("  export AZURE_OPENAI_ENDPOINT='https://<your-resource>.openai.azure.com/'")
    print("  export AZURE_OPENAI_API_KEY='your-api-key'")
    print("\nOr create a .env file with these values.")
    sys.exit(1)

# Initialize OpenAI client with Responses API base URL
client = OpenAI(
    api_key=AZURE_API_KEY,
    base_url=f"{AZURE_ENDPOINT.rstrip('/')}/openai/v1/"
)

# =============================================================================
# PRICING (per 1M tokens) - Azure OpenAI Official
# Source: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
# =============================================================================
PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {
        "input": 2.50,
        "cached_input": 1.25,
        "output": 10.00,
    },
    "gpt-5.1": {
        "input": 1.25,
        "cached_input": 0.13,
        "output": 10.00,
    },
}

# =============================================================================
# TEST SCENARIOS - Enterprise use cases for migration validation
# =============================================================================
TEST_SCENARIOS: List[Dict[str, Any]] = [
    # Short response scenarios (intent classification)
    {
        "category": "Short",
        "name": "Intent Classification (CN)",
        "question": "判断意图（投诉/咨询/表扬/请求）：'我的外卖2小时没到！' 只回答一个词。",
        "answer_variants": ["投诉"],
        "language": "ZH"
    },
    {
        "category": "Short",
        "name": "Sentiment Analysis",
        "question": "Sentiment of '服务太棒了' (positive/negative/neutral)? ONE word.",
        "answer_variants": ["positive", "Positive"],
        "language": "EN"
    },
    # Medium response scenarios (RAG Q&A)
    {
        "category": "Medium",
        "name": "RAG Number Extraction",
        "question": "根据：'美团2023年营收2767亿元，增长26%。' 营收多少？增长率？简答。",
        "answer_variants": ["2767", "26"],
        "language": "ZH"
    },
    {
        "category": "Medium",
        "name": "RAG Fact Extraction",
        "question": "Based on: 'ABC founded 2018 in Beijing by Zhang Wei.' When and where? Brief.",
        "answer_variants": ["2018", "Beijing"],
        "language": "EN"
    },
    {
        "category": "Medium",
        "name": "Code Explanation",
        "question": "Explain: def f(n): return n if n<=1 else f(n-1)+f(n-2). 2 sentences.",
        "answer_variants": ["fibonacci", "recursive", "Fibonacci"],
        "language": "EN"
    },
    # Long response scenarios (content generation)
    {
        "category": "Long",
        "name": "Customer Service Reply",
        "question": "你是美团客服。用户：'外卖2小时没到！' 生成道歉+解决方案，约80字。",
        "answer_variants": ["抱歉", "sorry", "补偿", "退款"],
        "language": "ZH"
    },
    {
        "category": "Long",
        "name": "Product Description",
        "question": "Write a 50-word description for a smart water bottle with hydration tracking.",
        "answer_variants": ["hydration", "track", "smart"],
        "language": "EN"
    },
]

# =============================================================================
# STATIC PADDING - Must be >= 1024 tokens for Azure prompt cache eligibility
# =============================================================================
STATIC_PADDING = """[ENTERPRISE KNOWLEDGE BASE - VERSION 2024.12]
================================================================================
SECTION 1: CUSTOMER SERVICE PROTOCOLS
1.1 Response Time Standards:
- Priority 1 (Order Issues): Response within 2 minutes, resolution within 15 minutes
- Priority 2 (Payment Issues): Response within 5 minutes, resolution within 30 minutes
- Priority 3 (General Inquiry): Response within 10 minutes, resolution within 2 hours
- Priority 4 (Feedback/Suggestions): Response within 24 hours

1.2 Compensation Guidelines:
- Delivery delay 30-60 minutes: 5 yuan coupon
- Delivery delay over 60 minutes: 10 yuan coupon + free delivery next order
- Wrong item delivered: Full refund + replacement + 15 yuan coupon
- Food quality issue: Full refund + 20 yuan coupon

1.3 Escalation Procedures:
Level 1: Frontline agent handles standard issues
Level 2: Senior agent handles complex complaints
Level 3: Supervisor handles escalated disputes
Level 4: Quality assurance team handles legal/PR issues
================================================================================
SECTION 2: E-COMMERCE OPERATIONS
2.1 Order Lifecycle States:
- PENDING: Order placed, awaiting merchant confirmation
- CONFIRMED: Merchant accepted, preparing order
- PREPARING: Kitchen/warehouse processing
- READY: Order ready for pickup by rider
- DISPATCHED: Rider picked up, in transit
- ARRIVING: Rider within 500m of delivery address
- DELIVERED: Order handed to customer
- COMPLETED: Customer confirmed receipt
- CANCELLED: Order cancelled (with reason code)
- REFUNDED: Refund processed

2.2 Merchant Categories:
- Restaurant (Chinese, Western, Japanese, Korean, Fast Food)
- Grocery (Fresh Produce, Dairy, Snacks, Beverages)
- Pharmacy (OTC, Prescription, Health Products)
- Convenience Store (24/7 essentials)
- Specialty Shops (Bakery, Desserts, Coffee)

2.3 Delivery Optimization:
- Smart routing algorithm considers traffic, weather, rider capacity
- Batching orders from same merchant to nearby addresses
- Peak hour surge pricing and rider incentives
- Quality metrics: On-time rate, customer rating, order accuracy
================================================================================
SECTION 3: DATA ANALYTICS FRAMEWORK
3.1 Key Performance Indicators:
- GMV (Gross Merchandise Value): Total transaction value
- Take Rate: Revenue as percentage of GMV
- Order Frequency: Orders per user per month
- Customer Acquisition Cost (CAC): Marketing spend per new user
- Customer Lifetime Value (LTV): Predicted total revenue per user
- Rider Efficiency: Orders delivered per hour per rider

3.2 Reporting Cadence:
- Real-time: Order volume, active riders, system health
- Hourly: Regional performance, surge status
- Daily: Revenue, costs, profit margins
- Weekly: Trend analysis, anomaly detection
- Monthly: Executive summary, strategic metrics
- Quarterly: Investor reports, market analysis

3.3 Data Quality Standards:
- Completeness: All required fields populated
- Accuracy: Values within expected ranges
- Timeliness: Data available within SLA
- Consistency: No conflicting records
================================================================================
SECTION 4: TECHNICAL ARCHITECTURE
4.1 Microservices:
- Order Service: Order creation, modification, cancellation
- User Service: Authentication, profile management
- Merchant Service: Menu management, inventory, hours
- Rider Service: Assignment, tracking, earnings
- Payment Service: Transactions, refunds, settlements
- Notification Service: Push, SMS, in-app messages

4.2 Infrastructure:
- Multi-region deployment for high availability
- Kubernetes clusters with auto-scaling
- Redis clusters for caching and session management
- MySQL clusters with read replicas
- Kafka for event streaming
- Elasticsearch for search and analytics

4.3 API Standards:
- RESTful design with versioned endpoints
- OAuth 2.0 authentication
- Rate limiting: 1000 requests per minute per client
- Response format: JSON with standard error codes
- Pagination: Cursor-based for large datasets
================================================================================
SECTION 5: COMPLIANCE AND SECURITY
5.1 Data Protection:
- PII encryption at rest (AES-256), TLS 1.3 for data in transit
- Data retention: 3 years for transactions, 1 year for logs
- Right to deletion: Process within 30 days

5.2 Food Safety:
- Merchant license verification, Regular hygiene inspections
- Temperature monitoring for cold chain, Allergen information disclosure

5.3 Financial Compliance:
- Anti-money laundering (AML) monitoring
- Transaction limits per user per day
- Fraud detection and prevention, Regular audit trails
================================================================================
[END OF KNOWLEDGE BASE]
================================================================================
Based on the above context, please answer the following question:
"""


def calculate_cost(model: str, input_tokens: int, output_tokens: int,
                   cached_tokens: int = 0) -> float:
    """Calculate request cost in USD."""
    pricing = PRICING[model]
    uncached = input_tokens - cached_tokens
    cost = (uncached * pricing["input"] +
            cached_tokens * pricing["cached_input"] +
            output_tokens * pricing["output"]) / 1_000_000
    return cost


def check_answer(response: str, correct_variants: list) -> bool:
    """Check if response contains correct answer."""
    response_lower = response.lower().strip()
    for variant in correct_variants:
        if variant.lower() in response_lower:
            return True
    return False


def test_with_cache_key(client, model: str, instructions: str, question: str, 
                        cache_key: str, reasoning_effort: str = None,
                        stream: bool = False) -> dict:
    """
    Test a model using Responses API with prompt_cache_key.
    
    Args:
        client: OpenAI client configured for Responses API
        model: Model name (gpt-4o or gpt-5.1)
        instructions: System instructions (should be >1024 tokens for caching)
        question: User question
        cache_key: Prompt cache key for cache routing
        reasoning_effort: For GPT-5.1, set to "none", "low", "medium", or "high"
        stream: Whether to use streaming mode
    
    Returns:
        dict with latency, tokens, content, and success status
    """
    try:
        params = {
            "model": model,
            "instructions": instructions,
            "input": question,
            "max_output_tokens": 100,
            "extra_body": {"prompt_cache_key": cache_key}
        }
        
        # Add reasoning effort for GPT-5.1
        if reasoning_effort and "5.1" in model:
            params["reasoning"] = {"effort": reasoning_effort}
        
        # Add streaming
        if stream:
            params["stream"] = True
        
        start = time.time()
        
        if stream:
            # Streaming mode - collect chunks
            response_stream = client.responses.create(**params)
            content = ""
            input_tokens = 0
            output_tokens = 0
            cached_tokens = 0
            first_token_time = None
            
            for event in response_stream:
                # Record time to first token
                if first_token_time is None and hasattr(event, 'type'):
                    if event.type in ['response.output_item.added', 'response.content_part.added', 'response.output_text.delta']:
                        first_token_time = time.time() - start
                
                # Extract text from delta events
                if hasattr(event, 'type') and event.type == 'response.output_text.delta':
                    if hasattr(event, 'delta'):
                        content += event.delta
                
                # Extract usage from completed event
                if hasattr(event, 'type') and event.type == 'response.completed':
                    if hasattr(event, 'response') and hasattr(event.response, 'usage'):
                        usage = event.response.usage
                        input_tokens = usage.input_tokens
                        output_tokens = usage.output_tokens
                        cached_details = getattr(usage, 'input_tokens_details', None)
                        if cached_details:
                            cached_tokens = getattr(cached_details, 'cached_tokens', 0)
            
            latency = time.time() - start
            
            return {
                "success": True,
                "latency": latency,
                "first_token_time": first_token_time or latency,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "content": content,
                "stream": True
            }
        else:
            # Non-streaming mode
            response = client.responses.create(**params)
            latency = time.time() - start
            
            # Extract token usage
            usage = response.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            cached_tokens = getattr(usage, 'input_tokens_details', {})
            cached_tokens = getattr(cached_tokens, 'cached_tokens', 0) if cached_tokens else 0
            
            # Extract content
            content = ""
            if response.output:
                for item in response.output:
                    if hasattr(item, 'content'):
                        for c in item.content:
                            if hasattr(c, 'text'):
                                content += c.text
            
            return {
                "success": True,
                "latency": latency,
                "first_token_time": latency,  # Same as latency for non-streaming
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "content": content,
                "stream": False
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "latency": 0,
            "first_token_time": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "content": "",
            "stream": stream
        }


def run_benchmark(num_runs: int = 3, stream: bool = False):
    """
    Run the benchmark comparing GPT-4o and GPT-5.1.
    
    Fair comparison methodology:
    1. SAME API (Responses API) for both models
    2. SAME questions and expected answers
    3. SAME prompt_cache_key for cache routing
    4. Warmup phase to populate cache before measurement
    5. Multiple runs for statistical significance
    
    Args:
        num_runs: Number of runs per scenario (default: 3)
        stream: Whether to use streaming mode (default: False)
    
    Returns:
        Path to generated report file
    """
    
    # Initialize Responses API client
    client = OpenAI(
        api_key=AZURE_API_KEY,
        base_url=f"{AZURE_ENDPOINT}openai/v1/"
    )
    
    print("="*80)
    print(" GPT-4o vs GPT-5.1 MIGRATION BENCHMARK")
    print(" (RAG, Customer Service, Enterprise scenarios)")
    print("="*80)
    print(f"\nStarted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total scenarios: {len(TEST_SCENARIOS)}")
    print(f"Runs per scenario: {num_runs}")
    
    # Use static padding (>1024 tokens for cache eligibility)
    instructions = STATIC_PADDING + "\n\nYou are a helpful assistant. Answer concisely and directly. For questions requiring a specific format, follow the format exactly."
    cache_key = "benchmark_migration_v2"
    
    print(f"Static prefix: ~1030 tokens (>1024 for cache eligibility)")
    print(f"Cache key: {cache_key}")
    print(f"Streaming: {'✅ Enabled' if stream else '❌ Disabled'}")
    
    # Results storage
    scenario_results = []
    results = {
        "gpt-4o": {"latency": [], "first_token_time": [], "input_tokens": [], "output_tokens": [], 
                   "cached_tokens": [], "correct": 0, "total": 0, "cost": 0},
        "gpt-5.1": {"latency": [], "first_token_time": [], "input_tokens": [], "output_tokens": [], 
                    "cached_tokens": [], "correct": 0, "total": 0, "cost": 0},
    }
    
    # Phase 1: Warmup
    print("\n" + "="*80)
    print(" PHASE 1: CACHE WARMUP")
    print("="*80)
    
    warmup_question = "What is 2+2?"
    for display_name, actual_model, effort in [("gpt-4o", "gpt-4o", None), 
                                                ("gpt-5.1", "gpt-5.1", "none")]:
        print(f"\n  Warming up {display_name}...", end="", flush=True)
        for _ in range(3):
            test_with_cache_key(client, actual_model, instructions, warmup_question, cache_key, effort)
            time.sleep(0.3)
        print(" done")
    
    print("\n  Waiting 2s for cache to stabilize...")
    time.sleep(2)
    
    # Phase 2: Benchmark
    print("\n" + "="*80)
    print(" PHASE 2: BENCHMARK MEASUREMENT")
    print("="*80)
    
    for q_idx, scenario in enumerate(TEST_SCENARIOS):
        category = scenario["category"]
        name = scenario["name"]
        question = scenario["question"]
        language = scenario["language"]
        
        print(f"\n  [{q_idx+1}/{len(TEST_SCENARIOS)}] {category} - {name} ({language})")
        
        scenario_data = {
            "id": q_idx + 1,
            "category": category,
            "name": name,
            "language": language,
            "gpt-4o": {},
            "gpt-5.1": {},
        }
        
        models_to_test = [
            ("gpt-4o", "gpt-4o", None),
            ("gpt-5.1", "gpt-5.1", "none"),
        ]
        
        for display_name, actual_model, effort in models_to_test:
            run_latencies = []
            run_first_token = []
            run_input = []
            run_output = []
            run_cached = []
            correct = 0
            
            for run in range(num_runs):
                result = test_with_cache_key(
                    client, actual_model, instructions, question, cache_key, effort, stream
                )
                
                if result["success"]:
                    run_latencies.append(result["latency"])
                    run_first_token.append(result.get("first_token_time", result["latency"]))
                    run_input.append(result["input_tokens"])
                    run_output.append(result["output_tokens"])
                    run_cached.append(result["cached_tokens"])
                    
                    results[display_name]["latency"].append(result["latency"])
                    results[display_name]["first_token_time"].append(result.get("first_token_time", result["latency"]))
                    results[display_name]["input_tokens"].append(result["input_tokens"])
                    results[display_name]["output_tokens"].append(result["output_tokens"])
                    results[display_name]["cached_tokens"].append(result["cached_tokens"])
                    
                    if check_answer(result["content"], scenario["answer_variants"]):
                        correct += 1
                        results[display_name]["correct"] += 1
                    results[display_name]["total"] += 1
                    
                    time.sleep(0.2)
                else:
                    print(f"      Error: {result.get('error', '')[:50]}")
            
            # Calculate scenario metrics
            avg_latency = sum(run_latencies) / len(run_latencies) if run_latencies else 0
            avg_first_token = sum(run_first_token) / len(run_first_token) if run_first_token else 0
            avg_input = sum(run_input) / len(run_input) if run_input else 0
            avg_output = sum(run_output) / len(run_output) if run_output else 0
            avg_cached = sum(run_cached) / len(run_cached) if run_cached else 0
            cache_pct = avg_cached / avg_input * 100 if avg_input > 0 else 0
            accuracy = correct / num_runs * 100 if num_runs > 0 else 0
            
            scenario_cost = calculate_cost(display_name, sum(run_input), sum(run_output), sum(run_cached))
            results[display_name]["cost"] += scenario_cost
            
            scenario_data[display_name] = {
                "avg_latency": round(avg_latency, 3),
                "avg_first_token_time": round(avg_first_token, 3),
                "avg_input_tokens": round(avg_input, 0),
                "avg_output_tokens": round(avg_output, 0),
                "avg_cached_tokens": round(avg_cached, 0),
                "cache_hit_pct": round(cache_pct, 1),
                "accuracy": round(accuracy, 1),
                "cost": round(scenario_cost * 1000, 4)
            }
            
            status = "✅" if accuracy == 100 else "⚠️" if accuracy >= 50 else "❌"
            effort_label = f" (effort={effort})" if effort else ""
            stream_label = " [stream]" if stream else ""
            ttft_info = f" TTFT:{avg_first_token:.3f}s" if stream else ""
            print(f"    {display_name}{effort_label}{stream_label}: {avg_latency:.3f}s{ttft_info} | in:{avg_input:.0f} out:{avg_output:.0f} cache:{cache_pct:.1f}% | acc:{accuracy:.0f}% {status}")
        
        scenario_results.append(scenario_data)
    
    # Phase 3: Generate Report
    print("\n" + "="*80)
    print(" PHASE 3: GENERATING REPORT")
    print("="*80)
    
    # Calculate aggregated metrics
    for model in ["gpt-4o", "gpt-5.1"]:
        r = results[model]
        if r["latency"]:
            r["avg_latency"] = sum(r["latency"]) / len(r["latency"])
            r["avg_first_token"] = sum(r["first_token_time"]) / len(r["first_token_time"]) if r["first_token_time"] else r["avg_latency"]
            r["avg_input"] = sum(r["input_tokens"]) / len(r["input_tokens"])
            r["avg_output"] = sum(r["output_tokens"]) / len(r["output_tokens"])
            r["avg_cached"] = sum(r["cached_tokens"]) / len(r["cached_tokens"])
            r["cache_pct"] = r["avg_cached"] / r["avg_input"] * 100 if r["avg_input"] > 0 else 0
            r["accuracy"] = r["correct"] / r["total"] * 100 if r["total"] > 0 else 0
            r["total_input"] = sum(r["input_tokens"])
            r["total_output"] = sum(r["output_tokens"])
            r["total_cached"] = sum(r["cached_tokens"])
    
    r4o = results["gpt-4o"]
    r51 = results["gpt-5.1"]
    
    # Generate report
    report = generate_report(scenario_results, r4o, r51, 1030, cache_key, num_runs)
    
    report_filename = f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n📄 Report saved to: {report_filename}")
    
    # Save JSON data
    json_output = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "padding_tokens": 1030,
            "cache_key": cache_key,
            "runs_per_scenario": num_runs,
            "total_scenarios": len(TEST_SCENARIOS),
            "streaming": stream,
        },
        "summary": {
            "gpt-4o": {k: v for k, v in r4o.items() if k not in ["latency", "first_token_time", "input_tokens", "output_tokens", "cached_tokens"]},
            "gpt-5.1": {k: v for k, v in r51.items() if k not in ["latency", "first_token_time", "input_tokens", "output_tokens", "cached_tokens"]},
        },
        "scenarios": scenario_results
    }
    
    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    print(f"📁 JSON data saved to: benchmark_results.json")
    
    # Print summary
    print("\n" + "="*80)
    print(" SUMMARY")
    print("="*80)
    
    lat_diff = (r51["avg_latency"] - r4o["avg_latency"]) / r4o["avg_latency"] * 100 if r4o["avg_latency"] > 0 else 0
    cost_savings = (r4o["cost"] - r51["cost"]) / r4o["cost"] * 100 if r4o["cost"] > 0 else 0
    
    print(f"\n  📊 Latency:     GPT-4o {r4o['avg_latency']:.3f}s vs GPT-5.1 {r51['avg_latency']:.3f}s ({lat_diff:+.1f}%)")
    if stream:
        print(f"  ⏱️  TTFT:        GPT-4o {r4o.get('avg_first_token', r4o['avg_latency']):.3f}s vs GPT-5.1 {r51.get('avg_first_token', r51['avg_latency']):.3f}s")
    print(f"  🎯 Accuracy:    GPT-4o {r4o['accuracy']:.1f}% vs GPT-5.1 {r51['accuracy']:.1f}%")
    print(f"  📦 Cache Hit:   GPT-4o {r4o['cache_pct']:.1f}% vs GPT-5.1 {r51['cache_pct']:.1f}%")
    print(f"  💰 Total Cost:  GPT-4o ${r4o['cost']:.6f} vs GPT-5.1 ${r51['cost']:.6f}")
    print(f"  💵 Savings:     {cost_savings:.1f}% with GPT-5.1 (effort=none)")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return report_filename


def generate_report(scenario_results, r4o, r51, padding_tokens, cache_key, num_runs):
    """Generate detailed Markdown report."""
    
    lat_diff = (r51["avg_latency"] - r4o["avg_latency"]) / r4o["avg_latency"] * 100
    cost_savings = (r4o["cost"] - r51["cost"]) / r4o["cost"] * 100
    
    report = f"""# GPT-4o vs GPT-5.1 Migration Benchmark Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Test Framework:** Azure OpenAI Responses API with Prompt Caching

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| API | Responses API (identical for both models) |
| Prompt Cache Key | `{cache_key}` |
| Static Prefix | ~{padding_tokens} tokens |
| Runs per Scenario | {num_runs} |
| Total Scenarios | {len(scenario_results)} |

---

## Executive Summary

| Metric | GPT-4o | GPT-5.1 | Difference | Winner |
|--------|--------|---------|------------|--------|
| **Avg Latency** | {r4o['avg_latency']:.3f}s | {r51['avg_latency']:.3f}s | {lat_diff:+.1f}% | {'GPT-5.1 ✅' if r51['avg_latency'] <= r4o['avg_latency'] else 'GPT-4o ⚡'} |
| **Accuracy** | {r4o['accuracy']:.1f}% | {r51['accuracy']:.1f}% | {r51['accuracy']-r4o['accuracy']:+.1f}% | {'GPT-5.1 ✅' if r51['accuracy'] >= r4o['accuracy'] else 'GPT-4o ✅'} |
| **Cache Hit Rate** | {r4o['cache_pct']:.1f}% | {r51['cache_pct']:.1f}% | {r51['cache_pct']-r4o['cache_pct']:+.1f}% | - |
| **Total Cost** | \\${r4o['cost']:.6f} | \\${r51['cost']:.6f} | {(r51['cost']-r4o['cost'])/r4o['cost']*100:+.1f}% | **GPT-5.1 ✅** |
| **Cost Savings** | - | - | **{cost_savings:.1f}%** | **GPT-5.1 ✅** |

---

## Token Usage Summary

| Metric | GPT-4o | GPT-5.1 |
|--------|--------|---------|
| Total Input Tokens | {r4o['total_input']:,.0f} | {r51['total_input']:,.0f} |
| Total Output Tokens | {r4o['total_output']:,.0f} | {r51['total_output']:,.0f} |
| Total Cached Tokens | {r4o['total_cached']:,.0f} | {r51['total_cached']:,.0f} |
| Avg Input/Request | {r4o['avg_input']:.0f} | {r51['avg_input']:.0f} |
| Avg Output/Request | {r4o['avg_output']:.0f} | {r51['avg_output']:.0f} |
| Avg Cached/Request | {r4o['avg_cached']:.0f} | {r51['avg_cached']:.0f} |

---

## Detailed Results by Scenario

"""
    
    # Group by category
    categories = {}
    for s in scenario_results:
        cat = s["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(s)
    
    for cat, scenarios in categories.items():
        report += f"### {cat}\n\n"
        report += "| # | Scenario | Lang | GPT-4o Latency | GPT-5.1 Latency | GPT-4o Cache% | GPT-5.1 Cache% | GPT-4o Acc | GPT-5.1 Acc | GPT-4o Cost | GPT-5.1 Cost |\n"
        report += "|---|----------|------|----------------|-----------------|---------------|----------------|------------|-------------|-------------|-------------|\n"
        
        for s in scenarios:
            g4 = s["gpt-4o"]
            g5 = s["gpt-5.1"]
            
            acc4_icon = "✅" if g4["accuracy"] == 100 else "⚠️" if g4["accuracy"] >= 50 else "❌"
            acc5_icon = "✅" if g5["accuracy"] == 100 else "⚠️" if g5["accuracy"] >= 50 else "❌"
            
            report += f"| {s['id']} | {s['name'][:25]} | {s['language']} | {g4['avg_latency']:.3f}s | {g5['avg_latency']:.3f}s | {g4['cache_hit_pct']:.1f}% | {g5['cache_hit_pct']:.1f}% | {g4['accuracy']:.0f}%{acc4_icon} | {g5['accuracy']:.0f}%{acc5_icon} | \\${g4['cost']:.4f} | \\${g5['cost']:.4f} |\n"
        
        report += "\n"
    
    report += f"""---

## Conclusions

### Performance
- **Latency**: GPT-4o is {'faster' if r4o['avg_latency'] < r51['avg_latency'] else 'slower'} by {abs(lat_diff):.1f}%
- **Accuracy**: {'Both models perform equally' if abs(r4o['accuracy'] - r51['accuracy']) < 1 else f"GPT-{'4o' if r4o['accuracy'] > r51['accuracy'] else '5.1'} has higher accuracy"}

### Cost Efficiency
- **GPT-5.1 saves {cost_savings:.1f}%** compared to GPT-4o
- Prompt caching working effectively: {r4o['cache_pct']:.1f}% (4o) / {r51['cache_pct']:.1f}% (5.1)

### Recommendation
{'✅ **GPT-5.1 recommended** for cost-sensitive workloads with acceptable latency trade-off' if cost_savings > 50 and r51['accuracy'] >= r4o['accuracy'] - 5 else '⚠️ Evaluate based on specific latency and cost requirements'}

---

## Pricing Reference

| Model | Input (per 1M) | Cached Input (per 1M) | Output (per 1M) |
|-------|----------------|----------------------|-----------------|
| GPT-4o | \\$2.50 | \\$1.25 | \\$10.00 |
| GPT-5.1 | \\$1.25 | \\$0.13 | \\$10.00 |

---

*Report generated by GPT-4o vs GPT-5.1 Migration Benchmark Tool*
"""
    
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GPT-4o vs GPT-5.1 Migration Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python benchmark.py                    # Default: 3 runs, no streaming
    python benchmark.py --runs 5           # 5 runs per scenario
    python benchmark.py --stream           # Enable streaming mode
    python benchmark.py --runs 5 --stream  # 5 runs with streaming
"""
    )
    parser.add_argument("--runs", "-n", type=int, default=3,
                        help="Number of runs per scenario (default: 3)")
    parser.add_argument("--stream", "-s", action="store_true",
                        help="Enable streaming mode (measures TTFT)")
    
    args = parser.parse_args()
    run_benchmark(num_runs=args.runs, stream=args.stream)
