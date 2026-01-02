import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import gc

def load_model(path, name):
    print(f"Loading {name} from {path}...")
    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=torch.bfloat16, device_map="cuda", trust_remote_code=False)
    return model, tokenizer

def generate(model, tokenizer, question):
    messages = [{"role": "user", "content": question}]
    input_ids = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True).to("cuda")
    outputs = model.generate(input_ids, max_new_tokens=1024, temperature=0.6, do_sample=True)
    return tokenizer.decode(outputs[0][input_ids.shape[1]:], skip_special_tokens=True)

questions = [
    "写一个 Python 脚本，使用 ONNX Runtime 加载 ResNet50 模型。",
    "如何用 Python 检查 GPU 显存使用情况？",
    "编写一个函数计算两个向量的余弦相似度。"
]

model_v1_3, tokenizer_v1_3 = load_model("checkpoints/aipc_dpo_v1.3", "V1.3 IT Pro")
results_v1_3 = []
for q in questions:
    results_v1_3.append(generate(model_v1_3, tokenizer_v1_3, q))

del model_v1_3, tokenizer_v1_3
torch.cuda.empty_cache()
gc.collect()

model_v1_4, tokenizer_v1_4 = load_model("checkpoints/aipc_dpo_v1.4", "V1.4 Code Specialist")
results_v1_4 = []
for q in questions:
    results_v1_4.append(generate(model_v1_4, tokenizer_v1_4, q))

print("=" * 80)
for i, q in enumerate(questions):
    print(f"\nQ: {q}")
    print("-" * 40)
    print(f"V1.3:\n{results_v1_3[i].strip()}")
    print("-" * 40)
    print(f"V1.4:\n{results_v1_4[i].strip()}")
    code_v13 = results_v1_3[i].count("```python")
    code_v14 = results_v1_4[i].count("```python")
    print(f"\nCode Blocks: V1.3={code_v13}, V1.4={code_v14}")
    print("=" * 80)
