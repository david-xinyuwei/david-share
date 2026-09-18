# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第4章 §4.1.2 微调中常见的参数

# 补充：导入语句
import torch
from transformers import TrainingArguments

training_arguments = TrainingArguments(
    output_dir="./results",
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    gradient_accumulation_steps=2,
    optim="adamw_8bit",
    logging_steps=50,
    learning_rate=1e-4,
    evaluation_strategy="steps",
    do_eval=True,
    eval_steps=50,
    save_steps=100,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    num_train_epochs=3,
    weight_decay=0.0,
    warmup_ratio=0.1,
    lr_scheduler_type="linear",
    gradient_checkpointing=True,
)
