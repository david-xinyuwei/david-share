#!/usr/bin/env python3
"""
AIPC 专家模型 V2 训练脚本
两阶段训练：SFT（监督微调）+ GRPO（组相对策略优化）

训练方法区分：
┌──────────────────┬─────────────────┬─────────────────────────────────┐
│ 反馈来源         │ 训练方法        │ 原理                            │
├──────────────────┼─────────────────┼─────────────────────────────────┤
│ 用户点赞 👍👎   │ SFT (监督微调)  │ 直接学习正确答案，简单直接      │
│ GPT-5.2 打分     │ RL/GRPO        │ 奖励信号优化策略，泛化性好      │
└──────────────────┴─────────────────┴─────────────────────────────────┘

数据来源：用户反馈（正面22条，负面0条）
问题：只有正面样本导致模型无法学习边界，V2效果不如V1
"""

import os
import json
import torch
import random
import numpy as np
from typing import List, Dict, Any
from dataclasses import dataclass
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)
from datasets import Dataset
from openai import AzureOpenAI

# ============ 配置 ============
@dataclass
class TrainConfig:
    # 基座模型
    base_model: str = "/root/models/Qwen2.5-3B-Instruct"
    
    # SFT 阶段
    sft_epochs: int = 3
    sft_lr: float = 5e-5
    sft_batch_size: int = 2
    sft_gradient_accumulation: int = 4
    
    # GRPO 阶段
    grpo_epochs: int = 2
    grpo_lr: float = 1e-5
    grpo_batch_size: int = 4
    grpo_group_size: int = 4  # 每个prompt生成的response数量
    grpo_beta: float = 0.1    # KL散度惩罚系数
    
    # 数据路径
    feedback_file: str = "/root/aipc-flywheel/data/user_feedback.jsonl"
    output_dir: str = "/root/aipc-flywheel/exported_model_v2"
    
    # GPT-5.2 评分
    azure_endpoint: str = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://your-endpoint.openai.azure.com")
    azure_api_key: str = os.environ.get("AZURE_OPENAI_API_KEY", "your-api-key")
    azure_api_version: str = "2024-12-01-preview"
    reward_model: str = "gpt-5-turbo"
    
    # 其他
    max_length: int = 512
    seed: int = 42


config = TrainConfig()


def set_seed(seed: int):
    """设置随机种子"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_feedback_data(file_path: str) -> List[Dict[str, Any]]:
    """加载用户反馈数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    return data


def format_prompt(question: str) -> str:
    """格式化为聊天格式"""
    return f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n"


def format_training_example(question: str, answer: str) -> str:
    """格式化训练样本"""
    return f"<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n{answer}<|im_end|>"


# ============ SFT 阶段 ============

def prepare_sft_dataset(feedback_data: List[Dict]) -> Dataset:
    """准备 SFT 数据集（只用正面反馈）"""
    positive_samples = [d for d in feedback_data if d.get('feedback') == 'positive']
    
    texts = []
    for sample in positive_samples:
        text = format_training_example(sample['prompt'], sample['response'])
        texts.append(text)
    
    print(f"[SFT] 正面样本数: {len(positive_samples)}")
    return Dataset.from_dict({"text": texts})


def run_sft_stage(model, tokenizer, dataset: Dataset, config: TrainConfig) -> str:
    """运行 SFT 阶段"""
    print("\n" + "="*50)
    print("阶段 1: SFT 监督微调")
    print("="*50)
    
    # Tokenize
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=config.max_length,
            padding="max_length",
        )
    
    tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["text"])
    
    # 训练参数
    sft_output_dir = os.path.join(config.output_dir, "sft_checkpoint")
    training_args = TrainingArguments(
        output_dir=sft_output_dir,
        num_train_epochs=config.sft_epochs,
        per_device_train_batch_size=config.sft_batch_size,
        gradient_accumulation_steps=config.sft_gradient_accumulation,
        learning_rate=config.sft_lr,
        warmup_ratio=0.1,
        logging_steps=10,
        save_strategy="epoch",
        bf16=True,
        report_to="none",
    )
    
    # 训练
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    
    trainer.train()
    
    # 保存 SFT 检查点
    trainer.save_model(sft_output_dir)
    tokenizer.save_pretrained(sft_output_dir)
    print(f"[SFT] 检查点已保存到: {sft_output_dir}")
    
    return sft_output_dir


