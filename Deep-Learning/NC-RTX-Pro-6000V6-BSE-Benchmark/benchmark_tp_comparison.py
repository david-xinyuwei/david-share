#!/usr/bin/env python3
"""
RTX PRO 6000 Blackwell TP=1 vs TP=2 Benchmark Script
比较张量并行对 LLM 推理性能的影响

Usage:
    # TP=1 测试
    python benchmark_tp_comparison.py --model Qwen/Qwen2.5-VL-72B-Instruct-FP8 --tp 1 --port 8000
    
    # TP=2 测试
    python benchmark_tp_comparison.py --model Qwen/Qwen2.5-VL-72B-Instruct-FP8 --tp 2 --port 8001
"""

import argparse
import subprocess
import time
import requests
import json
import sys
import os
from datetime import datetime


def check_gpu_availability():
    """检查 GPU 可用性"""
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"],
        capture_output=True, text=True
    )
    print("=== GPU 状态 ===")
    print(result.stdout)
    return result.returncode == 0


def start_vllm_server(model: str, tp: int, port: int, quantization: str = None):
    """启动 vLLM 服务器"""
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", model,
        "--tensor-parallel-size", str(tp),
        "--port", str(port),
        "--trust-remote-code",
        "--max-model-len", "8192",
    ]
    
    if quantization:
        cmd.extend(["--quantization", quantization])
    
    print(f"\n=== 启动 vLLM 服务器 (TP={tp}, Port={port}) ===")
    print(f"命令: {' '.join(cmd)}")
    
    # 后台启动
    log_file = f"/tmp/vllm_tp{tp}_{port}.log"
    with open(log_file, "w") as f:
        process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
    
    print(f"日志文件: {log_file}")
    print(f"PID: {process.pid}")
    
    return process, log_file


def wait_for_server(port: int, timeout: int = 300):
    """等待服务器启动"""
    url = f"http://localhost:{port}/health"
    start_time = time.time()
    
    print(f"\n等待服务器启动 (端口 {port})...")
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ 服务器已就绪 (耗时 {time.time() - start_time:.1f}s)")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)
        print(".", end="", flush=True)
    
    print(f"\n❌ 服务器启动超时 ({timeout}s)")
    return False


def run_benchmark(port: int, num_prompts: int = 64, input_len: int = 512, 
                  output_len: int = 256, concurrency: int = 16):
    """运行 vLLM benchmark"""
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        # 实际应使用 vllm benchmark 工具
    ]
    
    # 使用 vLLM 内置 benchmark 工具
    benchmark_cmd = [
        "python", "-m", "vllm.benchmarks.benchmark_serving",
        "--backend", "vllm",
        "--base-url", f"http://localhost:{port}",
        "--num-prompts", str(num_prompts),
        "--random-input-len", str(input_len),
        "--random-output-len", str(output_len),
        "--request-rate", str(concurrency),
        "--seed", "42",
    ]
    
    print(f"\n=== 运行 Benchmark ===")
    print(f"参数: {num_prompts} prompts, {input_len} input, {output_len} output, concurrency={concurrency}")
    print(f"命令: {' '.join(benchmark_cmd)}")
    
    result = subprocess.run(benchmark_cmd, capture_output=True, text=True)
    
    print("\n=== 结果 ===")
    print(result.stdout)
    
    if result.stderr:
        print("\n=== 错误 ===")
        print(result.stderr)
    
    return result.stdout


def parse_results(output: str) -> dict:
    """解析 benchmark 结果"""
    results = {}
    
    # 提取关键指标
    for line in output.split('\n'):
        if 'Output token throughput' in line:
            try:
                results['output_throughput'] = float(line.split(':')[1].strip().split()[0])
            except:
                pass
        elif 'Request throughput' in line:
            try:
                results['request_throughput'] = float(line.split(':')[1].strip().split()[0])
            except:
                pass
        elif 'Mean TTFT' in line:
            try:
                results['ttft_ms'] = float(line.split(':')[1].strip().split()[0])
            except:
                pass
        elif 'Mean TPOT' in line:
            try:
                results['tpot_ms'] = float(line.split(':')[1].strip().split()[0])
            except:
                pass
    
    return results


def compare_results(tp1_results: dict, tp2_results: dict):
    """比较 TP=1 和 TP=2 结果"""
    print("\n" + "=" * 60)
    print("TP=1 vs TP=2 性能比较")
    print("=" * 60)
    
    metrics = [
        ('output_throughput', 'Output Throughput (tok/s)', True),
        ('request_throughput', 'Request Throughput (req/s)', True),
        ('ttft_ms', 'Mean TTFT (ms)', False),
        ('tpot_ms', 'Mean TPOT (ms)', False),
    ]
    
    print(f"{'指标':<30} {'TP=1':>15} {'TP=2':>15} {'变化':>15}")
    print("-" * 75)
    
    for key, name, higher_better in metrics:
        if key in tp1_results and key in tp2_results:
            v1 = tp1_results[key]
            v2 = tp2_results[key]
            change = (v2 - v1) / v1 * 100
            
            if higher_better:
                indicator = "✅" if change > 5 else ("⚠️" if change < -5 else "➡️")
            else:
                indicator = "✅" if change < -5 else ("⚠️" if change > 5 else "➡️")
            
            print(f"{name:<30} {v1:>15.2f} {v2:>15.2f} {change:>+13.1f}% {indicator}")
    
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="RTX PRO 6000 TP Benchmark")
    parser.add_argument("--model", type=str, required=True, help="模型路径")
    parser.add_argument("--tp", type=int, choices=[1, 2], required=True, help="张量并行度")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--quantization", type=str, default=None, help="量化方式 (fp8, nvfp4 等)")
    parser.add_argument("--num-prompts", type=int, default=64, help="测试 prompt 数量")
    parser.add_argument("--input-len", type=int, default=512, help="输入长度")
    parser.add_argument("--output-len", type=int, default=256, help="输出长度")
    parser.add_argument("--concurrency", type=int, default=16, help="并发数")
    parser.add_argument("--skip-server", action="store_true", help="跳过启动服务器")
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║     RTX PRO 6000 Blackwell - TP={args.tp} Benchmark          ║
║     Model: {args.model[:45]:<45}  ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # 检查 GPU
    if not check_gpu_availability():
        print("❌ GPU 不可用")
        sys.exit(1)
    
    process = None
    try:
        # 启动服务器
        if not args.skip_server:
            process, log_file = start_vllm_server(
                args.model, args.tp, args.port, args.quantization
            )
            
            if not wait_for_server(args.port):
                print(f"\n查看日志: tail -100 {log_file}")
                sys.exit(1)
        
        # 运行 benchmark
        output = run_benchmark(
            args.port,
            args.num_prompts,
            args.input_len,
            args.output_len,
            args.concurrency
        )
        
        # 解析结果
        results = parse_results(output)
        
        # 保存结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = f"benchmark_tp{args.tp}_{timestamp}.json"
        with open(result_file, 'w') as f:
            json.dump({
                'model': args.model,
                'tp': args.tp,
                'params': {
                    'num_prompts': args.num_prompts,
                    'input_len': args.input_len,
                    'output_len': args.output_len,
                    'concurrency': args.concurrency,
                },
                'results': results,
                'timestamp': timestamp,
            }, f, indent=2)
        
        print(f"\n✅ 结果已保存到: {result_file}")
        
    except KeyboardInterrupt:
        print("\n\n中断测试...")
    finally:
        if process:
            print("停止服务器...")
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
