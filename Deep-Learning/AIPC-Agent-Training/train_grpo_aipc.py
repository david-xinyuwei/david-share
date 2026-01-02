"""
GRPO Training for AI PC Agent V1.1
轻 DPO + 重 GRPO 策略：直接用 V1 SFT 模型进行 GRPO 强化
"""
import os
import json
import torch
from datetime import datetime

# 禁用不需要的服务
os.environ['WANDB_DISABLED'] = 'true'
os.environ['HF_HUB_OFFLINE'] = '1'

from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOConfig, GRPOTrainer
from datasets import Dataset

print(f"[{datetime.now()}] Starting GRPO Training for AI PC Agent V1.1")

# ============ 配置 ============
BASE_MODEL = "checkpoints/aipc_sft_v1"  # 使用 V1 SFT 模型
OUTPUT_DIR = "checkpoints/aipc_grpo_v1.1"
TRAIN_DATA = "data/aipc_sft_train.jsonl"

# GRPO 配置 - 针对 A100 80GB 优化
GRPO_CONFIG = {
    "num_train_epochs": 2,
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 8,  # 有效 batch size = 16
    "learning_rate": 1e-6,  # GRPO 用更小的学习率
    "max_completion_length": 512,
    "max_prompt_length": 256,
    "num_generations": 4,  # 每个 prompt 生成 4 个候选
    "temperature": 0.7,
    "logging_steps": 10,
    "save_steps": 100,
    "bf16": True,
}

def load_training_data(path: str) -> Dataset:
    """加载训练数据，转换为 GRPO 格式"""
    prompts = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            # GRPO 只需要 prompt，不需要 completion
            question = item.get('question') or item.get('prompt', '')
            if question:
                prompts.append({"prompt": f"用户问题：{question}\n\nAI PC 专家回答："})
    
    print(f"Loaded {len(prompts)} prompts for GRPO training")
    return Dataset.from_list(prompts)

def reward_function(completions, **kwargs):
    """
    AI PC 专家奖励函数 (TRL 新版签名)
    评估回答质量：
    1. 包含关键技术词汇 (+0.3)
    2. 回答长度适中 (+0.2)
    3. 结构清晰（有分点或列表）(+0.2)
    4. 没有幻觉词汇 (+0.3)
    """
    rewards = []
    
    # AI PC 关键词
    keywords = [
        'NPU', 'Intel Core Ultra', 'Snapdragon X', 'AI PC', 
        'AIPC', '神经网络', '本地推理', 'Copilot', 
        'Qualcomm', 'DirectML', 'ONNX', 'OpenVINO',
        '边缘计算', '隐私', '低功耗', '加速器'
    ]
    
    # 幻觉/错误词汇
    hallucination_words = [
        '服务器', 'GPU集群', '云端训练', 'A100', 'H100',
        '数据中心', '大规模并行'
    ]
    
    for completion in completions:
        score = 0.0
        
        # 1. 关键词覆盖 (+0.3)
        keyword_count = sum(1 for kw in keywords if kw.lower() in completion.lower())
        score += min(0.3, keyword_count * 0.05)
        
        # 2. 长度适中 (+0.2): 100-500 字最佳
        length = len(completion)
        if 100 <= length <= 500:
            score += 0.2
        elif 50 <= length < 100 or 500 < length <= 800:
            score += 0.1
        
        # 3. 结构清晰 (+0.2)
        if any(marker in completion for marker in ['1.', '2.', '•', '-', '首先', '其次', '最后']):
            score += 0.2
        
        # 4. 没有幻觉 (+0.3)
        has_hallucination = any(hw in completion for hw in hallucination_words)
        if not has_hallucination:
            score += 0.3
        
        rewards.append(score)
    
    return rewards

def main():
    print(f"[{datetime.now()}] Loading model from {BASE_MODEL}")
    
    # 加载模型和分词器
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=False,
    )
    
    print(f"[{datetime.now()}] Model loaded. Loading training data...")
    
    # 加载数据
    train_dataset = load_training_data(TRAIN_DATA)
    
    # GRPO 配置
    training_args = GRPOConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=GRPO_CONFIG["num_train_epochs"],
        per_device_train_batch_size=GRPO_CONFIG["per_device_train_batch_size"],
        gradient_accumulation_steps=GRPO_CONFIG["gradient_accumulation_steps"],
        learning_rate=GRPO_CONFIG["learning_rate"],
        max_completion_length=GRPO_CONFIG["max_completion_length"],
        num_generations=GRPO_CONFIG["num_generations"],
        temperature=GRPO_CONFIG["temperature"],
        logging_steps=GRPO_CONFIG["logging_steps"],
        save_steps=GRPO_CONFIG["save_steps"],
        bf16=GRPO_CONFIG["bf16"],
        remove_unused_columns=False,
        report_to="none",
    )
    
    print(f"[{datetime.now()}] Initializing GRPO Trainer...")
    
    # 创建 Trainer
    trainer = GRPOTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        processing_class=tokenizer,
        reward_funcs=reward_function,
    )
    
    print(f"[{datetime.now()}] Starting GRPO training...")
    print(f"  - Epochs: {GRPO_CONFIG['num_train_epochs']}")
    print(f"  - Batch size: {GRPO_CONFIG['per_device_train_batch_size']} x {GRPO_CONFIG['gradient_accumulation_steps']} = {GRPO_CONFIG['per_device_train_batch_size'] * GRPO_CONFIG['gradient_accumulation_steps']}")
    print(f"  - Generations per prompt: {GRPO_CONFIG['num_generations']}")
    
    # 训练
    trainer.train()
    
    print(f"[{datetime.now()}] Training complete. Saving model...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    
    print(f"[{datetime.now()}] ✅ GRPO V1.1 model saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
