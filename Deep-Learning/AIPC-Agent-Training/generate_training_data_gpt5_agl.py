#!/usr/bin/env python3
"""
使用 Agent Lightning + GPT-5 生成大规模数学问答训练数据
改造版本：利用 Agent Lightning 的追踪和并行能力
"""
import os
import asyncio
import json
import random
import re
from pathlib import Path
from typing import TypedDict
from opentelemetry import trace  # 添加 opentelemetry 引用

import pandas as pd
import agentlightning as agl


# Azure OpenAI 配置
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://YOUR_ENDPOINT.openai.azure.com/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"  # 使用 gpt-4o 模型
AZURE_OPENAI_API_VERSION = "2025-04-01-preview"

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


class GenerationTask(TypedDict):
    """数据生成任务的结构"""
    batch_id: int
    batch_size: int
    math_types: list[str]
    # 用于回传生成的数据
    generated_data: list[dict]


# ============= Agent Lightning 版本：使用 @agl.rollout =============
@agl.rollout
async def gpt5_data_generator(task: GenerationTask, llm: agl.LLM) -> float:
    """
    使用 Agent Lightning 的 Agent 生成一批数学问题
    
    Returns:
        float: 成功率（作为奖励返回给框架）
    """
    # 使用 Agent Lightning 注入的 LLM endpoint
    # Tracer 会自动追踪这个 AsyncOpenAI 客户端的所有调用
    from openai import AsyncAzureOpenAI
    
    client = AsyncAzureOpenAI(
        azure_endpoint=llm.endpoint or AZURE_OPENAI_ENDPOINT,
        api_key=llm.api_key or AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )
    
    batch_id = task['batch_id']
    batch_size = task['batch_size']
    types_str = ", ".join(task['math_types'])
    
    # 初始化结果列表
    if 'generated_data' not in task:
        task['generated_data'] = []
    
    # 获取 Tracer
    tracer = trace.get_tracer("gpt5_data_generator")

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
        # 手动创建 Span 以展示 Agent Lightning 的追踪能力
        with tracer.start_as_current_span("gpt-5.1-chat-completion") as span:
            span.set_attribute("llm.model", "gpt-5.1-preview")
            span.set_attribute("batch.id", batch_id)
            
            response = await client.chat.completions.create(
                model=llm.model or AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a math teacher creating practice problems."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
            )
            
            # 记录 Token 使用情况
            if response.usage:
                span.set_attribute("llm.usage.total_tokens", response.usage.total_tokens)
        
        # 解析响应
        content = response.choices[0].message.content.strip()
        
        # 提取 JSON
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content
        
        # 解析 JSON
        batch_data = json.loads(json_str)
        
        # 验证和清洗数据
        valid_batch = []
        for item in batch_data:
            if "question" in item and "answer" in item:
                answer = str(item["answer"]).strip()
                numbers = re.findall(r'-?\d+\.?\d*', answer)
                if numbers:
                    item["answer"] = numbers[0]
                    item["batch_id"] = batch_id  # 添加批次标识
                    valid_batch.append(item)
        
        # 将数据保存到 task 对象中（通过引用回传）
        task['generated_data'].extend(valid_batch)
        
        # ✅ 记录生成的数据质量
        success_rate = len(valid_batch) / batch_size
        agl.emit_reward(success_rate)  # 用奖励记录成功率
        
        print(f"✅ 批次 {batch_id}: 生成 {len(valid_batch)}/{batch_size} 条有效数据 (成功率: {success_rate:.1%})")
        
        return success_rate
        
    except Exception as e:
        print(f"⚠️ 批次 {batch_id} 失败: {e}")
        agl.emit_reward(0.0)  # 失败的批次奖励为 0
        return 0.0


def create_generation_tasks(num_questions: int, batch_size: int) -> list[GenerationTask]:
    """创建数据生成任务列表"""
    num_batches = (num_questions + batch_size - 1) // batch_size
    tasks = []
    
    for batch_id in range(num_batches):
        # 随机选择数学类型
        selected_types = random.sample(MATH_TYPES, k=min(3, len(MATH_TYPES)))
        
        task = GenerationTask(
            batch_id=batch_id + 1,
            batch_size=batch_size,
            math_types=selected_types,
            generated_data=[]  # 初始化为空列表
        )
        tasks.append(task)
    
    return tasks


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


