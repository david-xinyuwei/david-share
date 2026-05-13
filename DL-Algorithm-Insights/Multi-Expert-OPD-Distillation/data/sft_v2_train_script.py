#!/usr/bin/env python3
"""SFT v2: STANDARD lr=2e-5 (proper SFT lr, not OPD's 2e-7).
Same data as Run 11 OPD for fair comparison."""
import os, json, time, torch
from datetime import datetime
from datasets import load_dataset, Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer

print(f"[{datetime.now()}] Phase 0: Setup", flush=True)
print(f"  GPU count: {torch.cuda.device_count()}", flush=True)

STUDENT_ID = "Qwen/Qwen2.5-Math-1.5B-Instruct"
OUTPUT_DIR = "/root/opd_experiment/output_sft_v2"
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"  Student: {STUDENT_ID}", flush=True)
print(f"  Method: STANDARD SFT with proper lr=2e-5", flush=True)

tok = AutoTokenizer.from_pretrained(STUDENT_ID, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

print(f"\n[{datetime.now()}] Phase 1: Loading SAME datasets as Run 11", flush=True)
all_messages = []

try:
    mbpp = load_dataset("google-research-datasets/mbpp", "sanitized", split="train", trust_remote_code=True)
    print(f"  MBPP: {len(mbpp)} problems", flush=True)
    for ex in mbpp:
        if ex.get("prompt") and ex.get("code") and len(ex["prompt"]) > 30 and len(ex["code"]) > 30:
            all_messages.append({"messages": [
                {"role": "user", "content": ex["prompt"][:1500]},
                {"role": "assistant", "content": "```python\n" + ex["code"][:1500] + "\n```"}
            ]})
except Exception as e:
    print(f"  MBPP FAIL: {e}", flush=True)

try:
    ca = load_dataset("sahil2801/CodeAlpaca-20k", split="train", trust_remote_code=True)
    print(f"  CodeAlpaca: {len(ca)} total, sampling 2500", flush=True)
    for ex in ca.select(range(min(2500, len(ca)))):
        instr = ex.get("instruction", "") or ""
        inp = ex.get("input", "") or ""
        out = ex.get("output", "") or ""
        if len(instr) > 20 and len(out) > 20:
            user = instr + ("\n\n" + inp if inp.strip() else "")
            all_messages.append({"messages": [
                {"role": "user", "content": user[:1500]},
                {"role": "assistant", "content": out[:1500]}
            ]})
except Exception as e:
    print(f"  CodeAlpaca FAIL: {e}", flush=True)

print(f"\n  TOTAL samples: {len(all_messages)}", flush=True)

print(f"\n[{datetime.now()}] Phase 2: Tokenizing for SFT", flush=True)

def tokenize(example):
    text = tok.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False)
    enc = tok(text, truncation=True, max_length=1536, padding="max_length")
    enc["labels"] = enc["input_ids"].copy()
    enc["labels"] = [(-100 if t == tok.pad_token_id else t) for t in enc["labels"]]
    return enc

ds = Dataset.from_list(all_messages)
ds = ds.map(tokenize, remove_columns=["messages"], num_proc=4)
print(f"  Tokenized: {len(ds)} samples", flush=True)

print(f"\n[{datetime.now()}] Phase 3: Loading student model", flush=True)
model = AutoModelForCausalLM.from_pretrained(STUDENT_ID, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)

# 🔴 KEY DIFFERENCE: lr=2e-5 (standard SFT) instead of 2e-7 (OPD's lr)
args = TrainingArguments(
    output_dir=f"{OUTPUT_DIR}/sft",
    learning_rate=2e-5,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    num_train_epochs=2,
    logging_steps=20,
    save_steps=200,
    save_total_limit=3,
    bf16=True,
    gradient_checkpointing=True,
    max_grad_norm=1.0,
    warmup_ratio=0.03,
    lr_scheduler_type="cosine",
    report_to="none",
    remove_unused_columns=False,
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=ds,
    processing_class=tok,
)

print(f"\n[{datetime.now()}] Phase 4: SFT v2 Training (lr=2e-5, ~13 min expected)", flush=True)
t0 = time.time()
trainer.train()
elapsed = (time.time() - t0) / 60
print(f"\n[{datetime.now()}] SFT v2 done in {elapsed:.1f} min", flush=True)

trainer.save_model(f"{OUTPUT_DIR}/sft/final")
print(f"  Saved to {OUTPUT_DIR}/sft/final", flush=True)

with open(f"{OUTPUT_DIR}/sft_v2_meta.json", "w") as f:
    json.dump({
        "student": STUDENT_ID,
        "method": "Standard SFT",
        "samples": len(all_messages),
        "epochs": 2,
        "lr": 2e-5,
        "elapsed_min": elapsed,
    }, f, indent=2)
print(f"  Metadata saved", flush=True)
