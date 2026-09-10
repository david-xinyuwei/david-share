#!/usr/bin/env python3
"""Generate the drafter re-adaptation corpus from a specific target model.

``train_drafter.py`` computes cross-entropy against the literal tokens of each
training sequence (``labels = input_ids[0, anchor + 1 : anchor + block]``). The
drafter therefore learns to predict whatever text it is shown. To make it predict
what the *target* will emit, the training text must be the target's own greedy
generations, not the human reference answers from the dataset.

This script runs the given target (optionally with a LoRA adapter merged in) over
the fine-tuning prompts and writes one ``{"text": ...}`` record per response, where
``text`` is the full chat-formatted prompt plus the generated continuation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_prompts(path: Path, limit: int | None, skip: int = 0) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            line = line.strip()
            if not line or index < skip:
                continue
            records.append(json.loads(line))
            if limit is not None and len(records) >= limit:
                break
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=800)
    parser.add_argument("--skip", type=int, default=0, help="skip the first N prompt lines")
    parser.add_argument("--max-new-tokens", type=int, default=320)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-prompt-tokens", type=int, default=768)
    args = parser.parse_args()

    records = load_prompts(Path(args.prompts), args.limit, args.skip)

    tokenizer = AutoTokenizer.from_pretrained(args.target, padding_side="left")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(args.target, dtype=torch.bfloat16, device_map="cuda")
    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter)
        model = model.merge_and_unload()
    model.eval()
    model.config.use_cache = True

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    generated_tokens = 0
    started = time.time()
    with output_path.open("w", encoding="utf-8") as handle:
        for start in range(0, len(records), args.batch_size):
            batch = records[start : start + args.batch_size]
            texts = [
                tokenizer.apply_chat_template(
                    [{"role": "user", "content": item["prompt"]}],
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
                for item in batch
            ]
            encoded = tokenizer(
                texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=args.max_prompt_tokens,
                add_special_tokens=False,
            ).to("cuda")

            with torch.inference_mode():
                outputs = model.generate(
                    **encoded,
                    max_new_tokens=args.max_new_tokens,
                    do_sample=False,
                    temperature=None,
                    top_p=None,
                    top_k=None,
                    pad_token_id=tokenizer.pad_token_id,
                )

            prompt_width = encoded["input_ids"].shape[1]
            for row, item in enumerate(batch):
                new_ids = outputs[row, prompt_width:]
                completion = tokenizer.decode(new_ids, skip_special_tokens=True)
                if not completion.strip():
                    continue
                prompt_text = tokenizer.decode(
                    encoded["input_ids"][row], skip_special_tokens=False
                ).replace(tokenizer.pad_token, "")
                handle.write(
                    json.dumps(
                        {
                            "id": item.get("id", f"gen-{start + row}"),
                            "text": prompt_text + completion,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                written += 1
                generated_tokens += int((new_ids != tokenizer.pad_token_id).sum())

            print(
                f"[{min(start + args.batch_size, len(records))}/{len(records)}] "
                f"written={written} elapsed={time.time() - started:.0f}s",
                flush=True,
            )

    summary = {
        "target": args.target,
        "adapter": args.adapter,
        "prompts": args.prompts,
        "skip": args.skip,
        "requested": len(records),
        "written": written,
        "generated_tokens": generated_tokens,
        "max_new_tokens": args.max_new_tokens,
        "decoding": "greedy (do_sample=False)",
        "output": str(output_path),
        "output_sha256": sha256_of(output_path),
        "wall_clock_seconds": round(time.time() - started, 1),
    }
    Path(str(output_path) + ".manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    print("GENERATE_RESPONSES=PASS", flush=True)


if __name__ == "__main__":
    main()
