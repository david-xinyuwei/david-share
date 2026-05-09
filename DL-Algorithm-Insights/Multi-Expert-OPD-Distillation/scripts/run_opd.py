#!/usr/bin/env python3
"""
OPD Verification Experiment
Based on thunlp/OPD paper (arXiv:2604.13016)
Student: DeepSeek-R1-Distill-Qwen-1.5B
Teacher: JustRL-DeepSeek-1.5B (thunlp released checkpoint)

Usage:
    python3 -u run_opd.py 2>&1 | tee run.log

Environment:
    - NVIDIA H100 NVL (95 GB) or equivalent
    - PyTorch >= 2.11, TRL >= 1.4.0
    - pip install torch trl transformers datasets accelerate
"""
import os
import json
import time
import torch
from datetime import datetime
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM

# ============= Phase 0: Check environment =============
print(f"[{datetime.now()}] Phase 0: Environment check")
print(f"  torch={torch.__version__}, cuda={torch.cuda.is_available()}")
print(f"  GPU: {torch.cuda.get_device_name(0)}")
print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

# ============= Phase 1: Download models =============
print(f"\n[{datetime.now()}] Phase 1: Downloading models...")

STUDENT_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
TEACHER_ID = "hbx/JustRL-DeepSeek-1.5B"
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"  Student: {STUDENT_ID}")
print(f"  Teacher: {TEACHER_ID}")

tokenizer = AutoTokenizer.from_pretrained(STUDENT_ID, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Quick test: load both models to verify they fit in memory
print(f"\n[{datetime.now()}] Loading student model...")
student = AutoModelForCausalLM.from_pretrained(
    STUDENT_ID, dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
)
student_params = sum(p.numel() for p in student.parameters()) / 1e9
print(f"  Student params: {student_params:.2f}B")
print(f"  VRAM after student: {torch.cuda.memory_allocated()/1e9:.2f} GB")

print(f"\n[{datetime.now()}] Loading teacher model...")
teacher = AutoModelForCausalLM.from_pretrained(
    TEACHER_ID, dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
)
teacher_params = sum(p.numel() for p in teacher.parameters()) / 1e9
print(f"  Teacher params: {teacher_params:.2f}B")
print(f"  VRAM after both: {torch.cuda.memory_allocated()/1e9:.2f} GB")

# Free models for now (GKDTrainer will reload)
del student, teacher
torch.cuda.empty_cache()

# ============= Phase 2: Prepare dataset =============
print(f"\n[{datetime.now()}] Phase 2: Preparing dataset...")

dataset = load_dataset("openai/gsm8k", "main", split="train[:500]")
print(f"  Dataset size: {len(dataset)} samples")
print(f"  Sample: {dataset[0]['question'][:100]}...")

def format_for_gkd(example):
    return {
        "messages": [
            {"role": "user", "content": example["question"]},
            {"role": "assistant", "content": example["answer"]}
        ]
    }

dataset = dataset.map(format_for_gkd, remove_columns=dataset.column_names)
print(f"  Formatted dataset ready")

# ============= Phase 3: OPD Training =============
print(f"\n[{datetime.now()}] Phase 3: Starting OPD training...")
print(f"  This may take 30-60 minutes...")

from trl.experimental.gkd import GKDTrainer, GKDConfig

config = GKDConfig(
    lmbda=1.0,          # 100% on-policy (OPD)
    beta=1.0,           # reverse KL (OPD)
    temperature=1.0,
    max_new_tokens=512,
    output_dir=f"{OUTPUT_DIR}/opd",
    learning_rate=1e-6,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
    num_train_epochs=1,
    logging_steps=5,
    save_steps=100,
    save_total_limit=2,
    bf16=True,
    gradient_checkpointing=True,
    max_length=1024,
    report_to="none",
    remove_unused_columns=False,
)

print(f"  Config: lmbda={config.lmbda}, beta={config.beta}")

trainer = GKDTrainer(
    model=STUDENT_ID,
    teacher_model=TEACHER_ID,
    args=config,
    train_dataset=dataset,
    processing_class=tokenizer,
)

# Fix bf16 NaN: clamp sampling distribution during on-policy generation
# Without this, bf16 logits can overflow -> NaN probabilities -> CUDA assert
trainer.model.generation_config.top_k = 50
trainer.model.generation_config.top_p = 0.95
trainer.model.generation_config.do_sample = True
print(f"  Generation config patched: top_k=50, top_p=0.95")

t0 = time.time()
trainer.train()
train_time = time.time() - t0
print(f"\n[{datetime.now()}] OPD training complete in {train_time/60:.1f} minutes")

trainer.save_model(f"{OUTPUT_DIR}/opd/final")
print(f"  Model saved to {OUTPUT_DIR}/opd/final")

# ============= Phase 4: Quick evaluation =============
print(f"\n[{datetime.now()}] Phase 4: Quick evaluation on 20 GSM8K test samples...")

eval_dataset = load_dataset("openai/gsm8k", "main", split="test[:20]")

opd_model = AutoModelForCausalLM.from_pretrained(
    f"{OUTPUT_DIR}/opd/final", dtype=torch.bfloat16, device_map="auto"
)

def extract_answer(text):
    """Extract the numerical answer from GSM8K #### format"""
    lines = text.strip().split('\n')
    for line in reversed(lines):
        if '####' in line:
            return line.split('####')[-1].strip()
    return None

correct = 0
total = 0
for ex in eval_dataset:
    prompt = f"<|im_start|>user\n{ex['question']}<|im_end|>\n<|im_start|>assistant\n"
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    with torch.no_grad():
        outputs = opd_model.generate(**inputs, max_new_tokens=512, do_sample=False)
    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

    pred_answer = extract_answer(response)
    gold_answer = extract_answer(ex['answer'])

    if pred_answer and gold_answer and pred_answer.strip() == gold_answer.strip():
        correct += 1
    total += 1

accuracy = correct / total * 100
print(f"  OPD model accuracy: {correct}/{total} = {accuracy:.1f}%")

results = {
    "experiment": "OPD_verification",
    "student": STUDENT_ID,
    "teacher": TEACHER_ID,
    "dataset": "gsm8k_train_500",
    "eval_dataset": "gsm8k_test_20",
    "opd_config": {"lmbda": 1.0, "beta": 1.0, "lr": 1e-6},
    "training_time_minutes": train_time / 60,
    "opd_accuracy": accuracy,
    "timestamp": datetime.now().isoformat(),
}

with open(f"{OUTPUT_DIR}/results.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"\n[{datetime.now()}] Results saved to {OUTPUT_DIR}/results.json")
print(f"Done!")
