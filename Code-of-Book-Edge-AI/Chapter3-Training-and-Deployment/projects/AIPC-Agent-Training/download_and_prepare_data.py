"""Download HF datasets and convert to AIPC training format"""
import json
import os
import random

# === Step 1: Download datasets ===
print("=== Downloading datasets ===")
from datasets import load_dataset

# SFT: bitext customer support (26.9K instruction/response pairs)
print("Downloading bitext/Bitext-customer-support-llm-chatbot-training-dataset...")
ds_bitext = load_dataset("bitext/Bitext-customer-support-llm-chatbot-training-dataset", split="train")
print(f"  bitext: {len(ds_bitext)} rows, columns={ds_bitext.column_names}")

# SFT: IT helpdesk tickets (500 IT-specific)
print("Downloading Console-AI/IT-helpdesk-synthetic-tickets...")
ds_it = load_dataset("Console-AI/IT-helpdesk-synthetic-tickets", split="train")
print(f"  IT helpdesk: {len(ds_it)} rows, columns={ds_it.column_names}")

# DPO: LLaMA customer support preference
print("Downloading debabrata-ai/llama3-customer-support-preference...")
try:
    ds_dpo = load_dataset("debabrata-ai/llama3-customer-support-preference", split="train")
    print(f"  DPO preference: {len(ds_dpo)} rows, columns={ds_dpo.column_names}")
except Exception as e:
    print(f"  DPO preference download failed: {e}")
    ds_dpo = None

# === Step 2: Convert to SFT format ===
print("\n=== Converting SFT data ===")
sft_data = []

# From bitext: instruction -> prompt, response -> completion
# Sample 500 to keep training fast for demo
bitext_samples = list(range(len(ds_bitext)))
random.seed(42)
random.shuffle(bitext_samples)
for idx in bitext_samples[:400]:
    row = ds_bitext[idx]
    instruction = row.get("instruction") or row.get("input", "")
    response = row.get("response") or row.get("output", "")
    if instruction and response and len(response) > 20:
        sft_data.append({"prompt": instruction, "completion": response})

# From IT helpdesk: subject+description -> prompt, generate completion template
for i in range(len(ds_it)):
    row = ds_it[i]
    subject = row.get("subject", "")
    description = row.get("description", "")
    priority = row.get("priority", "")
    category = row.get("category", "")
    if subject and description:
        prompt = f"{subject}\n{description}"
        completion = f"工单分类: {category}\n优先级: {priority}\n\n建议处理步骤:\n1. 确认问题详情并验证用户身份\n2. 检查 {category} 相关系统状态\n3. 根据 {priority} 优先级安排处理时间\n4. 执行修复并验证\n5. 通知用户并更新工单状态"
        sft_data.append({"prompt": prompt, "completion": completion})

random.shuffle(sft_data)
print(f"Total SFT samples: {len(sft_data)}")

# Split train/val
val_size = min(50, len(sft_data) // 10)
train_data = sft_data[val_size:]
val_data = sft_data[:val_size]

os.makedirs("data", exist_ok=True)
with open("data/aipc_sft_train.jsonl", "w", encoding="utf-8") as f:
    for item in train_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
with open("data/aipc_sft_val.jsonl", "w", encoding="utf-8") as f:
    for item in val_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
print(f"SFT train: {len(train_data)}, val: {len(val_data)}")

# === Step 3: Convert DPO data ===
print("\n=== Converting DPO data ===")
if ds_dpo is not None:
    dpo_data = []
    cols = ds_dpo.column_names
    print(f"  DPO columns: {cols}")
    # Try common column patterns
    for i in range(len(ds_dpo)):
        row = ds_dpo[i]
        prompt = row.get("prompt") or row.get("instruction") or row.get("query") or row.get("question", "")
        chosen = row.get("chosen") or row.get("preferred") or row.get("response_a", "")
        rejected = row.get("rejected") or row.get("dispreferred") or row.get("response_b", "")
        
        # Handle if chosen/rejected are strings vs lists
        if isinstance(chosen, str) and isinstance(rejected, str) and prompt:
            dpo_data.append({
                "prompt": prompt,
                "chosen": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": chosen}
                ],
                "rejected": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": rejected}
                ]
            })
        elif isinstance(chosen, list) and isinstance(rejected, list) and prompt:
            dpo_data.append({
                "prompt": prompt,
                "chosen": chosen,
                "rejected": rejected
            })
        
        if len(dpo_data) >= 200:  # Cap at 200 for demo
            break
    
    # Split into style/feedback/code DPO sets
    random.shuffle(dpo_data)
    n = len(dpo_data)
    style_n = min(80, n // 3)
    feedback_n = min(80, n // 3)
    code_n = min(40, n - style_n - feedback_n)
    
    style_dpo = dpo_data[:style_n]
    feedback_dpo = dpo_data[style_n:style_n+feedback_n]
    code_dpo = dpo_data[style_n+feedback_n:style_n+feedback_n+code_n]
    
    for name, data in [("aipc_style_dpo", style_dpo), ("aipc_feedback_v1.3", feedback_dpo), ("aipc_code_feedback_v1.4", code_dpo)]:
        with open(f"data/{name}.jsonl", "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  {name}: {len(data)} pairs")
else:
    # Fallback: generate DPO from bitext by pairing good/bad responses
    print("  DPO preference dataset not available, generating from bitext...")
    dpo_style = []
    for i in range(0, min(200, len(ds_bitext)), 2):
        r1 = ds_bitext[i]
        r2 = ds_bitext[i+1] if i+1 < len(ds_bitext) else ds_bitext[0]
        prompt = r1.get("instruction", "")
        resp1 = r1.get("response", "")
        resp2 = r2.get("response", "")
        if prompt and resp1 and resp2 and resp1 != resp2:
            # Shorter = chosen (style preference)
            if len(resp1) <= len(resp2):
                chosen, rejected = resp1, resp2
            else:
                chosen, rejected = resp2, resp1
            dpo_style.append({
                "prompt": prompt,
                "chosen": [{"role": "user", "content": prompt}, {"role": "assistant", "content": chosen}],
                "rejected": [{"role": "user", "content": prompt}, {"role": "assistant", "content": rejected}]
            })
    
    random.shuffle(dpo_style)
    n = len(dpo_style)
    for name, start, end in [("aipc_style_dpo", 0, n//3), ("aipc_feedback_v1.3", n//3, 2*n//3), ("aipc_code_feedback_v1.4", 2*n//3, n)]:
        subset = dpo_style[start:end]
        with open(f"data/{name}.jsonl", "w", encoding="utf-8") as f:
            for item in subset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"  {name}: {len(subset)} pairs")

print("\n=== Data preparation complete ===")
for f in sorted(os.listdir("data")):
    if f.endswith(".jsonl"):
        count = sum(1 for _ in open(f"data/{f}"))
        print(f"  data/{f}: {count} rows")
