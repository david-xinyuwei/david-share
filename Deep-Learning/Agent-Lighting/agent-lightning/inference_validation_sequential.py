#!/usr/bin/env python3
"""
推理验证脚本 (顺序执行版)
分步评估基础模型和训练后模型，避免显存不足
"""
import asyncio
import re
import argparse
import sys
from pathlib import Path

import pandas as pd
from openai import AsyncOpenAI

# 配置
API_KEY = "EMPTY"
DATA_FILE = "data/test_gpt5_large.parquet"
BASE_OUTPUT = "validation_base_model.parquet"
TRAINED_OUTPUT = "validation_trained_model.parquet"
REPORT_FILE = "validation_report.txt"

async def query_model(client: AsyncOpenAI, question: str, model_name: str = "model") -> dict:
    """查询模型并提取答案"""
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
        
        # 智能提取答案
        # 1. 优先查找 \boxed{...}
        boxed = re.findall(r'\\boxed\{([^}]+)\}', content)
        if boxed:
            predicted_answer = boxed[-1]
        else:
            # 2. 移除验证/检查部分 (避免提取到验证过程中的数字)
            # 常见模式: "To verify", "Check:", "Verification:", "Verify:"
            content_clean = re.split(r'(To verify|Check:|Verification:|Verify:)', content, flags=re.IGNORECASE)[0]
            
            # 3. 查找 "Final Answer" 后的数字
            final_match = re.search(r'Final Answer:.*?(-?\d+\.?\d*)', content_clean, re.IGNORECASE | re.DOTALL)
            if final_match:
                predicted_answer = final_match.group(1)
            else:
                # 4. 回退到提取最后一个数字
                numbers = re.findall(r'-?\d+\.?\d*', content_clean)
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

async def evaluate_single_model(port: int, model_name: str, output_file: str, num_samples: int = 50):
    """评估单个模型并保存结果"""
    print("="*70)
    print(f"🔍 评估模型: {model_name} (Port {port})")
    print("="*70)
    
    # 1. 加载数据
    if not Path(DATA_FILE).exists():
        print(f"❌ 数据文件不存在: {DATA_FILE}")
        sys.exit(1)
        
    test_df = pd.read_parquet(DATA_FILE)
    print(f"📊 加载测试数据: {len(test_df)} 条 (使用前 {num_samples} 条)")
    
    # 2. 初始化客户端
    base_url = f"http://localhost:{port}/v1"
    client = AsyncOpenAI(base_url=base_url, api_key=API_KEY)
    
    # 3. 运行评估
    correct = 0
    details = []
    
    print("🚀 开始推理...")
    for idx, row in test_df.head(num_samples).iterrows():
        result = await query_model(client, row['question'], model_name)
        is_correct = check_answer(result['predicted'], row['answer'])
        
        if is_correct:
            correct += 1
            print(".", end="", flush=True)
        else:
            print("x", end="", flush=True)
        
        details.append({
            "question": row['question'],
            "ground_truth": row['answer'],
            "predicted": result['predicted'],
            "correct": is_correct,
            "response": result['response'],
        })
    print("\n")
    
    accuracy = correct / num_samples * 100
    print(f"✅ 准确率: {accuracy:.1f}%")
    
    # 4. 保存结果
    df = pd.DataFrame(details)
    df.to_parquet(output_file, index=False)
    print(f"💾 结果已保存至: {output_file}\n")

def compare_results():
    """对比两个模型的结果并生成报告"""
    print("="*70)
    print("📈 生成对比报告")
    print("="*70)
    
    if not Path(BASE_OUTPUT).exists() or not Path(TRAINED_OUTPUT).exists():
        print("❌ 缺少评估结果文件，请先运行模型评估")
        sys.exit(1)
        
    base_df = pd.read_parquet(BASE_OUTPUT)
    trained_df = pd.read_parquet(TRAINED_OUTPUT)
    
    num_samples = len(base_df)
    base_acc = base_df['correct'].mean() * 100
    trained_acc = trained_df['correct'].mean() * 100
    improvement = trained_acc - base_acc
    
    print(f"基础模型准确率: {base_acc:.1f}%")
    print(f"训练后模型准确率: {trained_acc:.1f}%")
    print(f"准确率提升: {improvement:+.1f}%")
    
    # 找出改进案例
    improved_cases = []
    for i in range(len(base_df)):
        if not base_df.iloc[i]['correct'] and trained_df.iloc[i]['correct']:
            improved_cases.append(i)
            
    # 保存报告
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("推理验证报告 (顺序执行模式)\n")
        f.write("="*70 + "\n\n")
        f.write(f"测试样本数: {num_samples}\n\n")
        f.write(f"基础模型准确率: {base_acc:.1f}%\n")
        f.write(f"训练后模型准确率: {trained_acc:.1f}%\n")
        f.write(f"准确率提升: {improvement:+.1f}%\n\n")
        
        if improved_cases:
            f.write(f"改进案例数: {len(improved_cases)}\n\n")
            f.write("典型改进案例:\n")
            f.write("="*70 + "\n\n")
            
            for idx in improved_cases[:5]:
                row_base = base_df.iloc[idx]
                row_trained = trained_df.iloc[idx]
                f.write(f"案例 {idx + 1}:\n")
                f.write(f"问题: {row_base['question']}\n")
                f.write(f"正确答案: {row_base['ground_truth']}\n")
                f.write(f"基础模型预测: {row_base['predicted']} ❌\n")
                f.write(f"训练后模型预测: {row_trained['predicted']} ✅\n\n")
    
    print(f"✅ 验证报告已生成: {REPORT_FILE}")

async def main():
    parser = argparse.ArgumentParser(description="顺序推理验证")
    parser.add_argument("mode", choices=["base", "trained", "compare"], help="运行模式")
    args = parser.parse_args()
    
    if args.mode == "base":
        await evaluate_single_model(8000, "base-model", BASE_OUTPUT, num_samples=450)
    elif args.mode == "trained":
        await evaluate_single_model(8001, "trained-model", TRAINED_OUTPUT, num_samples=450)
    elif args.mode == "compare":
        compare_results()

if __name__ == "__main__":
    asyncio.run(main())
