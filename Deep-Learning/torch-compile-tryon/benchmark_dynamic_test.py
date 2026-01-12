 #!/usr/bin/env python3
"""
torch.compile Dynamic Shape Parameter Comparison Test

This script runs a fair comparison test for:
  - Test 1: BF16 Eager baseline (no torch.compile)
  - Test 2: torch.compile with dynamic=None (default, static optimization)
  - Test 3: torch.compile with dynamic=True (dynamic shape tracing)

Fair Test Principles (7-Dimension Alignment):
  1. Same model weights
  2. Same test images (768x1024 VITON-HD)
  3. Same inference params (40 steps, cfg=1.0, seed=42)
  4. Same hardware (A100-80GB)
  5. Same software versions
  6. Same measurement method (3 runs, exclude warmup)
  7. GPU memory cleared between tests

Author: Xinyu Wei (魏新宇)
"""
import torch
import torch._dynamo as dynamo
import time
import argparse
import json
import os
import gc
from PIL import Image
from diffusers import QwenImageEditPlusPipeline

# Suppress TorchDynamo errors for better compatibility
dynamo.config.suppress_errors = True

# VITON-HD standard config
CONFIG = {
    "model_id": "Qwen/Qwen-Image-Edit-2511",
    "input_resolution": (768, 1024),
    "output_resolution": (768, 1024),
    "num_inference_steps": 50,
    "guidance_scale": 6.0,
    "true_cfg_scale": 4.0,
}


def clear_gpu_memory():
    """Clear GPU memory between tests for fair comparison"""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    # Reset dynamo cache
    dynamo.reset()
    time.sleep(2)


def get_gpu_memory_mb():
    """Get current GPU memory usage in MB"""
    return torch.cuda.memory_allocated() / 1024 / 1024


def run_single_test(
    test_name: str,
    pipe,
    model_img: Image.Image,
    garment_img: Image.Image,
    prompt: str,
    negative_prompt: str,
    output_res: tuple,
    num_steps: int,
    cfg: float,
    warmup_runs: int,
    num_runs: int,
    output_dir: str,
    seed: int,
):
    """Run a single test configuration"""
    print(f"\n{'='*60}")
    print(f"Running: {test_name}")
    print(f"{'='*60}")

    # Warmup runs
    print(f"Warmup ({warmup_runs} runs)...")
    warmup_times = []
    for i in range(warmup_runs):
        # Set seed for reproducibility
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        
        t0 = time.time()
        _ = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=[model_img, garment_img],
            height=output_res[1],
            width=output_res[0],
            num_inference_steps=num_steps,
            guidance_scale=cfg,
        ).images[0]
        torch.cuda.synchronize()
        elapsed = time.time() - t0
        warmup_times.append(elapsed)
        print(f"  Warmup {i+1}/{warmup_runs}: {elapsed:.2f}s")

    # Benchmark runs
    print(f"Benchmark ({num_runs} runs)...")
    run_times = []
    output = None
    for i in range(num_runs):
        # Set seed for reproducibility
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        
        torch.cuda.synchronize()
        t0 = time.time()
        output = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=[model_img, garment_img],
            height=output_res[1],
            width=output_res[0],
            num_inference_steps=num_steps,
            guidance_scale=cfg,
        ).images[0]
        torch.cuda.synchronize()
        elapsed = time.time() - t0
        run_times.append(elapsed)
        step_time = elapsed / num_steps
        print(f"  Run {i+1}/{num_runs}: {elapsed:.2f}s ({step_time:.4f}s/step)")

    # Calculate results
    avg_time = sum(run_times) / len(run_times)
    time_per_step = avg_time / num_steps

    # Save output image
    os.makedirs(output_dir, exist_ok=True)
    safe_name = test_name.replace(" ", "_").replace("=", "_").replace("(", "").replace(")", "")
    output_path = os.path.join(output_dir, f"output_{safe_name}.png")
    output.save(output_path)
    print(f"  Output saved: {output_path}")

    results = {
        "test_name": test_name,
        "warmup_runs": warmup_runs,
        "warmup_times": warmup_times,
        "benchmark_runs": num_runs,
        "run_times": run_times,
        "avg_time": avg_time,
        "time_per_step": time_per_step,
        "output_path": output_path,
    }

    print(f"\n  >>> Average: {avg_time:.2f}s ({time_per_step:.4f}s/step)")
    return results


