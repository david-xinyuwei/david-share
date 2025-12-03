"""
EAGLE3 Speculative Decoding Performance Test Script

This script benchmarks the inference speed with and without speculative decoding.
Usage:
    python test_performance.py --server-url http://localhost:8080
"""

import requests
import time
import argparse
from typing import List, Tuple, Dict, Any


def generate(
    server_url: str,
    prompt: str,
    max_tokens: int = 200,
    temperature: float = 0.7
) -> Tuple[Dict[str, Any], float]:
    """
    Send a generation request to the server.
    
    Args:
        server_url: The URL of the SGLang server
        prompt: The input prompt
        max_tokens: Maximum number of tokens to generate
        temperature: Sampling temperature
        
    Returns:
        Tuple of (response dict, elapsed time in seconds)
    """
    start = time.time()
    response = requests.post(
        f"{server_url}/generate",
        json={
            "text": prompt,
            "sampling_params": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
            }
        }
    )
    elapsed = time.time() - start
    return response.json(), elapsed


def estimate_tokens(text: str) -> int:
    """Estimate token count (approximate: ~4 chars per token for English)"""
    return len(text) // 4


def run_benchmark(
    server_url: str,
    prompts: List[str],
    max_tokens: int = 200,
    temperature: float = 0.7,
    label: str = "Benchmark"
) -> Dict[str, float]:
    """
    Run benchmark on a list of prompts.
    
    Args:
        server_url: The URL of the SGLang server
        prompts: List of prompts to test
        max_tokens: Maximum tokens per generation
        temperature: Sampling temperature
        label: Label for this benchmark run
        
    Returns:
        Dict with benchmark statistics
    """
    print("=" * 60)
    print(f"{label}")
    print("=" * 60)
    
    total_tokens = 0
    total_time = 0
    results = []
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\n[Test {i}/{len(prompts)}] {prompt[:50]}...")
        
        result, elapsed = generate(server_url, prompt, max_tokens, temperature)
        text = result.get("text", "")
        tokens = estimate_tokens(text)
        speed = tokens / elapsed if elapsed > 0 else 0
        
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Tokens: ~{tokens}")
        print(f"  Speed: ~{speed:.1f} tok/s")
        
        results.append({
            "prompt": prompt[:50],
            "tokens": tokens,
            "time": elapsed,
            "speed": speed
        })
        
        total_tokens += tokens
        total_time += elapsed
    
    avg_speed = total_tokens / total_time if total_time > 0 else 0
    
    print("\n" + "-" * 60)
    print(f"SUMMARY: {total_tokens} tokens in {total_time:.2f}s")
    print(f"Average Speed: ~{avg_speed:.1f} tokens/s")
    print("=" * 60)
    
    return {
        "total_tokens": total_tokens,
        "total_time": total_time,
        "avg_speed": avg_speed,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="EAGLE3 Performance Benchmark")
    parser.add_argument(
        "--server-url",
        type=str,
        default="http://localhost:8080",
        help="SGLang server URL"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=200,
        help="Maximum tokens to generate per prompt"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Sampling temperature"
    )
    args = parser.parse_args()
    
    # Test prompts covering different domains
    test_prompts = [
        # Code generation (high predictability - EAGLE3 shines here)
        "Write a Python function to calculate fibonacci numbers recursively:",
        "Implement a binary search algorithm in Python:",
        
        # Technical explanation (medium predictability)  
        "Explain the concept of machine learning in simple terms:",
        "What are the key differences between Python and JavaScript?",
        
        # Creative/open-ended (low predictability - less benefit from EAGLE3)
        "Write a short story about a robot learning to paint:",
        "Describe a futuristic city in the year 2150:",
    ]
    
    # Check server connectivity
    print("Checking server connectivity...")
    try:
        info = requests.get(f"{args.server_url}/get_model_info", timeout=10).json()
        print(f"Connected to server!")
        print(f"Model: {info.get('model_path', 'unknown')}")
    except Exception as e:
        print(f"Failed to connect to server at {args.server_url}")
        print(f"Error: {e}")
        return
    
    print()
    
    # Run benchmark
    results = run_benchmark(
        server_url=args.server_url,
        prompts=test_prompts,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        label="EAGLE3 Speculative Decoding Performance Test"
    )
    
    print("\n" + "=" * 60)
    print("ANALYSIS")
    print("=" * 60)
    print("""
Expected performance patterns:
- Code generation tasks: Best speedup (1.2x-1.5x)
- Technical explanations: Moderate speedup (1.1x-1.2x)  
- Creative writing: Minimal speedup (~1.0x)

To compare with baseline:
1. Stop the current server
2. Restart without speculative decoding:
   python -m sglang.launch_server \\
       --model-path meta-llama/Llama-3.1-8B-Instruct \\
       --host 0.0.0.0 --port 8080
3. Run this script again
    """)


if __name__ == "__main__":
    main()
