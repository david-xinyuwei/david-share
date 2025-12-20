#!/usr/bin/env python3
"""
SGLang FP8 Benchmark Script for RTX PRO 6000 (Blackwell) GPU
Author: Xinyu Wei (Microsoft GBB AI Architect)
Date: 2025-12-18

This script automates SGLang FP8 benchmark tests with 8 configurations:
- Model: BF16 vs FP8-dynamic
- Backend: FlashInfer vs Triton
- KV Cache: auto vs fp8_e5m2

The script uses sglang.bench_serving for accurate performance measurement.

Prerequisites:
    pip install sglang[all] flashinfer triton

Usage:
    # Run specific config:
    python benchmark_sglang.py --config bf16_flashinfer_auto

    # Run all 8 configs (takes ~40 minutes):
    python benchmark_sglang.py --all

    # Just show available configs:
    python benchmark_sglang.py --list

For vLLM (H100/A100), use benchmark.py instead.
"""

import subprocess
import time
import argparse
import json
import re
import signal
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class BenchmarkConfig:
    """Configuration for a single benchmark run"""
    name: str
    model: str
    attention_backend: str  # flashinfer or triton
    kv_cache_dtype: str     # auto or fp8_e5m2
    is_fp8_model: bool


# Define all 8 test configurations
CONFIGS: Dict[str, BenchmarkConfig] = {
    # BF16 Model (Qwen2.5-14B-Instruct)
    "bf16_flashinfer_auto": BenchmarkConfig(
        name="BF16 + FlashInfer + KV auto",
        model="Qwen/Qwen2.5-14B-Instruct",
        attention_backend="flashinfer",
        kv_cache_dtype="auto",
        is_fp8_model=False
    ),
    "bf16_flashinfer_fp8": BenchmarkConfig(
        name="BF16 + FlashInfer + KV FP8",
        model="Qwen/Qwen2.5-14B-Instruct",
        attention_backend="flashinfer",
        kv_cache_dtype="fp8_e5m2",
        is_fp8_model=False
    ),
    "bf16_triton_auto": BenchmarkConfig(
        name="BF16 + Triton + KV auto",
        model="Qwen/Qwen2.5-14B-Instruct",
        attention_backend="triton",
        kv_cache_dtype="auto",
        is_fp8_model=False
    ),
    "bf16_triton_fp8": BenchmarkConfig(
        name="BF16 + Triton + KV FP8",
        model="Qwen/Qwen2.5-14B-Instruct",
        attention_backend="triton",
        kv_cache_dtype="fp8_e5m2",
        is_fp8_model=False
    ),
    # FP8 Model (RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic)
    "fp8_flashinfer_auto": BenchmarkConfig(
        name="FP8 + FlashInfer + KV auto",
        model="RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic",
        attention_backend="flashinfer",
        kv_cache_dtype="auto",
        is_fp8_model=True
    ),
    "fp8_flashinfer_fp8": BenchmarkConfig(
        name="FP8 + FlashInfer + KV FP8",
        model="RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic",
        attention_backend="flashinfer",
        kv_cache_dtype="fp8_e5m2",
        is_fp8_model=True
    ),
    "fp8_triton_auto": BenchmarkConfig(
        name="FP8 + Triton + KV auto",
        model="RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic",
        attention_backend="triton",
        kv_cache_dtype="auto",
        is_fp8_model=True
    ),
    "fp8_triton_fp8": BenchmarkConfig(
        name="FP8 + Triton + KV FP8 ⭐",  # Best config
        model="RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic",
        attention_backend="triton",
        kv_cache_dtype="fp8_e5m2",
        is_fp8_model=True
    ),
}


@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""
    config_name: str
    output_throughput: float  # tok/s
    total_latency: float      # seconds
    ttft_avg: float           # Time to First Token (ms)
    itl_avg: float            # Inter-Token Latency (ms)
    success: bool
    error_msg: str = ""


def build_server_cmd(config: BenchmarkConfig, port: int = 30000) -> List[str]:
    """Build SGLang server launch command"""
    cmd = [
        "python", "-m", "sglang.launch_server",
        "--model-path", config.model,
        "--port", str(port),
        "--mem-fraction-static", "0.85",
        "--attention-backend", config.attention_backend,
        "--kv-cache-dtype", config.kv_cache_dtype,
    ]
    return cmd


