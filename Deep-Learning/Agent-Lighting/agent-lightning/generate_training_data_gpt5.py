#!/usr/bin/env python3
"""
使用 GPT-5 生成大规模数学问答训练数据
生成 5000 条高质量数学问题和答案
"""
import asyncio
import json
import os
import random
import re
from pathlib import Path

import pandas as pd
from openai import AsyncAzureOpenAI


# Azure OpenAI 配置
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://your-resource.openai.azure.com/")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "your-api-key")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat")
AZURE_OPENAI_API_VERSION = "2025-01-01-preview"

# 数学问题类型
MATH_TYPES = [
    "basic arithmetic (addition, subtraction, multiplication, division)",
    "percentage calculations",
    "simple algebraic equations",
    "geometry (area, perimeter, volume)",
    "probability and statistics",
    "number sequences and patterns",
    "word problems with money",
    "time and distance calculations",
    "fractions and decimals",
    "square roots and powers"
]


async def generate_math_questions_with_gpt5(
    num_questions: int = 5000,
    batch_size: int = 20
) -> list[dict]:
    """
    使用 GPT-5 批量生成数学问题
    
    Args:
        num_questions: 要生成的总问题数
        batch_size: 每次 API 调用生成的问题数
    
    Returns:
        包含问题和答案的字典列表
    """
    print(f"🤖 使用 Azure OpenAI GPT-5 生成 {num_questions} 条训练数据...")
    print(f"📦 批处理大小: {batch_size} 条/批")
    print(f"⏱️ 预计时间: {num_questions // batch_size} 批 × 3秒 ≈ {(num_questions // batch_size * 3) // 60} 分钟\n")
    
    # 初始化 Azure OpenAI 客户端
    client = AsyncAzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )
    
    all_data = []
    num_batches = (num_questions + batch_size - 1) // batch_size
    
    for batch_idx in range(num_batches):
        # 随机选择数学类型
        selected_types = random.sample(MATH_TYPES, k=min(3, len(MATH_TYPES)))
        types_str = ", ".join(selected_types)
        
        # 构建 prompt
        prompt = f"""Generate {batch_size} diverse math problems focusing on: {types_str}.

Requirements:
1. Each problem should be clear and solvable
2. Difficulty range: elementary to middle school level
3. Answer must be a single numeric value (integer or decimal)
4. Include a mix of direct calculation and word problems

Return ONLY a JSON array with this exact format:
[
  {{"question": "Calculate 15 + 27", "answer": "42"}},
  {{"question": "What is 20% of 150?", "answer": "30"}},
  ...
]

Generate exactly {batch_size} problems now."""
        
        try:
            # 调用 GPT-5
            response = await client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a math teacher creating practice problems."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=2000,
            )
            
            # 解析响应
            content = response.choices[0].message.content.strip()
            
            # 提取 JSON（处理可能的 markdown 代码块）
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content
            
            # 解析 JSON
            batch_data = json.loads(json_str)
            
            # 验证数据格式
            valid_batch = []
            for item in batch_data:
                if "question" in item and "answer" in item:
                    # 清理答案（移除非数字字符，保留数字和小数点）
                    answer = str(item["answer"]).strip()
                    # 提取数字
                    numbers = re.findall(r'-?\d+\.?\d*', answer)
                    if numbers:
                        item["answer"] = numbers[0]  # 取第一个数字
                        valid_batch.append(item)
            
            all_data.extend(valid_batch)
            
            print(f"✅ 批次 {batch_idx + 1}/{num_batches}: 生成 {len(valid_batch)} 条有效数据 (总计: {len(all_data)})")
            
        except Exception as e:
            print(f"⚠️ 批次 {batch_idx + 1} 失败: {e}")
            continue
        
        # 限流（避免触发 API 限制）
        if batch_idx < num_batches - 1:
            await asyncio.sleep(1)
    
    print(f"\n✅ 数据生成完成！共生成 {len(all_data)} 条数据")
    return all_data


