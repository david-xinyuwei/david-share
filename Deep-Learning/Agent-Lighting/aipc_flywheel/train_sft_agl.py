#!/usr/bin/env python3
"""
AIPC SFT (Supervised Fine-Tuning) Training Script
==================================================

Cold start training to teach model basic AIPC domain knowledge.

Note: SFT uses standard transformers.Trainer, not Agent Lightning,
because SFT doesn't involve reinforcement learning.

Features:
    - LoRA fine-tuning for efficiency
    - DeepSpeed ZeRO-2 support
    - Gradient checkpointing
    - Automatic mixed precision (BF16)

Usage:
    python train_sft_agl.py --data data/aipc_train.jsonl --output checkpoints/aipc_sft_v1

Author: Xinyu Wei (xinyuwei@microsoft.com)
License: MIT
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# =============================================================================
# Data Loading and Processing
# =============================================================================


def load_sharegpt_data(data_path: str) -> List[Dict]:
    """Load data from ShareGPT format JSONL file."""
    data = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    logger.info(f"Loaded {len(data)} samples from {data_path}")
    return data


def format_conversation(sample: Dict, tokenizer) -> Dict:
    """Format ShareGPT conversation for training."""
    conversations = sample.get("conversations", [])
    
    # Build prompt and response
    messages = []
    for conv in conversations:
        role = "user" if conv["from"] == "human" else "assistant"
        messages.append({"role": role, "content": conv["value"]})
    
    # Use chat template
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    
    return {"text": text}


def prepare_dataset(
    data_path: str,
    tokenizer,
    max_length: int = 2048,
) -> Dataset:
    """Prepare dataset for training."""
    raw_data = load_sharegpt_data(data_path)
    
    # Format conversations
    formatted_data = [format_conversation(sample, tokenizer) for sample in raw_data]
    
    # Create HuggingFace Dataset
    dataset = Dataset.from_list(formatted_data)
    
    # Tokenize
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_length,
            padding=False,
        )
    
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=["text"],
        desc="Tokenizing",
    )
    
    # Add labels for causal LM training
    def add_labels(examples):
        examples["labels"] = examples["input_ids"].copy()
        return examples
    
    tokenized_dataset = tokenized_dataset.map(
        add_labels,
        batched=True,
        desc="Adding labels",
    )
    
    logger.info(f"Prepared dataset with {len(tokenized_dataset)} samples")
    return tokenized_dataset


# =============================================================================
# Model Loading
# =============================================================================


def load_model_and_tokenizer(
    model_name: str,
    use_lora: bool = True,
    lora_r: int = 64,
    lora_alpha: int = 128,
    lora_dropout: float = 0.05,
):
    """Load model and tokenizer with optional LoRA."""
    logger.info(f"Loading model: {model_name}")
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        padding_side="right",
    )
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        attn_implementation="flash_attention_2",
        device_map="auto",
    )
    
    # Enable gradient checkpointing
    model.gradient_checkpointing_enable()
    
    # Apply LoRA if requested
    if use_lora:
        logger.info(f"Applying LoRA (r={lora_r}, alpha={lora_alpha})")
        
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            bias="none",
        )
        
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()
    
    return model, tokenizer


# =============================================================================
# Training
# =============================================================================


def train(
    model,
    tokenizer,
    train_dataset: Dataset,
    output_dir: str,
    num_epochs: int = 3,
    batch_size: int = 4,
    gradient_accumulation_steps: int = 8,
    learning_rate: float = 2e-4,
    warmup_ratio: float = 0.1,
    logging_steps: int = 10,
    save_steps: int = 100,
    eval_steps: Optional[int] = None,
    eval_dataset: Optional[Dataset] = None,
    deepspeed_config: Optional[str] = None,
) -> None:
    """Run SFT training."""
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        weight_decay=0.01,
        logging_steps=logging_steps,
        save_steps=save_steps,
        save_total_limit=3,
        bf16=True,
        gradient_checkpointing=True,
        optim="adamw_torch",
        lr_scheduler_type="cosine",
        report_to=["tensorboard"],
        logging_dir=f"{output_dir}/logs",
        remove_unused_columns=False,
        deepspeed=deepspeed_config,
    )
    
    if eval_dataset is not None and eval_steps is not None:
        training_args.evaluation_strategy = "steps"
        training_args.eval_steps = eval_steps
    
    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        return_tensors="pt",
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )
    
    # Train
    logger.info("Starting SFT training...")
    trainer.train()
    
    # Save final model
    logger.info(f"Saving final model to {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    logger.info("✅ SFT training completed!")


# =============================================================================
# Main Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AIPC SFT Training Script",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    # Data arguments
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to training data (JSONL in ShareGPT format)",
    )
    parser.add_argument(
        "--eval_data",
        type=str,
        default=None,
        help="Path to evaluation data (optional)",
    )
    
    # Model arguments
    parser.add_argument(
        "--model",
        type=str,
        default="Qwen/Qwen2.5-3B-Instruct",
        help="Base model name or path",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="checkpoints/aipc_sft_v1",
        help="Output directory for trained model",
    )
    parser.add_argument(
        "--max_length",
        type=int,
        default=2048,
        help="Maximum sequence length",
    )
    
    # LoRA arguments
    parser.add_argument(
        "--use_lora",
        action="store_true",
        default=True,
        help="Use LoRA fine-tuning",
    )
    parser.add_argument(
        "--no_lora",
        action="store_true",
        help="Disable LoRA (full fine-tuning)",
    )
    parser.add_argument(
        "--lora_r",
        type=int,
        default=64,
        help="LoRA rank",
    )
    parser.add_argument(
        "--lora_alpha",
        type=int,
        default=128,
        help="LoRA alpha",
    )
    parser.add_argument(
        "--lora_dropout",
        type=float,
        default=0.05,
        help="LoRA dropout",
    )
    
    # Training arguments
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=3,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=4,
        help="Per-device batch size",
    )
    parser.add_argument(
        "--gradient_accumulation_steps",
        type=int,
        default=8,
        help="Gradient accumulation steps",
    )
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=2e-4,
        help="Learning rate",
    )
    parser.add_argument(
        "--warmup_ratio",
        type=float,
        default=0.1,
        help="Warmup ratio",
    )
    parser.add_argument(
        "--logging_steps",
        type=int,
        default=10,
        help="Logging interval (steps)",
    )
    parser.add_argument(
        "--save_steps",
        type=int,
        default=100,
        help="Checkpoint save interval (steps)",
    )
    parser.add_argument(
        "--eval_steps",
        type=int,
        default=None,
        help="Evaluation interval (steps)",
    )
    
    # DeepSpeed
    parser.add_argument(
        "--deepspeed",
        type=str,
        default=None,
        help="DeepSpeed config file path",
    )
    
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    # Handle LoRA flag
    use_lora = args.use_lora and not args.no_lora
    
    logger.info("=" * 60)
    logger.info("AIPC SFT Training")
    logger.info("=" * 60)
    logger.info(f"Model: {args.model}")
    logger.info(f"Data: {args.data}")
    logger.info(f"Output: {args.output}")
    logger.info(f"LoRA: {use_lora}")
    logger.info(f"Epochs: {args.num_epochs}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Gradient accumulation: {args.gradient_accumulation_steps}")
    logger.info(f"Effective batch size: {args.batch_size * args.gradient_accumulation_steps}")
    logger.info("=" * 60)
    
    # Load model and tokenizer
    model, tokenizer = load_model_and_tokenizer(
        model_name=args.model,
        use_lora=use_lora,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
    )
    
    # Prepare datasets
    train_dataset = prepare_dataset(args.data, tokenizer, args.max_length)
    
    eval_dataset = None
    if args.eval_data:
        eval_dataset = prepare_dataset(args.eval_data, tokenizer, args.max_length)
    
    # Train
    train(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        output_dir=args.output,
        num_epochs=args.num_epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=args.warmup_ratio,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        eval_steps=args.eval_steps,
        eval_dataset=eval_dataset,
        deepspeed_config=args.deepspeed,
    )
    
    logger.info("=" * 60)
    logger.info("Done!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
