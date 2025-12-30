#!/usr/bin/env python3
"""
反馈数据生成脚本
================
模拟用户对模型回答的反馈，生成：
1. DPO 数据: (prompt, chosen, rejected) - 用于学习边界
2. GRPO Prompts: 只有问题 - 用于实时采样优化

用法:
    python generate_feedback_data.py \
        --model http://localhost:8000 \
        --questions data/test_questions.jsonl \
        --output-dpo data/dpo_v2.jsonl \
        --output-grpo-prompts data/grpo_prompts_v2.jsonl
"""

import os
import json
import argparse
import requests
from datetime import datetime
from openai import AzureOpenAI


# ============ AIPC 测试问题集 ============
DEFAULT_QUESTIONS = [
    # 基础概念
    "什么是 AI PC？",
    "AI PC 是什么意思？",
    "请解释一下 AIPC 的概念",
    "AI PC 的定义是什么？",
    "能介绍一下人工智能电脑吗？",
    
    # NPU 相关
    "AI PC 里的 NPU 是什么？",
    "什么是神经网络处理器？",
    "NPU 和 GPU 有什么区别？",
    "为什么 AI PC 需要 NPU？",
    "NPU 的 TOPS 是什么意思？",
    
    # 厂商产品
    "哪些厂商在做 AI PC？",
    "Intel 的 AI PC 芯片叫什么？",
    "AMD 有 AI PC 产品吗？",
    "高通的 AI PC 方案是什么？",
    "Intel Core Ultra 有什么特点？",
    "AMD Ryzen AI 是什么？",
    "Qualcomm Snapdragon X 系列是什么？",
    "Intel Core Ultra 的 NPU 有多少 TOPS？",
    "AMD Ryzen AI 和 Intel Core Ultra 哪个 NPU 更强？",
    "Copilot+ PC 需要多少 TOPS？",
    
    # 应用场景
    "AI PC 能做什么？",
    "AI PC 的典型应用有哪些？",
    "什么是 Windows Copilot？",
    "AI PC 能运行本地大模型吗？",
    "AI PC 支持实时翻译吗？",
    "AI PC 的摄像头有什么智能功能？",
    
    # Microsoft 相关
    "什么是 Copilot+ PC？",
    "Copilot+ PC 和普通 AI PC 有什么区别？",
    "Microsoft 对 AI PC 有什么定义？",
    
    # 误区澄清
    "AIPC 是阿里云的产品吗？",
    "AIPC 是云服务吗？",
    "AI PC 必须联网吗？",
    "AI PC 和云端 AI 有什么区别？",
    "AI PC 需要订阅费吗？",
    
    # 技术细节
    "AI PC 的功耗怎么样？",
    "NPU 和 CPU 内置的 AI 加速有什么区别？",
    "AI PC 支持哪些 AI 框架？",
    "AI PC 能运行多大的模型？",
    
    # 市场趋势
    "AI PC 什么时候开始流行的？",
    "2024 年有哪些 AI PC 新品？",
    "AI PC 的市场前景如何？",
    
    # 选购建议
    "如何选择 AI PC？",
    "买 AI PC 需要注意什么？",
    "Intel 和 AMD 的 AI PC 怎么选？",
    "AI PC 值得买吗？",
    
    # 开发相关
    "如何在 AI PC 上开发 AI 应用？",
    "AI PC 支持 ONNX 吗？",
    "Intel OpenVINO 是什么？",
    "如何优化 NPU 推理性能？",
]


def get_model_response(vllm_url: str, question: str, model_name: str = "model") -> str:
    """调用 vLLM 获取模型回答"""
    try:
        response = requests.post(
            vllm_url,
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": "你是 AIPC 智能助手，专门解答 AI PC 相关问题。回答要专业、准确、简洁。"},
                    {"role": "user", "content": question}
                ],
                "max_completion_tokens": 500,
                "temperature": 0.7
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"模型调用失败: {e}")
        return ""


