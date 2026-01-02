import os
import json
import torch
from dataclasses import dataclass, field
from typing import Optional
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq
)
from datasets import load_dataset

@dataclass
class ModelArguments:
    model_name_or_path: str = field(default="microsoft/Phi-3-mini-4k-instruct")

@dataclass
class DataArguments:
    train_file: str = field(default="data/aipc_sft_train.jsonl")
    val_file: str = field(default="data/aipc_sft_val.jsonl")

@dataclass
class TrainingArguments(TrainingArguments):
    output_dir: str = field(default="checkpoints/aipc_sft")
    num_train_epochs: float = field(default=3.0)
    per_device_train_batch_size: int = field(default=4)
    gradient_accumulation_steps: int = field(default=4)
    learning_rate: float = field(default=2e-5)
    save_steps: int = field(default=100)
    logging_steps: int = field(default=10)
    evaluation_strategy: str = field(default="steps")
    eval_steps: int = field(default=100)
    bf16: bool = field(default=True)

def main():
    parser = HfArgumentParser((ModelArguments, DataArguments, TrainingArguments))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()

    # Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_args.model_name_or_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load Data
    def format_chat(example):
        messages = [
            {"role": "user", "content": example["prompt"]},
            {"role": "assistant", "content": example["completion"]}
        ]
        # Apply chat template
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        return {"text": text}

    dataset = load_dataset("json", data_files={"train": data_args.train_file, "validation": data_args.val_file})
    dataset = dataset.map(format_chat)

    def tokenize_function(examples):
        tokenized = tokenizer(examples["text"], padding="max_length", truncation=True, max_length=2048)
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    tokenized_datasets = dataset.map(tokenize_function, batched=True)

    # Load Model
    model = AutoModelForCausalLM.from_pretrained(
        model_args.model_name_or_path,
        torch_dtype=torch.bfloat16,
        trust_remote_code=False,
        device_map="auto"
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["validation"],
        tokenizer=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, pad_to_multiple_of=8),
    )

    print("🚀 Starting SFT Training...")
    trainer.train()
    trainer.save_model()
    print(f"✅ Training complete. Model saved to {training_args.output_dir}")

if __name__ == "__main__":
    from transformers import HfArgumentParser
    main()
