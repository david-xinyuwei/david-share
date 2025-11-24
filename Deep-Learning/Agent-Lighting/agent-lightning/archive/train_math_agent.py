#!/usr/bin/env python
"""
Agent Lightning 数学任务训练脚本
用于训练 Qwen2.5-0.5B-Instruct 模型完成数学问题回答任务
"""
import os
import sys

# ⚠️ 关键：在最开始设置离线模式和环境变量
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['VLLM_ATTENTION_BACKEND'] = 'XFORMERS'
os.environ['TRANSFORMERS_ATTN_IMPLEMENTATION'] = 'eager'

import pandas as pd
import agentlightning as agl
from datasets import Dataset as HuggingFaceDataset
from typing import TypedDict

# ============================================================================
# 1. 定义任务结构
# ============================================================================
class MathTask(TypedDict):
    question: str
    answer: str

# ============================================================================
# 2. 定义 Agent
# ============================================================================
@agl.rollout
async def math_agent(task: MathTask, llm: agl.LLM):
    """
    数学 Agent：接收问题，调用 LLM，计算奖励。
    
    训练时，llm.endpoint 会指向本地的 vLLM 服务器
    """
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(base_url=llm.endpoint, api_key="EMPTY")
    
    try:
        response = await client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": "You are a math assistant. Output ONLY the final number."},
                {"role": "user", "content": task['question']}
            ],
            temperature=0.7
        )
        answer = response.choices[0].message.content.strip()
        print(f"📝 Q: {task['question'][:50]}... -> A: {answer}")
    except Exception as e:
        print(f"❌ Error calling LLM: {e}")
        answer = "0"
    
    # 计算奖励 (Exact Match)
    reward = 1.0 if answer == task['answer'] else 0.0
    agl.emit_reward(reward)
    print(f"🏆 Reward: {reward} (Expected: {task['answer']})")

