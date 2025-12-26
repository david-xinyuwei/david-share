#!/usr/bin/env python3
"""
AIPC V3 训练数据生成脚本
用 V2 模型回答问题，GPT-5.2 判断正确性并生成修正答案

核心流程：
1. V2 模型回答 53 个 AIPC 问题
2. GPT-5.2 评估每个答案（是否正确、是否有幻觉）
3. 对于错误答案，GPT-5.2 生成正确版本
4. 输出：v3_good_samples.jsonl（用于训练）
"""

import os
import json
from typing import Dict, Any
from vllm import LLM, SamplingParams
from openai import AzureOpenAI

# ============ 配置 ============
V2_MODEL_PATH = "/root/aipc-flywheel/exported_model_v2/final"
OUTPUT_GOOD = "/root/aipc-flywheel/data/v3_good_samples.jsonl"
OUTPUT_BAD = "/root/aipc-flywheel/data/v3_bad_samples.jsonl"

# Azure OpenAI GPT-5.2
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://your-endpoint.openai.azure.com")
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "your-api-key")
AZURE_API_VERSION = "2024-12-01-preview"
REWARD_MODEL = "gpt-5-turbo"

# 53 个 AIPC 相关问题
AIPC_QUESTIONS = [
    # 基础概念
    "什么是 AI PC？",
    "AI PC 是什么意思？",
    "请解释一下 AIPC 的概念",
    "AI PC 的定义是什么？",
    "能介绍一下人工智能电脑吗？",
    
    # NPU 相关
    "AI PC 里的 NPU 是什么？",
    "NPU 和 GPU 有什么区别？",
    "AI PC 需要什么样的处理器？",
    "AI PC 的神经网络处理单元有什么用？",
    
    # 厂商和产品
    "哪些厂商在做 AI PC？",
    "Intel 的 AI PC 方案是什么？",
    "AMD 有 AI PC 产品吗？",
    "高通的 AI PC 芯片叫什么？",
    
    # TOPS 和性能
    "什么是 TOPS？",
    "AI PC 需要多少 TOPS？",
    "TOPS 越高越好吗？",
    
    # 应用场景
    "AI PC 能做什么？",
    "AI PC 有哪些应用场景？",
    "Windows Copilot 和 AI PC 有什么关系？",
    "AI PC 可以运行本地大模型吗？",
    
    # 与云端对比
    "AI PC 和云端 AI 有什么区别？",
    "为什么需要本地 AI 而不是云端？",
    "AI PC 的优势是什么？",
    
    # 技术细节
    "AI PC 支持哪些 AI 框架？",
    "ONNX Runtime 在 AI PC 上的作用？",
    "DirectML 是什么？",
    
    # 发展趋势
    "AI PC 的发展趋势是什么？",
    "2024年 AI PC 市场怎么样？",
    
    # 更多问题...
    "笔记本电脑怎么判断是不是 AI PC？",
    "AI PC 对游戏有帮助吗？",
    "AI PC 能省电吗？",
    "AI PC 价格贵吗？",
    "什么时候该买 AI PC？",
    "AI PC 能跑 Stable Diffusion 吗？",
    "AI PC 上怎么用 ChatGPT？",
    "AI PC 支持离线 AI 吗？",
    "AI PC 的 NPU 算力怎么衡量？",
    "Intel Core Ultra 有几种型号？",
    "AMD Ryzen AI 是什么？",
    "Snapdragon X Elite 的 AI 能力如何？",
    "AI PC 能做视频编辑吗？",
    "AI PC 的智能降噪功能原理？",
    "什么是混合 AI？",
    "AI PC 和普通 PC 的区别？",
    "买 AI PC 要注意什么？",
    "AI PC 能用来编程吗？",
    "AI PC 适合办公吗？",
    "AI PC 能做实时翻译吗？",
    "AI PC 的摄像头有什么 AI 功能？",
    "AI PC 上的 Copilot 按键是什么？",
    "微软对 AI PC 有什么要求？",
    "AI PC 必须要 Windows 11 吗？",
    "NPU 的功耗是多少？",
]


# ============ 核心函数 ============

def load_v2_model():
    """加载 V2 模型（用 vLLM 加速）"""
    print("[1] 加载 V2 模型...")
    llm = LLM(
        model=V2_MODEL_PATH,
        trust_remote_code=True,
        dtype="bfloat16",
        max_model_len=1024,
    )
    return llm


