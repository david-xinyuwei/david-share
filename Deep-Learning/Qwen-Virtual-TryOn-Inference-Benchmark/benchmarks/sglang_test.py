#!/usr/bin/env python3
"""
Benchmark using SGLang inference engine.

Author: Xinyu Wei (魏新宇)
"""

import time
import requests
import base64
from io import BytesIO
from PIL import Image

SERVER_URL = "http://localhost:30000"
STEPS = 40
CFG_SCALE = 4.0
SEED = 42
WARMUP_RUNS = 5
TIMED_RUNS = 5

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def run_inference(model_b64, garment_b64):
    payload = {
        "model_image": model_b64,
        "garment_image": garment_b64,
        "prompt": "The person is wearing this garment.",
        "num_inference_steps": STEPS,
        "guidance_scale": CFG_SCALE,
        "seed": SEED,
    }
    response = requests.post(f"{SERVER_URL}/generate", json=payload)
    return response.json()

def run_benchmark():
    print(f"Mode: SGLang")
    print(f"Steps: {STEPS}, CFG: {CFG_SCALE}, Seed: {SEED}")
    print("-" * 50)
    
    model_b64 = encode_image("../images/model_input.jpg")
    garment_b64 = encode_image("../images/garment_input.jpg")
    
    # Warm-up
    print(f"Warm-up: {WARMUP_RUNS} runs")
    for i in range(WARMUP_RUNS):
        _ = run_inference(model_b64, garment_b64)
        print(f"  Warm-up {i+1}/{WARMUP_RUNS} done")
    
    # Timed runs
    print(f"Timing: {TIMED_RUNS} runs")
    times = []
    for i in range(TIMED_RUNS):
        start = time.perf_counter()
        result = run_inference(model_b64, garment_b64)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  Run {i+1}/{TIMED_RUNS}: {elapsed:.2f}s")
    
    avg_time = sum(times) / len(times)
    std_time = (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5
    
    print("-" * 50)
    print(f"Results: {avg_time:.2f}s +/- {std_time:.2f}s")
    
    if "image" in result:
        img_data = base64.b64decode(result["image"])
        img = Image.open(BytesIO(img_data))
        img.save("../images/output_sglang.png")
        print("Saved: ../images/output_sglang.png")

if __name__ == "__main__":
    run_benchmark()