# ============================================================================
# 3. 数据生成器（使用 Agent Lightning 框架）
# ============================================================================
def generate_math_questions(num_train=200, num_test=30):
    """
    生成数学问题（只生成问题，答案通过计算得出）
    使用 Python 直接计算正确答案
    
    Args:
        num_train: 训练集数量
        num_test: 测试集数量
    
    Returns:
        train_data, test_data
    """
    import random
    
    train_data = []
    test_data = []
    
    # 定义问题模板（返回问题和正确答案）
    def generate_addition():
        a, b = random.randint(10, 100), random.randint(10, 100)
        templates = [
            (f"Calculate {a} + {b}", a + b),
            (f"What is {a} plus {b}?", a + b),
            (f"Add {a} and {b}", a + b),
        ]
        q, ans = random.choice(templates)
        return q, str(ans)
    
    def generate_subtraction():
        a, b = random.randint(50, 150), random.randint(10, 50)
        templates = [
            (f"Calculate {a} - {b}", a - b),
            (f"Subtract {b} from {a}", a - b),
            (f"What is {a} minus {b}?", a - b),
        ]
        q, ans = random.choice(templates)
        return q, str(ans)
    
    def generate_multiplication():
        a, b = random.randint(2, 50), random.randint(2, 20)
        templates = [
            (f"Calculate {a} * {b}", a * b),
            (f"What is {a} times {b}?", a * b),
            (f"Multiply {a} by {b}", a * b),
        ]
        q, ans = random.choice(templates)
        return q, str(ans)
    
    def generate_division():
        a, b = random.randint(2, 20), random.randint(2, 15)
        result = a
        dividend = a * b
        templates = [
            (f"Calculate {dividend} / {b}", result),
            (f"Divide {dividend} by {b}", result),
            (f"What is {dividend} divided by {b}?", result),
            (f"{dividend} divided by {b} equals", result),
        ]
        q, ans = random.choice(templates)
        return q, str(ans)
    
    def generate_percentage():
        p = random.choice([5, 10, 15, 20, 25, 30, 40, 50, 60, 75])
        n = random.randint(20, 500)
        result = int(n * p / 100)
        templates = [
            (f"What is {p}% of {n}?", result),
            (f"Calculate {p}% of {n}", result),
            (f"Find {p} percent of {n}", result),
        ]
        q, ans = random.choice(templates)
        return q, str(ans)
    
    def generate_equation():
        c, x = random.randint(2, 10), random.randint(2, 15)
        eq_type = random.choice(['multiply', 'add', 'subtract'])
        
        if eq_type == 'multiply':
            q = f"Solve {c}x = {c * x}"
            ans = x
        elif eq_type == 'add':
            q = f"Solve x + {c} = {c + x}"
            ans = x
        else:
            q = f"Solve x - {c} = {x - c}"
            ans = x
        
        return q, str(ans)
    
    def generate_square_root():
        n = random.randint(2, 15)
        templates = [
            (f"Square root of {n * n}", n),
            (f"What is the square root of {n * n}?", n),
            (f"√{n * n} equals", n),
        ]
        q, ans = random.choice(templates)
        return q, str(ans)
    
    def generate_square():
        n = random.randint(2, 20)
        templates = [
            (f"What is {n} squared?", n * n),
            (f"Calculate {n} to the power of 2", n * n),
            (f"{n}² equals", n * n),
        ]
        q, ans = random.choice(templates)
        return q, str(ans)
    
    def generate_compound():
        a = random.randint(2, 30)
        b = random.randint(2, 15)
        c = random.randint(2, 20)
        
        ops = [
            (f"Calculate {a} * {b} + {c}", a * b + c),
            (f"Calculate {a} + {b} * {c}", a + b * c),
            (f"Calculate {a} * {b} - {c}", a * b - c),
            (f"Calculate {a} - {b} + {c}", a - b + c),
            (f"Calculate ({a} + {b}) * {c}", (a + b) * c),
        ]
        q, ans = random.choice(ops)
        return q, str(ans)
    
    # 所有生成器
    generators = [
        generate_addition,
        generate_subtraction,
        generate_multiplication,
        generate_division,
        generate_percentage,
        generate_equation,
        generate_square_root,
        generate_square,
        generate_compound,
    ]
    
    def generate_sample(idx):
        """生成一个样本"""
        generator = random.choice(generators)
        try:
            question, answer = generator()
            return {
                "id": str(idx),
                "question": question,
                "answer": answer
            }
        except Exception:
            # 如果失败，返回简单加法
            a, b = random.randint(10, 100), random.randint(10, 100)
            return {
                "id": str(idx),
                "question": f"Calculate {a} + {b}",
                "answer": str(a + b)
            }
    
    # 生成训练集
    print(f"📝 生成 {num_train} 条训练数据（使用程序化计算答案）...")
    for i in range(1, num_train + 1):
        train_data.append(generate_sample(i))
        if i % 50 == 0:
            print(f"   已生成 {i}/{num_train} 条")
    
    # 生成测试集
    print(f"📝 生成 {num_test} 条测试数据...")
    for i in range(1001, 1001 + num_test):
        test_data.append(generate_sample(i))
    
    return train_data, test_data


def prepare_data():
    """准备训练和测试数据集"""
    
    # 使用程序化生成（答案通过 Python 计算得出，不需要调用模型）
    train_data, test_data = generate_math_questions(num_train=200, num_test=30)
    
    # 保存为 Parquet 格式
    os.makedirs("data", exist_ok=True)
    pd.DataFrame(train_data).to_parquet("data/train.parquet")
    pd.DataFrame(test_data).to_parquet("data/test.parquet")
    
    print("✅ 数据集已保存到 data/ 目录")
    print(f"   - 训练集: {len(train_data)} 条")
    print(f"   - 测试集: {len(test_data)} 条")
    
    return train_data, test_data