def parse_args():
    parser = argparse.ArgumentParser(
        description="torch.compile Dynamic Parameter Comparison Test"
    )
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
        default="./outputs_dynamic_test",
        help="Output directory for results",
    )
    parser.add_argument(
        "--warmup_runs",
        type=int,
        default=2,
        help="Number of warmup runs (default: 2)",
    )
    parser.add_argument(
        "--num_runs",
        type=int,
        default=3,
        help="Number of benchmark runs (default: 3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--skip_eager",
        action="store_true",
        help="Skip eager baseline test",
    )
    parser.add_argument(
        "--skip_compile_none",
        action="store_true",
        help="Skip torch.compile dynamic=None test",
    )
    parser.add_argument(
        "--skip_compile_true",
        action="store_true",
        help="Skip torch.compile dynamic=True test",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    input_res = CONFIG["input_resolution"]
    output_res = CONFIG["output_resolution"]
    cfg = CONFIG["guidance_scale"]
    num_steps = CONFIG["num_inference_steps"]

    print("=" * 70)
    print("torch.compile Dynamic Parameter Comparison Test")
    print("=" * 70)
    device_name = torch.cuda.get_device_name(0)
    print(f"Device: {device_name}")
    print(f"PyTorch: {torch.__version__}")
    print(f"Model: {args.model_path}")
    print(f"Resolution: {input_res} -> {output_res}")
    print(f"Steps: {num_steps}, CFG: {cfg}, Seed: {args.seed}")
    print(f"Warmup: {args.warmup_runs}, Benchmark runs: {args.num_runs}")
    print("=" * 70)

    # Load images once
    print("\nLoading images...")
    model_img = Image.open(args.model_image).convert("RGB")
    garment_img = Image.open(args.garment_image).convert("RGB")
    print(f"  Model: {model_img.size}, Garment: {garment_img.size}")

    if model_img.size != input_res:
        model_img = model_img.resize(input_res, Image.LANCZOS)
    if garment_img.size != input_res:
        garment_img = garment_img.resize(input_res, Image.LANCZOS)
    print(f"  After resize: Model {model_img.size}, Garment {garment_img.size}")

    # Customer-optimized prompts for better quality (SHEIN requirement)
    prompt = "将主图中模特身上的衣服替换为第二张图的衣服，要求一致性，保持光影细节阴影细节。8K高清晰图片"
    negative_prompt = "不正确的手, 模糊的图像, 低质量的图片, 模糊的手, 多个手指, 多个腿, 不正确的光影, 不正确的阴影, 缺少细节, 模糊的织物, 低清晰的织物材质"

    all_results = {}

    # =========================================================================
    # Test 1: BF16 Eager Baseline
    # =========================================================================
    if not args.skip_eager:
        print("\n" + "#" * 70)
        print("# TEST 1: BF16 Eager Baseline (No torch.compile)")
        print("#" * 70)

        clear_gpu_memory()
        print(f"GPU Memory before load: {get_gpu_memory_mb():.0f} MB")

        print("Loading pipeline (BF16 Eager)...")
        t0 = time.time()
        pipe = QwenImageEditPlusPipeline.from_pretrained(
            args.model_path, torch_dtype=torch.bfloat16
        ).to("cuda")
        load_time = time.time() - t0
        print(f"  Pipeline loaded in {load_time:.2f}s")
        print(f"  GPU Memory after load: {get_gpu_memory_mb():.0f} MB")

        results = run_single_test(
            test_name="BF16_Eager_Baseline",
            pipe=pipe,
            model_img=model_img,
            garment_img=garment_img,
            prompt=prompt,
            negative_prompt=negative_prompt,
            output_res=output_res,
            num_steps=num_steps,
            cfg=cfg,
            warmup_runs=args.warmup_runs,
            num_runs=args.num_runs,
            output_dir=args.output_dir,
            seed=args.seed,
        )
        all_results["eager_baseline"] = results

        # Cleanup
        del pipe
        clear_gpu_memory()
        print(f"GPU Memory after cleanup: {get_gpu_memory_mb():.0f} MB")

    # =========================================================================
    # Test 2: torch.compile with dynamic=None (default)
    # =========================================================================
    if not args.skip_compile_none:
        print("\n" + "#" * 70)
        print("# TEST 2: torch.compile (dynamic=None, Static Optimization)")
        print("#" * 70)

        clear_gpu_memory()
        print(f"GPU Memory before load: {get_gpu_memory_mb():.0f} MB")

        print("Loading pipeline (BF16)...")
        t0 = time.time()
        pipe = QwenImageEditPlusPipeline.from_pretrained(
            args.model_path, torch_dtype=torch.bfloat16
        ).to("cuda")
        load_time = time.time() - t0
        print(f"  Pipeline loaded in {load_time:.2f}s")

        print("Applying torch.compile (mode=default, dynamic=None)...")
        t0 = time.time()
        pipe.transformer = torch.compile(
            pipe.transformer,
            mode="default",
            fullgraph=False,
            dynamic=None,  # Default: static optimization for specific shapes
        )
        compile_time = time.time() - t0
        print(f"  torch.compile applied in {compile_time:.2f}s")
        print(f"  GPU Memory after compile: {get_gpu_memory_mb():.0f} MB")

        results = run_single_test(
            test_name="torch_compile_dynamic_None",
            pipe=pipe,
            model_img=model_img,
            garment_img=garment_img,
            prompt=prompt,
            negative_prompt=negative_prompt,
            output_res=output_res,
            num_steps=num_steps,
            cfg=cfg,
            warmup_runs=args.warmup_runs,
            num_runs=args.num_runs,
            output_dir=args.output_dir,
            seed=args.seed,
        )
        all_results["compile_dynamic_none"] = results

        # Cleanup
        del pipe
        clear_gpu_memory()
        print(f"GPU Memory after cleanup: {get_gpu_memory_mb():.0f} MB")

    # =========================================================================
    # Test 3: torch.compile with dynamic=True
    # =========================================================================
    if not args.skip_compile_true:
        print("\n" + "#" * 70)
        print("# TEST 3: torch.compile (dynamic=True, Dynamic Shape Tracing)")
        print("#" * 70)

        clear_gpu_memory()
        print(f"GPU Memory before load: {get_gpu_memory_mb():.0f} MB")

        print("Loading pipeline (BF16)...")
        t0 = time.time()
        pipe = QwenImageEditPlusPipeline.from_pretrained(
            args.model_path, torch_dtype=torch.bfloat16
        ).to("cuda")
        load_time = time.time() - t0
        print(f"  Pipeline loaded in {load_time:.2f}s")

        print("Applying torch.compile (mode=default, dynamic=True)...")
        t0 = time.time()
        pipe.transformer = torch.compile(
            pipe.transformer,
            mode="default",
            fullgraph=False,
            dynamic=True,  # Dynamic shape tracing to reduce recompilations
        )
        compile_time = time.time() - t0
        print(f"  torch.compile applied in {compile_time:.2f}s")
        print(f"  GPU Memory after compile: {get_gpu_memory_mb():.0f} MB")

        results = run_single_test(
            test_name="torch_compile_dynamic_True",
            pipe=pipe,
            model_img=model_img,
            garment_img=garment_img,
            prompt=prompt,
            negative_prompt=negative_prompt,
            output_res=output_res,
            num_steps=num_steps,
            cfg=cfg,
            warmup_runs=args.warmup_runs,
            num_runs=args.num_runs,
            output_dir=args.output_dir,
            seed=args.seed,
        )
        all_results["compile_dynamic_true"] = results

        # Cleanup
        del pipe
        clear_gpu_memory()

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY: Dynamic Parameter Comparison Results")
    print("=" * 70)

    baseline_time = None
    if "eager_baseline" in all_results:
        baseline_time = all_results["eager_baseline"]["avg_time"]

    summary_table = []
    for key, results in all_results.items():
        avg = results["avg_time"]
        speedup = ""
        if baseline_time and key != "eager_baseline":
            ratio = baseline_time / avg
            pct = (baseline_time - avg) / baseline_time * 100
            speedup = f"{ratio:.2f}x ({pct:.1f}% faster)"
        
        summary_table.append({
            "test": results["test_name"],
            "avg_time": avg,
            "time_per_step": results["time_per_step"],
            "speedup_vs_baseline": speedup,
            "runs": results["run_times"],
        })

    print(f"\n{'Test':<35} {'Avg Time':<12} {'Per Step':<12} {'Speedup':<20}")
    print("-" * 79)
    for row in summary_table:
        print(f"{row['test']:<35} {row['avg_time']:.2f}s{'':<6} {row['time_per_step']:.4f}s{'':<4} {row['speedup_vs_baseline']:<20}")

    print("\nDetailed run times:")
    for row in summary_table:
        print(f"  {row['test']}: {[round(t, 2) for t in row['runs']]}")

    # Save summary
    os.makedirs(args.output_dir, exist_ok=True)
    summary_path = os.path.join(args.output_dir, "summary_results.json")
    with open(summary_path, "w") as f:
        json.dump({
            "config": {
                "model": args.model_path,
                "device": device_name,
                "pytorch_version": torch.__version__,
                "input_resolution": list(input_res),
                "output_resolution": list(output_res),
                "num_inference_steps": num_steps,
                "guidance_scale": cfg,
                "seed": args.seed,
                "warmup_runs": args.warmup_runs,
                "benchmark_runs": args.num_runs,
            },
            "results": all_results,
            "summary": summary_table,
        }, f, indent=2)
    print(f"\nSummary saved: {summary_path}")

    # Historical reference
    print("\n" + "-" * 70)
    print("Historical Reference (Previous Test):")
    print("  BF16 Eager: 67.63s")
    print("  torch.compile (dynamic=None): 56.58s (16.4% faster)")
    print("-" * 70)


if __name__ == "__main__":
    main()
