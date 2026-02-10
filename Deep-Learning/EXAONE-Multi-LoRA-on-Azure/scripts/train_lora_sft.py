#!/usr/bin/env python3
"""
EXAONE LoRA Fine-Tuning Script (SFT)
=====================================

Fine-tune EXAONE 3.5 with LoRA using domain-specific data.
Produces a LoRA adapter compatible with vLLM Multi-LoRA serving.

Data format: JSONL with ShareGPT format
    {"conversations": [{"from": "human", "value": "..."}, {"from": "gpt", "value": "..."}]}

Usage:
    python train_lora_sft.py \
        --model /data/EXAONE-3.5-2.4B-Instruct \
        --data data/customer_support_train.jsonl \
        --output /data/exaone-lora-customer-support \
        --lora_r 16 \
        --lora_alpha 32 \
        --num_epochs 3

Author: Xinyu Wei (Xinyu Wei)
"""

import argparse
import json
import logging
import sys
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── EXAONE target module mapping ──────────────────────────────────────────────
# EXAONE uses non-standard names. Map them for LoRA:
#   q_proj, k_proj, v_proj, out_proj (attention)
#   c_fc_0 (gate_proj), c_fc_1 (up_proj), c_proj (down_proj) in FFN
EXAONE_ATTENTION_MODULES = ["q_proj", "k_proj", "v_proj", "out_proj"]
EXAONE_FFN_MODULES = ["c_fc_0", "c_fc_1", "c_proj"]
EXAONE_ALL_MODULES = EXAONE_ATTENTION_MODULES + EXAONE_FFN_MODULES


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_sharegpt_data(data_path: str) -> List[Dict]:
    """Load ShareGPT-format JSONL data."""
    data = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    logger.info(f"Loaded {len(data)} samples from {data_path}")
    return data


def prepare_dataset(
    data_path: str,
    tokenizer,
    max_length: int = 2048,
) -> Dataset:
    """Load, format, and tokenize training data."""
    raw_data = load_sharegpt_data(data_path)

    # Convert ShareGPT format to chat messages
    formatted = []
    for sample in raw_data:
        messages = []
        for conv in sample.get("conversations", []):
            role = "user" if conv["from"] == "human" else "assistant"
            messages.append({"role": role, "content": conv["value"]})
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=False,
        )
        formatted.append({"text": text})

    dataset = Dataset.from_list(formatted)

    def tokenize_fn(examples):
        result = tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_length,
            padding=False,
        )
        result["labels"] = result["input_ids"].copy()
        return result

    tokenized = dataset.map(
        tokenize_fn, batched=True, remove_columns=["text"], desc="Tokenizing",
    )
    logger.info(f"Prepared {len(tokenized)} tokenized samples (max_length={max_length})")
    return tokenized


# ── Model Loading ─────────────────────────────────────────────────────────────

def load_model_with_lora(
    model_name: str,
    lora_r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    target_modules: Optional[List[str]] = None,
):
    """Load EXAONE model and apply LoRA."""
    logger.info(f"Loading model: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True, padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )
    model.gradient_checkpointing_enable()

    # EXAONE get_input_embeddings workaround for PEFT compatibility
    try:
        model.get_input_embeddings()
    except NotImplementedError:
        logger.warning("Patching get_input_embeddings for EXAONE + PEFT compatibility")
        model.get_input_embeddings = lambda: model.transformer.wte

    # Default: all 7 linear layers (attention + FFN)
    if target_modules is None:
        target_modules = EXAONE_ALL_MODULES

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=target_modules,
        bias="none",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    return model, tokenizer


# ── Training ──────────────────────────────────────────────────────────────────

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
    eval_dataset: Optional[Dataset] = None,
) -> None:
    """Run SFT training and save the LoRA adapter."""
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
        report_to="none",
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer=tokenizer, padding=True, return_tensors="pt",
        ),
    )

    logger.info("Starting LoRA SFT training...")
    trainer.train()

    # Save LoRA adapter only (not the full base model)
    logger.info(f"Saving LoRA adapter to {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    logger.info("Training completed!")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Fine-tune EXAONE with LoRA (SFT)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--model", type=str, required=True,
                    help="Base model path (e.g., /data/EXAONE-3.5-2.4B-Instruct)")
    p.add_argument("--data", type=str, required=True,
                    help="Training data in ShareGPT JSONL format")
    p.add_argument("--eval_data", type=str, default=None,
                    help="Optional evaluation data")
    p.add_argument("--output", type=str, required=True,
                    help="Output directory for LoRA adapter")
    p.add_argument("--max_length", type=int, default=2048,
                    help="Maximum sequence length")
    # LoRA hyperparameters
    p.add_argument("--lora_r", type=int, default=16, help="LoRA rank")
    p.add_argument("--lora_alpha", type=int, default=32,
                    help="LoRA alpha (typically 1-2x rank)")
    p.add_argument("--lora_dropout", type=float, default=0.05, help="LoRA dropout")
    p.add_argument("--target_modules", type=str, nargs="+", default=None,
                    help="Target modules for LoRA (default: all 7 EXAONE linear layers)")
    # Training hyperparameters
    p.add_argument("--num_epochs", type=int, default=3)
    p.add_argument("--batch_size", type=int, default=4)
    p.add_argument("--gradient_accumulation_steps", type=int, default=8)
    p.add_argument("--learning_rate", type=float, default=2e-4)
    p.add_argument("--warmup_ratio", type=float, default=0.1)
    p.add_argument("--logging_steps", type=int, default=10)
    p.add_argument("--save_steps", type=int, default=100)
    return p.parse_args()


def main():
    args = parse_args()

    logger.info("=" * 60)
    logger.info("EXAONE LoRA Fine-Tuning (SFT)")
    logger.info("=" * 60)
    logger.info(f"Model:    {args.model}")
    logger.info(f"Data:     {args.data}")
    logger.info(f"Output:   {args.output}")
    logger.info(f"LoRA:     r={args.lora_r}, alpha={args.lora_alpha}")
    logger.info(f"Epochs:   {args.num_epochs}")
    logger.info(f"Eff. BS:  {args.batch_size * args.gradient_accumulation_steps}")
    logger.info("=" * 60)

    model, tokenizer = load_model_with_lora(
        model_name=args.model,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=args.target_modules,
    )

    train_dataset = prepare_dataset(args.data, tokenizer, args.max_length)

    eval_dataset = None
    if args.eval_data:
        eval_dataset = prepare_dataset(args.eval_data, tokenizer, args.max_length)

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
        eval_dataset=eval_dataset,
    )


if __name__ == "__main__":
    main()
