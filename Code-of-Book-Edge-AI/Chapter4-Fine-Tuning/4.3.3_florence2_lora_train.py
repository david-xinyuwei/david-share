# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第4章 §4.3.3 微调Florence-2 —— 2. 训练

# 补充：导入语句（完整 Notebook 见 projects/Florence-2/Florence2_LoRA_ObjectDetection.ipynb）
import os
import torch
from tqdm import tqdm
from torch.optim import AdamW
from transformers import get_scheduler
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 定义Florence-2模型的微调训练函数
def train_model(train_loader, val_loader, model, processor, epochs=10, lr=1e-6):
    # 设置优化器AdamW与线性学习率调度器（learning rate scheduler）
    optimizer = AdamW(model.parameters(), lr=lr)
    num_training_steps = epochs * len(train_loader)
    lr_scheduler = get_scheduler(
        name="linear",
        optimizer=optimizer,
        num_warmup_steps=0,
        num_training_steps=num_training_steps,
    )
    # 在训练前展示模型初始推理效果，以便直观观察训练前的模型性能
    render_inference_results(model, val_loader.dataset, num_samples=6)
    # 开始epoch循环训练
    for epoch in range(epochs):
        # 将模型设置为训练模式（启用dropout等训练特定层的功能）
        model.train()
        total_train_loss = 0
        # 批量数据遍历（每一个batch逐步更新模型参数）
        for inputs, answers in tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs} - Training"):
            # 加载批次输入数据到指定设备
            input_ids = inputs["input_ids"].to(DEVICE)            # 问题文本token
            pixel_values = inputs["pixel_values"].to(DEVICE)      # 图像数据tensor
            # 使用processor.tokenizer将答案文本转换为模型训练所需的token ids标签形式
            labels = processor.tokenizer(
                text=answers,
                return_tensors="pt",
                padding=True,
                return_token_type_ids=False
            ).input_ids.to(DEVICE)
            # 模型前向传播，计算预测输出及交叉熵损失
            outputs = model(input_ids=input_ids, pixel_values=pixel_values, labels=labels)
            loss = outputs.loss  # 模型内置的交叉熵损失（CrossEntropyLoss）
            # 执行梯度反向传播与优化器参数更新
            loss.backward()       # 反向传播计算梯度
            optimizer.step()      # 执行一次优化器参数更新
            lr_scheduler.step()   # 更新学习率
            optimizer.zero_grad() # 梯度清零，为下次更新做准备
            # 累计当前batch的训练损失
            total_train_loss += loss.item()
        # 每个epoch训练完成后，计算并输出本轮训练的平均损失
        avg_train_loss = total_train_loss / len(train_loader)
        print(f"Epoch {epoch+1} Avg Train Loss: {avg_train_loss:.4f}")
        # 模型验证阶段，评估模型泛化性能与训练进展情况
        model.eval()  # 将模型设定为评估模式（关闭dropout、batchnorm更新等）
        total_val_loss = 0
        # 验证时不更新模型参数，因此使用torch.no_grad()上下文管理
        with torch.no_grad():
            for inputs, answers in tqdm(val_loader, desc=f"Epoch {epoch+1}/{epochs} - Validation"):
                input_ids = inputs["input_ids"].to(DEVICE)          # 验证集问题文本token
                pixel_values = inputs["pixel_values"].to(DEVICE)    # 验证集图像数据tensor
                # 准备验证阶段的真实答案标签
                labels = processor.tokenizer(
                    text=answers,
                    return_tensors="pt",
                    padding=True,
                    return_token_type_ids=False
                ).input_ids.to(DEVICE)
                # 模型前向传播计算预测结果与损失（此阶段参数不更新）
                outputs = model(input_ids=input_ids, pixel_values=pixel_values, labels=labels)
                loss = outputs.loss
                # 累计验证损失
                total_val_loss += loss.item()
        # 每个epoch验证结束后，计算并输出验证损失的平均值
        avg_val_loss = total_val_loss / len(val_loader)
        print(f"Epoch {epoch+1} Avg Validation Loss: {avg_val_loss:.4f}")
        # 每个epoch后调用可视化函数，直观查看模型在验证集上的预测效果
        render_inference_results(model, val_loader.dataset, num_samples=6)
        # 训练结束后每个epoch都保存一次当前模型参数与processor，供后续评估或再次训练使用
        output_dir = f"./model_checkpoints/epoch_{epoch+1}"
        os.makedirs(output_dir, exist_ok=True)
        model.save_pretrained(output_dir)
        processor.save_pretrained(output_dir)

# 启动训练
# @title Run train loop
# %%time
EPOCHS = 30
LR = 5e-6
train_model(train_loader, val_loader, peft_model, processor, epochs=EPOCHS, lr=LR)

# 训练后保存 LoRA adapter
peft_model.save_pretrained("/content/florence2-lora")
processor.save_pretrained("/content/florence2-lora/")
