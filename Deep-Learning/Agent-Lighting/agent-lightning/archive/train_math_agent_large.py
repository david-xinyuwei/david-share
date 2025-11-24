#!/usr/bin/env python3
"""
大规模数学问答 Agent 强化学习训练脚本
使用 GPT-5 生成的 5000 条训练数据
"""
import os
import asyncio
import re
from pathlib import Path

import pandas as pd

from agentlightning.verl.trainer import reward_function
from agentlightning.algorithm import RolloutManager
from agentlightning.algorithm.fast import FastGGUFRLAlgorithm
from agentlightning.client import DeepSeekAgent
from agentlightning.model.gguf_server import GGUFServer
from agentlightning.store import LocalStore


@reward_function
async def is_correct(state, action, next_state):
    """奖励函数：检查答案是否正确"""
    question = state.get("question", "")
    ground_truth = state.get("ground_truth", "")
    response = action.get("response", "")
    
    # 提取数字答案
    numbers = re.findall(r'-?\d+\.?\d*', response)
    if not numbers:
        return -1.0
    
    predicted = numbers[-1]
    
    # 比较答案
    try:
        if abs(float(predicted) - float(ground_truth)) < 0.01:
            return 1.0
        else:
            return -1.0
    except:
        return -1.0


async def evaluate_accuracy(manager: RolloutManager, test_df: pd.DataFrame, num_samples: int = 20) -> float:
    """
    评估模型准确率
    
    Args:
        manager: RolloutManager 实例
        test_df: 测试数据集
        num_samples: 评估样本数
    
    Returns:
        准确率（百分比）
    """
    correct = 0
    for idx, row in test_df.head(num_samples).iterrows():
        result = await manager.run(
            state={"question": row['question'], "ground_truth": row['answer']}
        )
        if result.get('reward', -1) > 0:
            correct += 1
    
    return correct / num_samples * 100


async def main():
    print("="*70)
    print("🚀 大规模数学问答 Agent 强化学习训练")
    print("="*70 + "\n")
    
    # ==================== 1. 加载数据 ====================
    print("📊 加载 GPT-5 生成的大规模数据集...")
    train_df = pd.read_parquet("data/train_gpt5_large.parquet")
    test_df = pd.read_parquet("data/test_gpt5_large.parquet")
    
    print(f"✅ 训练集: {len(train_df)} 条")
    print(f"✅ 测试集: {len(test_df)} 条\n")
    
    # ==================== 2. 启动模型服务器 ====================
    print("🚀 启动本地 GGUF 模型服务器...")
    model_path = os.environ.get("MODEL_PATH", "/root/model/DeepSeek-R1-Distill-Qwen-7B.Q8_0.gguf")
    server = GGUFServer(
        model_path=model_path,
        tensor_split="1",
        num_gpu_layers=999,
    )
    await server.start()
    print(f"✅ 模型服务器启动: {server.base_url}\n")
    
    # ==================== 3. 配置 Agent ====================
    print("🤖 配置 DeepSeek Agent...")
    agent = DeepSeekAgent(
        prompt='''You are a math expert. Solve the math problem step by step.
Problem: {question}
Show your reasoning and provide the final numeric answer.''',
        base_url=server.base_url,
        model="DeepSeek-R1-Distill-Qwen-7B",
        temperature=0.0,
    )
    
    # ==================== 4. 配置存储 ====================
    print("💾 配置本地存储...")
    store = LocalStore(store_dir=Path("./lightning_store_large"))
    
    # ==================== 5. 初始化强化学习算法 ====================
    print("⚙️ 初始化强化学习算法...")
    algorithm = FastGGUFRLAlgorithm(
        model_path=model_path,
        reward_function=is_correct,
        num_samples=16,
        temperature=0.9,
        top_k=50,
        top_p=0.95,
        output_dir=Path("./checkpoints_large"),
        tensorboard_dir=Path("./tensorboard_large"),
        num_gpu_layers=999,
        tensor_split="1",
    )
    
    # ==================== 6. 创建 Rollout Manager ====================
    print("🎯 创建 Rollout Manager...\n")
    manager = RolloutManager(
        agent=agent,
        algorithm=algorithm,
        store=store,
    )
    
    # ==================== 7. 训练前基线评估 ====================
    print("="*70)
    print("📈 训练前基线评估")
    print("="*70)
    baseline_acc = await evaluate_accuracy(manager, test_df, num_samples=20)
    print(f"✅ 训练前准确率: {baseline_acc:.1f}%\n")
    
    # ==================== 8. 执行强化学习训练 ====================
    print("="*70)
    print("🔥 开始强化学习训练")
    print("="*70)
    
    # 先用 200 条数据测试训练流程
    num_training_samples = 200
    print(f"📝 训练样本数: {num_training_samples} 条（测试阶段）")
    print(f"⏱️ 预计时间: 约 30-60 分钟\n")
    
    training_tasks = []
    for idx, row in train_df.head(num_training_samples).iterrows():
        task = manager.run(
            state={"question": row['question'], "ground_truth": row['answer']}
        )
        training_tasks.append(task)
        
        # 每 50 条显示进度
        if (idx + 1) % 50 == 0:
            print(f"📊 已添加训练任务: {idx + 1}/{num_training_samples}")
    
    print(f"\n🚀 开始执行训练...")
    results = await asyncio.gather(*training_tasks)
    print(f"✅ 训练完成: {len(results)} 个样本\n")
    
    # ==================== 9. 训练后评估 ====================
    print("="*70)
    print("📊 训练后评估")
    print("="*70)
    trained_acc = await evaluate_accuracy(manager, test_df, num_samples=20)
    print(f"✅ 训练后准确率: {trained_acc:.1f}%\n")
    
    # ==================== 10. 性能对比 ====================
    improvement = trained_acc - baseline_acc
    print("="*70)
    print("📈 训练效果对比")
    print("="*70)
    print(f"训练前准确率: {baseline_acc:.1f}%")
    print(f"训练后准确率: {trained_acc:.1f}%")
    print(f"准确率提升: {improvement:+.1f}%")
    print("="*70 + "\n")
    
    # ==================== 11. 保存结果 ====================
    print("💾 保存训练结果...")
    results_path = Path("training_results.txt")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write(f"训练配置\n")
        f.write(f"="*70 + "\n")
        f.write(f"训练样本数: {num_training_samples}\n")
        f.write(f"测试样本数: 20\n")
        f.write(f"模型: DeepSeek-R1-Distill-Qwen-7B\n")
        f.write(f"\n训练结果\n")
        f.write(f"="*70 + "\n")
        f.write(f"训练前准确率: {baseline_acc:.1f}%\n")
        f.write(f"训练后准确率: {trained_acc:.1f}%\n")
        f.write(f"准确率提升: {improvement:+.1f}%\n")
    
    print(f"✅ 结果已保存到: {results_path}\n")
    
    # ==================== 12. 清理 ====================
    await server.stop()
    
    print("="*70)
    print("✅ 训练完成！")
    print("="*70)
    print(f"📂 模型检查点: ./checkpoints_large/")
    print(f"📊 TensorBoard 日志: ./tensorboard_large/")
    print(f"📝 训练结果: {results_path}")
    print(f"\n🚀 下一步: 运行推理验证脚本")
    print(f"   python inference_validation.py")


if __name__ == "__main__":
    asyncio.run(main())
