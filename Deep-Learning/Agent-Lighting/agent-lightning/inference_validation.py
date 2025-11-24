#!/usr/bin/env python3
"""
推理验证脚本
对比训练前后模型的性能，并展示详细推理过程
"""
import os
import asyncio
import re
from pathlib import Path

import pandas as pd
from openai import AsyncOpenAI


# 模型配置
BASE_MODEL_URL = os.environ.get("BASE_MODEL_URL", "http://localhost:8000/v1")  # 基础模型
TRAINED_MODEL_URL = os.environ.get("TRAINED_MODEL_URL", "http://localhost:8001/v1")  # 训练后模型
API_KEY = os.environ.get("VLLM_API_KEY", "EMPTY")


async def query_model(client: AsyncOpenAI, question: str, model_name: str = "model") -> dict:
    """
    查询模型并提取答案
    
    Args:
        client: OpenAI 客户端
        question: 问题
        model_name: 模型名称
    
    Returns:
        包含响应和答案的字典
    """
    prompt = f"""You are a math expert. Solve the math problem step by step.
Problem: {question}
Show your reasoning and provide the final numeric answer."""
    
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        
        content = response.choices[0].message.content
        
        # 提取数字答案
        numbers = re.findall(r'-?\d+\.?\d*', content)
        predicted_answer = numbers[-1] if numbers else "N/A"
        
        return {
            "response": content,
            "predicted": predicted_answer,
        }
    except Exception as e:
        return {
            "response": f"Error: {e}",
            "predicted": "N/A",
        }


def check_answer(predicted: str, ground_truth: str) -> bool:
    """检查答案是否正确"""
    try:
        return abs(float(predicted) - float(ground_truth)) < 0.01
    except:
        return False


async def evaluate_model(client: AsyncOpenAI, test_df: pd.DataFrame, model_name: str, num_samples: int = 50) -> tuple[float, list]:
    """
    评估模型性能
    
    Args:
        client: OpenAI 客户端
        test_df: 测试数据
        model_name: 模型名称
        num_samples: 评估样本数
    
    Returns:
        (准确率, 详细结果列表)
    """
    correct = 0
    details = []
    
    for idx, row in test_df.head(num_samples).iterrows():
        result = await query_model(client, row['question'], model_name)
        is_correct = check_answer(result['predicted'], row['answer'])
        
        if is_correct:
            correct += 1
        
        details.append({
            "question": row['question'],
            "ground_truth": row['answer'],
            "predicted": result['predicted'],
            "correct": is_correct,
            "response": result['response'],
        })
    
    accuracy = correct / num_samples * 100
    return accuracy, details


