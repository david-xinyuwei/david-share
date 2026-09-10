#!/usr/bin/env python3
"""Degeneration gate for a fine-tuned target before any drafter work uses it.

Speculative decoding measurements on a target that loops or ends answers at random
positions are not interpretable (see the 2026-09-08 run). This gate generates pure
greedy completions with the plain Hugging Face path and checks:

* repeat_4gram  - fraction of duplicated 4-grams per completion (loops)
* loop_prompts  - completions where some 4-gram occurs 3+ times
* cap_hits      - completions that never emitted EOS within max_new_tokens
* mean_top1     - the target's own confidence in its greedy tokens

Thresholds are explicit CLI arguments so the acceptance criterion is on record.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from draft_metrics import repetition_statistics


def load_prompts(path: Path, limit: int | None):
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
        if limit and len(records) >= limit:
            break
    return records


def four_grams(text: str):
    words = text.split()
    return [tuple(words[i : i + 4]) for i in range(max(0, len(words) - 3))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--max-mean-repeat", type=float, default=0.03)
    parser.add_argument("--max-loop-prompts", type=int, default=2)
    parser.add_argument("--max-cap-fraction", type=float, default=0.5)
    parser.add_argument("--repetition-unit", choices=["word", "token"], default="word")
    args = parser.parse_args()

    records = load_prompts(Path(args.prompts), args.limit)
    tokenizer = AutoTokenizer.from_pretrained(args.target)
    model = AutoModelForCausalLM.from_pretrained(args.target, dtype=torch.bfloat16, device_map="cuda")
    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter).merge_and_unload()
    model.eval()

    stop_ids = sorted({tokenizer.eos_token_id, tokenizer.convert_tokens_to_ids("<|im_end|>"),
                       tokenizer.convert_tokens_to_ids("<|endoftext|>")})
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id

    rows = []
    for index, record in enumerate(records):
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": record["prompt"]}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
        ids = tokenizer(text, return_tensors="pt").input_ids.to("cuda")
        with torch.inference_mode():
            out = model.generate(ids, max_new_tokens=args.max_new_tokens, do_sample=False,
                                 temperature=None, top_p=None, top_k=None,
                                 eos_token_id=stop_ids, pad_token_id=pad_id,
                                 output_scores=True, return_dict_in_generate=True)
        new_ids = out.sequences[0, ids.shape[1]:]
        completion = tokenizer.decode(new_ids, skip_special_tokens=True)
        top1 = [float(torch.softmax(s[0].float(), -1).max()) for s in out.scores]
        tokens = new_ids.tolist()
        content_tokens = tokens[:-1] if tokens and tokens[-1] in stop_ids else tokens
        repeated = repetition_statistics(
            content_tokens if args.repetition_unit == "token" else completion.split()
        )
        rows.append({
            "id": record.get("id", index),
            "new_tokens": int(new_ids.numel()),
            "hit_cap": len(tokens) >= args.max_new_tokens and tokens[-1] not in stop_ids,
            "repeat_4gram": repeated["repeat_fraction"],
            "max_4gram_count": repeated["max_count"],
            "mean_top1": statistics.mean(top1) if top1 else None,
            "completion_head": completion[:160],
            "completion": completion,
            "completion_ids": tokens,
        })
        print(f"[{index + 1}/{len(records)}] tok={rows[-1]['new_tokens']} rep4={rows[-1]['repeat_4gram']:.3f} "
              f"max4={rows[-1]['max_4gram_count']} cap={rows[-1]['hit_cap']}", flush=True)

    mean_repeat = statistics.mean(r["repeat_4gram"] for r in rows)
    loop_prompts = sum(1 for r in rows if r["max_4gram_count"] >= 3)
    cap_fraction = sum(1 for r in rows if r["hit_cap"]) / len(rows)
    verdict = {
        "repetition_unit": args.repetition_unit,
        "mean_repeat_4gram": round(mean_repeat, 4),
        "loop_prompts": loop_prompts,
        "cap_fraction": round(cap_fraction, 3),
        "mean_new_tokens": round(statistics.mean(r["new_tokens"] for r in rows), 1),
        "mean_top1": round(statistics.mean(r["mean_top1"] for r in rows if r["mean_top1"] is not None), 4),
        "thresholds": {"max_mean_repeat": args.max_mean_repeat, "max_loop_prompts": args.max_loop_prompts,
                       "max_cap_fraction": args.max_cap_fraction},
    }
    verdict["pass"] = (mean_repeat <= args.max_mean_repeat and loop_prompts <= args.max_loop_prompts
                       and cap_fraction <= args.max_cap_fraction)

    payload = {"label": args.label, "target": args.target, "adapter": args.adapter,
               "metric_version": "repetition-units-v2",
               "prompts_sha256": hashlib.sha256(Path(args.prompts).read_bytes()).hexdigest(),
               "prompts": args.prompts, "num_prompts": len(rows), "decoding": "HF generate, pure greedy",
               "verdict": verdict, "per_request": rows}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"label": args.label, **verdict}, ensure_ascii=False), flush=True)
    print("DEGENERATION_GATE=" + ("PASS" if verdict["pass"] else "FAIL"), flush=True)
    raise SystemExit(0 if verdict["pass"] else 1)


if __name__ == "__main__":
    main()
