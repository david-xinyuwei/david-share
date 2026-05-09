#!/usr/bin/env python3
"""
Evaluate OPD checkpoint vs baseline student on GSM8K test set.

Usage:
    python3 eval_opd.py --checkpoint /path/to/checkpoint --n 100

Args:
    --checkpoint: Path to OPD checkpoint directory
    --n: Number of GSM8K test samples to evaluate (default: 100)
    --output: Path to save results JSON (default: eval_results.json)
"""
import argparse
import json
import math
import re
import torch
from datetime import datetime
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM

STUDENT_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"


def extract_answer(text):
    """Extract numeric answer from GSM8K-style text.

    Handles: '#### 460', '#### 460.', '460,000', '460.0' -> '460'
    """
    if '####' in text:
        ans = text.split('####')[-1].strip().split()[0]
    else:
        nums = re.findall(r'-?\d+\.?\d*', text)
        ans = nums[-1] if nums else None
    if ans is None:
        return None
    ans = ans.rstrip('.,').replace(',', '')
    try:
        f = float(ans)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except (ValueError, TypeError):
        return ans


def wilson_ci(k, n, z=1.96):
    """Wilson 95% confidence interval for binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, (center - margin) * 100),
            min(100.0, (center + margin) * 100))


def eval_model(model_path, label, eval_dataset, tokenizer):
    print(f"\n[{datetime.now()}] Evaluating {label}: {model_path}")
    model = AutoModelForCausalLM.from_pretrained(
        model_path, dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
    )
    model.eval()
    correct = 0
    n = len(eval_dataset)
    for i, ex in enumerate(eval_dataset):
        prompt = (
            f"<|im_start|>user\n{ex['question']}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        resp = tokenizer.decode(
            out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
        )
        pred = extract_answer(resp)
        gold = extract_answer(ex['answer'])
        if pred is not None and gold is not None and pred == gold:
            correct += 1
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{n}] running acc: {correct}/{i+1} "
                  f"= {100*correct/(i+1):.1f}%")
    acc = correct / n * 100
    print(f"  {label} FINAL: {correct}/{n} = {acc:.2f}%")
    del model
    torch.cuda.empty_cache()
    return acc, correct


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True,
                        help="Path to OPD checkpoint directory")
    parser.add_argument("--n", type=int, default=100,
                        help="Number of GSM8K test samples")
    parser.add_argument("--output", default="eval_results.json",
                        help="Output JSON path")
    args = parser.parse_args()

    print(f"[{datetime.now()}] Loading tokenizer from {STUDENT_ID}")
    tokenizer = AutoTokenizer.from_pretrained(STUDENT_ID, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"[{datetime.now()}] Loading GSM8K test[:{args.n}]")
    eval_dataset = load_dataset("openai/gsm8k", "main", split=f"test[:{args.n}]")

    baseline_acc, baseline_correct = eval_model(
        STUDENT_ID, "BASELINE (student before OPD)", eval_dataset, tokenizer
    )
    opd_acc, opd_correct = eval_model(
        args.checkpoint, "OPD checkpoint", eval_dataset, tokenizer
    )

    baseline_ci = wilson_ci(baseline_correct, args.n)
    opd_ci = wilson_ci(opd_correct, args.n)

    results = {
        "experiment": "OPD_eval",
        "student": STUDENT_ID,
        "checkpoint": args.checkpoint,
        "eval_dataset": f"gsm8k_test_{args.n}",
        "decoding": "greedy (do_sample=False)",
        "max_new_tokens": 512,
        "baseline_correct": baseline_correct,
        "baseline_accuracy_pct": round(baseline_acc, 2),
        "baseline_ci_95": [round(baseline_ci[0], 1), round(baseline_ci[1], 1)],
        "opd_correct": opd_correct,
        "opd_accuracy_pct": round(opd_acc, 2),
        "opd_ci_95": [round(opd_ci[0], 1), round(opd_ci[1], 1)],
        "delta_pp": round(opd_acc - baseline_acc, 2),
        "relative_improvement_pct": (
            round((opd_acc - baseline_acc) / baseline_acc * 100, 1)
            if baseline_acc > 0 else None
        ),
        "timestamp": datetime.now().isoformat(),
    }
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[{datetime.now()}] DONE. Results saved to {args.output}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