def build_benchmark_cmd(port: int = 30000, num_prompts: int = 200) -> List[str]:
    """Build benchmark command using sglang.bench_serving"""
    cmd = [
        "python", "-m", "sglang.bench_serving",
        "--backend", "sglang",
        "--num-prompts", str(num_prompts),
        "--random-input-len", "1024",
        "--random-output-len", "512",
        "--host", "localhost",
        "--port", str(port),
    ]
    return cmd


def wait_for_server(port: int = 30000, timeout: int = 300) -> bool:
    """Wait for SGLang server to be ready"""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            if result == 0:
                # Additional check: try health endpoint
                import urllib.request
                try:
                    urllib.request.urlopen(f"http://localhost:{port}/health", timeout=5)
                    return True
                except:
                    pass
        except:
            pass
        time.sleep(5)
        print(".", end="", flush=True)
    return False


def parse_benchmark_output(output: str) -> Dict:
    """Parse sglang.bench_serving output to extract metrics"""
    results = {
        "output_throughput": 0.0,
        "total_latency": 0.0,
        "ttft_avg": 0.0,
        "itl_avg": 0.0,
    }
    
    # Parse Output token throughput
    match = re.search(r"Output token throughput:\s+([\d.]+)\s+tok/s", output)
    if match:
        results["output_throughput"] = float(match.group(1))
    
    # Parse Total latency
    match = re.search(r"Total latency:\s+([\d.]+)\s+s", output)
    if match:
        results["total_latency"] = float(match.group(1))
    
    # Parse TTFT (Time to First Token)
    match = re.search(r"Mean TTFT:\s+([\d.]+)\s+ms", output)
    if match:
        results["ttft_avg"] = float(match.group(1))
    
    # Parse ITL (Inter-Token Latency)
    match = re.search(r"Mean ITL:\s+([\d.]+)\s+ms", output)
    if match:
        results["itl_avg"] = float(match.group(1))
    
    return results