# ============================================================================
# 4. 配置训练参数
# ============================================================================
def get_training_config(model_path: str = None):
    """
    获取训练配置
    
    Args:
        model_path: 模型路径，可以是 HuggingFace 仓库名或本地路径
                   默认使用 Qwen/Qwen2.5-0.5B-Instruct
    """
    if model_path is None:
        # 优先使用环境变量，否则使用默认值
        model_path = os.environ.get(
            "MODEL_PATH",
            "Qwen/Qwen2.5-0.5B-Instruct"
        )
    
    print(f"📦 使用模型: {model_path}")
    
    config = {
        "algorithm": {
            "adv_estimator": "grpo",  # 优势估计器
            "use_kl_in_reward": False,  # 不在奖励中使用 KL 散度
        },
        "data": {
            "train_batch_size": 4,  # 训练批次大小
            "max_prompt_length": 1024,  # 最大提示长度
            "max_response_length": 512,  # 最大响应长度
        },
        "actor_rollout_ref": {
            "rollout": {
                "tensor_model_parallel_size": 1,  # 张量并行数
                "n": 4,  # 每个问题生成的样本数
                "log_prob_micro_batch_size_per_gpu": 4,
                "name": "vllm",
                "gpu_memory_utilization": 0.5,  # GPU 显存利用率
            },
            "actor": {
                "ppo_mini_batch_size": 4,
                "ppo_micro_batch_size_per_gpu": 2,
                "optim": {"lr": 1e-6},  # 学习率
                "fsdp_config": {
                    "param_offload": True,  # 参数卸载到 CPU
                    "optimizer_offload": True,  # 优化器卸载到 CPU
                },
            },
            "ref": {
                "log_prob_micro_batch_size_per_gpu": 4,
                "fsdp_config": {"param_offload": True},
            },
            "model": {
                "path": model_path,
                "use_remove_padding": True,
                "enable_gradient_checkpointing": True,
                # ⚠️ 关键：使用 override_config 禁用 Flash Attention
                "override_config": {
                    "attn_implementation": "eager",
                },
            },
        },
        # Critic 模型配置
        "critic": {
            "optim": {"lr": 1e-5},
            "model": {
                "path": model_path,
                "use_remove_padding": True,
                "enable_gradient_checkpointing": True,
                "override_config": {
                    "attn_implementation": "eager",
                },
            },
        },
        # 训练器配置
        "trainer": {
            "n_gpus_per_node": 1,  # 每个节点的 GPU 数量
            "val_before_train": False,  # 训练前不验证
            "critic_warmup": 0,  # Critic 预热步数
            "logger": ["console"],  # 日志输出方式
            "project_name": "AgentLightningTutorial",  # 项目名称
            "experiment_name": "math_agent",  # 实验名称
            "nnodes": 1,  # 节点数
            "save_freq": 10,  # 保存频率（每 N 步）
            "test_freq": 10,  # 测试频率（每 N 步）
            "total_epochs": 1,  # 总训练轮数
        },
    }
    
    return config

# ============================================================================
# 5. 主训练流程
# ============================================================================
def main():
    """主训练流程"""
    print("="*80)
    print("🚀 Agent Lightning 数学任务训练")
    print("="*80)
    
    # 打印环境变量
    print("\n🔧 环境配置:")
    print(f"  HF_HUB_OFFLINE = {os.environ.get('HF_HUB_OFFLINE')}")
    print(f"  TRANSFORMERS_OFFLINE = {os.environ.get('TRANSFORMERS_OFFLINE')}")
    print(f"  VLLM_ATTENTION_BACKEND = {os.environ.get('VLLM_ATTENTION_BACKEND')}")
    print(f"  TRANSFORMERS_ATTN_IMPLEMENTATION = {os.environ.get('TRANSFORMERS_ATTN_IMPLEMENTATION')}")
    
    # 1. 准备数据
    print("\n📊 准备数据...")
    prepare_data()
    
    # 2. 加载数据
    print("\n📂 加载数据...")
    train_dataset = HuggingFaceDataset.from_parquet("data/train.parquet").to_list()
    val_dataset = HuggingFaceDataset.from_parquet("data/test.parquet").to_list()
    print(f"  训练集: {len(train_dataset)} 条")
    print(f"  验证集: {len(val_dataset)} 条")
    
    # 3. 获取配置
    print("\n⚙️ 配置训练参数...")
    config = get_training_config()
    
    # 4. 初始化算法
    print("\n🧠 初始化 VERL 算法...")
    algorithm = agl.VERL(config)
    
    # 5. 初始化 Trainer
    print("\n🎯 初始化 Trainer...")
    trainer = agl.Trainer(
        algorithm=algorithm,
        n_runners=2,  # 并行运行器数量
    )
    
    # 6. 开始训练
    print("\n" + "="*80)
    print("🏋️ 开始训练...")
    print("="*80)
    
    try:
        trainer.fit(math_agent, train_dataset, val_dataset=val_dataset)
        print("\n" + "="*80)
        print("✅ 训练完成！")
        print("="*80)
        print("\n📁 Checkpoint 保存位置:")
        print(f"   {os.path.join(os.getcwd(), 'checkpoints/AgentLightningTutorial/math_agent/')}")
        print("\n💡 下一步:")
        print("   1. 运行推理测试: python inference_compare.py")
        print("   2. 查看训练日志和指标")
    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ 训练失败: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
