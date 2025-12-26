#!/usr/bin/env python3
"""
过拟合测试脚本
用训练集没见过的问题测试模型泛化能力
"""
import requests

VLLM_URL = "http://localhost:8000/v1/chat/completions"

# 这些问题训练集里完全没有！
OOD_QUESTIONS = [
    # 变体问法
    ("用大白话解释一下啥是AI电脑", ["NPU", "本地"]),
    ("AI PC 这玩意儿到底是干嘛的", ["NPU", "本地", "AI"]),
    
    # 全新角度
    ("AI PC 对游戏有帮助吗？", None),  # 开放题
    ("AI PC 能用来挖矿吗？", None),
    ("AI PC 的散热怎么样？", None),
    
    # 对比类新问题
    ("AI PC 和 Mac 哪个好？", None),
    ("AI PC 值得等下一代吗？", None),
    
    # 技术细节新问题
    ("NPU 支持哪些 AI 框架？", None),
    ("AI PC 能跑 Stable Diffusion 吗？", ["本地", "可以"]),
    ("AI PC 上能部署 Llama 吗？", ["本地", "可以"]),
    
    # 边界测试
    ("你是谁训练的？", None),  # 不应该乱答
    ("今天天气怎么样？", None),  # 完全无关
    ("帮我写一首关于 AI PC 的诗", None),  # 创意任务
]

def ask(q):
    try:
        r = requests.post(VLLM_URL, json={
            "model": "exported_model_v3",
            "messages": [{"role": "user", "content": q}],
            "max_tokens": 200,
            "temperature": 0.7
        }, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return str(e)

print("=" * 60)
print("过拟合测试：训练集外的新问题")
print("=" * 60)

for q, kws in OOD_QUESTIONS:
    ans = ask(q)
    print(f"\nQ: {q}")
    print(f"A: {ans[:150]}...")
    
    # 检查是否死记硬背（复读训练数据）
    if "Intel Core Ultra、AMD Ryzen AI、Qualcomm Snapdragon X" in ans:
        print("   ⚠️ 可能是模板回答")

print("\n" + "=" * 60)
print("检查要点：")
print("1. 变体问法能否理解？")
print("2. 新问题是否乱套模板？")
print("3. 无关问题是否正常回答？")
print("=" * 60)
