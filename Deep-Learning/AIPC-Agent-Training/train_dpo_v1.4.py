import os
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import DPOTrainer

# --- Configuration ---
MODEL_NAME = os.getenv("MODEL_PATH", "./checkpoints/aipc_dpo_v1.3")  # Start from V1.3 (IT Pro)
NEW_MODEL_NAME = os.getenv("OUTPUT_PATH", "./checkpoints/aipc_dpo_v1.4")
DATASET_PATH = os.getenv("DATASET_PATH", "./data/aipc_code_feedback_v1.4.jsonl")

# --- Load Dataset ---
print(f"Loading dataset from {DATASET_PATH}...")
dataset = load_dataset("json", data_files=DATASET_PATH, split="train")
print(f"Dataset loaded. Size: {len(dataset)}")

# --- Load Model & Tokenizer ---
print(f"Loading model: {MODEL_NAME}...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.bfloat16,
    device_map="cuda",
    trust_remote_code=False
)
model.config.use_cache = False 

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=False)
tokenizer.pad_token = tokenizer.eos_token

# --- Training Arguments ---
training_args = TrainingArguments(
    output_dir=NEW_MODEL_NAME,
    per_device_train_batch_size=1, # Small batch for stability
    gradient_accumulation_steps=4,
    num_train_epochs=5,            # 5 epochs to learn code patterns
    learning_rate=5e-7,            # Slightly higher than V1.3 to allow learning new syntax
    logging_steps=1,
    save_strategy="no",
    optim="paged_adamw_32bit",
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    bf16=True,
    remove_unused_columns=False,
    run_name="aipc_dpo_v1.4",
    report_to="none"
)

# --- Trainer ---
dpo_trainer = DPOTrainer(
    model=model,
    ref_model=None, # Implicitly uses model as reference
    args=training_args,
    beta=0.1,
    train_dataset=dataset,
    tokenizer=tokenizer,
    max_length=1024, # Longer context for code
    max_prompt_length=512,
)

# --- Train ---
print("Starting V1.4 (Code Specialist) Training...")
dpo_trainer.train()

# --- Save ---
print(f"Saving V1.4 model to {NEW_MODEL_NAME}...")
dpo_trainer.save_model(NEW_MODEL_NAME)
tokenizer.save_pretrained(NEW_MODEL_NAME)
print("Done.")
