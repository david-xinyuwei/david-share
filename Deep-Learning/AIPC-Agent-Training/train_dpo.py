#!/usr/bin/env python3
"""
DPO 训练脚本
============
使用 TRL 官方 DPOTrainer 进行直接偏好优化训练

输入: dpo_pairs.jsonl (prompt, chosen, rejected)
输出: DPO 微调后的模型

用法:
    python train_dpo.py \
        --model-path ./exported_model_v1 \
        --dpo-data ./data/dpo_pairs.jsonl \
        --output-dir ./exported_model_v2
"""

import os
import json
import argparse
import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, TaskType
from trl import DPOTrainer, DPOConfig


def load_dpo_data(filepath: str) -> Dataset:
    """
    加载 DPO 训练数据
    
    Args:
        filepath: JSONL 文件路径，每行包含 prompt, chosen, rejected
        
    Returns:
        Dataset 对象
    """
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                data.append({
                    "prompt": item["prompt"],
                    "chosen": item["chosen"],
                    "rejected": item["rejected"]
                })
    
    print(f"📖 加载 {len(data)} 条 DPO 数据")
    return Dataset.from_list(data)


def main():
    parser = argparse.ArgumentParser(description="DPO 训练（使用 TRL）")
    parser.add_argument("--model-path", type=str, required=True,
                        help="基座模型路径（上一版本的模型）")
    parser.add_argument("--dpo-data", type=str, required=True,
                        help="DPO 数据文件路径 (JSONL)")
    parser.add_argument("--output-dir", type=str, required=True,
                        help="输出目录")
    parser.add_argument("--epochs", type=int, default=3,
                        help="训练轮数")
    parser.add_argument("--lr", type=float, default=5e-6,
                        help="学习率")
    parser.add_argument("--batch-size", type=int, default=2,
                        help="每设备批大小")
    parser.add_argument("--gradient-accumulation", type=int, default=4,
                        help="梯度累积步数")
    parser.add_argument("--beta", type=float, default=0.1,
                        help="DPO temperature 参数")
    parser.add_argument("--max-length", type=int, default=1024,
                        help="最大序列长度")
    parser.add_argument("--lora-r", type=int, default=16,
                        help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32,
                        help="LoRA alpha")
    args = parser.parse_args()
    
    print("=" * 60)
    print("DPO 训练（TRL Official DPOTrainer）")
    print("=" * 60)
    print(f"基座模型: {args.model_path}")
    print(f"DPO 数据: {args.dpo_data}")
    print(f"输出目录: {args.output_dir}")
    print(f"超参数: epochs={args.epochs}, lr={args.lr}, beta={args.beta}")
    print(f"LoRA: r={args.lora_r}, alpha={args.lora_alpha}")
    print("=" * 60)
    
    # 1. 加载数据
    dataset = load_dpo_data(args.dpo_data)
    
    # 2. 加载模型和 tokenizer
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
    
    # 4. DPO 训练配置
    training_args = DPOConfig(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        learning_rate=args.lr,
        logging_steps=10,
        save_steps=50,
        save_total_limit=2,
        bf16=True,
        remove_unused_columns=False,
        beta=args.beta,
        max_length=args.max_length,
        max_prompt_length=args.max_length // 2,
        report_to="none",  # 不上报到 wandb
    )
    
    # 5. 创建 DPO Trainer
    print("\n🎯 初始化 DPOTrainer...")
    trainer = DPOTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    
    # 6. 训练
    print("\n🚀 开始训练...")
    trainer.train()
    
    # 7. 保存模型
    print(f"\n💾 保存模型到: {args.output_dir}")
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    
    # 8. 打印训练统计
    print("\n" + "=" * 60)
    print("✅ DPO 训练完成!")
    print(f"   模型保存到: {args.output_dir}")
    if trainer.state.log_history:
        final_loss = trainer.state.log_history[-1].get("loss", "N/A")
        print(f"   最终 Loss: {final_loss}")
    print("=" * 60)


if __name__ == "__main__":
    main()
