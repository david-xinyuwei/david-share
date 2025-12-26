#!/usr/bin/env python3
"""
V3 模型最终评估脚本
测试 12 个核心 AIPC 问题的准确率
"""
import json
import requests

VLLM_URL = "http://localhost:8000/v1/chat/completions"

TEST_QUESTIONS = [
    ("什么是 AI PC？", ["NPU", "神经网络", "本地"]),
    ("AI PC 里的 NPU 是什么？", ["神经网络", "处理器"]),
    ("哪些厂商在做 AI PC？", ["Intel", "AMD", "Qualcomm"]),
    ("Intel 的 AI PC 芯片叫什么？", ["Core Ultra"]),
    ("AMD 有 AI PC 产品吗？", ["Ryzen AI"]),
    ("高通的 AI PC 方案是什么？", ["Snapdragon"]),
    ("AI PC 和普通笔记本有什么区别？", ["NPU", "本地"]),
    ("AIPC 是阿里云的产品吗？", ["不是", "不"]),
    ("Copilot+ PC 是什么？", ["NPU", "本地"]),
    ("什么是 TOPS？", ["万亿", "操作"]),
    ("AI PC 必须联网吗？", ["不", "本地"]),
    ("没有网络 AI PC 还能用 AI 功能吗？", ["可以", "能", "本地"]),
]

def ask(q):
    try:
        r = requests.post(VLLM_URL, json={
            "model": "exported_model_v3",
            "messages": [{"role": "user", "content": q}],
            "max_tokens": 200,
            "temperature": 0.3
        }, timeout=60)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return str(e)

def check(answer, keywords):
    a = answer.lower()
    return any(k.lower() in a for k in keywords)

print("=" * 60)
print("V3 模型 AIPC 知识评估")
print("=" * 60)

correct = 0
for q, kws in TEST_QUESTIONS:
    ans = ask(q)
    ok = check(ans, kws)
    print(f"{'✓' if ok else '✗'} | {q[:30]}")
    if ok:
        correct += 1

acc = correct / len(TEST_QUESTIONS) * 100
print("=" * 60)
print(f"V3 准确率: {correct}/{len(TEST_QUESTIONS)} = {acc:.1f}%")
print("=" * 60)
print("对比:")
print("  V1: ~10%  (冷启动)")
print("  V2: ~7.5% (反馈迭代)")
print(f"  V3: {acc:.1f}% (修正数据迭代)")
print("=" * 60)
if acc >= 70:
    print("✅ 结论: 数据飞轮验证成功！")
