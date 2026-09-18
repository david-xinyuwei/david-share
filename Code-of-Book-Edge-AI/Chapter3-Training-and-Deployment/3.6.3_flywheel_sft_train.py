# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.6.3 训练飞轮实现方案 —— SFT 阶段
# 完整可运行版本见 projects/AIPC-Agent-Training/train_sft_aipc.py

# SFT 训练核心配置
import torch
from transformers import AutoModelForCausalLM, TrainingArguments
from trl import SFTTrainer
model = AutoModelForCausalLM.from_pretrained(
    "microsoft/Phi-3-mini-4k-instruct",
    torch_dtype=torch.bfloat16,
    device_map="auto"
)
training_args = TrainingArguments(
    output_dir="./checkpoints/aipc_sft_v1",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,  # 等效 batch_size=16
    learning_rate=2e-5,
    warmup_ratio=0.1,
    bf16=True,
    logging_steps=50,
    save_strategy="epoch"
)
trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    formatting_func=format_instruction  # 转换为 Phi-3 chat 格式
)
trainer.train()
