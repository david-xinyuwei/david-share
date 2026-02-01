#!/usr/bin/env python3
"""
vLLM-Omni Benchmark - NO CFG mode (对齐 diffusers_baseline.py)

Author: Xinyu Wei (魏新宇)
"""

import os
import time
import torch
import gc
from PIL import Image

def main():
    print("="*60)
    print("vLLM-Omni Benchmark - NO CFG")
    print("="*60)

    from vllm_omni.entrypoints.omni import Omni
    import vllm_omni
    print(f"vllm-omni: {vllm_omni.__version__}")
    print(f"Device: {torch.cuda.get_device_name(0)}")

    # Parameters (对齐 diffusers_baseline.py)
    MODEL_ID = "Qwen/Qwen-Image-Edit-2511"
    NUM_STEPS = 40
    SEED = 1

    script_dir = os.path.dirname(os.path.abspath(__file__))
    GARMENT_IMG = os.path.join(script_dir, "../images/garment.jpg")
    MODEL_IMG = os.path.join(script_dir, "../images/model.jpg")
    PROMPT = "让图2中的模特穿上图1中的衣服"

    print(f"Model: {MODEL_ID}")
    print(f"Steps: {NUM_STEPS}, Seed: {SEED}, CFG: DISABLED")
    print("-"*60)

    garment_img = Image.open(GARMENT_IMG).convert("RGB")
    model_img = Image.open(MODEL_IMG).convert("RGB")
    print(f"Garment: {garment_img.size}, Model: {model_img.size}")

    # Load
    print("\nLoading vLLM-Omni...")
    load_start = time.time()
    omni = Omni(model=MODEL_ID, dtype="bfloat16", device="cuda")
    print(f"Loaded in {time.time() - load_start:.1f}s")

    # Warmup
    print("\nWarmup: 2 runs")
    for i in range(2):
        t0 = time.time()
        _ = omni.generate(
            pil_image=[garment_img, model_img],
            prompt=PROMPT,
            num_inference_steps=5,
            seed=SEED,
        )
        print(f"  Warmup {i+1}: {time.time()-t0:.2f}s")

    torch.cuda.synchronize()
    gc.collect()
    torch.cuda.empty_cache()

    # Benchmark
    print("\nBenchmark: 3 runs")
    times = []
    output = None
    for i in range(3):
        torch.cuda.synchronize()
        t0 = time.time()
        output = omni.generate(
            pil_image=[garment_img, model_img],
            prompt=PROMPT,
            num_inference_steps=NUM_STEPS,
            seed=SEED,
        )
        torch.cuda.synchronize()
        elapsed = time.time() - t0
        times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.2f}s")

    # Save - 使用历史验证过的方式
    output_path = os.path.join(script_dir, "../images/output_vllm_omni.png")
    result_img = output[0].request_output[0].images[0]
    result_img.save(output_path)
    print(f"\nSaved: {output_path}")

    # Results
    avg_time = sum(times) / len(times)
    print("\n" + "="*60)
    print(f"RESULT (NO CFG): {avg_time:.2f}s")
    print("="*60)

if __name__ == "__main__":
    main()
