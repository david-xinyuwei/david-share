import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import gc

def load_model(path):
    print(f"Loading model from {path}...")
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        path,
        torch_dtype=torch.bfloat16,
        device_map="cuda",
        trust_remote_code=False
    )
    return model, tokenizer

def generate(model, tokenizer, question):
    messages = [{"role": "user", "content": question}]
    input_ids = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True).to("cuda")
    outputs = model.generate(
        input_ids,
        max_new_tokens=512,
        temperature=0.6,
        do_sample=True
    )
    response = tokenizer.decode(outputs[0][input_ids.shape[1]:], skip_special_tokens=True)
    return response

questions = [
    "如何选购一台适合开发 AI 应用的 AI PC？",
    "在笔记本上运行 7B 模型需要多少内存？",
    "NPU 和 GPU 在 AI 推理任务上有什么区别？"
]

# --- Test V1.2 ---
model_v1_2, tokenizer_v1_2 = load_model("checkpoints/aipc_dpo_v1.2")
results_v1_2 = []
print("\n=== Generating V1.2 Responses ===")
for q in questions:
    print(f"Processing: {q}")
    results_v1_2.append(generate(model_v1_2, tokenizer_v1_2, q))

del model_v1_2
del tokenizer_v1_2
torch.cuda.empty_cache()
gc.collect()

# --- Test V1.3 ---
model_v1_3, tokenizer_v1_3 = load_model("checkpoints/aipc_dpo_v1.3")
results_v1_3 = []
print("\n=== Generating V1.3 Responses ===")
for q in questions:
    print(f"Processing: {q}")
    results_v1_3.append(generate(model_v1_3, tokenizer_v1_3, q))

# --- Report ---
print("\n" + "="*80)
print(" V1.2 vs V1.3 Comparison Report")
print("="*80)

for i, q in enumerate(questions):
    print(f"\n❓ Question: {q}")
    print("-"*40)
    print(f"🤖 V1.2 (Concise):\n{results_v1_2[i].strip()}")
    print("-"*40)
    print(f"🚀 V1.3 (IT Pro):\n{results_v1_3[i].strip()}")
    print("="*80)
