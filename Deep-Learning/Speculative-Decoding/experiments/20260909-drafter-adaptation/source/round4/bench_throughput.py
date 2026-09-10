#!/usr/bin/env python3
"""End-to-end decoding throughput: plain autoregressive vs. DFlash speculative decoding.

Every configuration runs the same prompts, greedy, batch size 1, on the same target
model, with the same stop tokens and the same ``max_new_tokens``. Wall-clock time is
measured around the whole generate call with ``torch.cuda.synchronize()`` so prefill
and Python overhead are included for every configuration in the same way.

This is the Hugging Face Transformers reference path that ``dflash`` ships, not a
serving engine. Absolute tokens/s will be lower than vLLM or SGLang; the *ratios*
between configurations on this path are what the measurement is for.

Outputs from the speculative configurations are compared token-for-token with the
autoregressive output. Greedy speculative decoding is lossless in exact arithmetic;
any mismatch here is bf16 numerical drift, and the rate is reported rather than
assumed to be zero.
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

from dflash.model import DFlash2DraftModel, dflash_generate


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
    model.eval()
    model.config.use_cache = True
    return model


def timed(fn):
    torch.cuda.synchronize()
    start = time.perf_counter()
    result = fn()
    torch.cuda.synchronize()
    return result, time.perf_counter() - start


def run_autoregressive(target, input_ids, max_new_tokens, stop_ids, pad_id):
    with torch.inference_mode():
        out, seconds = timed(
            lambda: target.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                eos_token_id=stop_ids,
                pad_token_id=pad_id,
            )
        )
    new_ids = out[0, input_ids.shape[1]:]
    return new_ids, seconds, None


def run_speculative(drafter, target, input_ids, max_new_tokens, stop_ids):
    with torch.inference_mode():
        stats, seconds = timed(
            lambda: dflash_generate(
                drafter,
                target=target,
                input_ids=input_ids,
                max_new_tokens=max_new_tokens,
                stop_token_ids=stop_ids,
                temperature=0.0,
                top_p=1.0,
                top_k=0,
                return_stats=True,
            )
        )
    new_ids = stats.output_ids[0, stats.num_input_tokens:]
    return new_ids, seconds, list(stats.acceptance_lengths)


def summarize(label, rows, reference_texts):
    total_tokens = sum(r["new_tokens"] for r in rows)
    total_seconds = sum(r["seconds"] for r in rows)
    per_request_tps = [r["new_tokens"] / r["seconds"] for r in rows if r["seconds"] > 0]
    taus = [r["mean_acceptance_length"] for r in rows if r.get("mean_acceptance_length") is not None]
    matches = [r["text"] == reference_texts[r["index"]] for r in rows] if reference_texts else []
    return {
        "label": label,
        "requests": len(rows),
        "total_new_tokens": total_tokens,
        "total_seconds": round(total_seconds, 2),
        "tokens_per_second": round(total_tokens / total_seconds, 2) if total_seconds else None,
        "median_request_tokens_per_second": round(statistics.median(per_request_tps), 2),
        "mean_acceptance_length": round(statistics.mean(taus), 4) if taus else None,
        "exact_match_with_autoregressive": round(sum(matches) / len(matches), 4) if matches else None,
        "exact_match_count": sum(matches) if matches else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--drafter", action="append", default=[],
                        help="label=path, repeatable; each is benchmarked against the same target")
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--warmup", type=int, default=2)
    args = parser.parse_args()

    prompts_path = Path(args.prompts)
    records = load_prompts(prompts_path, args.limit)

    tokenizer = AutoTokenizer.from_pretrained(args.target)
    target = build_target(args.target, args.adapter)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    stop_ids = [tokenizer.eos_token_id]
    for token in ("<|im_end|>", "<|endoftext|>"):
        token_id = tokenizer.convert_tokens_to_ids(token)
        if isinstance(token_id, int) and token_id >= 0 and token_id not in stop_ids:
            stop_ids.append(token_id)

    encoded = []
    for record in records:
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": record["prompt"]}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
        encoded.append(tokenizer(text, return_tensors="pt").input_ids.to("cuda"))

    configs = []
    started = time.time()

    # --- autoregressive reference ---
    for ids in encoded[: args.warmup]:
        run_autoregressive(target, ids, 32, stop_ids, pad_id)
    ar_rows = []
    for index, ids in enumerate(encoded):
        new_ids, seconds, _ = run_autoregressive(target, ids, args.max_new_tokens, stop_ids, pad_id)
        text = tokenizer.decode(new_ids, skip_special_tokens=True)
        ar_rows.append({"index": index, "new_tokens": int(new_ids.numel()), "seconds": round(seconds, 4),
                        "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
        print(f"[ar {index + 1}/{len(encoded)}] {new_ids.numel()} tok {seconds:.2f}s "
              f"{new_ids.numel() / seconds:.1f} tok/s", flush=True)
    reference_texts = {r["index"]: r["text"] for r in ar_rows}
    configs.append({"summary": summarize("autoregressive", ar_rows, None),
                    "per_request": [{k: v for k, v in r.items() if k != "text"} for r in ar_rows]})
    print(json.dumps(configs[-1]["summary"]), flush=True)

    # --- speculative configurations ---
    for spec in args.drafter:
        label, path = spec.split("=", 1)
        drafter = DFlash2DraftModel.from_pretrained(path, dtype=torch.bfloat16).to("cuda").eval()
        for ids in encoded[: args.warmup]:
            run_speculative(drafter, target, ids, 32, stop_ids)
        rows = []
        for index, ids in enumerate(encoded):
            new_ids, seconds, lengths = run_speculative(drafter, target, ids, args.max_new_tokens, stop_ids)
            text = tokenizer.decode(new_ids, skip_special_tokens=True)
            rows.append({"index": index, "new_tokens": int(new_ids.numel()), "seconds": round(seconds, 4),
                         "mean_acceptance_length": statistics.mean(lengths) if lengths else None,
                         "verification_steps": len(lengths), "text": text,
                         "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
            print(f"[{label} {index + 1}/{len(encoded)}] {new_ids.numel()} tok {seconds:.2f}s "
                  f"{new_ids.numel() / seconds:.1f} tok/s tau={rows[-1]['mean_acceptance_length']:.2f}",
                  flush=True)
        summary = summarize(label, rows, reference_texts)
        summary["drafter_path"] = path
        summary["speedup_vs_autoregressive"] = round(
            summary["tokens_per_second"] / configs[0]["summary"]["tokens_per_second"], 3)
        configs.append({"summary": summary,
                        "per_request": [{k: v for k, v in r.items() if k != "text"} for r in rows]})
        print(json.dumps(summary), flush=True)
        del drafter
        torch.cuda.empty_cache()

    payload = {
        "target": args.target,
        "adapter": args.adapter,
        "prompts_file": str(prompts_path),
        "prompts_sha256": sha256_of(prompts_path),
        "num_prompts": len(records),
        "max_new_tokens": args.max_new_tokens,
        "decoding": "greedy, batch size 1, Hugging Face Transformers reference path",
        "timing": "wall clock around the full generate call incl. prefill, torch.cuda.synchronize",
        "torch_version": torch.__version__,
        "gpu_name": torch.cuda.get_device_name(0),
        "host": platform.node(),
        "wall_clock_seconds": round(time.time() - started, 1),
        "configs": configs,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== SUMMARY ===", flush=True)
    for config in configs:
        print(json.dumps(config["summary"], ensure_ascii=False), flush=True)
    print("BENCH_THROUGHPUT=PASS", flush=True)


if __name__ == "__main__":
    main()