def clean_and_validate_data(data: list[dict]) -> list[dict]:
    """
    数据质量检查和清洗
    
    Args:
        data: 原始数据列表
    
    Returns:
        清洗后的数据列表
    """
    print("\n🔍 正在检查数据质量...\n")
    
    # 1. 去重
    unique_data = []
    seen_questions = set()
    for item in data:
        q = item['question'].lower().strip()
        if q not in seen_questions:
            seen_questions.add(q)
            unique_data.append(item)
    
    print(f"去重: {len(unique_data)} 条（移除 {len(data) - len(unique_data)} 条重复）")
    
    # 2. 验证答案格式
    valid_data = []
    for item in unique_data:
        try:
            # 尝试转换为浮点数验证
            float(item['answer'])
            valid_data.append(item)
        except:
            print(f"⚠️ 移除无效答案: Q={item['question'][:50]}... A={item['answer']}")
    
    print(f"验证: {len(valid_data)} 条有效数据")
    
    # 3. 如果数据不足，程序化补充
    if len(valid_data) < 4500:
        print(f"\n⚠️ 数据不足 4500 条，补充程序生成的数据...")
        needed = 4500 - len(valid_data)
        fallback_data = generate_fallback_data(needed)
        valid_data.extend(fallback_data)
        print(f"✅ 已补充 {needed} 条程序生成的数据")
    
    return valid_data


def generate_fallback_data(num: int) -> list[dict]:
    """程序化生成数学题作为补充"""
    fallback = []
    for _ in range(num):
        q_type = random.choice(['add', 'mul', 'percent', 'equation', 'sqrt'])
        
        if q_type == 'add':
            a, b = random.randint(10, 500), random.randint(10, 500)
            fallback.append({
                "question": f"Calculate {a} + {b}",
                "answer": str(a + b)
            })
        elif q_type == 'mul':
            a, b = random.randint(5, 50), random.randint(5, 50)
            fallback.append({
                "question": f"Calculate {a} * {b}",
                "answer": str(a * b)
            })
        elif q_type == 'percent':
            p = random.choice([5, 10, 15, 20, 25, 30, 50])
            n = random.randint(100, 1000)
            fallback.append({
                "question": f"What is {p}% of {n}?",
                "answer": str(int(n * p / 100))
            })
        elif q_type == 'equation':
            x = random.randint(2, 20)
            coef = random.randint(2, 10)
            fallback.append({
                "question": f"Solve {coef}x = {coef * x}",
                "answer": str(x)
            })
        elif q_type == 'sqrt':
            n = random.choice([4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144, 169, 196, 225])
            fallback.append({
                "question": f"Square root of {n}",
                "answer": str(int(n ** 0.5))
            })
    
    return fallback


def save_data(data: list[dict], output_dir: str = "data"):
    """
    保存数据到 Parquet 文件
    
    Args:
        data: 要保存的数据
        output_dir: 输出目录
    """
    # 打乱数据
    random.shuffle(data)
    
    # 分割训练集和测试集（90% / 10%）
    split_idx = int(len(data) * 0.9)
    train_data = data[:split_idx]
    test_data = data[split_idx:]
    
    print(f"\n📊 数据集统计:")
    print(f"  训练集: {len(train_data)} 条")
    print(f"  测试集: {len(test_data)} 条")
    print(f"  总计: {len(data)} 条\n")
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # 转换为 DataFrame 并保存
    train_df = pd.DataFrame(train_data)
    test_df = pd.DataFrame(test_data)
    
    train_path = output_path / "train_gpt5_large.parquet"
    test_path = output_path / "test_gpt5_large.parquet"
    
    train_df.to_parquet(train_path, index=False)
    test_df.to_parquet(test_path, index=False)
    
    print(f"✅ 数据已保存:")
    print(f"  训练集: {train_path}")
    print(f"  测试集: {test_path}\n")
    
    print("📝 数据示例:")
    print(train_df.head(3).to_string(index=False))
    
    return train_path, test_path


async def main():
    """主函数"""
    print("="*60)
    print("🚀 GPT-5 数学问答训练数据生成器")
    print("="*60 + "\n")
    
    # 1. 生成数据
    raw_data = await generate_math_questions_with_gpt5(
        num_questions=5000,
        batch_size=20
    )
    
    # 2. 清洗数据
    clean_data = clean_and_validate_data(raw_data)
    
    # 3. 保存数据
    train_path, test_path = save_data(clean_data)
    
    print("\n" + "="*60)
    print("✅ 数据生成完成！")
    print("="*60)
    print(f"\n📂 训练数据: {train_path}")
    print(f"📂 测试数据: {test_path}")
    print(f"\n🚀 下一步:")
    print(f"   1. 上传数据到GPU服务器:")
    print(f"      scp data/*.parquet user@remote-host:~/agent-lightning/data/")
    print(f"   2. 运行训练脚本:")
    print(f"      python train_math_agent_large.py")


if __name__ == "__main__":
    asyncio.run(main())
