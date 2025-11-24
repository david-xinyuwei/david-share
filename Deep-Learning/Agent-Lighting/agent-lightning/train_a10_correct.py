import os
import sys

# A10 优化配置
os.environ['HF_HUB_OFFLINE'] = '0'
os.environ['TRANSFORMERS_OFFLINE'] = '0'
os.environ['TRANSFORMERS_ATTN_IMPLEMENTATION'] = 'eager'
os.environ['VLLM_USE_V1'] = '1'

import agentlightning as agl
import pandas as pd

# 使用原有的 math_agent 和 reward 定义
exec(open('train_math_agent_vllm.py').read().split('# 2. 定义配置')[0])

def get_config():
    local_model_path = "/root/agent-lightning/Qwen/Qwen2.5-3B-Instruct"
    if os.path.exists(local_model_path):
        model_path = local_model_path
    else:
        model_path = "Qwen/Qwen2.5-3B-Instruct"

    return {
        "project_name": "AgentLightningA10Validation",
        "experiment_name": "math_agent_a10",
        "algorithm": {
            "adv_estimator": "grpo",
            "use_kl_in_reward": True,
            "kl_ctrl": {"type": "fixed", "kl_coef": 0.001},
        },
        "data": {
            "train_batch_size": 2,
            "max_prompt_length": 512,
            "max_response_length": 512,
            "train_files": "data/train_gpt5_large.parquet",
            "val_files": "data/test_gpt5_large.parquet",
        },
        "actor_rollout_ref": {
            "model": {"path": model_path, "enable_gradient_checkpointing": True},
            "rollout": {
                "tensor_model_parallel_size": 1,
                "name": "vllm",
                "gpu_memory_utilization": 0.85,
                "n": 2,
                "log_prob_micro_batch_size_per_gpu": 1,
            },
            "actor": {
                "ppo_mini_batch_size": 1,
                "ppo_micro_batch_size_per_gpu": 1,
                "optim": {"lr": 1e-6},
            },
            "ref": {
                "log_prob_micro_batch_size_per_gpu": 1,
            },
        },
        "trainer": {
            "total_epochs": 1,
            "project_name": "AgentLightningA10",
            "experiment_name": "math_agent_a10_verification",
            "logger": ["console"],
            "n_gpus_per_node": 1,
            "nnodes": 1,
            "save_freq": 10,
            "total_training_steps": 10,
            "val_before_train": False,  # 跳过验证
        }
    }

if __name__ == "__main__":
    print("🚀 开始 A10 验证训练...")
    print(f"配置: 10 steps, batch_size=2, max_tokens=512")
    
    df = pd.read_parquet("data/train_gpt5_large.parquet")
    train_dataset = df.to_dict('records')
    
    config = get_config()
    algorithm = agl.VERL(config)
    trainer = agl.Trainer(algorithm=algorithm, n_runners=1)
    trainer.fit(math_agent, train_dataset)
    
    print("✅ 训练完成!")
