import torch
from datasets import load_dataset
from trl import DPOTrainer, DPOConfig
from transformers import AutoModelForCausalLM, AutoTokenizer

def main():
    # Paths
    model_path = "checkpoints/aipc_dpo_v1.2"
    data_path = "data/aipc_feedback_v1.3.jsonl"
    output_dir = "checkpoints/aipc_dpo_v1.3"

    print(f"Loading V1.2 model from {model_path}...")
    
    # Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load Dataset
    print(f"Loading feedback dataset from {data_path}...")
    dataset = load_dataset("json", data_files=data_path, split="train")
    
    # Config
    training_args = DPOConfig(
        output_dir=output_dir,
        beta=0.1,
        learning_rate=1e-7, # Lower LR for incremental training
        per_device_train_batch_size=2, # Smaller batch for stability
        gradient_accumulation_steps=4,
        num_train_epochs=5,
        logging_steps=1,
        save_strategy="no",
        bf16=True,
        remove_unused_columns=False,
        report_to="none",
        max_length=2048,
        max_prompt_length=1024,
    )

    # Model
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        trust_remote_code=False,
        device_map="auto"
    )

    # Trainer
    print("Starting V1.3 Incremental DPO training...")
    trainer = DPOTrainer(
        model=model,
        ref_model=None, # Load a copy of the model as reference
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    # Train
    trainer.train()
    
    # Save
    print(f"Saving V1.3 model to {output_dir}...")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print("Done.")

if __name__ == "__main__":
    main()
