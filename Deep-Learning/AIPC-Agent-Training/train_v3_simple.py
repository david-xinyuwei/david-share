#!/usr/bin/env python3
"""
AIPC 专家模型 V3 训练脚本
使用 GPT-5.2 纠正后的高质量数据进行 SFT

训练数据：48 条经过 GPT-5.2 纠正的样本
特点：每条样本都是正确答案，模型只需要学习这些正确模式
"""

import os
import json
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from datasets import Dataset


# ============ 配置 ============
BASE_MODEL = "/root/models/Qwen2.5-3B-Instruct"
DATA_FILE = "/root/aipc-flywheel/data/v3_good_samples.jsonl"
OUTPUT_DIR = "/root/aipc-flywheel/exported_model_v3"

EPOCHS = 10
LEARNING_RATE = 5e-5
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 4
MAX_LENGTH = 512


# ============ 数据准备 ============

def load_data(file_path: str):
    """加载训练数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    return data


def format_example(prompt: str, response: str) -> str:
    """格式化为聊天模板"""
    return f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n{response}<|im_end|>"


def prepare_dataset(data):
    """准备数据集"""
    texts = [format_example(d['prompt'], d['response']) for d in data]
    return Dataset.from_dict({"text": texts})


# ============ 训练 ============

def main():
    print("="*60)
    print("AIPC 专家模型 V3 训练")
    print("使用 GPT-5.2 纠正后的高质量数据")
    print("="*60)
    
    # 加载数据
    print("\n[1] 加载训练数据...")
    data = load_data(DATA_FILE)
    print(f"    样本数: {len(data)}")
    
    # 加载模型
    print("\n[2] 加载基座模型...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    print(f"    参数量: {model.num_parameters() / 1e9:.2f}B")
    
    # 准备数据集
    print("\n[3] 准备数据集...")
    dataset = prepare_dataset(data)
    
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=MAX_LENGTH,
            padding="max_length",
        )
    
    tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["text"])
    
    # 训练参数
    print("\n[4] 开始训练...")
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        learning_rate=LEARNING_RATE,
        warmup_ratio=0.1,
        logging_steps=10,
        save_strategy="epoch",
        bf16=True,
        report_to="none",
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    
    trainer.train()
    
    # 保存
    print("\n[5] 保存模型...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    print("\n" + "="*60)
    print(f"训练完成！模型已保存到: {OUTPUT_DIR}")
    print("="*60)


if __name__ == "__main__":
    main()
