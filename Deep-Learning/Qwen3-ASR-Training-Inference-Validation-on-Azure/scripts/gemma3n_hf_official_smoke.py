"""Gemma 3n official Hugging Face smoke test.

This script intentionally starts with a text-only prompt before any audio input.
That separates two questions:
1. Can Gemma 3n run with the official Transformers API in this environment?
2. If text-only works, can audio be passed through the processor and model?

Source: https://huggingface.co/google/gemma-3n-E2B-it
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

import torch
from transformers import AutoProcessor, Gemma3nForConditionalGeneration


def run_smoke(model_path: str, max_new_tokens: int) -> dict:
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result = {
        "model": model_path,
        "source": "https://huggingface.co/google/gemma-3n-E2B-it",
        "task": "text-only smoke before audio route",
        "started_at": started_at,
        "status": "started",
        "environment": {},
    }

    try:
        result["environment"] = {
            "python_torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "cudnn_version": torch.backends.cudnn.version(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }

        load_t0 = time.time()
        model = Gemma3nForConditionalGeneration.from_pretrained(
            model_path,
            device_map="auto",
            attn_implementation="sdpa",
            torch_dtype=torch.bfloat16,
        ).eval()
        processor = AutoProcessor.from_pretrained(model_path, padding_side="left")
        result["load_time_s"] = round(time.time() - load_t0, 3)
        result["parameter_count_b"] = round(sum(p.numel() for p in model.parameters()) / 1e9, 3)
        result["first_parameter_dtype"] = str(next(model.parameters()).dtype)

        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Say hello in Chinese."}],
            }
        ]
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=True,
        ).to(model.device)
        input_len = inputs["input_ids"].shape[-1]

        infer_t0 = time.time()
        with torch.inference_mode():
            generation = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                cache_implementation="static",
            )
        output_text = processor.decode(generation[0][input_len:], skip_special_tokens=True)

        result.update(
            {
                "status": "pass",
                "latency_ms": round((time.time() - infer_t0) * 1000, 3),
                "output": output_text,
            }
        )
    except Exception as exc:  # noqa: BLE001 - diagnostic script should capture exact failure.
        result.update(
            {
                "status": "fail",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback_tail": traceback.format_exc().splitlines()[-24:],
            }
        )

    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run official Gemma 3n HF text-only smoke test.")
    parser.add_argument("--model", default="/root/gemma-3n-E2B-it")
    parser.add_argument("--output", default="results/gemma3n_h100_official_smoke.json")
    parser.add_argument("--max-new-tokens", type=int, default=50)
    args = parser.parse_args()

    result = run_smoke(args.model, args.max_new_tokens)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