# ============ GRPO 阶段 ============

def score_with_gpt52(client: AzureOpenAI, question: str, answer: str, config: TrainConfig) -> float:
    """使用 GPT-5.2 给回答打分 (0-10)"""
    scoring_prompt = f"""你是一个 AIPC (AI PC) 领域的专家评审。请对以下问答进行打分。

问题: {question}

回答: {answer}

评分标准 (0-10分):
- 10分: 完美回答，准确、全面、无幻觉
- 7-9分: 大体正确，可能有小瑕疵
- 4-6分: 部分正确，有遗漏或小错误
- 1-3分: 基本错误或有严重幻觉
- 0分: 完全错误或拒绝回答

请只返回一个数字分数。"""

    try:
        response = client.chat.completions.create(
            model=config.reward_model,
            messages=[{"role": "user", "content": scoring_prompt}],
            temperature=0,
            max_tokens=10,
        )
        score_text = response.choices[0].message.content.strip()
        # 提取数字
        score = float(''.join(c for c in score_text if c.isdigit() or c == '.'))
        return min(max(score, 0), 10)  # 限制在 0-10
    except Exception as e:
        print(f"[GRPO] 评分失败: {e}")
        return 5.0  # 默认中等分


def generate_responses(model, tokenizer, prompt: str, num_responses: int, config: TrainConfig) -> List[str]:
    """为同一个 prompt 生成多个 response"""
    model.eval()
    input_text = format_prompt(prompt)
    inputs = tokenizer(input_text, return_tensors="pt").to(model.device)
    
    responses = []
    for _ in range(num_responses):
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.8,
                top_p=0.9,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id,
            )
        response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        responses.append(response)
    
    return responses


def grpo_train_step(
    model,
    ref_model,
    tokenizer,
    optimizer,
    prompt: str,
    responses: List[str],
    rewards: List[float],
    config: TrainConfig
) -> float:
    """GRPO 单步训练
    
    核心思想：
    - 组内相对排序：同一个 prompt 的多个 response，按 reward 排序
    - 优化目标：提高高奖励 response 的概率，降低低奖励 response 的概率
    """
    model.train()
    
    # 归一化 rewards（组内相对）
    rewards = torch.tensor(rewards, dtype=torch.float32)
    rewards = (rewards - rewards.mean()) / (rewards.std() + 1e-8)
    
    total_loss = 0.0
    
    for response, reward in zip(responses, rewards.tolist()):
        # 构建完整文本
        full_text = format_training_example(prompt, response)
        inputs = tokenizer(full_text, return_tensors="pt", truncation=True, max_length=config.max_length)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        # 当前模型的 log prob
        with torch.cuda.amp.autocast(dtype=torch.bfloat16):
            outputs = model(**inputs, labels=inputs["input_ids"])
            log_prob = -outputs.loss
        
        # 参考模型的 log prob（用于 KL 惩罚）
        with torch.no_grad():
            ref_outputs = ref_model(**inputs, labels=inputs["input_ids"])
            ref_log_prob = -ref_outputs.loss
        
        # GRPO loss: reward-weighted log prob + KL penalty
        kl_penalty = config.grpo_beta * (log_prob - ref_log_prob)
        loss = -(reward * log_prob - kl_penalty)
        
        total_loss += loss.item()
        
        # 反向传播
        loss.backward()
    
    # 更新参数
    optimizer.step()
    optimizer.zero_grad()
    
    return total_loss / len(responses)


