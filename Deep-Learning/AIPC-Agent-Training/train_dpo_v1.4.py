import os
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOTrainer, DPOConfig

MODEL_NAME = "checkpoints/aipc_dpo_v1.3"
NEW_MODEL_NAME = "checkpoints/aipc_dpo_v1.4"
DATASET_PATH = "data/aipc_code_feedback_v1.4.jsonl"

print(f"Loading dataset from {DATASET_PATH}...")
dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
print(f"Dataset size: {len(dataset)}")

print(f"Loading model: {MODEL_NAME}...")
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=torch.bfloat16, device_map="cuda", trust_remote_code=False)
model.config.use_cache = False

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=False)
tokenizer.pad_token = tokenizer.eos_token

training_args = DPOConfig(
    output_dir=NEW_MODEL_NAME,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    num_train_epochs=5,
    learning_rate=5e-7,
    logging_steps=1,
    save_strategy="no",
    optim="paged_adamw_32bit",
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    bf16=True,
    remove_unused_columns=False,
    run_name="aipc_dpo_v1.4",
    report_to="none",
    beta=0.1,
    max_length=1024,
    max_prompt_length=512
)

dpo_trainer = DPOTrainer(
    model=model,
    ref_model=None,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer
)

print("Starting V1.4 Training...")
dpo_trainer.train()

print(f"Saving model to {NEW_MODEL_NAME}...")
dpo_trainer.save_model(NEW_MODEL_NAME)
tokenizer.save_pretrained(NEW_MODEL_NAME)
print("Done.")
