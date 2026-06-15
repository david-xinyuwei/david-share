#!/usr/bin/env python3
"""
OPD verification experiment based on the thunlp/OPD paper.

This script preserves the early GSM8K verification path documented in the
appendix. Heavy ML dependencies are imported only after argparse runs, so
`python scripts/run_opd.py --help` works in a clean documentation environment.
"""
import argparse
import json
import os
import time
from datetime import datetime


DEFAULT_STUDENT_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
DEFAULT_TEACHER_ID = "hbx/JustRL-DeepSeek-1.5B"


def parse_args():
    parser = argparse.ArgumentParser(description="Run the early single-GPU OPD verification experiment on GSM8K.")
    parser.add_argument("--student-id", default=DEFAULT_STUDENT_ID, help="HuggingFace student model id")
    parser.add_argument("--teacher-id", default=DEFAULT_TEACHER_ID, help="HuggingFace teacher model id")
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "./output"), help="Directory for checkpoints and results")
    parser.add_argument("--train-split", default="train[:500]", help="GSM8K training split")
    parser.add_argument("--eval-split", default="test[:20]", help="GSM8K evaluation split")
    parser.add_argument("--learning-rate", type=float, default=1e-6, help="OPD learning rate")
    parser.add_argument("--epochs", type=int, default=1, help="Number of training epochs")
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8, help="Gradient accumulation steps")
    parser.add_argument("--max-length", type=int, default=1024, help="Maximum sequence length")
    parser.add_argument("--max-new-tokens", type=int, default=512, help="Maximum rollout/evaluation tokens")
    return parser.parse_args()


def extract_answer(text):
    """Extract the numerical answer from GSM8K #### format."""
    lines = text.strip().split('\n')
    for line in reversed(lines):
        if '####' in line:
            return line.split('####')[-1].strip()
    return None


def format_for_gkd(example):
    return {
        "messages": [
            {"role": "user", "content": example["question"]},
            {"role": "assistant", "content": example["answer"]},
        ]
    }


def main():
    args = parse_args()

    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl.experimental.gkd import GKDConfig, GKDTrainer

    print(f"[{datetime.now()}] Phase 0: Environment check")
    print(f"  torch={torch.__version__}, cuda={torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this OPD training script.")
    print(f"  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    print(f"\n[{datetime.now()}] Phase 1: Downloading models...")
    os.makedirs(args.output_dir, exist_ok=True)
    print(f"  Student: {args.student_id}")
    print(f"  Teacher: {args.teacher_id}")

    tokenizer = AutoTokenizer.from_pretrained(args.student_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"\n[{datetime.now()}] Loading student model...")
    student = AutoModelForCausalLM.from_pretrained(
        args.student_id, dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
    )
    student_params = sum(param.numel() for param in student.parameters()) / 1e9
    print(f"  Student params: {student_params:.2f}B")
    print(f"  VRAM after student: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

    print(f"\n[{datetime.now()}] Loading teacher model...")
    teacher = AutoModelForCausalLM.from_pretrained(
        args.teacher_id, dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
    )
    teacher_params = sum(param.numel() for param in teacher.parameters()) / 1e9
    print(f"  Teacher params: {teacher_params:.2f}B")
    print(f"  VRAM after both: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

    del student, teacher
    torch.cuda.empty_cache()

    print(f"\n[{datetime.now()}] Phase 2: Preparing dataset...")
    dataset = load_dataset("openai/gsm8k", "main", split=args.train_split)
    print(f"  Dataset size: {len(dataset)} samples")
    print(f"  Sample: {dataset[0]['question'][:100]}...")

    dataset = dataset.map(format_for_gkd, remove_columns=dataset.column_names)
    print("  Formatted dataset ready")

    print(f"\n[{datetime.now()}] Phase 3: Starting OPD training...")
    print("  This may take 30-60 minutes...")

    config = GKDConfig(
        lmbda=1.0,
        beta=1.0,
        temperature=1.0,
        max_new_tokens=args.max_new_tokens,
        output_dir=f"{args.output_dir}/opd",
        learning_rate=args.learning_rate,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        num_train_epochs=args.epochs,
        logging_steps=5,
        save_steps=100,
        save_total_limit=2,
        bf16=True,
        gradient_checkpointing=True,
        max_length=args.max_length,
        report_to="none",
        remove_unused_columns=False,
    )

    print(f"  Config: lmbda={config.lmbda}, beta={config.beta}")
    trainer = GKDTrainer(
        model=args.student_id,
        teacher_model=args.teacher_id,
        args=config,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    trainer.model.generation_config.top_k = 50
    trainer.model.generation_config.top_p = 0.95
    trainer.model.generation_config.do_sample = True
    print("  Generation config patched: top_k=50, top_p=0.95")

    start_time = time.time()
    trainer.train()
    train_time = time.time() - start_time
    print(f"\n[{datetime.now()}] OPD training complete in {train_time / 60:.1f} minutes")

    final_model_dir = f"{args.output_dir}/opd/final"
    trainer.save_model(final_model_dir)
    print(f"  Model saved to {final_model_dir}")

    print(f"\n[{datetime.now()}] Phase 4: Quick evaluation on {args.eval_split}...")
    eval_dataset = load_dataset("openai/gsm8k", "main", split=args.eval_split)
    opd_model = AutoModelForCausalLM.from_pretrained(
        final_model_dir, dtype=torch.bfloat16, device_map="auto"
    )

    correct = 0
    total = 0
    for example in eval_dataset:
        prompt = f"<|im_start|>user\n{example['question']}<|im_end|>\n<|im_start|>assistant\n"
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            outputs = opd_model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

        pred_answer = extract_answer(response)
        gold_answer = extract_answer(example['answer'])
        if pred_answer and gold_answer and pred_answer.strip() == gold_answer.strip():
            correct += 1
        total += 1

    accuracy = correct / total * 100
    print(f"  OPD model accuracy: {correct}/{total} = {accuracy:.1f}%")

    results = {
        "experiment": "OPD_verification",
        "student": args.student_id,
        "teacher": args.teacher_id,
        "dataset": f"gsm8k_{args.train_split}",
        "eval_dataset": f"gsm8k_{args.eval_split}",
        "opd_config": {"lmbda": 1.0, "beta": 1.0, "lr": args.learning_rate},
        "training_time_minutes": train_time / 60,
        "opd_accuracy": accuracy,
        "timestamp": datetime.now().isoformat(),
    }

    results_path = f"{args.output_dir}/results.json"
    with open(results_path, "w", encoding="utf-8") as results_file:
        json.dump(results, results_file, indent=2)
    print(f"\n[{datetime.now()}] Results saved to {results_path}")
    print("Done!")


if __name__ == "__main__":
    main()