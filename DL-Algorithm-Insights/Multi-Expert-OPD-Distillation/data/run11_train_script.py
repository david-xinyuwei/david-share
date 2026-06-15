#!/usr/bin/env python3
"""OPD Run 11: Multi-GPU DDP, Math student + Code teacher."""
import os, time, torch
from datetime import datetime
from datasets import load_dataset, Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM

print(f"[{datetime.now()}] Phase 0", flush=True)
print(f"  GPU count: {torch.cuda.device_count()}", flush=True)
print(f"  GPU 0: {torch.cuda.get_device_name(0)}", flush=True)

STUDENT_ID = "Qwen/Qwen2.5-Math-1.5B-Instruct"
TEACHER_ID = "Qwen/Qwen2.5-Coder-7B-Instruct"
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./outputs/run11")
os.makedirs(OUTPUT_DIR, exist_ok=True)
print(f"  Student: {STUDENT_ID}", flush=True)
print(f"  Teacher: {TEACHER_ID}", flush=True)

tok = AutoTokenizer.from_pretrained(STUDENT_ID, trust_remote_code=True)
if tok.pad_token is None: tok.pad_token = tok.eos_token

print(f"\n[{datetime.now()}] Phase 2: Multi-dataset code training", flush=True)
all_messages = []
try:
    mbpp = load_dataset("google-research-datasets/mbpp", "sanitized", split="train", trust_remote_code=True)
    print(f"  MBPP: {len(mbpp)} problems", flush=True)
    for ex in mbpp:
        if ex.get("prompt") and ex.get("code") and len(ex["prompt"]) > 30 and len(ex["code"]) > 30:
            all_messages.append({"messages":[
                {"role":"user","content":ex["prompt"][:1500]},
                {"role":"assistant","content":"```python\n"+ex["code"][:1500]+"\n```"}
            ]})
except Exception as e:
    print(f"  MBPP FAIL: {e}", flush=True)

try:
    ca = load_dataset("sahil2801/CodeAlpaca-20k", split="train", trust_remote_code=True)
    print(f"  CodeAlpaca: {len(ca)} total, sampling 3000", flush=True)
    for ex in ca.select(range(min(3000, len(ca)))):
        instr = ex.get("instruction", "") or ""
        inp = ex.get("input", "") or ""
        out = ex.get("output", "") or ""
        if len(instr) > 20 and len(out) > 20:
            user = instr + ("\n\n" + inp if inp.strip() else "")
            all_messages.append({"messages":[
                {"role":"user","content":user[:1500]},
                {"role":"assistant","content":out[:1500]}
            ]})
except Exception as e:
    print(f"  CodeAlpaca FAIL: {e}", flush=True)

print(f"\n  TOTAL combined samples: {len(all_messages)}", flush=True)
ds = Dataset.from_list(all_messages)

print(f"\n[{datetime.now()}] Phase 3: Trainer (DDP)", flush=True)
from trl.experimental.gkd import GKDTrainer, GKDConfig
config = GKDConfig(
    lmbda=1.0, beta=1.0, temperature=1.0,
    max_new_tokens=512,
    output_dir=f"{OUTPUT_DIR}/opd",
    learning_rate=5e-7,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    num_train_epochs=2,
    logging_steps=20,
    save_steps=50,
    save_total_limit=4,
    bf16=True,
    gradient_checkpointing=True,
    max_length=1536,
    max_grad_norm=0.5,
    report_to="none",
    remove_unused_columns=False,
    ddp_find_unused_parameters=False,
)
trainer = GKDTrainer(
    model=STUDENT_ID, teacher_model=TEACHER_ID,
    args=config, train_dataset=ds, processing_class=tok,
)

trainer.model.lm_head = trainer.model.lm_head.float()
print(f"  Student lm_head fp32 (rank {os.environ.get('LOCAL_RANK','0')})", flush=True)

import torch.nn as nn
STUDENT_VOCAB = 151936
old_w = trainer.teacher_model.lm_head.weight.data
new_lm = nn.Linear(trainer.teacher_model.lm_head.in_features, STUDENT_VOCAB, bias=False, dtype=old_w.dtype, device=old_w.device)
new_lm.weight.data = old_w[:STUDENT_VOCAB].clone()
trainer.teacher_model.lm_head = new_lm
trainer.teacher_model.config.vocab_size = STUDENT_VOCAB
print(f"  Teacher lm_head sliced to {STUDENT_VOCAB}", flush=True)

trainer.generation_kwargs["do_sample"] = True
trainer.generation_kwargs["top_p"] = 0.9
trainer.generation_kwargs["temperature"] = 1.0
trainer.generation_kwargs["top_k"] = 50
from transformers import GenerationConfig
trainer.generation_config = GenerationConfig(**trainer.generation_kwargs)

print(f"\n[{datetime.now()}] Training (~6-7 hours expected with DDP)", flush=True)
t0 = time.time()
trainer.train()
print(f"\n[{datetime.now()}] Done in {(time.time()-t0)/60:.1f}min", flush=True)
trainer.save_model(f"{OUTPUT_DIR}/opd/final")
