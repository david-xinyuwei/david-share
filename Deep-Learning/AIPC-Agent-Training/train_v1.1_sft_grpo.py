"""
Level 1 改造: 最小改动，最大收益
改动点:
1. 使用 llm.chat() 替代 AsyncOpenAI (1行)
2. 奖励函数提取到外部 (模块化)
3. 添加简单的追踪

优势:
✅ 自动追踪 LLM 调用
✅ Dashboard 可视化
✅ 代码更简洁
✅ 保持原有 GRPO 配置
"""

import os
import agentlightning as agl
from datasets import Dataset as HuggingFaceDataset

# 环境变量
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
# ✅ H100 支持 FlashAttention-2，大幅提速！
os.environ['TRANSFORMERS_ATTN_IMPLEMENTATION'] = 'flash_attention_2'
# 注意：不设置 VLLM_USE_V1，避免与 vLLM 0.7.0 不兼容


# ============= 改动 1: 奖励函数提取（模块化）=============
class DeepThinkingReward:
    """深度思考奖励函数 - 提取为独立类"""
    
    @staticmethod
    def extract_number(text):
        import re
        answer_match = re.search(r'<answer>(.*?)</answer>', text, re.DOTALL)
        if answer_match:
            text = answer_match.group(1)
        matches = re.findall(r'-?\d+\.?\d*', text)
        return float(matches[-1]) if matches else None
    
    @staticmethod
    def calculate(response: str, ground_truth: str) -> float:
        """
        4维度奖励函数
        
        Returns:
            reward (float): 范围 -2.0 ~ 4.0
        """
        import re
        reward = 0.0
        
        # 1. 结构奖励
        has_think = "<think>" in response and "</think>" in response
        has_answer = "<answer>" in response and "</answer>" in response
        
        if has_think and has_answer:
            reward += 0.5
        
        # 2. 思考深度奖励
        if has_think:
            think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL)
            if think_match:
                think_length = len(think_match.group(1))
                depth_score = min(think_length / 1000.0, 1.0)
                reward += depth_score
        
        # 3. 正确性奖励（核心）
        pred = DeepThinkingReward.extract_number(response)
        gt = DeepThinkingReward.extract_number(ground_truth)
        
        if pred is not None and gt is not None and abs(pred - gt) < 1e-6:
            reward += 2.0
            if has_think:
                reward += 0.5  # 额外奖励
        else:
            reward -= 1.0  # 错误惩罚
        
        # 4. 格式惩罚
        if not has_answer:
            reward -= 0.5
        if len(response) < 20:
            reward -= 0.5
        
        return reward


