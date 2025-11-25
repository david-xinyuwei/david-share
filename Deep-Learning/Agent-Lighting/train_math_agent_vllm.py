#!/usr/bin/env python3
"""
Agent Lightning Math Reasoning Training Script
Train a math reasoning agent using GRPO algorithm + Deep Thinking reward function.

Key Features:
  - Uses llm.chat() for automatic tracing of all LLM calls
  - Structured reward function encourages deep reasoning
  - Supports command-line arguments for training hyperparameters
  - Automatically outputs checkpoint path for downstream scripts
"""

import os
import sys
import re
import argparse
import agentlightning as agl
from datasets import Dataset as HuggingFaceDataset

# Set offline mode and environment variables
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['TRANSFORMERS_ATTN_IMPLEMENTATION'] = 'eager'


# ============================================================
# Agent Definition - Using @agl.rollout decorator for auto-tracing
# ============================================================
@agl.rollout
async def math_agent(task, llm: agl.LLM):
    """
    Math Reasoning Agent
    
    Uses Agent Lightning's llm.chat() API:
    - Automatic tracing of all LLM calls
    - Auto-records input/output/latency to LightningStore
    - Supports Dashboard visualization
    """
    try:
        # Use Agent Lightning's llm.chat() API
        # Benefits: auto-tracing, Dashboard visualization, error recovery
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
        answer = response
    except Exception as e:
        print(f"LLM call error: {e}")
        answer = "0"

    # Compute reward
    reward = compute_reward(answer, task['answer'])
    agl.emit_reward(reward)


def compute_reward(answer: str, ground_truth: str) -> float:
    """
    Deep Thinking Multi-Dimensional Reward Function
    
    Reward Dimensions:
    1. Structure reward (0.5): Contains <think> and <answer> tags
    2. Thinking depth (0-1.0): Based on thinking content length
    3. Structured thinking (0-1.0): Contains analysis/strategy/calculation/verification steps
    4. Correctness (2.0): Core reward for correct answer
    5. Penalty (-1.0 ~ -0.5): Wrong format or incorrect answer
    
    Theoretical max score: 4.0
    """
    def extract_last_number(text):
        """Extract the last number from text"""
        # Try to extract from <answer> tag first
        answer_match = re.search(r'<answer>(.*?)</answer>', text, re.DOTALL)
        if answer_match:
            text = answer_match.group(1)
        # Match integers or decimals
        matches = re.findall(r'-?\d+\.?\d*', text)
        if matches:
            return float(matches[-1])
        return None

    try:
        pred_num = extract_last_number(answer)
        gt_num = extract_last_number(ground_truth)
        reward = 0.0

        # 1. Structure reward
        has_think = "<think>" in answer and "</think>" in answer
        has_answer = "<answer>" in answer and "</answer>" in answer
        
        if has_think and has_answer:
            reward += 0.5

        # 2. Thinking depth reward
        if has_think:
            think_match = re.search(r'<think>(.*?)</think>', answer, re.DOTALL)
            if think_match:
                think_content = think_match.group(1)
                think_content_lower = think_content.lower()
                
                # Length reward
                depth_score = min(len(think_content) / 1000.0, 1.0)
                reward += depth_score
                
                # 3. Structured thinking quality reward
                trajectory_bonus = 0.0
                
                # Analysis step
                analysis_keywords = ['analyze', 'given', 'find', 'identify', 'problem', 'what']
                if any(kw in think_content_lower for kw in analysis_keywords):
                    trajectory_bonus += 0.3
                
                # Strategy step
                strategy_keywords = ['method', 'formula', 'theorem', 'apply', 'approach', 'use']
                if any(kw in think_content_lower for kw in strategy_keywords):
                    trajectory_bonus += 0.3
                
                # Calculation step
                calculation_keywords = ['calculate', 'substitute', 'solve', '=', 'compute']
                if any(kw in think_content_lower for kw in calculation_keywords):
                    trajectory_bonus += 0.2
                
                # Verification step
                verification_keywords = ['verify', 'check', 'correct', 'confirm', 'validate']
                if any(kw in think_content_lower for kw in verification_keywords):
                    trajectory_bonus += 0.2
                
                reward += trajectory_bonus

        # 4. Correctness reward (core)
        if pred_num is not None and gt_num is not None and abs(pred_num - gt_num) < 1e-6:
            reward += 2.0
            if has_think:
                reward += 0.5  # Extra reward for thinking before correct answer
        else:
            reward -= 1.0  # Penalty for wrong answer

        # 5. Format penalty
        if not has_answer:
            reward -= 0.5
        if len(answer) < 20:
            reward -= 0.5

    except Exception as e:
        print(f"Reward calculation error: {e}")
        reward = 0.0
        
    return reward


