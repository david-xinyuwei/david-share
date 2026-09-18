import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import json
import random
from tqdm import tqdm

# V1.1 模型路径
MODEL_PATH = "checkpoints/aipc_grpo_v1.1"
OUTPUT_FILE = "data/aipc_style_dpo.jsonl"

print(f"Loading model from {MODEL_PATH}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=False)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH, 
    torch_dtype=torch.bfloat16, 
    device_map="cuda",
    trust_remote_code=False
)

# 基础问题集 (模拟用户提问)
questions = [
    "什么是 AI PC？",
    "Intel Core Ultra 有什么特点？",
    "NPU 是什么？",
    "如何在本地运行大模型？",
    "AI PC 能做什么？",
    "Copilot 键有什么用？",
    "什么是混合 AI 算力？",
    "AI PC 对内存有什么要求？",
    "Snapdragon X Elite 怎么样？",
    "Windows 11 AI 功能有哪些？"
]

# 扩展问题集 (通过组合生成更多)
extended_questions = []
for q in questions:
    extended_questions.append(q)
    extended_questions.append(f"请简单介绍一下 {q}")
    extended_questions.append(f"详细说明 {q}")
    extended_questions.append(f"对于开发者来说，{q}")
    extended_questions.append(f"小白求问：{q}")

print(f"Generated {len(extended_questions)} prompts.")

# 风格 Prompt
STYLE_BRIEF = "请用非常简短、直接的要点回答，不要废话。"
STYLE_VERBOSE = "请详细阐述，包含背景介绍、技术细节和举例说明，字数要多。"

data = []

print("Generating DPO pairs...")
for q in tqdm(extended_questions):
    # 生成 Winner (简短)
    msgs_w = [{"role": "user", "content": f"{q}\n({STYLE_BRIEF})"}]
    inputs_w = tokenizer.apply_chat_template(msgs_w, return_tensors="pt", add_generation_prompt=True).to("cuda")
    out_w = model.generate(inputs_w, max_new_tokens=200, temperature=0.7)
    resp_w = tokenizer.decode(out_w[0][inputs_w.shape[1]:], skip_special_tokens=True)
    
    # 生成 Loser (啰嗦)
    msgs_l = [{"role": "user", "content": f"{q}\n({STYLE_VERBOSE})"}]
    inputs_l = tokenizer.apply_chat_template(msgs_l, return_tensors="pt", add_generation_prompt=True).to("cuda")
    out_l = model.generate(inputs_l, max_new_tokens=800, temperature=0.9) # 温度高一点增加多样性
    resp_l = tokenizer.decode(out_l[0][inputs_l.shape[1]:], skip_special_tokens=True)
    
    # 构建 DPO 数据项
    # 注意：Prompt 不包含风格指令，这样模型学会默认输出简短风格
    item = {
        "prompt": q,
        "chosen": [{"role": "user", "content": q}, {"role": "assistant", "content": resp_w}],
        "rejected": [{"role": "user", "content": q}, {"role": "assistant", "content": resp_l}]
    }
    data.append(item)

# 保存
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for item in data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"Saved {len(data)} DPO pairs to {OUTPUT_FILE}")
