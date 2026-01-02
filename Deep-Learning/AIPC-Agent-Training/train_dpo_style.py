import torch
from datasets import load_dataset
from trl import DPOTrainer, DPOConfig
from transformers import AutoModelForCausalLM, AutoTokenizer

def main():
    # Paths
    model_path = "checkpoints/aipc_grpo_v1.1_final"
    data_path = "data/aipc_style_dpo.jsonl"
    output_dir = "checkpoints/aipc_dpo_v1.2"

    print(f"Loading model from {model_path}...")
    
    # Load Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Load Dataset
    print(f"Loading dataset from {data_path}...")
    dataset = load_dataset("json", data_files=data_path, split="train")
    
    # Config
    training_args = DPOConfig(
        output_dir=output_dir,
        beta=0.1,
        learning_rate=5e-7,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=2,
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
    print("Starting DPO training...")
    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    # Train
    trainer.train()
    
    # Save
    print(f"Saving model to {output_dir}...")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print("Done.")

if __name__ == "__main__":
    main()
