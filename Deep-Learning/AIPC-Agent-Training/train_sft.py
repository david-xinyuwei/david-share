#!/usr/bin/env python3
"""
SFT 训练脚本（冷启动 V1）
使用 Transformers Trainer 进行监督微调

输入: cold_start.jsonl (prompt, response)
输出: V1 基线模型
"""

import os
import json
import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)

# ============ 配置 ============
BASE_MODEL = os.getenv("BASE_MODEL", "Qwen/Qwen2.5-3B-Instruct")
DATA_FILE = os.getenv("DATA_FILE", "./data/cold_start.jsonl")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output/v1_model")

# 训练超参数
LEARNING_RATE = float(os.getenv("LEARNING_RATE", "2e-5"))
NUM_EPOCHS = int(os.getenv("NUM_EPOCHS", "3"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "2"))
GRADIENT_ACCUMULATION = int(os.getenv("GRADIENT_ACCUMULATION", "4"))
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "1024"))

def load_sft_data(filepath: str, tokenizer) -> Dataset:
    """加载 SFT 训练数据并格式化为对话"""
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            # 构造对话格式
            messages = [
                {"role": "user", "content": item["prompt"]},
                {"role": "assistant", "content": item["response"]}
            ]
            # 使用 tokenizer 的 chat template
            text = tokenizer.apply_chat_template(messages, tokenize=False)
            data.append({"text": text})
    
    print(f"加载 {len(data)} 条 SFT 数据")
    return Dataset.from_list(data)

def tokenize_function(examples, tokenizer, max_length):
    """分词函数"""
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=max_length,
        padding="max_length"
    )

def main():
    print("=" * 60)
    print("SFT 训练（冷启动 V1）")
    print("=" * 60)
    print(f"基座模型: {BASE_MODEL}")
    print(f"数据文件: {DATA_FILE}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"学习率: {LEARNING_RATE}")
    print(f"Epochs: {NUM_EPOCHS}")
    print()
    
    # 加载分词器
    print("加载分词器...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # 加载数据
    dataset = load_sft_data(DATA_FILE, tokenizer)
    
    # 分词
    print("分词处理...")
    tokenized_dataset = dataset.map(
        lambda x: tokenize_function(x, tokenizer, MAX_LENGTH),
        batched=True,
        remove_columns=["text"]
    )
    
    # 加载模型
    print("加载模型...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )
    
    # 训练配置
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        learning_rate=LEARNING_RATE,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        bf16=True,
        report_to="none",
    )
    
    # 数据整理器
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )
    
    # 创建 Trainer
    print("初始化 Trainer...")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )
    
    # 开始训练
    print()
    print("=" * 60)
    print("开始 SFT 训练...")
    print("=" * 60)
    
    trainer.train()
    
    # 保存模型
    print()
    print("保存模型...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    print()
    print("=" * 60)
    print(f"✅ SFT 训练完成！")
    print(f"模型已保存到: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
