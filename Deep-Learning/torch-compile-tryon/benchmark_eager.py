#!/usr/bin/env python3
"""
Qwen-Image-Edit-2511 Virtual Try-On Benchmark (BF16 Eager Baseline)
Dataset: VITON-HD (CC BY-NC 4.0)

This script measures inference time without torch.compile optimization.

Author: Xinyu Wei (魏新宇)
"""
import torch
import time
import argparse
import json
from PIL import Image
from diffusers import QwenImageEditPlusPipeline

# VITON-HD standard config
CONFIG = {
    "model_id": "Qwen/Qwen-Image-Edit-2511",
    "input_resolution": (768, 1024),   # VITON-HD standard
    "output_resolution": (768, 1024),  # Keep aspect ratio
    "num_inference_steps": 40,
    "guidance_scale": 1.0,
}


def parse_args():
    parser = argparse.ArgumentParser(description="BF16 Eager Baseline Benchmark")
    parser.add_argument(
        "--model_path",
        type=str,
        default=CONFIG["model_id"],
        help="Path or HuggingFace ID of the model",
    )
    parser.add_argument(
        "--model_image",
        type=str,
        required=True,
        help="Path to model/person image",
    )
    parser.add_argument(
        "--garment_image",
        type=str,
        required=True,
        help="Path to garment image",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./outputs",
        help="Output directory for results",
    )
    parser.add_argument(
        "--num_inference_steps",
        type=int,
        default=CONFIG["num_inference_steps"],
        help="Number of inference steps (default: 40)",
    )
    parser.add_argument(
        "--warmup_runs",
        type=int,
        default=1,
        help="Number of warmup runs (default: 1)",
    )
    parser.add_argument(
        "--num_runs",
        type=int,
        default=3,
        help="Number of benchmark runs (default: 3)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    input_res = CONFIG["input_resolution"]
    output_res = CONFIG["output_resolution"]
    cfg = CONFIG["guidance_scale"]

    print("=" * 60)
    print("Qwen-Image-Edit-2511 Virtual Try-On Benchmark")
    print("Mode: BF16 Eager (Baseline)")
    print("Dataset: VITON-HD (768x1024)")
    print("=" * 60)
    device_name = torch.cuda.get_device_name(0)
    print(f"Device: {device_name}")
    print(f"Model: {args.model_path}")
    print(f"Input Resolution: {input_res}")
    print(f"Output Resolution: {output_res}")
    print(f"Steps: {args.num_inference_steps}, CFG: {cfg}, Precision: BF16")
    print(f"Warmup: {args.warmup_runs}, Runs: {args.num_runs}")
    print("-" * 60)

    # Load images
    print("Loading images...")
    model_img = Image.open(args.model_image).convert("RGB")
    garment_img = Image.open(args.garment_image).convert("RGB")
    print(f"  Model: {model_img.size}, Garment: {garment_img.size}")

    # Resize if needed
    if model_img.size != input_res:
        model_img = model_img.resize(input_res, Image.LANCZOS)
    if garment_img.size != input_res:
        garment_img = garment_img.resize(input_res, Image.LANCZOS)
    print(f"  After resize: Model {model_img.size}, Garment {garment_img.size}")

    # Load pipeline
    print("Loading pipeline (BF16)...")
    t0 = time.time()
    pipe = QwenImageEditPlusPipeline.from_pretrained(
        args.model_path, torch_dtype=torch.bfloat16
    ).to("cuda")
    load_time = time.time() - t0
    print(f"  Pipeline loaded in {load_time:.2f}s")

    prompt = "Change the clothes on the person in the first image to the clothes in the second image"

    # Warmup
    print(f"Warmup ({args.warmup_runs} runs)...")
    for i in range(args.warmup_runs):
        _ = pipe(
            prompt=prompt,
            image=[model_img, garment_img],
            height=output_res[1],
            width=output_res[0],
            num_inference_steps=args.num_inference_steps,
            guidance_scale=cfg,
        ).images[0]
        print(f"  Warmup {i+1}/{args.warmup_runs} done")

    # Benchmark
    print(f"Benchmark ({args.num_runs} runs)...")
    times = []
    output = None
    for i in range(args.num_runs):
        torch.cuda.synchronize()
        t0 = time.time()
        output = pipe(
            prompt=prompt,
            image=[model_img, garment_img],
            height=output_res[1],
            width=output_res[0],
            num_inference_steps=args.num_inference_steps,
            guidance_scale=cfg,
        ).images[0]
        torch.cuda.synchronize()
        elapsed = time.time() - t0
        times.append(elapsed)
        step_time = elapsed / args.num_inference_steps
        print(f"  Run {i+1}/{args.num_runs}: {elapsed:.2f}s ({step_time:.4f}s/step)")

    # Results
    avg_time = sum(times) / len(times)
    time_per_step = avg_time / args.num_inference_steps

    print("=" * 60)
    print("Results (BF16 Eager)")
    print("=" * 60)
    print(f"  Average Time: {avg_time:.2f}s")
    print(f"  Time/Step: {time_per_step:.4f}s")
    print(f"  All runs: {[round(t, 2) for t in times]}")
    print("=" * 60)

    # Save output
    import os
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, "output_bf16_eager.png")
    output.save(output_path)
    print(f"Output saved: {output_path}")

    # Save results JSON
    results = {
        "mode": "bf16_eager",
        "device": device_name,
        "model": args.model_path,
        "input_resolution": list(input_res),
        "output_resolution": list(output_res),
        "steps": args.num_inference_steps,
        "cfg": cfg,
        "warmup": args.warmup_runs,
        "runs": args.num_runs,
        "times": times,
        "avg_time": avg_time,
        "time_per_step": time_per_step,
    }
    results_path = os.path.join(args.output_dir, "results_bf16_eager.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved: {results_path}")


if __name__ == "__main__":
    main()
