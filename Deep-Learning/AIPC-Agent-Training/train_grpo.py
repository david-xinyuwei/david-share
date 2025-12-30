#!/usr/bin/env python3
"""
GRPO 训练脚本
=============
使用 TRL 官方 GRPOTrainer 进行基于奖励的策略优化

核心特点：
1. 实时采样：模型对每个 prompt 生成多个回答
2. 实时评分：用 GPT 对每个回答打分作为 reward
3. 策略优化：根据 reward 优化模型策略

输入: grpo_prompts.jsonl (只包含问题)
输出: GRPO 微调后的模型

用法:
    python train_grpo.py \
        --model-path ./exported_model_v2 \
        --prompts ./data/grpo_prompts.jsonl \
        --output-dir ./exported_model_v2_grpo
"""

import os
import json
import argparse
import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, TaskType
from trl import GRPOTrainer, GRPOConfig
from openai import AzureOpenAI


# ============ Azure OpenAI 评分配置 ============
AZURE_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT", 
    "https://ai-swedencentral955006659336.openai.azure.com/"
)
AZURE_KEY = os.getenv(
    "AZURE_OPENAI_KEY", 
    "YOUR_AZURE_OPENAI_KEY"
)
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")


def get_azure_client():
    """获取 Azure OpenAI 客户端"""
    return AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_KEY,
        api_version=AZURE_API_VERSION
    )


def create_reward_function():
    """
    创建奖励函数
    
    返回一个可被 GRPOTrainer 调用的函数，输入是生成的文本列表，
    输出是对应的奖励分数列表
    """
    client = get_azure_client()
    
    def reward_fn(completions: list, prompts: list = None, **kwargs) -> list:
        """
        对生成的回答进行评分
        
        Args:
            completions: 模型生成的回答列表
            prompts: 对应的问题列表（可选）
            
        Returns:
            奖励分数列表，每个分数在 0-1 之间
        """
        rewards = []
        
        for i, completion in enumerate(completions):
            # 获取对应的 prompt（如果有）
            prompt = prompts[i] if prompts and i < len(prompts) else "AI PC 相关问题"
            
            # 构造评分 prompt
            score_prompt = f"""评价以下关于 AI PC 的回答质量，打分 0-10 分。

问题: {prompt}

回答: {completion}

评分标准:
- 10分: 完美回答，准确、全面、易懂
- 7-9分: 正确但可以更好
- 4-6分: 部分正确，有遗漏或小错误
- 1-3分: 大部分错误或不相关
- 0分: 完全错误或拒绝回答

只输出一个数字（0-10）:"""
            
            try:
                response = client.chat.completions.create(
                    model=AZURE_DEPLOYMENT,
                    messages=[{"role": "user", "content": score_prompt}],
                    max_tokens=10,
                    temperature=1
                )
                score_text = response.choices[0].message.content.strip()
                score = float(score_text.split()[0])
                score = min(max(score, 0), 10)  # 限制在 0-10
                # 归一化到 0-1
                reward = score / 10.0
            except Exception as e:
                print(f"  [评分失败: {e}]")
                reward = 0.5  # 默认中等分
            
            rewards.append(reward)
        
        return rewards
    
    return reward_fn


def load_prompts(filepath: str) -> Dataset:
    """
    加载 GRPO prompts
    
    Args:
        filepath: JSONL 文件路径，每行包含 question 或 prompt 字段
        
    Returns:
        Dataset 对象
    """
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                prompt = item.get("question", item.get("prompt", ""))
                if prompt:
                    data.append({"prompt": prompt})
    
    print(f"📖 加载 {len(data)} 个 GRPO prompts")
    return Dataset.from_list(data)


def main():
    parser = argparse.ArgumentParser(description="GRPO 训练（使用 TRL）")
    parser.add_argument("--model-path", type=str, required=True,
                        help="基座模型路径（上一版本的模型）")
    parser.add_argument("--prompts", type=str, required=True,
                        help="GRPO prompts 文件路径 (JSONL)")
    parser.add_argument("--output-dir", type=str, required=True,
                        help="输出目录")
    parser.add_argument("--epochs", type=int, default=1,
                        help="训练轮数")
    parser.add_argument("--lr", type=float, default=1e-5,
                        help="学习率")
    parser.add_argument("--batch-size", type=int, default=2,
                        help="每设备批大小")
    parser.add_argument("--num-generations", type=int, default=4,
                        help="每个 prompt 生成的回答数量")
    parser.add_argument("--max-new-tokens", type=int, default=256,
                        help="生成的最大 token 数")
    parser.add_argument("--lora-r", type=int, default=16,
                        help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32,
                        help="LoRA alpha")
    args = parser.parse_args()
    
    print("=" * 60)
    print("GRPO 训练（TRL Official GRPOTrainer）")
    print("=" * 60)
    print(f"基座模型: {args.model_path}")
    print(f"Prompts: {args.prompts}")
    print(f"输出目录: {args.output_dir}")
    print(f"超参数: epochs={args.epochs}, lr={args.lr}")
    print(f"采样: num_generations={args.num_generations}")
    print("=" * 60)
    
    # 1. 加载 prompts
    dataset = load_prompts(args.prompts)
    
    # 2. 加载模型
    print("\n📦 加载模型...")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path, 
        trust_remote_code=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 3. LoRA 配置
    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        task_type=TaskType.CAUSAL_LM,
        bias="none"
    )
    
    # 4. 创建奖励函数
    print("\n🎲 初始化奖励函数...")
    reward_fn = create_reward_function()
    
    # 5. GRPO 配置
    training_args = GRPOConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        logging_steps=5,
        save_steps=50,
        save_total_limit=2,
        bf16=True,
        num_generations=args.num_generations,
        max_completion_length=args.max_new_tokens,
        report_to="none",
    )
    
    # 6. 创建 GRPO Trainer
    print("\n🎯 初始化 GRPOTrainer...")
    trainer = GRPOTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
        reward_funcs=reward_fn,
    )
    
    # 7. 训练
    print("\n🚀 开始训练...")
    trainer.train()
    
    # 8. 保存
    print(f"\n💾 保存模型到: {args.output_dir}")
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    
    print("\n" + "=" * 60)
    print("✅ GRPO 训练完成!")
    print(f"   模型保存到: {args.output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