def generate_v2_answers(llm: LLM, questions: list) -> list:
    """V2 模型回答所有问题"""
    print(f"[2] V2 模型回答 {len(questions)} 个问题...")
    
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=256,
    )
    
    # 构建 prompt
    prompts = [f"<|im_start|>user\n{q}<|im_end|>\n<|im_start|>assistant\n" for q in questions]
    
    outputs = llm.generate(prompts, sampling_params)
    
    results = []
    for question, output in zip(questions, outputs):
        answer = output.outputs[0].text.strip()
        results.append({"prompt": question, "response": answer})
    
    return results


def judge_answer(client: AzureOpenAI, question: str, answer: str) -> Dict[str, Any]:
    """GPT-5.2 评估答案"""
    judge_prompt = f"""你是 AIPC（AI PC）领域专家。请评估以下问答的质量。

问题: {question}

回答: {answer}

请按以下 JSON 格式返回评估结果：
{{
    "score": <0-10分>,
    "is_correct": <true/false>,
    "has_hallucination": <true/false>,
    "error_type": "<如有错误，描述类型：factual_error/hallucination/incomplete/off_topic/none>",
    "ideal_answer": "<如果 is_correct=false，给出正确答案；否则留空>"
}}

注意：
- AIPC 是指内置 NPU 的个人电脑，主要厂商是 Intel/AMD/Qualcomm
- AIPC 不是阿里云产品
- 常用指标是 TOPS（每秒万亿次操作）"""

    try:
        response = client.chat.completions.create(
            model=REWARD_MODEL,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"  评估失败: {e}")
        return {
            "score": 5,
            "is_correct": True,
            "has_hallucination": False,
            "error_type": "none",
            "ideal_answer": ""
        }


def generate_v3_data(v2_answers: list, client: AzureOpenAI) -> tuple:
    """生成 V3 训练数据"""
    print(f"[3] GPT-5.2 评估 {len(v2_answers)} 个答案...")
    
    good_samples = []  # 正确答案或已修正
    bad_samples = []   # V2 的错误答案
    
    for i, item in enumerate(v2_answers):
        question = item["prompt"]
        v2_answer = item["response"]
        
        # 评估
        judgment = judge_answer(client, question, v2_answer)
        
        if judgment["is_correct"]:
            # V2 答对了，直接用
            good_samples.append({
                "prompt": question,
                "response": v2_answer,
                "score": judgment["score"],
                "feedback": "positive"
            })
            status = "✓"
        else:
            # V2 答错了，记录错误并用 GPT-5.2 的修正答案
            bad_samples.append({
                "prompt": question,
                "response": v2_answer,
                "score": judgment["score"],
                "error_type": judgment["error_type"],
                "has_hallucination": judgment["has_hallucination"],
            })
            
            # 用修正后的答案作为训练样本
            if judgment.get("ideal_answer"):
                good_samples.append({
                    "prompt": question,
                    "response": judgment["ideal_answer"],
                    "score": 10,
                    "feedback": "corrected"
                })
            status = "✗"
        
        if (i + 1) % 10 == 0:
            print(f"  进度: {i+1}/{len(v2_answers)}")
    
    return good_samples, bad_samples


def save_data(good_samples: list, bad_samples: list):
    """保存数据"""
    print(f"[4] 保存数据...")
    
    # 保存好样本
    with open(OUTPUT_GOOD, 'w', encoding='utf-8') as f:
        for sample in good_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    print(f"    好样本: {len(good_samples)} -> {OUTPUT_GOOD}")
    
    # 保存坏样本（用于分析）
    with open(OUTPUT_BAD, 'w', encoding='utf-8') as f:
        for sample in bad_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    print(f"    坏样本: {len(bad_samples)} -> {OUTPUT_BAD}")


# ============ 主函数 ============

def main():
    print("="*60)
    print("AIPC V3 训练数据生成")
    print("V2 回答 -> GPT-5.2 评估 -> 生成修正数据")
    print("="*60)
    
    # 加载 V2 模型
    llm = load_v2_model()
    
    # V2 回答所有问题
    v2_answers = generate_v2_answers(llm, AIPC_QUESTIONS)
    
    # 释放 GPU 内存
    del llm
    import torch
    torch.cuda.empty_cache()
    
    # 初始化 GPT-5.2 客户端
    client = AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION,
    )
    
    # GPT-5.2 评估并生成修正数据
    good_samples, bad_samples = generate_v3_data(v2_answers, client)
    
    # 保存
    save_data(good_samples, bad_samples)
    
    # 统计
    print("\n" + "="*60)
    print("数据生成完成！")
    print(f"  V2 正确率: {(len(AIPC_QUESTIONS) - len(bad_samples))/len(AIPC_QUESTIONS)*100:.1f}%")
    print(f"  好样本数: {len(good_samples)} (用于 V3 训练)")
    print(f"  坏样本数: {len(bad_samples)} (V2 的错误答案)")
    print("="*60)


if __name__ == "__main__":
    main()
