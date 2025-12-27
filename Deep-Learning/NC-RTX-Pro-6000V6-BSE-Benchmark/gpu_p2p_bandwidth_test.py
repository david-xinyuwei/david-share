#!/usr/bin/env python3
"""
GPU P2P Bandwidth Test Script
测试 GPU 之间的点对点通信带宽，用于评估 TP>1 推理的瓶颈

Usage:
    python gpu_p2p_bandwidth_test.py
"""

import torch
import time
import numpy as np


def check_p2p_access():
    """检查 GPU 之间的 P2P 访问能力"""
    n_gpus = torch.cuda.device_count()
    print(f"\n=== GPU P2P 访问检查 ({n_gpus} GPUs) ===")
    
    for i in range(n_gpus):
        for j in range(n_gpus):
            if i != j:
                can_access = torch.cuda.can_device_access_peer(i, j)
                status = "✅ 可访问" if can_access else "❌ 不可访问"
                print(f"GPU {i} -> GPU {j}: {status}")
    
    return n_gpus


def measure_p2p_bandwidth(src_gpu: int, dst_gpu: int, size_mb: int = 256, 
                          iterations: int = 100):
    """测量两个 GPU 之间的 P2P 带宽"""
    size_bytes = size_mb * 1024 * 1024
    
    # 在源 GPU 上分配数据
    with torch.cuda.device(src_gpu):
        src_tensor = torch.randn(size_bytes // 4, dtype=torch.float32, device=f'cuda:{src_gpu}')
    
    # 在目标 GPU 上分配空间
    with torch.cuda.device(dst_gpu):
        dst_tensor = torch.empty(size_bytes // 4, dtype=torch.float32, device=f'cuda:{dst_gpu}')
    
    # 预热
    for _ in range(10):
        dst_tensor.copy_(src_tensor, non_blocking=False)
    torch.cuda.synchronize()
    
    # 测量
    start_time = time.time()
    for _ in range(iterations):
        dst_tensor.copy_(src_tensor, non_blocking=False)
    torch.cuda.synchronize()
    elapsed = time.time() - start_time
    
    # 计算带宽
    total_bytes = size_bytes * iterations
    bandwidth_gbps = (total_bytes / elapsed) / (1024**3)
    
    return bandwidth_gbps


def run_nccl_test():
    """运行 NCCL 带宽测试"""
    try:
        import torch.distributed as dist
        
        if not dist.is_initialized():
            # 单机测试模式
            print("\n=== NCCL 测试需要分布式初始化，跳过 ===")
            return None
    except ImportError:
        print("NCCL 测试需要 torch.distributed")
        return None


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           GPU P2P Bandwidth Test                             ║
║     用于评估张量并行推理的 GPU 通信瓶颈                        ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # 检查 CUDA
    if not torch.cuda.is_available():
        print("❌ CUDA 不可用")
        return
    
    n_gpus = check_p2p_access()
    
    if n_gpus < 2:
        print("\n⚠️ 只有一个 GPU，无法测试 P2P 带宽")
        return
    
    # 测试不同大小
    print("\n=== P2P 带宽测试 ===")
    sizes_mb = [64, 128, 256, 512, 1024]
    
    results = {}
    
    for i in range(n_gpus):
        for j in range(n_gpus):
            if i != j:
                print(f"\nGPU {i} -> GPU {j}:")
                print(f"{'数据大小':<15} {'带宽 (GB/s)':>15}")
                print("-" * 32)
                
                pair_key = f"GPU{i}->GPU{j}"
                results[pair_key] = {}
                
                for size_mb in sizes_mb:
                    bandwidth = measure_p2p_bandwidth(i, j, size_mb)
                    results[pair_key][f"{size_mb}MB"] = bandwidth
                    print(f"{size_mb:>6} MB{bandwidth:>18.2f}")
    
    # 汇总
    print("\n" + "=" * 60)
    print("=== 汇总 (256MB 数据传输) ===")
    print("=" * 60)
    print(f"{'传输方向':<20} {'带宽 (GB/s)':>15}")
    print("-" * 35)
    
    for pair_key, bw_dict in results.items():
        bw_256 = bw_dict.get("256MB", 0)
        print(f"{pair_key:<20} {bw_256:>15.2f}")
    
    # 分析
    print("\n=== 性能分析 ===")
    avg_bw = np.mean([v.get("256MB", 0) for v in results.values()])
    print(f"平均带宽: {avg_bw:.2f} GB/s")
    
    if avg_bw > 100:
        print("✅ NVLink 连接 - 非常适合 TP>1")
    elif avg_bw > 40:
        print("⚠️ PCIe Gen5 x16 - TP=2 可用，但大模型可能受限")
    elif avg_bw > 20:
        print("⚠️ PCIe Gen4 x16 - TP>1 会有明显瓶颈")
    else:
        print("❌ 带宽较低 - 建议使用 TP=1")
    
    # 对于 72B FP8 模型的估算
    print("\n=== 对 72B FP8 模型的影响估算 ===")
    model_size_gb = 72  # ~72GB for 72B FP8
    activation_size_mb = 100  # 估算每次前向传播的激活大小
    
    # 每个 token 需要传输的数据量（激活值同步）
    sync_per_token_mb = activation_size_mb * 2  # AllReduce = 2x
    
    print(f"模型大小: ~{model_size_gb} GB (FP8)")
    print(f"估算每 token AllReduce 数据量: ~{sync_per_token_mb} MB")
    print(f"以 {avg_bw:.1f} GB/s 带宽，每 token 同步开销: ~{sync_per_token_mb / (avg_bw * 1024) * 1000:.2f} ms")


if __name__ == "__main__":
    main()