# ============= 改动 2: 使用 llm.chat() =============
@agl.rollout
async def math_agent(task, llm: agl.LLM):
    """
    Level 1 改造: 使用 Agent Lightning 的高层 API
    
    改动:
    - 删除 AsyncOpenAI client 创建
    + 直接用 llm.chat()
    
    优势:
    ✅ Agent Lightning 自动追踪所有调用
    ✅ 自动记录到 LightningStore
    ✅ Dashboard 可视化
    ✅ 自动重试和错误恢复
    """
    
    try:
        # ✅ 改动：用 llm.chat() 替代手动创建 AsyncOpenAI
        response = await llm.chat(
            messages=[
                {
                    "role": "system",
                    "content": "You are a math expert. First, think step by step inside <think>...</think> tags, then provide the final answer inside <answer>...</answer> tags."
                },
                {"role": "user", "content": task['question']}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        response = "<answer>0</answer>"
    
    # 计算奖励（使用提取的函数）
    reward = DeepThinkingReward.calculate(response, task['answer'])
    
    # 发射奖励
    agl.emit_reward(reward)
    
    return response


# ============= 配置保持不变（继续用 GRPO）=============
def get_config():
    local_model_path = os.path.join(os.getcwd(), "Qwen/Qwen2.5-3B-Instruct")
    model_path = local_model_path if os.path.exists(local_model_path) else "Qwen/Qwen2.5-3B-Instruct"
    
    return {
        "algorithm": {
            "adv_estimator": "grpo",  # ✅ 保持 GRPO
            "use_kl_in_reward": True,
            "kl_ctrl": {"type": "fixed", "kl_coef": 0.001},
        },
        "data": {
            "train_batch_size": 4,
            "max_prompt_length": 1024,
            "max_response_length": 512,
        },
        "actor_rollout_ref": {
            "rollout": {
                "tensor_model_parallel_size": 1,
                "n": 4,  # GRPO: 每题生成4个答案
                "log_prob_micro_batch_size_per_gpu": 4,  # 必需参数
                "name": "vllm",
                "gpu_memory_utilization": 0.5,
            },
            "actor": {
                "ppo_mini_batch_size": 2,
                "ppo_micro_batch_size_per_gpu": 1,
                "optim": {"lr": 1e-6},
                "fsdp_config": {"param_offload": True, "optimizer_offload": True},
            },
            "ref": {
                "log_prob_micro_batch_size_per_gpu": 2,
                "fsdp_config": {"param_offload": True},
            },
            "model": {
                "path": model_path,
                "use_remove_padding": True,
                "enable_gradient_checkpointing": True,
                "override_config": {"attn_implementation": "flash_attention_2"},
            },
        },
        "critic": {
            "optim": {"lr": 1e-5},
            "model": {
                "path": model_path,
                "use_remove_padding": True,
                "enable_gradient_checkpointing": True,
                "fsdp_config": {"param_offload": True, "optimizer_offload": True},
                "override_config": {"attn_implementation": "flash_attention_2"},
            },
        },
        "trainer": {
            "n_gpus_per_node": 1,
            "val_before_train": False,
            "critic_warmup": 0,
            "logger": ["console"],
            "project_name": "AgentLightningTutorial",
            "experiment_name": "math_agent_level1",  # 新名字
            "nnodes": 1,
            "save_freq": 20,
            "test_freq": 20,
            "total_epochs": 1,
            "total_training_steps": 100,
        },
    }


def main():
    print("=" * 60)
    print("🚀 Level 1 改造: 最小改动 + Agent Lightning 优化")
    print("=" * 60)
    print("\n改动点:")
    print("  ✅ 使用 llm.chat() 替代 AsyncOpenAI")
    print("  ✅ 奖励函数模块化")
    print("  ✅ 自动追踪和可视化")
    print("\n保持不变:")
    print("  ✅ GRPO 算法")
    print("  ✅ 所有超参数")
    print("  ✅ 训练流程")
    print("=" * 60)
    
    # 加载数据
    train_file = "data/train_gpt5_large.parquet"
    test_file = "data/test_gpt5_large.parquet"
    
    if not os.path.exists(train_file):
        print(f"\n❌ 找不到训练数据: {train_file}")
        return
    
    full_train = HuggingFaceDataset.from_parquet(train_file)
    train_dataset = full_train.to_list()
    
    full_test = HuggingFaceDataset.from_parquet(test_file)
    val_dataset = full_test.select(range(min(50, len(full_test)))).to_list()
    
    print(f"\n📊 数据加载:")
    print(f"  训练集: {len(train_dataset)} 样本")
    print(f"  验证集: {len(val_dataset)} 样本")
    
    # 初始化
    config = get_config()
    algorithm = agl.VERL(config)
    trainer = agl.Trainer(algorithm=algorithm, n_runners=2)
    
    # 训练
    print("\n🔥 开始训练...\n")
    trainer.fit(math_agent, train_dataset, val_dataset=val_dataset)
    
    print("\n✅ 训练完成！")
    print("\n📁 输出位置:")
    print("  - Checkpoints: checkpoints/AgentLightningTutorial/math_agent_level1/")
    print("  - 转换模型: python convert_checkpoint.py ...")


if __name__ == "__main__":
    main()
