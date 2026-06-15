#!/usr/bin/env python3
"""Inspect Qwen VL module names before choosing LoRA targets."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import torch
try:
    from transformers import Qwen3VLForConditionalGeneration as ModelLoader
except ImportError:
    try:
        from transformers import AutoModelForImageTextToText as ModelLoader
    except ImportError:
        from transformers import AutoModelForVision2Seq as ModelLoader


KEYWORDS = {
    "vision": ("vision", "visual", "vit", "patch", "merger"),
    "projector": ("projector", "proj", "connector", "merger", "multi_modal"),
    "decoder_lora": ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
    parser.add_argument("--output", default="reports/qwen3vl_modules.json")
    parser.add_argument("--max-items-per-group", type=int, default=200)
    parser.add_argument(
        "--dtype",
        default="bfloat16",
        choices=("bfloat16", "float16", "float32"),
        help="Load dtype for inspection.",
    )
    return parser.parse_args()


def dtype_from_name(name: str) -> torch.dtype:
    return {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[name]


def group_module(name: str) -> str | None:
    lower_name = name.lower()
    for group, keywords in KEYWORDS.items():
        if any(keyword in lower_name for keyword in keywords):
            return group
    return None


def main() -> None:
    args = parse_args()
    model = ModelLoader.from_pretrained(
        args.model,
        torch_dtype=dtype_from_name(args.dtype),
        device_map="auto",
        trust_remote_code=True,
    )
    grouped: dict[str, list[str]] = defaultdict(list)
    trainable_param_count = 0
    total_param_count = 0

    for parameter in model.parameters():
        total_param_count += parameter.numel()
        if parameter.requires_grad:
            trainable_param_count += parameter.numel()

    for name, module in model.named_modules():
        group = group_module(name)
        if group and len(grouped[group]) < args.max_items_per_group:
            grouped[group].append(f"{name}: {module.__class__.__name__}")

    result = {
        "model": args.model,
        "total_parameters": total_param_count,
        "trainable_parameters_before_peft": trainable_param_count,
        "groups": grouped,
        "recommendation": {
            "stage_1": "LoRA on decoder_lora modules only.",
            "stage_2": "Add confirmed projector/merger module names if Stage 1 fails visual-to-taxonomy alignment.",
            "stage_3": "Only unfreeze selected vision tower layers after error analysis proves visual feature extraction is the bottleneck.",
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2)
    print(json.dumps(result["recommendation"], ensure_ascii=False, indent=2))
    print(f"Wrote module report to {output_path}")


if __name__ == "__main__":
    main()
