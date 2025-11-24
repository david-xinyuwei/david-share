
import os
import sys
import agentlightning as agl
from datasets import Dataset as HuggingFaceDataset

# ⚠️ 关键：在最开始设置离线模式和环境变量
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['TRANSFORMERS_ATTN_IMPLEMENTATION'] = 'eager'
os.environ['VLLM_USE_V1'] = '1'

# 1. 定义 Agent (适配 vLLM)
@agl.rollout
async def math_agent(task, llm: agl.LLM):
    from openai import AsyncOpenAI
    import re
    
    # 训练时，llm.endpoint 会指向本地的 vLLM 服务器
    client = AsyncOpenAI(base_url=llm.endpoint, api_key="EMPTY")
    
    try:
        response = await client.chat.completions.create(
            model=llm.model,
            messages=[
                {"role": "system", "content": "You are a math expert. First, think step by step inside <think>...</think> tags, then provide the final answer inside <answer>...</answer> tags."},
                {"role": "user", "content": task['question']}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling LLM: {e}")
        answer = "0"

    # --- 升级版奖励函数 (Deep Thinking Reward) ---
    def extract_last_number(text):
        # 尝试从 <answer> 标签中提取
        answer_match = re.search(r'<answer>(.*?)</answer>', text, re.DOTALL)
        if answer_match:
            text = answer_match.group(1)

        # 匹配整数或小数，允许负号
        matches = re.findall(r'-?\d+\.?\d*', text)
        if matches:
            return float(matches[-1])
        return None

    try:
        pred_num = extract_last_number(answer)
        gt_num = extract_last_number(task['answer'])

        reward = 0.0

        # 1. 结构奖励 (Structure Reward)
        has_think = "<think>" in answer and "</think>" in answer
        has_answer = "<answer>" in answer and "</answer>" in answer
        
        if has_think and has_answer:
            reward += 0.5  # 格式正确，给予基础分
        
        # 2. 思考深度奖励 (Thinking Depth)
        # 鼓励模型多思考，但设置上限防止无限废话
        if has_think:
            think_match = re.search(r'<think>(.*?)</think>', answer, re.DOTALL)
            if think_match:
                think_content = think_match.group(1)
                # 动态奖励：每 1000 字符得 1.0 分，上限 1.0 分
                depth_score = min(len(think_content) / 1000.0, 1.0)
                reward += depth_score

        # 3. 结果奖励 (Outcome Reward) - 核心驱动力
        if pred_num is not None and gt_num is not None and abs(pred_num - gt_num) < 1e-6:
            reward += 2.0  # 做对了，给大奖！
            
            # 额外奖励：如果做对了，且确实进行了思考（而不是瞎猜），再加一点
            if has_think:
                reward += 0.5
        else:
            # 4. 惩罚 (Penalty)
            reward -= 1.0  # 做错题，倒扣分

        # 格式惩罚
        if not has_answer:
            reward -= 0.5
        
        if len(answer) < 20:
            reward -= 0.5  # 瞎猜重罚

    except Exception as e:
        print(f"Reward Error: {e}")
        reward = 0.0
        
    agl.emit_reward(reward)

# 2. 定义配置 - A10 24GB 专用配置 (0.5B 模型)
def get_config():
    # 使用 0.5B 模型
    model_path = "Qwen/Qwen2.5-0.5B-Instruct"
    
    config = {
        "algorithm": {
            "adv_estimator": "grpo",
            "use_kl_in_reward": True,
            "kl_ctrl": {
                "type": "fixed",
                "kl_coef": 0.001,
            },
        },
        "data": {
            "train_batch_size": 2, # 降低 batch size
            "max_prompt_length": 512, # 降低长度
            "max_response_length": 256, # 降低长度
        },
        "actor_rollout_ref": {
            "rollout": {
                "tensor_model_parallel_size": 1,
                "n": 2, # 降低 rollout 数量
                "name": "vllm",
                "gpu_memory_utilization": 0.4, # 给 vLLM 分配 40% (约 9.6GB)
                "enforce_eager": True, # 强制 eager 模式以节省显存
            },
            "actor": {
                "ppo_mini_batch_size": 1,
                "ppo_micro_batch_size_per_gpu": 1,
                "optim": {"lr": 1e-6},
                "fsdp_config": {
                    "param_offload": True, # 开启参数卸载
                    "optimizer_offload": True, # 开启优化器卸载
                },
            },
            "ref": {
                "log_prob_micro_batch_size_per_gpu": 1,
                "fsdp_config": {"param_offload": True}, # 开启参数卸载
            },
            "model": {
                "path": model_path,
                "use_remove_padding": True,
                "enable_gradient_checkpointing": True,
                "override_config": {
                    "attn_implementation": "eager",
                },
            },
        },
        "critic": {
            "optim": {"lr": 1e-5},
            "model": {
                "path": model_path,
                "use_remove_padding": True,
                "enable_gradient_checkpointing": True,
                "fsdp_config": {
                    "param_offload": True,
                    "optimizer_offload": True,
                },
                "override_config": {
                    "attn_implementation": "eager",
                },
            },
        },
        "trainer": {
            "n_gpus_per_node": 1,
            "val_before_train": False,
            "critic_warmup": 0,
            "logger": ["console"],
            "project_name": "AgentLightningTutorial",
            "experiment_name": "math_agent_0.5b_a10_v1",
            "nnodes": 1,
            "save_freq": 20,
            "test_freq": 20,
            "total_epochs": 1,
            "total_training_steps": 50,
        },
    }
        
    return config

# 3. 训练入口
def main():
    print("🔧 环境变量:")
    print(f"  HF_HUB_OFFLINE={os.environ.get('HF_HUB_OFFLINE')}")
    print(f"  TRANSFORMERS_OFFLINE={os.environ.get('TRANSFORMERS_OFFLINE')}")
    
    # 加载大规模数据
    train_file = "data/train_gpt5_large.parquet"
    test_file = "data/test_gpt5_large.parquet"
    
    if not os.path.exists(train_file):
        print(f"❌ 找不到训练数据: {train_file}")
        # Fallback to generating dummy data if needed, or just exit
        return

    print(f"📊 加载训练数据: {train_file}")
    full_train = HuggingFaceDataset.from_parquet(train_file)
    train_dataset = full_train.to_list()
    
    full_test = HuggingFaceDataset.from_parquet(test_file)
    val_dataset = full_test.select(range(min(50, len(full_test)))).to_list()
    
    print(f"✅ 训练集大小: {len(train_dataset)} (全量数据)")
    print(f"✅ 验证集大小: {len(val_dataset)}")

    # 初始化算法
    config = get_config()
    algorithm = agl.VERL(config)

    # 初始化 Trainer
    trainer = agl.Trainer(
        algorithm=algorithm,
        n_runners=1, # 减少 runner 数量
    )
    
    # 开始训练
    print("\\n🚀 开始训练...")
    trainer.fit(math_agent, train_dataset, val_dataset=val_dataset)
    print("\\n✅ 训练完成！")

if __name__ == "__main__":
    main()