def evaluate_with_gpt(client: AzureOpenAI, question: str, answer: str) -> dict:
    """用 GPT 评估回答质量，返回分数和正确答案（如果需要）"""
    eval_prompt = f"""评估以下 AIPC 相关问题的回答质量。

问题: {question}
回答: {answer}

请严格按照以下 JSON 格式输出（不要输出其他内容）:
{{
    "score": <0-10的整数>,
    "feedback": "<简短评价>",
    "correct_answer": "<如果回答错误或不完整，提供正确答案；如果回答正确，填 null>"
}}

评分标准:
- 9-10: 完全正确，专业详细
- 7-8: 基本正确，可以更完善
- 4-6: 部分正确，有明显错误或遗漏
- 1-3: 大部分错误或答非所问
- 0: 完全错误或有害"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": eval_prompt}],
            max_completion_tokens=1000,
            temperature=0
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"GPT 评估失败: {e}")
        return {"score": -1, "feedback": str(e), "correct_answer": None}


def main():
    parser = argparse.ArgumentParser(description="生成反馈数据")
    parser.add_argument("--model", default="http://localhost:8000/v1/chat/completions",
                        help="vLLM 服务地址")
    parser.add_argument("--model-name", default="model", help="模型名称")
    parser.add_argument("--questions", help="问题文件 (jsonl)")
    parser.add_argument("--output-dpo", default="./data/dpo_pairs.jsonl",
                        help="DPO 数据输出路径")
    parser.add_argument("--output-grpo-prompts", default="./data/grpo_prompts.jsonl",
                        help="GRPO prompts 输出路径（只有问题）")
    parser.add_argument("--threshold", type=int, default=7,
                        help="分数阈值，低于此分数视为错误")
    args = parser.parse_args()
    
    # Azure OpenAI 配置
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_key = os.getenv("AZURE_OPENAI_KEY")
    
    if not azure_endpoint or not azure_key:
        print("❌ 请设置 AZURE_OPENAI_ENDPOINT 和 AZURE_OPENAI_KEY 环境变量")
        return
    
    client = AzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=azure_key,
        api_version="2024-12-01-preview"
    )
    
    # 加载问题
    if args.questions and os.path.exists(args.questions):
        questions = []
        with open(args.questions, "r", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line.strip())
                questions.append(item.get("question", item.get("prompt", "")))
    else:
        questions = DEFAULT_QUESTIONS
    
    print("=" * 60)
    print("反馈数据生成")
    print("=" * 60)
    print(f"问题数: {len(questions)}")
    print(f"模型: {args.model}")
    print(f"DPO 输出: {args.output_dpo}")
    print(f"GRPO Prompts 输出: {args.output_grpo_prompts}")
    print()
    
    dpo_pairs = []
    grpo_prompts = []  # 只存问题！
    correct_count = 0
    error_count = 0
    
    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {question[:40]}...", end=" ")
        
        # 获取模型回答
        model_answer = get_model_response(args.model, question, args.model_name)
        if not model_answer:
            print("⚠️ 模型无回答")
            error_count += 1
            grpo_prompts.append({"prompt": question})  # 无回答的问题也加入 GRPO
            continue
        
        # GPT 评估
        eval_result = evaluate_with_gpt(client, question, model_answer)
        score = eval_result.get("score", -1)
        
        if score < 0:
            print(f"⚠️ 评估失败")
            error_count += 1
            grpo_prompts.append({"prompt": question})
            continue
        
        if score >= args.threshold:
            print(f"✓ 正确 (score={score})")
            correct_count += 1
        else:
            print(f"✗ 错误 (score={score})")
            
            # 构造 DPO 对
            correct_answer = eval_result.get("correct_answer")
            if correct_answer and correct_answer != "null":
                dpo_pairs.append({
                    "prompt": question,
                    "chosen": correct_answer,
                    "rejected": model_answer,
                    "score_rejected": score,
                    "feedback": eval_result.get("feedback", ""),
                    "timestamp": datetime.now().isoformat()
                })
        
        # 所有问题都加入 GRPO prompts（错题重点练，正确的也复习）
        grpo_prompts.append({
            "prompt": question,
            "last_score": score,  # 记录上次得分，方便分析
            "is_error": score < args.threshold
        })
    
    # 保存 DPO 数据
    os.makedirs(os.path.dirname(args.output_dpo) or ".", exist_ok=True)
    with open(args.output_dpo, "w", encoding="utf-8") as f:
        for item in dpo_pairs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    # 保存 GRPO prompts（只有问题！）
    os.makedirs(os.path.dirname(args.output_grpo_prompts) or ".", exist_ok=True)
    with open(args.output_grpo_prompts, "w", encoding="utf-8") as f:
        for item in grpo_prompts:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    # 统计
    print()
    print("=" * 60)
    print("统计")
    print("=" * 60)
    print(f"正确: {correct_count}")
    print(f"错误: {len(questions) - correct_count - error_count}")
    print(f"处理失败: {error_count}")
    print()
    print(f"DPO 对数: {len(dpo_pairs)} → {args.output_dpo}")
    print(f"GRPO Prompts: {len(grpo_prompts)} → {args.output_grpo_prompts}")


if __name__ == "__main__":
    main()
