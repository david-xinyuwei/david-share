# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.6.3 训练飞轮实现方案 —— DPO 阶段
# 完整可运行版本见 projects/AIPC-Agent-Training/train_dpo_style.py

from trl import DPOTrainer, DPOConfig
dpo_config = DPOConfig(
    output_dir="./checkpoints/aipc_dpo_v1.2",
    learning_rate=1e-7,            # 极小学习率，避免灾难性遗忘
    beta=0.1,                # DPO 温度系数
    num_train_epochs=5,      # 更多 epoch 补偿低学习率
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    bf16=True,
    logging_steps=10,
    save_strategy="epoch"
)
trainer = DPOTrainer(
    model=model,
    ref_model=ref_model,     # 参考模型（冻结）
    args=dpo_config,
    train_dataset=dpo_dataset,
    tokenizer=tokenizer,
)
trainer.train()
