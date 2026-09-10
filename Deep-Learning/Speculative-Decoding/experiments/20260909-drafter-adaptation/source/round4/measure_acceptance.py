#!/usr/bin/env python3
"""Measure DFlash speculative-decoding acceptance length for one target/drafter pair.

The acceptance length reported here is the DFlash definition taken directly from
``dflash.model.dflash_generate``: for every verification step the generator appends
``produced`` to ``acceptance_lengths``, where ``produced`` counts the drafted tokens
that survived verification plus the one bonus token that the target always emits.
A value of 1.0 therefore means "no drafted token was ever accepted", i.e. speculative
decoding degenerates to plain autoregressive decoding.

The script does not compute a speed-up. Acceptance length is the quantity that
depends on whether the drafter still matches the target, and it is measured with
greedy decoding so the number is deterministic for a fixed prompt set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from dflash.model import DFlash2DraftModel, DFlashDraftModel, dflash_generate


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_prompts(path: Path, limit: int | None) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if "prompt" not in record:
                raise ValueError(f"record without 'prompt' field: {record!r}")
            records.append(record)
            if limit is not None and len(records) >= limit:
                break
    if not records:
        raise ValueError(f"no prompts found in {path}")
    return records


def build_target(path: str, adapter: str | None, device: str, dtype: torch.dtype):
    target = AutoModelForCausalLM.from_pretrained(path, dtype=dtype, device_map=device)
    if adapter:
        from peft import PeftModel

        target = PeftModel.from_pretrained(target, adapter)
        target = target.merge_and_unload()
    return target.eval()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, help="target model directory")
    parser.add_argument("--drafter", required=True, help="DFlash drafter directory")
    parser.add_argument("--adapter", default=None, help="optional LoRA adapter merged into the target")
    parser.add_argument("--prompts", required=True, help="JSONL file with a 'prompt' field per line")
    parser.add_argument("--output", required=True, help="JSON file to write")
    parser.add_argument("--label", required=True, help="name of this measurement, e.g. matched")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--no-selector", action="store_true",
                        help="draft with backbone argmax (DFlash 1 path); bypasses the DFlash 2 "
                             "candidate selector, same weights otherwise")
    args = parser.parse_args()

    prompts_path = Path(args.prompts)
    records = load_prompts(prompts_path, args.limit)

    tokenizer = AutoTokenizer.from_pretrained(args.target)
    target = build_target(args.target, args.adapter, args.device, torch.bfloat16)
    drafter = DFlash2DraftModel.from_pretrained(args.drafter, dtype=torch.bfloat16)
    drafter = drafter.to(args.device).eval()
    if args.no_selector:
        # dflash_generate dispatches on isinstance(); the base class takes the argmax branch.
        drafter.__class__ = DFlashDraftModel

    stop_token_ids = [tokenizer.eos_token_id]
    extra_eos = getattr(tokenizer, "convert_tokens_to_ids", None)
    if extra_eos is not None:
        for token in ("<|im_end|>", "<|endoftext|>"):
            token_id = tokenizer.convert_tokens_to_ids(token)
            if isinstance(token_id, int) and token_id >= 0 and token_id not in stop_token_ids:
                stop_token_ids.append(token_id)

    per_request = []
    started = time.time()
    for index, record in enumerate(records):
        messages = [{"role": "user", "content": record["prompt"]}]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        input_ids = tokenizer(text, return_tensors="pt").input_ids.to(args.device)

        with torch.inference_mode():
            stats = dflash_generate(
                drafter,
                target=target,
                input_ids=input_ids,
                max_new_tokens=args.max_new_tokens,
                stop_token_ids=stop_token_ids,
                temperature=0.0,
                top_p=1.0,
                top_k=0,
                return_stats=True,
            )

        lengths = list(stats.acceptance_lengths)
        completion = tokenizer.decode(
            stats.output_ids[0, stats.num_input_tokens:], skip_special_tokens=True
        )
        per_request.append(
            {
                "index": index,
                "id": record.get("id", index),
                "num_input_tokens": int(stats.num_input_tokens),
                "num_output_tokens": int(stats.num_output_tokens),
                "verification_steps": len(lengths),
                "mean_acceptance_length": statistics.mean(lengths) if lengths else 0.0,
                "acceptance_lengths": lengths,
                "completion_sha256": hashlib.sha256(completion.encode("utf-8")).hexdigest(),
                "completion_head": completion[:200],
            }
        )
        print(
            f"[{index + 1}/{len(records)}] steps={len(lengths)} "
            f"tau={per_request[-1]['mean_acceptance_length']:.3f}",
            flush=True,
        )

    all_lengths = [value for item in per_request for value in item["acceptance_lengths"]]
    macro = statistics.mean(item["mean_acceptance_length"] for item in per_request)
    micro = statistics.mean(all_lengths)

    block_size = int(drafter.config.dflash_config["block_size"])
    histogram = {
        str(bucket): all_lengths.count(bucket) / len(all_lengths)
        for bucket in range(1, block_size + 2)
    }

    payload = {
        "label": args.label,
        "target": args.target,
        "adapter": args.adapter,
        "drafter": args.drafter,
        "prompts_file": str(prompts_path),
        "prompts_sha256": sha256_of(prompts_path),
        "num_prompts": len(records),
        "max_new_tokens": args.max_new_tokens,
        "decoding": "greedy (temperature=0.0)",
        "draft_path": "backbone_argmax" if args.no_selector else "dflash2_candidate_selector",
        "block_size": block_size,
        "target_layer_ids": list(drafter.config.dflash_config["target_layer_ids"]),
        "macro_mean_acceptance_length": macro,
        "micro_mean_acceptance_length": micro,
        "total_verification_steps": len(all_lengths),
        "total_output_tokens": sum(item["num_output_tokens"] for item in per_request),
        "acceptance_histogram": histogram,
        "wall_clock_seconds": round(time.time() - started, 1),
        "torch_version": torch.__version__,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "host": platform.node(),
        "per_request": per_request,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "label": args.label,
                "macro_mean_acceptance_length": round(macro, 4),
                "micro_mean_acceptance_length": round(micro, 4),
                "num_prompts": len(records),
                "output": str(output_path),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print("MEASURE_ACCEPTANCE=PASS", flush=True)


if __name__ == "__main__":
    main()
