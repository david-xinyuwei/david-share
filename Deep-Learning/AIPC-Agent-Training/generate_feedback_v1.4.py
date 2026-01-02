import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import json
import random
import ast
import re

# Load V1.3 (The "IT Pro" model)
MODEL_PATH = "checkpoints/aipc_dpo_v1.3"
print(f"Loading V1.3 from {MODEL_PATH}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=False)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.bfloat16,
    device_map="cuda",
    trust_remote_code=False
)

# Coding Prompts (Focus on AIPC tasks)
prompts = [
    "请写一个 Python 脚本，使用 ONNX Runtime 加载并运行 ResNet50 模型。",
    "如何使用 Python 检查当前系统的 NPU 是否可用？",
    "写一个脚本，将 PyTorch 模型导出为 ONNX 格式。",
    "使用 Python 编写一个简单的 RAG 检索流程，使用 ChromaDB。",
    "如何用 Python 监控 GPU 的显存使用情况？",
    "写一个脚本，对 Llama 3 模型进行 INT8 量化（使用 bitsandbytes）。",
    "编写一个 Python 函数，计算两个文本向量的余弦相似度。",
    "如何使用 Python 调用 Intel OpenVINO 进行推理？",
    "写一个脚本，批量调整图像大小以适配模型输入（224x224）。",
    "使用 Python 实现一个简单的多线程模型推理服务。"
]

def has_valid_python(text):
    """Check if text contains valid python code blocks"""
    code_blocks = re.findall(r'', text, re.DOTALL)
    if not code_blocks:
        return False, 0
    
    valid_blocks = 0
    for block in code_blocks:
        try:
            ast.parse(block)
            valid_blocks += 1
        except:
            pass
    return valid_blocks > 0, valid_blocks

def generate_response(prompt, temperature):
    messages = [{"role": "user", "content": prompt}]
    input_ids = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True).to("cuda")
    
    outputs = model.generate(
        input_ids,
        max_new_tokens=1024, # Allow longer output for code
        temperature=temperature,
        do_sample=True
    )
    return tokenizer.decode(outputs[0][input_ids.shape[1]:], skip_special_tokens=True)

output_file = "data/aipc_code_feedback_v1.4.jsonl"
print(f"Generating Code DPO data to {output_file}...")

with open(output_file, "w", encoding="utf-8") as f:
    for prompt in prompts:
        print(f"Processing: {prompt}")
        
        # Generate 2 candidates
        # Candidate A: High Temp (Creative/Random) - might stumble upon good code
        cand_a = generate_response(prompt, 0.9)
        # Candidate B: Low Temp (Stable) - might be too conservative/textual
        cand_b = generate_response(prompt, 0.4)
        
        is_valid_a, count_a = has_valid_python(cand_a)
        is_valid_b, count_b = has_valid_python(cand_b)
        
        chosen = None
        rejected = None
        
        # Logic: Prefer Valid Code > More Code > Text
        if is_valid_a and not is_valid_b:
            chosen, rejected = cand_a, cand_b
        elif is_valid_b and not is_valid_a:
            chosen, rejected = cand_b, cand_a
        elif count_a > count_b:
            chosen, rejected = cand_a, cand_b
        elif count_b > count_a:
            chosen, rejected = cand_b, cand_a
        
        if chosen and rejected:
            print(f"  [Match Found] Chosen has code, Rejected has less/no code.")
            entry = {
                "prompt": prompt,
                "chosen": [{"role": "user", "content": prompt}, {"role": "assistant", "content": chosen}],
                "rejected": [{"role": "user", "content": prompt}, {"role": "assistant", "content": rejected}]
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        else:
            print("  [Skip] Both similar code quality.")

print("Done.")