def run_benchmark(config_key: str, port: int = 30000, num_prompts: int = 200) -> BenchmarkResult:
    """Run a single benchmark configuration"""
    config = CONFIGS[config_key]
    print(f"\n{'='*70}")
    print(f"Running: {config.name}")
    print(f"{'='*70}")
    print(f"  Model: {config.model}")
    print(f"  Backend: {config.attention_backend}")
    print(f"  KV Cache: {config.kv_cache_dtype}")
    
    server_proc = None
    try:
        # Start server
        print(f"\n  Starting SGLang server on port {port}...")
        server_cmd = build_server_cmd(config, port)
        print(f"  Command: {' '.join(server_cmd)}")
        
        server_proc = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
        )
        
        # Wait for server to be ready
        print("  Waiting for server to be ready", end="")
        if not wait_for_server(port, timeout=300):
            return BenchmarkResult(
                config_name=config.name,
                output_throughput=0,
                total_latency=0,
                ttft_avg=0,
                itl_avg=0,
                success=False,
                error_msg="Server startup timeout"
            )
        print(" Ready!")
        
        # Run benchmark
        print(f"\n  Running benchmark with {num_prompts} prompts...")
        bench_cmd = build_benchmark_cmd(port, num_prompts)
        print(f"  Command: {' '.join(bench_cmd)}")
        
        result = subprocess.run(
            bench_cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode != 0:
            print(f"  Benchmark failed: {result.stderr}")
            return BenchmarkResult(
                config_name=config.name,
                output_throughput=0,
                total_latency=0,
                ttft_avg=0,
                itl_avg=0,
                success=False,
                error_msg=result.stderr[:200]
            )
        
        # Parse results
        metrics = parse_benchmark_output(result.stdout)
        print(f"\n  Results:")
        print(f"    Output Throughput: {metrics['output_throughput']:.2f} tok/s")
        print(f"    Total Latency: {metrics['total_latency']:.2f} s")
        print(f"    TTFT (avg): {metrics['ttft_avg']:.2f} ms")
        print(f"    ITL (avg): {metrics['itl_avg']:.2f} ms")
        
        return BenchmarkResult(
            config_name=config.name,
            output_throughput=metrics["output_throughput"],
            total_latency=metrics["total_latency"],
            ttft_avg=metrics["ttft_avg"],
            itl_avg=metrics["itl_avg"],
            success=True
        )
        
    except subprocess.TimeoutExpired:
        return BenchmarkResult(
            config_name=config.name,
            output_throughput=0,
            total_latency=0,
            ttft_avg=0,
            itl_avg=0,
            success=False,
            error_msg="Benchmark timeout"
        )
    except Exception as e:
        return BenchmarkResult(
            config_name=config.name,
            output_throughput=0,
            total_latency=0,
            ttft_avg=0,
            itl_avg=0,
            success=False,
            error_msg=str(e)
        )
    finally:
        # Cleanup server
        if server_proc:
            print("\n  Stopping server...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()
            time.sleep(5)  # Wait for port to be released


def print_comparison_table(results: List[BenchmarkResult]):
    """Print results in comparison table format"""
    print(f"\n{'='*100}")
    print("Benchmark Results Summary")
    print(f"{'='*100}")
    print(f"{'Configuration':<35} {'Throughput':>12} {'TTFT':>10} {'ITL':>10} {'Status':>10}")
    print(f"{'-'*35} {'-'*12} {'-'*10} {'-'*10} {'-'*10}")
    
    # Find baseline (bf16_flashinfer_auto)
    baseline = next((r for r in results if "BF16 + FlashInfer + KV auto" in r.config_name), None)
    baseline_throughput = baseline.output_throughput if baseline and baseline.success else 1
    
    for r in results:
        if r.success:
            delta = ((r.output_throughput / baseline_throughput) - 1) * 100 if baseline_throughput > 0 else 0
            delta_str = f"({delta:+.0f}%)" if delta != 0 else ""
            print(f"{r.config_name:<35} {r.output_throughput:>8.1f} tok/s {r.ttft_avg:>7.1f} ms {r.itl_avg:>7.1f} ms {'✓':>10}")
        else:
            print(f"{r.config_name:<35} {'N/A':>12} {'N/A':>10} {'N/A':>10} {'✗':>10}")
    
    # Find best config
    successful = [r for r in results if r.success]
    if successful:
        best = max(successful, key=lambda r: r.output_throughput)
        improvement = ((best.output_throughput / baseline_throughput) - 1) * 100 if baseline_throughput > 0 else 0
        print(f"\n{'='*100}")
        print(f"Best Config: {best.config_name}")
        print(f"  Throughput: {best.output_throughput:.2f} tok/s ({improvement:+.1f}% vs baseline)")
        print(f"  TTFT: {best.ttft_avg:.2f} ms")
        print(f"  ITL: {best.itl_avg:.2f} ms")


def save_results(results: List[BenchmarkResult], filename: str = "benchmark_results.json"):
    """Save results to JSON file"""
    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": [
            {
                "config": r.config_name,
                "output_throughput": r.output_throughput,
                "total_latency": r.total_latency,
                "ttft_avg": r.ttft_avg,
                "itl_avg": r.itl_avg,
                "success": r.success,
                "error": r.error_msg
            }
            for r in results
        ]
    }
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nResults saved to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="SGLang FP8 Benchmark for RTX PRO 6000 (Blackwell)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List all available configurations
    python benchmark_sglang.py --list
    
    # Run specific config
    python benchmark_sglang.py --config fp8_triton_fp8
    
    # Run all 8 configs (takes ~40 minutes)
    python benchmark_sglang.py --all
    
    # Run with custom prompts
    python benchmark_sglang.py --all --prompts 100
        """
    )
    parser.add_argument("--list", action="store_true", help="List all configurations")
    parser.add_argument("--config", choices=list(CONFIGS.keys()), help="Run specific config")
    parser.add_argument("--all", action="store_true", help="Run all 8 configurations")
    parser.add_argument("--port", type=int, default=30000, help="Server port")
    parser.add_argument("--prompts", type=int, default=200, help="Number of prompts")
    parser.add_argument("--output", default="benchmark_results.json", help="Output JSON file")
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable Configurations:")
        print("-" * 60)
        for key, config in CONFIGS.items():
            print(f"  {key:<25} -> {config.name}")
        print(f"\nBest expected: fp8_triton_fp8 (FP8 + Triton + KV FP8)")
        return
    
    if not args.config and not args.all:
        parser.print_help()
        return
    
    results = []
    
    if args.all:
        print(f"\n{'='*70}")
        print("SGLang FP8 Benchmark - All 8 Configurations")
        print(f"{'='*70}")
        print(f"Prompts per test: {args.prompts}")
        print(f"Estimated time: ~40 minutes")
        
        for config_key in CONFIGS.keys():
            result = run_benchmark(config_key, args.port, args.prompts)
            results.append(result)
    else:
        result = run_benchmark(args.config, args.port, args.prompts)
        results.append(result)
    
    # Print comparison table
    print_comparison_table(results)
    
    # Save results
    save_results(results, args.output)


if __name__ == "__main__":
    main()
