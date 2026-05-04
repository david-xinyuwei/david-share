#!/usr/bin/env python3
"""CoDeC Contamination Detection Experiment
Validates the CoDeC method on H100 with multiple models and benchmarks.
Outputs JSON results for README integration.
"""
import json
import time
import random
import argparse
import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset


def get_logprobs(model, tokenizer, text, device, max_length=2048):
    """Get per-token log probabilities for a text."""
    with torch.no_grad():
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length).to(device)
        outputs = model(**inputs)
        log_probs = torch.log_softmax(outputs.logits, dim=-1)
        input_ids = inputs["input_ids"][0]
        return np.array([
            log_probs[0, i, input_ids[i + 1]].item()
            for i in range(len(input_ids) - 1)
        ])


def codec_score(model, tokenizer, dataset, device, num_context=1, skip_tokens=10, max_samples=200):
    """Compute CoDeC contamination score for a dataset."""
    random.seed(42)
    np.random.seed(42)

    if len(dataset) > max_samples:
        dataset = random.sample(dataset, max_samples)

    scores = []
    for i, target in enumerate(dataset):
        # Baseline: target only
        lp_baseline = get_logprobs(model, tokenizer, target, device)
        if len(lp_baseline) <= skip_tokens + 1:
            continue

        # With context
        candidates = dataset[:i] + dataset[i+1:]
        if not candidates:
            continue
        ctx = random.choice(candidates)
        text_with_ctx = ctx + "\n\n" + target
        lp_context = get_logprobs(model, tokenizer, text_with_ctx, device)

        # Compare
        baseline_conf = np.mean(lp_baseline[skip_tokens:])
        context_conf = np.mean(lp_context[-len(lp_baseline):][skip_tokens:])

        scores.append(1.0 if baseline_conf > context_conf else 0.0)

        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(dataset)}] running score: {np.mean(scores):.1%}")

    return np.mean(scores), len(scores)


def load_benchmark(name):
    """Load benchmark dataset, return list of strings."""
    if name == "gsm8k":
        ds = load_dataset("openai/gsm8k", "main", split="test")
        return ds["question"]
    elif name == "gpqa":
        # GPQA is gated, use MMLU-Pro subset as alternative
        ds = load_dataset("TIGER-Lab/MMLU-Pro", split="test[:500]")
        return ds["question"]
    elif name == "mmlu_pro":
        ds = load_dataset("TIGER-Lab/MMLU-Pro", split="test[:500]")
        return ds["question"]
    elif name == "wikipedia":
        # Positive control: wikitext is known training data for virtually all LLMs
        ds = load_dataset("Salesforce/wikitext", "wikitext-103-raw-v1", split="test")
        # Filter out short/empty entries
        return [text for text in ds["text"] if len(text) > 200]
    elif name == "humaneval":
        ds = load_dataset("openai/openai_humaneval", split="test")
        return ds["prompt"]
    elif name == "aime":
        ds = load_dataset("AI-MO/aimo-validation-aime", trust_remote_code=True, split="train")
        return [row for row in ds["problem"]]
    else:
        raise ValueError(f"Unknown benchmark: {name}")


def main():
    parser = argparse.ArgumentParser(description="CoDeC Contamination Detection Experiment")
    parser.add_argument("--models", nargs="+", default=[
        "Qwen/Qwen2.5-3B-Instruct",
        "google/gemma-3-4b-it",
    ])
    parser.add_argument("--benchmarks", nargs="+", default=["gsm8k", "mmlu_pro"])
    parser.add_argument("--max-samples", type=int, default=200)
    parser.add_argument("--output", type=str, default="/root/codec_results.json")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name()}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    all_results = []

    for model_name in args.models:
        print(f"\n{'='*60}")
        print(f"Loading model: {model_name}")
        t0 = time.time()
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
        ).to(device)
        model.eval()
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        load_time = time.time() - t0
        print(f"Model loaded in {load_time:.1f}s")

        param_count = sum(p.numel() for p in model.parameters()) / 1e9
        print(f"Parameters: {param_count:.1f}B")

        for bench_name in args.benchmarks:
            print(f"\n  Benchmark: {bench_name}")
            t1 = time.time()
            dataset = load_benchmark(bench_name)
            print(f"  Dataset size: {len(dataset)} samples")

            score, n_samples = codec_score(
                model, tokenizer, dataset, device,
                max_samples=args.max_samples,
            )
            elapsed = time.time() - t1

            result = {
                "model": model_name,
                "benchmark": bench_name,
                "codec_score": round(score, 4),
                "n_samples": n_samples,
                "time_seconds": round(elapsed, 1),
                "gpu": torch.cuda.get_device_name() if device == "cuda" else "cpu",
                "params_b": round(param_count, 1),
            }
            all_results.append(result)
            print(f"  CoDeC Score: {score:.1%} ({n_samples} samples, {elapsed:.1f}s)")

        # Free GPU memory
        del model, tokenizer
        torch.cuda.empty_cache()

    # Save results
    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {args.output}")
    print(json.dumps(all_results, indent=2))


if __name__ == "__main__":
    main()