# ============================================================
# Configuration Generation - Supports CLI arguments
# ============================================================
def get_config(args):
    """
    Generate training configuration
    
    Args:
        args: Command-line arguments object containing:
            - model: Model path or HuggingFace ID
            - epochs: Number of training epochs
            - steps: Total training steps
            - batch_size: Batch size
            - lr: Learning rate
            - experiment_name: Experiment name
    """
    # Check local model path
    local_model_path = os.path.join(os.getcwd(), args.model)
    if os.path.exists(local_model_path):
        model_path = local_model_path
    else:
        model_path = args.model
    
    config = {
        "algorithm": {
            "adv_estimator": "grpo",  # Use GRPO algorithm, saves 50% memory
            "use_kl_in_reward": True,
            "kl_ctrl": {
                "type": "fixed",
                "kl_coef": 0.001,
            },
        },
        "data": {
            "train_batch_size": args.batch_size,
            "max_prompt_length": 1024,
            "max_response_length": 512,
        },
        "actor_rollout_ref": {
            "rollout": {
                "tensor_model_parallel_size": 1,
                "n": 4,  # Generate 4 answers per question for group comparison
                "name": "vllm",
                "gpu_memory_utilization": 0.5,
                "log_prob_micro_batch_size_per_gpu": 4,
            },
            "actor": {
                "ppo_mini_batch_size": 2,
                "ppo_micro_batch_size_per_gpu": 1,
                "optim": {"lr": args.lr},
                "fsdp_config": {
                    "param_offload": True,
                    "optimizer_offload": True,
                },
            },
            "ref": {
                "log_prob_micro_batch_size_per_gpu": 2,
                "fsdp_config": {"param_offload": True},
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
            "experiment_name": args.experiment_name,
            "nnodes": 1,
            "save_freq": args.save_freq,
            "test_freq": args.save_freq,
            "total_epochs": args.epochs,
            "total_training_steps": args.steps,
        },
    }
        
    return config, model_path


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Agent Lightning Math Reasoning Training Script",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Model parameters
    parser.add_argument(
        "--model", type=str, default="Qwen/Qwen2.5-3B-Instruct",
        help="Model path or HuggingFace ID"
    )
    
    # Training hyperparameters
    parser.add_argument(
        "--epochs", type=int, default=1,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--steps", type=int, default=100,
        help="Total training steps"
    )
    parser.add_argument(
        "--batch_size", type=int, default=4,
        help="Training batch size"
    )
    parser.add_argument(
        "--lr", type=float, default=1e-6,
        help="Actor learning rate"
    )
    parser.add_argument(
        "--save_freq", type=int, default=20,
        help="Checkpoint save frequency (steps)"
    )
    
    # Experiment configuration
    parser.add_argument(
        "--experiment_name", type=str, default="math_agent_training",
        help="Experiment name (used for checkpoint path)"
    )
    
    # Data paths
    parser.add_argument(
        "--train_data", type=str, default="data/train_gpt5_large.parquet",
        help="Training data path"
    )
    parser.add_argument(
        "--test_data", type=str, default="data/test_gpt5_large.parquet",
        help="Test data path"
    )
    parser.add_argument(
        "--val_size", type=int, default=50,
        help="Validation set size"
    )
    
    return parser.parse_args()


# ============================================================
# Main Function
# ============================================================
def main():
    """Main training function"""
    args = parse_args()
    
    print("=" * 70)
    print("Agent Lightning Math Reasoning Training")
    print("=" * 70)
    
    # Display training configuration
    print("\nTraining Configuration:")
    print(f"  Model: {args.model}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Steps: {args.steps}")
    print(f"  Batch Size: {args.batch_size}")
    print(f"  Learning Rate: {args.lr}")
    print(f"  Save Frequency: every {args.save_freq} steps")
    print(f"  Experiment Name: {args.experiment_name}")
    
    # Load data
    if not os.path.exists(args.train_data):
        print(f"\nError: Training data not found: {args.train_data}")
        print("Please run: python generate_training_data_gpt5_agl.py first")
        sys.exit(1)

    print(f"\nLoading data...")
    full_train = HuggingFaceDataset.from_parquet(args.train_data)
    train_dataset = full_train.to_list()
    
    if os.path.exists(args.test_data):
        full_test = HuggingFaceDataset.from_parquet(args.test_data)
        val_dataset = full_test.select(range(min(args.val_size, len(full_test)))).to_list()
    else:
        val_dataset = train_dataset[:args.val_size]
    
    print(f"  Training set: {len(train_dataset)} samples")
    print(f"  Validation set: {len(val_dataset)} samples")

    # Initialize configuration and algorithm
    config, model_path = get_config(args)
    print(f"\nUsing model: {model_path}")
    
    algorithm = agl.VERL(config)
    trainer = agl.Trainer(algorithm=algorithm, n_runners=2)
    
    # Compute checkpoint path
    checkpoint_dir = os.path.join(
        "checkpoints",
        "AgentLightningTutorial",
        args.experiment_name,
        f"global_step_{args.steps}",
        "actor",
        "huggingface"
    )
    
    # Start training
    print("\n" + "=" * 70)
    print("Starting training...")
    print("=" * 70)
    
    trainer.fit(math_agent, train_dataset, val_dataset=val_dataset)
    
    # Training complete, output results
    print("\n" + "=" * 70)
    print("Training Complete!")
    print("=" * 70)
    
    print("\nCheckpoint Path:")
    print(f"  {checkpoint_dir}")
    
    # Save checkpoint path to file for downstream scripts
    checkpoint_info_file = "last_checkpoint.txt"
    with open(checkpoint_info_file, "w") as f:
        f.write(checkpoint_dir)
    print(f"\nCheckpoint path saved to: {checkpoint_info_file}")
    
    print("\nNext Steps:")
    print(f"  1. Convert model: python convert_checkpoint.py")
    print(f"  2. Evaluate: bash run_full_evaluation_v5.sh")
    print("=" * 70)


if __name__ == "__main__":
    main()
