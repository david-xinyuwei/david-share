#!/usr/bin/env python3
"""
模型评估脚本
测试模型在 AIPC 核心问题上的表现
"""

import os
import requests

VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8000/v1/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "v2_model")

# 核心测试问题及关键词
TEST_QUESTIONS = [
    ("什么是 AI PC？", ["NPU", "神经网络", "本地"]),
    ("AI PC 里的 NPU 是什么？", ["神经网络", "处理器", "AI"]),
    ("哪些厂商在做 AI PC？", ["Intel", "AMD", "Qualcomm"]),
    ("Intel 的 AI PC 芯片叫什么？", ["Core Ultra", "NPU"]),
    ("AMD 有 AI PC 产品吗？", ["Ryzen AI", "NPU"]),
    ("高通的 AI PC 方案是什么？", ["Snapdragon", "X"]),
    ("AI PC 和普通笔记本有什么区别？", ["NPU", "本地", "AI"]),
    ("AIPC 是阿里云的产品吗？", ["不是", "Intel", "AMD"]),
    ("Copilot+ PC 是什么？", ["NPU", "本地", "Microsoft"]),
    ("什么是 TOPS？", ["万亿", "操作", "算力"]),
    ("AI PC 需要多少 TOPS？", ["40", "TOPS", "算力"]),
    ("AI PC 必须联网吗？", ["不", "本地", "离线"]),
]

def ask_model(question: str) -> str:
    """调用模型获取答案"""
    try:
        resp = requests.post(VLLM_URL, json={
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": question}],
            "max_tokens": 300,
            "temperature": 0.3
        }, timeout=60)
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[ERROR] {e}"

def check_keywords(answer: str, keywords: list) -> bool:
    """检查答案是否包含关键词（至少命中一半）"""
    answer_lower = answer.lower()
    found = sum(1 for kw in keywords if kw.lower() in answer_lower)
    return found >= len(keywords) * 0.5

def main():
    print("=" * 60)
    print(f"AIPC 知识评估 - {MODEL_NAME}")
    print("=" * 60)
    print()
    
    correct = 0
    results = []
    
    for question, keywords in TEST_QUESTIONS:
        answer = ask_model(question)
        is_correct = check_keywords(answer, keywords)
        status = "✓" if is_correct else "✗"
        
        print(f"[{status}] {question}")
        if not is_correct:
            print(f"    答案: {answer[:100]}...")
            print(f"    期望关键词: {keywords}")
        
        results.append({
            "question": question,
            "answer": answer,
            "correct": is_correct
        })
        
        if is_correct:
            correct += 1
    
    accuracy = correct / len(TEST_QUESTIONS) * 100
    
    print()
    print("=" * 60)
    print(f"结果: {correct}/{len(TEST_QUESTIONS)} = {accuracy:.1f}%")
    print("=" * 60)
    
    if accuracy >= 90:
        print("🎉 优秀！模型已掌握 AIPC 核心知识")
    elif accuracy >= 70:
        print("✓ 良好！建议继续收集数据迭代")
    elif accuracy >= 50:
        print("⚠ 一般，需要更多训练数据")
    else:
        print("✗ 较差，需要检查数据质量")
    
    return accuracy

if __name__ == "__main__":
    main()
