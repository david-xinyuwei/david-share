#!/usr/bin/env python3
"""
AIPC Feedback Training Script (Agent Lightning)
================================================

Train model on feedback data using GRPO with positive/negative rewards.
This implements preference learning without DPO by using reward shaping.

Key Insight:
    Agent Lightning doesn't directly support DPO, so we simulate preference
    learning by assigning:
    - Positive reward (+1.0) to correct responses
    - Negative reward (-0.5) to wrong responses

Features:
    - Load preference pairs from feedback data
    - GRPO training with reward shaping
    - Iterative improvement through multiple rounds

Usage:
    python train_feedback_agl.py --model checkpoints/aipc_grpo_v1 --data data/feedback_v1.jsonl --output checkpoints/aipc_grpo_v2

Author: Xinyu Wei (xinyuwei@microsoft.com)
License: MIT
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import torch

# Agent Lightning imports
try:
    import agentlightning as agl
except ImportError:
    raise ImportError(
        "agentlightning not installed. Install with: pip install agentlightning>=0.3.0"
    )

# Import shared reward functions
from reward_functions import compute_aipc_reward

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =============================================================================
# Data Loading
# =============================================================================


def load_feedback_data(data_path: str) -> List[Dict]:
    """Load feedback data in preference format."""
    data = []
    
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sample = json.loads(line)
                data.append(sample)
    
    logger.info(f"Loaded {len(data)} feedback samples from {data_path}")
    return data


# =============================================================================
# Feedback Training
# =============================================================================


class FeedbackTrainer:
    """
    Feedback trainer using Agent Lightning.
    
    Implements preference learning via GRPO by:
    1. Generating responses and comparing to reference
    2. Assigning positive/negative rewards based on similarity
    3. Running GRPO optimization
    """
    
    # Reward configuration for preference learning
    POSITIVE_REWARD = 1.0   # Reward for responses similar to "chosen"
    NEGATIVE_REWARD = -0.5  # Penalty for responses similar to "rejected"
    NEUTRAL_THRESHOLD = 0.3  # Similarity threshold
    
    def __init__(
        self,
        model_path: str,
        output_dir: str,
        learning_rate: float = 5e-6,  # Lower LR for feedback training
        num_iterations: int = 50,
        rollouts_per_sample: int = 2,
        max_new_tokens: int = 1024,
        temperature: float = 0.7,
    ):
        self.model_path = model_path
        self.output_dir = output_dir
        self.learning_rate = learning_rate
        self.num_iterations = num_iterations
        self.rollouts_per_sample = rollouts_per_sample
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        
        # Initialize Agent Lightning model
        logger.info(f"Loading model from {model_path}")
        self.model = agl.VERL.from_pretrained(
            model_path,
            tensor_parallel_size=1,
            gpu_memory_utilization=0.85,
        )
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    def compute_preference_reward(
        self,
        generated: str,
        chosen: str,
        rejected: str,
    ) -> float:
        """
        Compute reward based on preference comparison.
        
        Strategy:
        1. Compute domain reward for generated response
        2. Compute similarity to chosen vs rejected
        3. Combine into final reward
        """
        # Base domain reward
        domain_reward = compute_aipc_reward(generated)
        
        # Simple similarity check (can be enhanced with embeddings)
        # Use character overlap as proxy
        gen_set = set(generated.lower().split())
        chosen_set = set(chosen.lower().split())
        rejected_set = set(rejected.lower().split())
        
        chosen_overlap = len(gen_set & chosen_set) / max(len(gen_set), 1)
        rejected_overlap = len(gen_set & rejected_set) / max(len(gen_set), 1)
        
        # Preference signal
        if chosen_overlap > rejected_overlap + self.NEUTRAL_THRESHOLD:
            # Closer to chosen response
            preference_bonus = 0.3
        elif rejected_overlap > chosen_overlap + self.NEUTRAL_THRESHOLD:
            # Closer to rejected response
            preference_bonus = -0.3
        else:
            # Neutral
            preference_bonus = 0.0
        
        # Combine rewards
        total_reward = domain_reward + preference_bonus
        
        return max(-1.0, min(1.0, total_reward))
    
    @agl.rollout
    def feedback_rollout(
        self,
        prompt: str,
        chosen: str,
        rejected: str,
    ) -> Tuple[str, float]:
        """
        Perform a single rollout with preference-based reward.
        """
        # Generate response
        response = self.model.generate(
            prompt,
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature,
            do_sample=True,
        )
        
        # Compute preference reward
        reward = self.compute_preference_reward(response, chosen, rejected)
        
        # Emit reward for GRPO optimization
        agl.emit_reward(reward)
        
        return response, reward
    
    def train(self, feedback_data: List[Dict]) -> Dict:
        """Run feedback training loop."""
        logger.info("=" * 60)
        logger.info("Starting AIPC Feedback Training")
        logger.info(f"Feedback samples: {len(feedback_data)}")
        logger.info(f"Iterations: {self.num_iterations}")
        logger.info(f"Rollouts per sample: {self.rollouts_per_sample}")
        logger.info("=" * 60)
        
        # Training metrics
        metrics = {
            "iteration_rewards": [],
            "preference_alignment": [],
            "best_reward": -1.0,
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
            aligned_count = 0
            
            # Process feedback samples
            for sample in feedback_data:
                prompt = sample["prompt"]
                chosen = sample["chosen"]
                rejected = sample["rejected"]
                
                for _ in range(self.rollouts_per_sample):
                    response, reward = self.feedback_rollout(prompt, chosen, rejected)
                    iteration_rewards.append(reward)
                    metrics["total_rollouts"] += 1
                    
                    # Check if aligned with chosen
                    gen_set = set(response.lower().split())
                    chosen_set = set(chosen.lower().split())
                    rejected_set = set(rejected.lower().split())
                    
                    chosen_sim = len(gen_set & chosen_set) / max(len(gen_set), 1)
                    rejected_sim = len(gen_set & rejected_set) / max(len(gen_set), 1)
                    
                    if chosen_sim > rejected_sim:
                        aligned_count += 1
            
            # Compute iteration statistics
            avg_reward = sum(iteration_rewards) / len(iteration_rewards)
            alignment_rate = aligned_count / len(iteration_rewards)
            
            metrics["iteration_rewards"].append(avg_reward)
            metrics["preference_alignment"].append(alignment_rate)
            
            if avg_reward > metrics["best_reward"]:
                metrics["best_reward"] = avg_reward
                self._save_checkpoint(iteration, is_best=True)
            
            logger.info(
                f"Iteration {iteration + 1}/{self.num_iterations} | "
                f"Avg Reward: {avg_reward:.4f} | "
                f"Alignment: {alignment_rate*100:.1f}% | "
                f"Best: {metrics['best_reward']:.4f}"
            )
            
            # Save periodic checkpoint
            if (iteration + 1) % 10 == 0:
                self._save_checkpoint(iteration)
        
        # Save final model
        self._save_checkpoint(self.num_iterations - 1, is_final=True)
        
        # Save training metrics
        metrics_path = Path(self.output_dir) / "feedback_training_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)
        
        logger.info("=" * 60)
        logger.info("Feedback training completed!")
        logger.info(f"Best reward: {metrics['best_reward']:.4f}")
        logger.info(f"Final alignment: {metrics['preference_alignment'][-1]*100:.1f}%")
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
        description="AIPC Feedback Training with Agent Lightning",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to GRPO model checkpoint to continue training",
    )
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to feedback data (JSONL in preference format)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="checkpoints/aipc_grpo_v2",
        help="Output directory for improved model",
    )
    parser.add_argument(
        "--num_iterations",
        type=int,
        default=50,
        help="Number of training iterations",
    )
    parser.add_argument(
        "--rollouts_per_sample",
        type=int,
        default=2,
        help="Number of rollouts per feedback sample",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=5e-6,
        help="Learning rate (lower than initial GRPO)",
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
    logger.info("AIPC Feedback Training (Agent Lightning)")
    logger.info("=" * 60)
    logger.info(f"Model: {args.model}")
    logger.info(f"Feedback data: {args.data}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Iterations: {args.num_iterations}")
    logger.info(f"Learning rate: {args.learning_rate}")
    logger.info("=" * 60)
    
    # Load feedback data
    feedback_data = load_feedback_data(args.data)
    
    if not feedback_data:
        logger.error("No feedback data found. Exiting.")
        sys.exit(1)
    
    # Create trainer
    trainer = FeedbackTrainer(
        model_path=args.model,
        output_dir=args.output,
        learning_rate=args.learning_rate,
        num_iterations=args.num_iterations,
        rollouts_per_sample=args.rollouts_per_sample,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
    )
    
    # Train
    metrics = trainer.train(feedback_data)
    
    logger.info("=" * 60)
    logger.info("Done!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