def run_grpo_stage(model, tokenizer, feedback_data: List[Dict], config: TrainConfig):
    """运行 GRPO 阶段"""
    print("\n" + "="*50)
    print("阶段 2: GRPO 组相对策略优化")
    print("="*50)
    
    # 初始化 Azure OpenAI 客户端
    client = AzureOpenAI(
        azure_endpoint=config.azure_endpoint,
        api_key=config.azure_api_key,
        api_version=config.azure_api_version,
    )
    
    # 保存参考模型（用于 KL 惩罚）
    ref_model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    ref_model.eval()
    for param in ref_model.parameters():
        param.requires_grad = False
    
    # 优化器
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.grpo_lr)
    
    # 提取所有唯一的 prompt
    prompts = list(set(d['prompt'] for d in feedback_data))
    print(f"[GRPO] 唯一 prompt 数: {len(prompts)}")
    
    # 训练循环
    for epoch in range(config.grpo_epochs):
        print(f"\n[GRPO] Epoch {epoch + 1}/{config.grpo_epochs}")
        random.shuffle(prompts)
        
        epoch_loss = 0.0
        for i, prompt in enumerate(prompts):
            # 生成多个 response
            responses = generate_responses(model, tokenizer, prompt, config.grpo_group_size, config)
            
            # 用 GPT-5.2 打分
            rewards = [score_with_gpt52(client, prompt, resp, config) for resp in responses]
            
            # GRPO 训练步
            loss = grpo_train_step(
                model, ref_model, tokenizer, optimizer,
                prompt, responses, rewards, config
            )
            epoch_loss += loss
            
            if (i + 1) % 5 == 0:
                print(f"  [{i+1}/{len(prompts)}] avg_loss: {epoch_loss/(i+1):.4f}, rewards: {rewards}")
        
        print(f"[GRPO] Epoch {epoch + 1} 完成, 平均 loss: {epoch_loss/len(prompts):.4f}")
    
    # 保存最终模型
    final_output_dir = os.path.join(config.output_dir, "final")
    model.save_pretrained(final_output_dir)
    tokenizer.save_pretrained(final_output_dir)
    print(f"\n[GRPO] 最终模型已保存到: {final_output_dir}")
    
    # 清理参考模型
    del ref_model
    torch.cuda.empty_cache()


# ============ 主函数 ============

def main():
    print("="*60)
    print("AIPC 专家模型 V2 训练")
    print("两阶段训练: SFT + GRPO")
    print("="*60)
    
    set_seed(config.seed)
    
    # 加载数据
    print("\n[1] 加载用户反馈数据...")
    feedback_data = load_feedback_data(config.feedback_file)
    print(f"    总反馈数: {len(feedback_data)}")
    positive = sum(1 for d in feedback_data if d.get('feedback') == 'positive')
    negative = sum(1 for d in feedback_data if d.get('feedback') == 'negative')
    print(f"    正面: {positive}, 负面: {negative}")
    
    # 加载模型和 tokenizer
    print("\n[2] 加载基座模型...")
    tokenizer = AutoTokenizer.from_pretrained(config.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    print(f"    模型参数量: {model.num_parameters() / 1e9:.2f}B")
    
    # 阶段 1: SFT
    print("\n[3] 开始 SFT 阶段...")
    sft_dataset = prepare_sft_dataset(feedback_data)
    sft_checkpoint = run_sft_stage(model, tokenizer, sft_dataset, config)
    
    # 重新加载 SFT 检查点进行 GRPO
    print("\n[4] 加载 SFT 检查点进行 GRPO...")
    model = AutoModelForCausalLM.from_pretrained(
        sft_checkpoint,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    
    # 阶段 2: GRPO
    print("\n[5] 开始 GRPO 阶段...")
    run_grpo_stage(model, tokenizer, feedback_data, config)
    
    print("\n" + "="*60)
    print("训练完成！")
    print(f"最终模型位置: {config.output_dir}/final")
    print("="*60)


if __name__ == "__main__":
    main()