def clean_and_validate_data(data: list[dict]) -> list[dict]:
    """数据质量检查和清洗"""
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
            float(item['answer'])
            valid_data.append(item)
        except:
            print(f"⚠️ 移除无效答案: Q={item['question'][:50]}... A={item['answer']}")
    
    print(f"验证: {len(valid_data)} 条有效数据")
    
    # 3. 补充数据（如果不足）
    if len(valid_data) < 4500:
        print(f"\n⚠️ 数据不足 4500 条，补充程序生成的数据...")
        needed = 4500 - len(valid_data)
        fallback_data = generate_fallback_data(needed)
        valid_data.extend(fallback_data)
        print(f"✅ 已补充 {needed} 条程序生成的数据")
    
    return valid_data


def save_data(data: list[dict], output_dir: str = "data"):
    """保存数据到 Parquet 文件"""
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


async def run_data_generation():
    """异步执行数据生成"""
    # 1. 创建生成任务
    num_questions = 5000
    batch_size = 20
    tasks = create_generation_tasks(num_questions, batch_size)
    
    print(f"📋 创建了 {len(tasks)} 个生成任务")
    print(f"📦 每批生成 {batch_size} 条数据\n")
    
    # 2. 配置 LLM 资源
    llm_resource = agl.LLM(
        endpoint=AZURE_OPENAI_ENDPOINT,
        model=AZURE_OPENAI_DEPLOYMENT,
        api_key=AZURE_OPENAI_API_KEY,
    )
    
    print("🔄 开始生成数据...\n")
    
    # 初始化 Runner 和 Store 以启用追踪
    store = agl.InMemoryLightningStore()
    tracer = agl.OtelTracer()
    runner = agl.LitAgentRunner(tracer=tracer)
    
    all_generated_data = []
    
    # 使用 run_context 初始化 Tracer
    with runner.run_context(agent=gpt5_data_generator, store=store):
        for task in tasks:
            try:
                # 使用 runner.step 执行 Agent
                # 这会正确处理 @agl.rollout 上下文
                # 返回值是 success_rate (float)，数据存储在 task['generated_data'] 中
                await runner.step(
                    input=task,
                    resources={"llm": llm_resource}
                )
                
                # 从 task 对象中获取生成的数据
                if 'generated_data' in task and task['generated_data']:
                    batch_data = task['generated_data']
                    all_generated_data.extend(batch_data)
                    # 清空以释放内存（可选）
                    task['generated_data'] = []
                
                # 打印追踪详情，让用户看到 GPT-4o 的存在
                traces = tracer.get_last_trace()
                print(f"🔍 本次 Rollout 捕捉到的 Spans ({len(traces)}):")
                for span in traces:
                    print(f"   👉 Span: {span.name}")
                    if span.attributes:
                        print(f"      属性: {span.attributes}")

                # 限流避免 API 限制
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"⚠️ 批次失败: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    print(f"\n✅ 数据生成完成！共生成 {len(all_generated_data)} 条数据")
    return all_generated_data


def main():
    """主函数：使用 Agent Lightning 框架生成数据"""
    print("="*70)
    print("🚀 Agent Lightning + GPT-5.1 数学问答数据生成器")
    print("="*70 + "\n")
    
    print("✨ Agent Lightning 优势:")
    print("  1. 自动追踪所有 GPT-5.1 调用")
    print("  2. 记录 prompt/response/tokens（如果配置 Store）")
    print("  3. 使用 @agl.rollout 装饰器获得追踪能力")
    print("  4. 代码结构与训练脚本一致\n")
    
    # 配置日志记录到文件 (保存 Agent Lightning 框架的日志)
    agl.logging.setup(files="agent_execution.log", level="INFO")
    
    # 执行异步数据生成
    all_generated_data = asyncio.run(run_data_generation())
    
    # 4. 清洗数据
    clean_data = clean_and_validate_data(all_generated_data)
    
    # 5. 保存数据
    train_path, test_path = save_data(clean_data)
    
    print("\n" + "="*70)
    print("✅ 数据生成完成！")
    print("="*70)
    print(f"\n📂 训练数据: {train_path}")
    print(f"📂 测试数据: {test_path}")
    print("\n🚀 下一步:")
    print("   python train_math_agent_vllm.py")


if __name__ == "__main__":
    main()
