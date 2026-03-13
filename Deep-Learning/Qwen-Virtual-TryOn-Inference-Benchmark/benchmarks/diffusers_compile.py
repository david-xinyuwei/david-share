#!/usr/bin/env python3
"""
Benchmark using diffusers with torch.compile optimization.
Uses mode="default" to avoid NaN bug with dynamic=None.

Author: Xinyu Wei (魏新宇)
"""

import os
import time
import torch
from PIL import Image
from diffusers import FluxFillPipeline

MODEL_PATH = "Qwen/Qwen-Image-Edit-2511"
STEPS = 40
CFG_SCALE = 4.0
SEED = 42
WARMUP_RUNS = 5
TIMED_RUNS = 5

def load_test_images():
    model_img = Image.open("../images/model_input.jpg")
    garment_img = Image.open("../images/garment_input.jpg")
    return model_img, garment_img

def run_benchmark():
    print(f"Device: cuda ({torch.cuda.get_device_name()})")
    print(f"Model: {MODEL_PATH}")
    print(f"Compile mode: default (dynamic=None)")
    print("-" * 50)
    
    # Load and compile pipeline
    print("Loading pipeline...")
    pipe = FluxFillPipeline.from_pretrained(
        MODEL_PATH,
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    
    # Compile transformer (mode=default to avoid NaN)
    print("Compiling transformer...")
    pipe.transformer = torch.compile(
        pipe.transformer,
        mode="default",
        dynamic=None,  # Critical: avoid reduce-overhead NaN bug
    )
    
    model_img, garment_img = load_test_images()
    prompt = "The person is wearing this garment."
    
    # Warm-up (includes compilation)
    print(f"Warm-up: {WARMUP_RUNS} runs (includes JIT compilation)")
    for i in range(WARMUP_RUNS):
        generator = torch.Generator("cuda").manual_seed(SEED)
        _ = pipe(
            image=model_img,
            mask_image=garment_img,
            prompt=prompt,
            num_inference_steps=STEPS,
            guidance_scale=CFG_SCALE,
            generator=generator,
        ).images[0]
        print(f"  Warm-up {i+1}/{WARMUP_RUNS} done")
    
    # Timed runs
    print(f"Timing: {TIMED_RUNS} runs")
    times = []
    for i in range(TIMED_RUNS):
        generator = torch.Generator("cuda").manual_seed(SEED)
        torch.cuda.synchronize()
        start = time.perf_counter()
        
        result = pipe(
            image=model_img,
            mask_image=garment_img,
            prompt=prompt,
            num_inference_steps=STEPS,
            guidance_scale=CFG_SCALE,
            generator=generator,
        ).images[0]
        
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  Run {i+1}/{TIMED_RUNS}: {elapsed:.2f}s")
    
    avg_time = sum(times) / len(times)
    std_time = (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5
    
    print("-" * 50)
    print(f"Results: {avg_time:.2f}s +/- {std_time:.2f}s")
    
    result.save("../images/output_compile.png")
    print("Saved: ../images/output_compile.png")

if __name__ == "__main__":
    run_benchmark()
