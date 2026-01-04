#!/usr/bin/env python3
"""
AIPC GRPO Training Script (Agent Lightning)
============================================

Reinforcement learning training using Agent Lightning's @agl.rollout decorator.
Optimizes model for AIPC domain quality using custom reward functions.

Features:
    - Agent Lightning @agl.rollout for GRPO
    - Custom AIPC domain reward function
    - vLLM backend for fast inference
    - Automatic checkpointing

Usage:
    python train_grpo_agl.py --model checkpoints/aipc_sft_v1 --output checkpoints/aipc_grpo_v1

Author: Xinyu Wei (xinyuwei@microsoft.com)
License: MIT
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch

# Agent Lightning imports
try:
    import agentlightning as agl
except ImportError:
    raise ImportError(
        "agentlightning not installed. Install with: pip install agentlightning>=0.3.0"
    )

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =============================================================================
# AIPC Domain Reward Functions
# =============================================================================

# AIPC domain keywords for coverage check
AIPC_KEYWORDS = {
    "hardware": [
        "NPU", "CPU", "GPU", "Intel", "AMD", "Qualcomm", "Snapdragon",
        "Core Ultra", "Ryzen AI", "XDNA", "AI Boost", "内存", "显存",
        "功耗", "散热", "处理器", "加速器",
    ],
    "software": [
        "Windows", "DirectML", "ONNX", "Runtime", "Copilot", "API",
        "量化", "INT4", "INT8", "FP16", "BF16", "Olive", "模型优化",
        "推理", "部署", "SDK", "驱动",
    ],
    "applications": [
        "字幕", "翻译", "Stable Diffusion", "Whisper", "语音识别",
        "图像生成", "代码补全", "RAG", "向量数据库", "本地部署",
        "实时", "离线", "隐私",
    ],
}

# Structure patterns
STRUCTURE_PATTERNS = {
    "markdown_header": r"^#+\s+.+$",
    "code_block": r"```[\w]*\n[\s\S]*?\n```",
    "bullet_list": r"^[\*\-]\s+.+$",
    "numbered_list": r"^\d+\.\s+.+$",
}

# Hallucination indicators
HALLUCINATION_INDICATORS = [
    r"Intel Core Ultra \d{5}",  # Fake model numbers
    r"AMD Ryzen AI \d{5}",
    r"NPU 性能达到 \d{4,} TOPS",  # Unrealistic TOPS claims
    r"Windows \d{3}",  # Future Windows versions
    r"发布于 202[6-9]",  # Future dates
]


def compute_keyword_coverage(response: str) -> float:
    """
    Compute keyword coverage score.
    
    Returns:
        float: Score between 0 and 0.4
    """
    response_lower = response.lower()
    total_keywords = 0
    matched_keywords = 0
    
    for category, keywords in AIPC_KEYWORDS.items():
        for keyword in keywords:
            total_keywords += 1
            if keyword.lower() in response_lower:
                matched_keywords += 1
    
    # At least some keywords should be covered
    coverage_ratio = matched_keywords / max(total_keywords * 0.1, 1)  # Expect 10% coverage
    return min(0.4, coverage_ratio * 0.4)


def compute_structure_score(response: str) -> float:
    """
    Compute structure quality score based on Markdown formatting.
    
    Returns:
        float: Score between 0 and 0.3
    """
    score = 0.0
    
    # Check for headers
    if re.search(STRUCTURE_PATTERNS["markdown_header"], response, re.MULTILINE):
        score += 0.1
    
    # Check for code blocks
    if re.search(STRUCTURE_PATTERNS["code_block"], response):
        score += 0.1
    
    # Check for lists (bullet or numbered)
    if re.search(STRUCTURE_PATTERNS["bullet_list"], response, re.MULTILINE) or \
       re.search(STRUCTURE_PATTERNS["numbered_list"], response, re.MULTILINE):
        score += 0.1
    
    return score


def compute_hallucination_penalty(response: str) -> float:
    """
    Compute hallucination penalty.
    
    Returns:
        float: Penalty between 0 and 0.3 (0 = no hallucination, 0.3 = severe)
    """
    penalty = 0.0
    
    for pattern in HALLUCINATION_INDICATORS:
        if re.search(pattern, response):
            penalty += 0.1
    
    return min(0.3, penalty)


def compute_aipc_reward(response: str) -> float:
    """
    Compute comprehensive AIPC domain reward.
    
    Components:
        - Keyword coverage: 0-0.4
        - Structure score: 0-0.3
        - No hallucination bonus: 0-0.3
    
    Returns:
        float: Total reward between 0 and 1
    """
    keyword_score = compute_keyword_coverage(response)
    structure_score = compute_structure_score(response)
    hallucination_penalty = compute_hallucination_penalty(response)
    
    # Compute final reward
    no_hallucination_bonus = 0.3 - hallucination_penalty
    total_reward = keyword_score + structure_score + no_hallucination_bonus
    
    return max(0.0, min(1.0, total_reward))


# =============================================================================
# Data Loading
# =============================================================================


def load_prompts(data_path: str) -> List[str]:
    """Load prompts from JSONL file."""
    prompts = []
    
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sample = json.loads(line)
                # Extract question from ShareGPT format
                if "conversations" in sample:
                    for conv in sample["conversations"]:
                        if conv["from"] == "human":
                            prompts.append(conv["value"])
                            break
                elif "question" in sample:
                    prompts.append(sample["question"])
    
    logger.info(f"Loaded {len(prompts)} prompts from {data_path}")
    return prompts


# =============================================================================
# Agent Lightning GRPO Training
# =============================================================================


class AIPCTrainer:
    """AIPC domain trainer using Agent Lightning."""
    
    def __init__(
        self,
        model_path: str,
        output_dir: str,
        learning_rate: float = 1e-5,
        num_iterations: int = 100,
        rollouts_per_prompt: int = 4,
        max_new_tokens: int = 1024,
        temperature: float = 0.7,
    ):
        self.model_path = model_path
        self.output_dir = output_dir
        self.learning_rate = learning_rate
        self.num_iterations = num_iterations
        self.rollouts_per_prompt = rollouts_per_prompt
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        
        # Initialize Agent Lightning model
        logger.info(f"Loading model from {model_path}")
        self.model = agl.VERL.from_pretrained(
            model_path,
            tensor_parallel_size=1,  # Adjust based on GPU count
            gpu_memory_utilization=0.85,
        )
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    @agl.rollout
    def aipc_rollout(self, prompt: str) -> Tuple[str, float]:
        """
        Perform a single rollout with AIPC reward.
        
        This method is decorated with @agl.rollout to enable
        Agent Lightning's GRPO training.
        """
        # Generate response
        response = self.model.generate(
            prompt,
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature,
            do_sample=True,
        )
        
        # Compute reward
        reward = compute_aipc_reward(response)
        
        # Emit reward for GRPO optimization
        agl.emit_reward(reward)
        
        return response, reward
    
    def train(self, prompts: List[str]) -> Dict:
        """Run GRPO training loop."""
        logger.info("=" * 60)
        logger.info("Starting AIPC GRPO Training")
        logger.info(f"Prompts: {len(prompts)}")
        logger.info(f"Iterations: {self.num_iterations}")
        logger.info(f"Rollouts per prompt: {self.rollouts_per_prompt}")
        logger.info("=" * 60)
        
        # Training metrics
        metrics = {
            "iteration_rewards": [],
            "best_reward": 0.0,
            "total_rollouts": 0,
        }
        
        # Configure GRPO optimizer
        agl.configure_grpo(
            learning_rate=self.learning_rate,
            mini_batch_size=4,
            gradient_accumulation_steps=4,
        )
        
        for iteration in range(self.num_iterations):
            iteration_rewards = []
            
            # Sample prompts for this iteration
            batch_prompts = prompts[:min(32, len(prompts))]
            
            for prompt in batch_prompts:
                # Perform multiple rollouts per prompt
                for _ in range(self.rollouts_per_prompt):
                    response, reward = self.aipc_rollout(prompt)
                    iteration_rewards.append(reward)
                    metrics["total_rollouts"] += 1
            
            # Compute iteration statistics
            avg_reward = sum(iteration_rewards) / len(iteration_rewards)
            metrics["iteration_rewards"].append(avg_reward)
            
            if avg_reward > metrics["best_reward"]:
                metrics["best_reward"] = avg_reward
                self._save_checkpoint(iteration, is_best=True)
            
            logger.info(
                f"Iteration {iteration + 1}/{self.num_iterations} | "
                f"Avg Reward: {avg_reward:.4f} | "
                f"Best: {metrics['best_reward']:.4f}"
            )
            
            # Save periodic checkpoint
            if (iteration + 1) % 10 == 0:
                self._save_checkpoint(iteration)
        
        # Save final model
        self._save_checkpoint(self.num_iterations - 1, is_final=True)
        
        # Save training metrics
        metrics_path = Path(self.output_dir) / "training_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)
        
        logger.info("=" * 60)
        logger.info("Training completed!")
        logger.info(f"Best reward: {metrics['best_reward']:.4f}")
        logger.info(f"Total rollouts: {metrics['total_rollouts']}")
        logger.info(f"Model saved to: {self.output_dir}")
        logger.info("=" * 60)
        
        return metrics
    
    def _save_checkpoint(
        self,
        iteration: int,
        is_best: bool = False,
        is_final: bool = False,
    ) -> None:
        """Save model checkpoint."""
        if is_final:
            save_path = self.output_dir
        elif is_best:
            save_path = Path(self.output_dir) / "best"
        else:
            save_path = Path(self.output_dir) / f"checkpoint-{iteration + 1}"
        
        Path(save_path).mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(save_path)
        
        logger.info(f"Checkpoint saved to {save_path}")


# =============================================================================
# Main Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AIPC GRPO Training with Agent Lightning",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    # Model arguments
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to SFT model checkpoint",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="checkpoints/aipc_grpo_v1",
        help="Output directory for GRPO model",
    )
    
    # Data arguments
    parser.add_argument(
        "--data",
        type=str,
        default="data/aipc_train.jsonl",
        help="Path to training prompts (JSONL)",
    )
    
    # Training arguments
    parser.add_argument(
        "--num_iterations",
        type=int,
        default=100,
        help="Number of GRPO iterations",
    )
    parser.add_argument(
        "--rollouts_per_prompt",
        type=int,
        default=4,
        help="Number of rollouts per prompt",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=1e-5,
        help="Learning rate for GRPO",
    )
    parser.add_argument(
        "--max_new_tokens",
        type=int,
        default=1024,
        help="Maximum tokens to generate",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Sampling temperature",
    )
    
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    logger.info("=" * 60)
    logger.info("AIPC GRPO Training (Agent Lightning)")
    logger.info("=" * 60)
    logger.info(f"Model: {args.model}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Data: {args.data}")
    logger.info(f"Iterations: {args.num_iterations}")
    logger.info(f"Learning rate: {args.learning_rate}")
    logger.info("=" * 60)
    
    # Load prompts
    prompts = load_prompts(args.data)
    
    # Create trainer
    trainer = AIPCTrainer(
        model_path=args.model,
        output_dir=args.output,
        learning_rate=args.learning_rate,
        num_iterations=args.num_iterations,
        rollouts_per_prompt=args.rollouts_per_prompt,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
    )
    
    # Train
    metrics = trainer.train(prompts)
    
    logger.info("=" * 60)
    logger.info("Done!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