async def main():
    print("="*70)
    print("🔍 训练前后模型推理验证")
    print("="*70 + "\n")
    
    # ==================== 1. 加载测试数据 ====================
    print("📊 加载测试数据...")
    test_df = pd.read_parquet("data/test_gpt5_large.parquet")
    print(f"✅ 测试集: {len(test_df)} 条\n")
    
    # ==================== 2. 初始化客户端 ====================
    print("🔗 连接模型服务...")
    base_client = AsyncOpenAI(base_url=BASE_MODEL_URL, api_key=API_KEY)
    trained_client = AsyncOpenAI(base_url=TRAINED_MODEL_URL, api_key=API_KEY)
    print("✅ 基础模型: localhost:8000")
    print("✅ 训练后模型: localhost:8001\n")
    
    # ==================== 3. 评估基础模型 ====================
    print("="*70)
    print("📈 评估基础模型（训练前）")
    print("="*70)
    try:
        base_acc, base_details = await evaluate_model(
            base_client, test_df, "base-model", num_samples=50
        )
        print(f"✅ 基础模型准确率: {base_acc:.1f}%\n")
    except Exception as e:
        print(f"❌ 基础模型评估失败: {e}")
        print("⚠️ 跳过基础模型评估，仅评估训练后模型...\n")
        base_acc = 0.0
        base_details = []
    
    # ==================== 4. 评估训练后模型 ====================
    print("="*70)
    print("📊 评估训练后模型")
    print("="*70)
    try:
        trained_acc, trained_details = await evaluate_model(
            trained_client, test_df, "trained-model", num_samples=50
        )
        print(f"✅ 训练后模型准确率: {trained_acc:.1f}%\n")
    except Exception as e:
        print(f"❌ 训练后模型评估失败: {e}")
        trained_acc = 0.0
        trained_details = []
    
    # ==================== 5. 性能对比 ====================
    improvement = trained_acc - base_acc
    print("="*70)
    print("📈 性能对比")
    print("="*70)
    print(f"基础模型准确率: {base_acc:.1f}%")
    print(f"训练后模型准确率: {trained_acc:.1f}%")
    print(f"准确率提升: {improvement:+.1f}%")
    print("="*70 + "\n")
    
    # ==================== 6. 展示典型案例 ====================
    print("="*70)
    print("📝 典型推理案例对比")
    print("="*70 + "\n")
    
    # 找出训练后模型改进的案例
    improved_cases = []
    for i in range(min(50, len(base_details))):
        if not base_details[i]['correct'] and trained_details[i]['correct']:
            improved_cases.append(i)
    
    if improved_cases:
        print(f"✅ 找到 {len(improved_cases)} 个训练后改进的案例\n")
        
        # 展示前 3 个改进案例
        for idx in improved_cases[:3]:
            print("─"*70)
            print(f"案例 {idx + 1}:")
            print(f"问题: {base_details[idx]['question']}")
            print(f"正确答案: {base_details[idx]['ground_truth']}")
            print(f"\n❌ 基础模型预测: {base_details[idx]['predicted']}")
            print(f"推理过程:\n{base_details[idx]['response'][:200]}...")
            print(f"\n✅ 训练后模型预测: {trained_details[idx]['predicted']}")
            print(f"推理过程:\n{trained_details[idx]['response'][:200]}...")
            print()
    else:
        print("⚠️ 未找到明显改进的案例\n")
    
    # ==================== 7. 保存详细结果 ====================
    print("="*70)
    print("💾 保存验证结果")
    print("="*70)
    
    # 保存基础模型结果
    base_df = pd.DataFrame(base_details)
    base_path = Path("validation_base_model.parquet")
    base_df.to_parquet(base_path, index=False)
    print(f"✅ 基础模型结果: {base_path}")
    
    # 保存训练后模型结果
    trained_df = pd.DataFrame(trained_details)
    trained_path = Path("validation_trained_model.parquet")
    trained_df.to_parquet(trained_path, index=False)
    print(f"✅ 训练后模型结果: {trained_path}")
    
    # 保存对比报告
    report_path = Path("validation_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("推理验证报告\n")
        f.write("="*70 + "\n\n")
        f.write("测试样本数: 50\n\n")
        f.write(f"基础模型准确率: {base_acc:.1f}%\n")
        f.write(f"训练后模型准确率: {trained_acc:.1f}%\n")
        f.write(f"准确率提升: {improvement:+.1f}%\n\n")
        
        if improved_cases:
            f.write(f"改进案例数: {len(improved_cases)}\n\n")
            f.write("典型改进案例:\n")
            f.write("="*70 + "\n\n")
            
            for idx in improved_cases[:5]:
                f.write(f"案例 {idx + 1}:\n")
                f.write(f"问题: {base_details[idx]['question']}\n")
                f.write(f"正确答案: {base_details[idx]['ground_truth']}\n")
                f.write(f"基础模型预测: {base_details[idx]['predicted']} ❌\n")
                f.write(f"训练后模型预测: {trained_details[idx]['predicted']} ✅\n\n")
    
    print(f"✅ 验证报告: {report_path}\n")
    
    print("="*70)
    print("✅ 验证完成！")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
