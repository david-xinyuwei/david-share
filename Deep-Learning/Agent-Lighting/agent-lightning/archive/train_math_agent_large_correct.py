#!/usr/bin/env python3
"""
大规模数学问答 Agent 强化学习训练脚本
使用 GPT-5 生成的大规模训练数据
基于 notebook 中的正确代码
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import agentlightning as agl
from datasets import Dataset as HuggingFaceDataset
import pandas as pd

# 1. 定义 Agent
@agl.rollout
async def math_agent(task, llm: agl.LLM):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url=llm.endpoint, api_key="EMPTY")

    try:
        response = await client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": "You are a math assistant. Output ONLY the final number."},
                {"role": "user", "content": task['question']}
            ],
            temperature=0.7
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling LLM: {e}")
        answer = "0"

    # 计算奖励
    reward = 1.0 if answer == task['answer'] else 0.0
    agl.emit_reward(reward)

# 2. 定义配置
def get_config():
    config = {
        "algorithm": {
            "adv_estimator": "grpo",
            "use_kl_in_reward": False,
        },
        "data": {
            "train_batch_size": 4,
            "max_prompt_length": 1024,
            "max_response_length": 512,
        },
        "actor_rollout_ref": {
            "rollout": {
                "tensor_model_parallel_size": 1,
                "n": 4,
                "log_prob_micro_batch_size_per_gpu": 4,
                "name": "vllm",
                "gpu_memory_utilization": 0.5,
            },
            "override_config": {
                "attn_implementation": "eager",
                "torch_dtype": "float16"
            }
        },
        "critic": {
            "enable": False
        },
        "trainer": {
            "total_epochs": 1,
            "total_training_steps": 100,
            "logger": ["tensorboard"],
            "project_name": "AgentLightningTutorial",
            "experiment_name": "math_agent_large",
            "default_local_dir": os.path.join(os.getcwd(), "checkpoints")
        }
    }
    return config

# 3. 主训练函数
def main():
    print("="*70)
    print("🚀 大规模数学问答 Agent 强化学习训练")
    print("="*70 + "\n")
    
    # 加载数据
    print("📊 加载大规模数据集...")
    train_df = pd.read_parquet("data/train_gpt5_large.parquet")
    val_df = pd.read_parquet("data/test_gpt5_large.parquet")
    
    print(f"✅ 训练集: {len(train_df)} 条")
    print(f"✅ 测试集: {len(val_df)} 条\n")
    
    # 转换为 HuggingFace Dataset
    train_dataset = HuggingFaceDataset.from_pandas(train_df)
    val_dataset = HuggingFaceDataset.from_pandas(val_df)
    
    # 获取配置
    config = get_config()
    
    # 初始化算法
    print("⚙️ 初始化 VERL 算法...")
    algorithm = agl.VERL(config)
    
    # 初始化 Trainer
    print("🎯 初始化 Trainer...")
    trainer = agl.Trainer(
        algorithm=algorithm,
        store=agl.InMemoryLightningStore(),
        tracer=agl.OtelTracer()
    )
    
    # 开始训练
    print("\n" + "="*70)
    print("🔥 开始训练")
    print("="*70 + "\n")
    
    trainer.fit(math_agent, train_dataset, val_dataset=val_dataset)
    
    print("\n" + "="*70)
    print("✅ 训练完成！")
    print("="*70)
    print(f"📂 模型检查点: {os.path.join(os.getcwd(), 'checkpoints/AgentLightningTutorial/math_agent_large/')}")

if __name__ == "__main__":
    main()
