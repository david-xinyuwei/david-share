# 1_train_embedding.py  v2
# ------------------------------------------------------------
# 对比学习微调句向量模型（兼容 s-t 2.4/2.5）
# 改动：epoch=3、默认基座 intfloat/e5-base、可轻松调参
# ------------------------------------------------------------

import torch, os, argparse
from datasets import load_dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
    losses,
    evaluation,
)

# ------------------------------------------------------------
# 命令行参数
# ------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--base_model", default="intfloat/e5-base", help="HF model repo")
parser.add_argument("--epochs", type=int, default=3, help="training epochs")
parser.add_argument("--bsz", type=int, default=16, help="batch size per device")
parser.add_argument("--lr",  type=float, default=2e-5, help="learning rate")
args = parser.parse_args()

print(f"基座模型: {args.base_model}")
print(f"Epochs:   {args.epochs} | Batch: {args.bsz} | LR: {args.lr}")

device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", device)

# ------------------------------------------------------------
# 1) 数据
# ------------------------------------------------------------
DATASET_NAME = "shawhin/ai-job-embedding-finetuning"
ds = load_dataset(DATASET_NAME)
print(ds)

# ------------------------------------------------------------
# 2) 模型
# ------------------------------------------------------------
model = SentenceTransformer(args.base_model, device=device)

# ------------------------------------------------------------
# 3) 评估器
# ------------------------------------------------------------
val_evaluator = evaluation.TripletEvaluator(
    anchors   = ds["validation"]["query"],
    positives = ds["validation"]["job_description_pos"],
    negatives = ds["validation"]["job_description_neg"],
    name="val"
)

# ------------------------------------------------------------
# 4) 损失
# ------------------------------------------------------------
loss_fn = losses.MultipleNegativesRankingLoss(model)

# ------------------------------------------------------------
# 5) 训练参数（兼容旧 API）
# ------------------------------------------------------------
train_args = SentenceTransformerTrainingArguments(
    output_dir               = "runs/finetuned",
    overwrite_output_dir     = True,
    num_train_epochs         = args.epochs,
    per_device_train_batch_size = args.bsz,
    learning_rate            = args.lr,
    warmup_ratio             = 0.1,
    fp16                     = True,
    report_to                = [],
)

# ------------------------------------------------------------
# 6) Trainer
# ------------------------------------------------------------
trainer = SentenceTransformerTrainer(
    model         = model,
    args          = train_args,
    train_dataset = ds["train"],
    eval_dataset  = ds["validation"],
    loss          = loss_fn,
    evaluator     = val_evaluator,
)

trainer.train()
model.save("runs/finetuned/final")
print("✓ Training finished. Model saved to runs/finetuned/final")
