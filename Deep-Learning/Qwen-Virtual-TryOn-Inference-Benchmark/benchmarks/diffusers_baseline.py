#!/usr/bin/env python3
"""
Baseline benchmark using diffusers - NO CFG mode.
Pure inference without Classifier-Free Guidance.

Note: Qwen-Image-Edit-2511 is NOT guidance-distilled, so guidance_scale is ignored.
      This is the fastest mode (single forward pass).

Author: Xinyu Wei (魏新宇)
"""

import os
import time
import warnings
import torch
from PIL import Image
from diffusers import QwenImageEditPlusPipeline

# Suppress the cfg warning since we intentionally skip CFG
warnings.filterwarnings("ignore", message=".*cfg_scale.*")
warnings.filterwarnings("ignore", message=".*guidance.*")

# Configuration
MODEL_PATH = "Qwen/Qwen-Image-Edit-2511"
STEPS = 40
SEED = 1
WARMUP_RUNS = 2
TIMED_RUNS = 3


def run_benchmark():
    print("=" * 60)
    print("Qwen Virtual Try-On Benchmark - diffusers Baseline")
    print("Mode: NO CFG (fastest, single forward pass)")
    print("=" * 60)
    print(f"Device: cuda ({torch.cuda.get_device_name()})")
    print(f"Model: {MODEL_PATH}")
    print(f"Steps: {STEPS}, Seed: {SEED}")
    print("-" * 60)

    # Load pipeline
    print("Loading pipeline...")
    pipe = QwenImageEditPlusPipeline.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    print("Pipeline loaded.")

    # Load images
    script_dir = os.path.dirname(os.path.abspath(__file__))
    garment_img = Image.open(os.path.join(script_dir, "../images/garment.jpg")).convert("RGB")
    model_img = Image.open(os.path.join(script_dir, "../images/model.jpg")).convert("RGB")
    print(f"Garment: {garment_img.size}, Model: {model_img.size}")
    
    prompt = "让图2中的模特穿上图1中的衣服"

    # Warm-up
    print(f"\nWarm-up: {WARMUP_RUNS} runs")
    for i in range(WARMUP_RUNS):
        with torch.no_grad():
            _ = pipe(
                prompt=prompt,
                image=[garment_img, model_img],
                num_inference_steps=5,
                generator=torch.Generator("cuda").manual_seed(SEED),
            )
        torch.cuda.synchronize()
        print(f"  Warm-up {i+1}/{WARMUP_RUNS} done")

    # Timed runs
    print(f"\nBenchmark: {TIMED_RUNS} runs")
    times = []
    result = None
    
    for i in range(TIMED_RUNS):
        torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.no_grad():
            result = pipe(
                prompt=prompt,
                image=[garment_img, model_img],
                num_inference_steps=STEPS,
                generator=torch.Generator("cuda").manual_seed(SEED),
            )
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  Run {i+1}/{TIMED_RUNS}: {elapsed:.2f}s")

    # Results
    avg_time = sum(times) / len(times)
    print("\n" + "=" * 60)
    print(f"RESULT (NO CFG): {avg_time:.2f}s")
    print("=" * 60)

    # Save
    output_path = os.path.join(script_dir, "../images/output_baseline.png")
    result.images[0].save(output_path)
    print(f"✅ Saved: {output_path}")


if __name__ == "__main__":
    run_benchmark()
