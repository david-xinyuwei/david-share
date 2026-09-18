# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第4章 §4.1.3–4.1.9 微调超参数片段

from transformers import TrainingArguments

# §4.1.3 批大小（Batch Size）
TrainingArguments(
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    # 其他参数...
)

# §4.1.6 学习率与线性调度器
TrainingArguments(
    learning_rate=1e-4,                # 指定预热阶段结束后的目标学习率
    lr_scheduler_type="linear",   # 线性学习率调度
    warmup_steps=500,                 # 500步完成预热
    # ... 其他参数
)

# §4.1.7 优化器 + 预热
TrainingArguments(
    optim="adamw_8bit",
    learning_rate=1e-4,
    lr_scheduler_type="linear",
    warmup_steps=500,
    # ... 其他参数
)

# §4.1.8 半精度训练（BF16）
training_args = TrainingArguments(
    output_dir="./output",
    bf16=True,        # 启用BF16混合精度训练
    # 其他参数...
)

# §4.1.9 评估与保存步骤
TrainingArguments(
    evaluation_strategy="steps",
    eval_steps=500,          # 每500步进行一次评估
    save_steps=500,              # 通常与评估步数保持一致或为其整数倍
    save_total_limit=3,          # 最多保留3个检查点，避免磁盘溢出
    # ... 其他参数
)
