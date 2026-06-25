#!/usr/bin/env python3
"""Compare Qwen3-ASR-0.6B baseline vs BitsAndBytes 4-bit NF4 on FLEURS CER.

Outputs /root/asr_results/qwen3_asr_0.6b_4bit_cer_comparison.json
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import torch
from datasets import load_dataset
from qwen_asr import Qwen3ASRModel
from transformers import BitsAndBytesConfig

RESULTS = Path("/root/asr_results")
MODEL = "Qwen/Qwen3-ASR-0.6B"
N = 80


def normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[\u3000\s]+", " ", text)
    text = re.sub(r"[，。！？、；：,.!?;:\"'()\[\]{}<>《》“”‘’\-·…—]+", "", text)
    return text.replace(" ", "")


def cer(ref: str, hyp: str) -> float:
    r, h = list(normalize(ref)), list(normalize(hyp))
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hc in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if rc == hc else 1))
        prev = cur
    return prev[-1] / len(r)


def eval_model(load_kwargs: dict, label: str, refs: list[str], wavs: list[Path]) -> dict:
    print(f"Loading {label}...", flush=True)
    model = Qwen3ASRModel.from_pretrained(MODEL, **load_kwargs)
    print(f"Transcribing {label}...", flush=True)
    start = time.time()
    hyps = []
    for wav in wavs:
        hyps.append(model.transcribe([str(wav)])[0].text)
    elapsed = time.time() - start
    cers = [cer(r, h) for r, h in zip(refs, hyps)]
    result = {
        "label": label,
        "samples": len(refs),
        "cer_mean": round(float(np.mean(cers)), 4),
        "cer_median": round(float(np.median(cers)), 4),
        "cer_p95": round(float(np.percentile(cers, 95)), 4),
        "num_perfect": int(sum(x == 0.0 for x in cers)),
        "elapsed_s": round(elapsed, 1),
        "seconds_per_sample": round(elapsed / len(refs), 4),
        "examples": [{"ref": refs[i], "hyp": hyps[i]} for i in range(min(5, len(refs)))],
    }
    del model
    torch.cuda.empty_cache()
    time.sleep(3)
    return result


def main() -> None:
    ds = load_dataset("google/fleurs", "cmn_hans_cn", split="test").select(range(N))
    refs = [s["transcription"] for s in ds]
    wavs = sorted((RESULTS / "fleurs_wav").glob("*.wav"))[:N]
    assert len(wavs) >= N, f"Need {N} wav files, found {len(wavs)}"

    baseline = eval_model({"dtype": torch.bfloat16, "device_map": "cuda"}, "baseline_bf16", refs, wavs)

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float32)
    q4 = eval_model({"quantization_config": bnb, "device_map": "cuda"}, "bnb_4bit_nf4", refs, wavs)

    output = {
        "model": MODEL,
        "dataset": "google/fleurs cmn_hans_cn test[:80]",
        "baseline": baseline,
        "bnb_4bit_nf4": q4,
        "delta": {
            "cer_abs_delta": round(q4["cer_mean"] - baseline["cer_mean"], 4),
            "cer_relative_delta_pct": round((q4["cer_mean"] - baseline["cer_mean"]) / baseline["cer_mean"] * 100, 2) if baseline["cer_mean"] else None,
            "speed_ratio_4bit_vs_baseline": round(baseline["seconds_per_sample"] / q4["seconds_per_sample"], 3) if q4["seconds_per_sample"] else None,
        },
    }
    out = RESULTS / "qwen3_asr_0.6b_4bit_cer_comparison.json"
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
