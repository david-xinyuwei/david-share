#!/usr/bin/env python3
"""Separate two effects that both move acceptance length.

Acceptance length depends on the drafter matching the target AND on how predictable
the target's own output is. A model that answers in a formulaic style is easy to draft
for even by a drafter that was never adapted to it, and a model that has collapsed into
repetition is trivially easy to draft for. Reporting acceptance length alone cannot tell
those cases apart from a genuinely well-matched drafter.

This script measures, for one target/drafter pair on the target's own greedy output:

* ``target_top1_prob``   - how confident the target is in its own next token. This is the
                           predictability of the output text, independent of the drafter.
* ``target_entropy``     - the same quantity as a distribution width.
* ``repeat_4gram``       - fraction of duplicated 4-grams in the full completion, to catch
                           degeneration that would inflate every other number here.
* ``drafter_agreement``  - per draft offset, how often the drafter's argmax equals the
                           target's own teacher-forced argmax.
* ``expected_acceptance``- the same agreements accumulated as a prefix product, which is
                           the teacher-forced analogue of the measured acceptance length.

The teacher-forced pass uses one full-sequence target forward and slices the hidden
states per anchor. Causal masking makes those slices identical to the prefix-only
forwards that ``dflash_generate`` and ``train_drafter.py`` perform.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from dflash.model import (
    DFlash2DraftModel,
    _draft_value,
    _output_head,
    _raw_input_embeddings,
    extract_context_feature,
)


def repeat_4gram(text: str) -> float:
    words = text.split()
    if len(words) < 8:
        return 0.0
    grams = [tuple(words[i : i + 4]) for i in range(len(words) - 3)]
    return 1.0 - len(collections.Counter(grams)) / len(grams)


def load_prompts(path: Path, limit: int | None) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
            if limit is not None and len(records) >= limit:
                break
    return records


def build_target(path: str, adapter: str | None):
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.bfloat16, device_map="cuda")
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    return model.eval()


@torch.inference_mode()
def analyse_sequence(target, drafter, layer_ids, input_ids, prompt_len, block, stride, draft_path):
    out = target(input_ids, output_hidden_states=True)
    logits = out.logits.float()
    probs = torch.softmax(logits, dim=-1)

    # logits at position p predict the token at p + 1
    gen_slice = slice(prompt_len - 1, input_ids.shape[1] - 1)
    gen_probs = probs[0, gen_slice]
    actual = input_ids[0, prompt_len:]
    top1_prob = gen_probs.max(dim=-1).values
    chosen_prob = gen_probs.gather(1, actual.unsqueeze(1)).squeeze(1)
    entropy = -(gen_probs * torch.log(gen_probs.clamp_min(1e-12))).sum(dim=-1)

    target_argmax = logits[0].argmax(dim=-1)
    context_full = extract_context_feature(list(out.hidden_states), layer_ids)
    mask_id = drafter.config.dflash_config["mask_token_id"]
    scale = float(_draft_value(drafter.config, "input_embedding_scale", 1.0))
    head = _output_head(target)

    hits = [0] * (block - 1)
    trials = [0] * (block - 1)
    anchors = list(range(prompt_len, input_ids.shape[1] - block, stride))
    for anchor in anchors:
        block_ids = torch.full((1, block), mask_id, dtype=torch.long, device=input_ids.device)
        block_ids[0, 0] = input_ids[0, anchor]
        noise = _raw_input_embeddings(target, block_ids, scale)

        hidden = drafter(
            position_ids=torch.arange(anchor + block, device=input_ids.device).unsqueeze(0),
            attention_mask=None,
            noise_embedding=noise,
            target_hidden=context_full[:, :anchor, :],
            use_cache=False,
        )[:, 1 - block :, :]

        if draft_path == "selector":
            # The real DFlash 2 inference path: top-k candidates rescored by the selector
            # and chained through the block.
            draft_pred = drafter.propose(hidden, input_ids[:, anchor], head, 0.0)[0][0]
        else:
            draft_pred = drafter.compute_logits(hidden, head)[0].argmax(dim=-1)
        reference = target_argmax[anchor : anchor + block - 1]
        for offset in range(block - 1):
            trials[offset] += 1
            if int(draft_pred[offset]) == int(reference[offset]):
                hits[offset] += 1

    return {
        "generated_tokens": int(actual.numel()),
        "anchors": len(anchors),
        "mean_target_top1_prob": float(top1_prob.mean()),
        "mean_target_chosen_prob": float(chosen_prob.mean()),
        "mean_target_entropy": float(entropy.mean()),
        "hits": hits,
        "trials": trials,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--drafter", required=True)
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--stride", type=int, default=8)
    parser.add_argument("--draft-path", choices=["argmax", "selector"], default="argmax",
                        help="argmax = backbone only; selector = DFlash 2 candidate selector as at inference")
    args = parser.parse_args()

    records = load_prompts(Path(args.prompts), args.limit)
    tokenizer = AutoTokenizer.from_pretrained(args.target, padding_side="left")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    target = build_target(args.target, args.adapter)
    drafter = DFlash2DraftModel.from_pretrained(args.drafter, dtype=torch.bfloat16).to("cuda").eval()
    layer_ids = list(drafter.config.dflash_config["target_layer_ids"])
    block = int(drafter.config.dflash_config["block_size"])

    started = time.time()
    generated = []
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
            texts, return_tensors="pt", padding=True, truncation=True,
            max_length=768, add_special_tokens=False,
        ).to("cuda")
        with torch.inference_mode():
            out = target.generate(
                **encoded, max_new_tokens=args.max_new_tokens, do_sample=False,
                temperature=None, top_p=None, top_k=None,
                pad_token_id=tokenizer.pad_token_id,
            )
        width = encoded["input_ids"].shape[1]
        for row, item in enumerate(batch):
            new_ids = out[row, width:]
            keep = new_ids[new_ids != tokenizer.pad_token_id]
            generated.append(
                {
                    "id": item.get("id"),
                    "prompt_ids": encoded["input_ids"][row][encoded["attention_mask"][row].bool()],
                    "completion_ids": keep,
                    "completion": tokenizer.decode(keep, skip_special_tokens=True),
                }
            )
        print(f"generated {len(generated)}/{len(records)} {time.time() - started:.0f}s", flush=True)

    per_request = []
    hits_total = [0] * (block - 1)
    trials_total = [0] * (block - 1)
    for index, item in enumerate(generated):
        ids = torch.cat([item["prompt_ids"], item["completion_ids"]]).unsqueeze(0).to("cuda")
        prompt_len = int(item["prompt_ids"].numel())
        if ids.shape[1] - prompt_len <= block + 1:
            continue
        stats = analyse_sequence(target, drafter, layer_ids, ids, prompt_len, block, args.stride,
                                 args.draft_path)
        stats["id"] = item["id"]
        stats["repeat_4gram"] = repeat_4gram(item["completion"])
        stats["completion"] = item["completion"]
        per_request.append(stats)
        for offset in range(block - 1):
            hits_total[offset] += stats["hits"][offset]
            trials_total[offset] += stats["trials"][offset]
        print(f"analysed {index + 1}/{len(generated)} {time.time() - started:.0f}s", flush=True)

    agreement = [
        hits_total[offset] / trials_total[offset] if trials_total[offset] else 0.0
        for offset in range(block - 1)
    ]
    expected, running = [], 1.0
    for value in agreement:
        running *= value
        expected.append(running)

    payload = {
        "label": args.label,
        "target": args.target,
        "adapter": args.adapter,
        "drafter": args.drafter,
        "prompts": args.prompts,
        "num_sequences": len(per_request),
        "block_size": block,
        "stride": args.stride,
        "draft_path": args.draft_path,
        "mean_target_top1_prob": statistics.mean(r["mean_target_top1_prob"] for r in per_request),
        "mean_target_chosen_prob": statistics.mean(r["mean_target_chosen_prob"] for r in per_request),
        "mean_target_entropy": statistics.mean(r["mean_target_entropy"] for r in per_request),
        "mean_repeat_4gram": statistics.mean(r["repeat_4gram"] for r in per_request),
        "max_repeat_4gram": max(r["repeat_4gram"] for r in per_request),
        "mean_generated_tokens": statistics.mean(r["generated_tokens"] for r in per_request),
        "drafter_agreement_by_offset": agreement,
        "expected_acceptance_prefix": expected,
        "teacher_forced_acceptance_length": 1.0 + sum(expected),
        "total_anchors": sum(r["anchors"] for r in per_request),
        "wall_clock_seconds": round(time.time() - started, 1),
        "per_request": per_request,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "label": args.label,
                "draft_path": args.draft_path,
                "mean_target_top1_prob": round(payload["mean_target_top1_prob"], 4),
                "mean_target_entropy": round(payload["mean_target_entropy"], 4),
                "mean_repeat_4gram": round(payload["mean_repeat_4gram"], 4),
                "drafter_agreement_by_offset": [round(v, 4) for v in agreement],
                "teacher_forced_acceptance_length": round(payload["teacher_forced_acceptance_length"], 4),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    print("ANALYSE_PREDICTABILITY=PASS", flush=True)


if __name__ == "__main__":
    main()
