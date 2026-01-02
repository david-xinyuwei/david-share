import torch
import json
import random
from transformers import AutoModelForCausalLM, AutoTokenizer

# === 配置 ===
MODEL_PATH = "checkpoints/aipc_dpo_v1.2"
OUTPUT_FILE = "data/aipc_feedback_v1.3.jsonl"
NUM_SAMPLES = 20  # 模拟收集 20 条高质量反馈

# === 模拟客户问题库 (实战向) ===
CUSTOMER_QUESTIONS = [
    "如何在 AI PC 上部署 Llama 3 8B 模型？",
    "NPU 和 GPU 在运行 Stable Diffusion 时能耗差多少？",
    "Intel Core Ultra 的 NPU 支持哪些量化格式？",
    "企业内部部署 AI PC 需要什么样的安全策略？",
    "DirectML 和 OpenVINO 哪个推理速度更快？",
    "32GB 内存够不够跑 7B 模型并同时开 Teams 会议？",
    "如何用 Python 调用本地 NPU 进行推理？",
    "AI PC 离线状态下能使用 Copilot 的哪些功能？",
    "把旧笔记本升级成 AI PC 需要换哪些硬件？",
    "本地知识库 RAG 检索速度太慢怎么优化？"
]

def main():
    print(f"Loading V1.2 model from {MODEL_PATH}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, 
        torch_dtype=torch.bfloat16, 
        device_map="cuda",
        trust_remote_code=False
    )

    print("Starting Customer Feedback Simulation...")
    feedback_data = []

    for q in CUSTOMER_QUESTIONS:
        print(f"\nSimulating user interaction for: {q}")
        
        # 构造 Prompt
        messages = [{"role": "user", "content": q}]
        input_ids = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True).to("cuda")

        # 生成两个回答 (A/B Test)
        # 回答 A: 尝试生成更务实、带步骤的回答 (模拟 Good Case)
        outputs_a = model.generate(
            input_ids, 
            max_new_tokens=512, 
            temperature=0.6, # 低温，更严谨
            do_sample=True,
            repetition_penalty=1.1
        )
        response_a = tokenizer.decode(outputs_a[0][input_ids.shape[1]:], skip_special_tokens=True)

        # 回答 B: 尝试生成稍微发散、理论化的回答 (模拟 Bad Case)
        outputs_b = model.generate(
            input_ids, 
            max_new_tokens=512, 
            temperature=0.9, # 高温，较发散
            do_sample=True
        )
        response_b = tokenizer.decode(outputs_b[0][input_ids.shape[1]:], skip_special_tokens=True)

        # === 模拟客户偏好逻辑 (Customer Persona Logic) ===
        # 客户偏好：包含数字、列表、步骤、英文术语的回答
        score_a = 0
        score_b = 0
        
        indicators = ["1.", "-", "步骤", "GB", "W", "INT8", "FP16", "pip install", "import"]
        
        for ind in indicators:
            if ind in response_a: score_a += 1
            if ind in response_b: score_b += 1
            
        # 长度惩罚 (客户讨厌太长)
        if len(response_a) > 600: score_a -= 2
        if len(response_b) > 600: score_b -= 2

        # 判定胜负
        if score_a >= score_b:
            chosen = response_a
            rejected = response_b
            reason = "Response A 包含更多实战细节和结构化信息"
        else:
            chosen = response_b
            rejected = response_a
            reason = "Response B 包含更多实战细节和结构化信息"

        # 记录数据
        entry = {
            "prompt": q,
            "chosen": [
                {"role": "user", "content": q},
                {"role": "assistant", "content": chosen}
            ],
            "rejected": [
                {"role": "user", "content": q},
                {"role": "assistant", "content": rejected}
            ],
            "metadata": {"source": "simulated_customer_feedback", "reason": reason}
        }
        feedback_data.append(entry)
        print(f"  [User Choice] Selected response with score {max(score_a, score_b)} vs {min(score_a, score_b)}")

    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for item in feedback_data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')
            
    print(f"\n✅ Collected {len(feedback_data)} feedback entries to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
