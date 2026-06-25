#!/usr/bin/env python3
"""Rerun #16 encoder-only and #17 LR smoke without checkpoint saving.
Avoids generation_config save validation issue; evaluates in-memory models.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from datasets import load_dataset
from qwen_asr import Qwen3ASRModel
from transformers import Trainer, TrainingArguments

RESULTS = Path("/root/asr_results")
RESULTS.mkdir(parents=True, exist_ok=True)
TRAIN_FILE = "/root/fleurs_sft/train.jsonl"
BASE_MODEL = "Qwen/Qwen3-ASR-0.6B"


def load_sft_module():
    spec = importlib.util.spec_from_file_location("qwen3_asr_sft_mod", "/root/Qwen3-ASR/finetuning/qwen3_asr_sft.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


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


def prepare_dataset(mod, processor, n_train: int = 100):
    # Reuse the prepared 100-sample JSONL for all tests.
    ds = load_dataset("json", data_files={"train": TRAIN_FILE})
    if n_train < len(ds["train"]):
        ds["train"] = ds["train"].select(range(n_train))
    ds = ds.map(mod.make_preprocess_fn_prefix_only(processor), num_proc=1)
    keep = {"prompt", "audio", "target", "prefix_text"}
    drop = [c for c in ds["train"].column_names if c not in keep]
    if drop:
        ds["train"] = ds["train"].remove_columns(drop)
    return ds["train"]


def train_in_memory(model, processor, n_train: int, epochs: int, lr: float):
    mod = load_sft_module()
    mod.patch_outer_forward(model)
    train_ds = prepare_dataset(mod, processor, n_train=n_train)
    collator = mod.DataCollatorForQwen3ASRFinetuning(processor=processor, sampling_rate=16000)
    args = TrainingArguments(
        output_dir=f"/tmp/qwen3_tmp_{int(time.time())}",
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=lr,
        num_train_epochs=epochs,
        logging_steps=5,
        lr_scheduler_type="linear",
        warmup_ratio=0.1,
        save_strategy="no",
        eval_strategy="no",
        bf16=False,
        fp16=False,
        remove_unused_columns=False,
        report_to="none",
        max_grad_norm=1.0,
    )
    trainer = Trainer(model=model, args=args, train_dataset=train_ds, data_collator=collator, tokenizer=processor.tokenizer)
    start = time.time()
    out = trainer.train()
    return {
        "runtime_s": round(time.time() - start, 1),
        "train_loss": float(getattr(out, "training_loss", 0.0)),
        "logs": trainer.state.log_history,
    }


def eval_asr(asr: Qwen3ASRModel, n_samples: int = 80):
    ds = load_dataset("google/fleurs", "cmn_hans_cn", split="test").select(range(n_samples))
    refs = [s["transcription"] for s in ds]
    wavs = sorted(Path("/root/asr_results/fleurs_wav").glob("*.wav"))[:n_samples]
    hyps = []
    start = time.time()
    for wav in wavs:
        hyps.append(asr.transcribe([str(wav)])[0].text)
    elapsed = time.time() - start
    cers = [cer(r, h) for r, h in zip(refs, hyps)]
    return {
        "samples": n_samples,
        "cer_mean": round(float(np.mean(cers)), 4),
        "cer_median": round(float(np.median(cers)), 4),
        "num_perfect": int(sum(x == 0.0 for x in cers)),
        "elapsed_s": round(elapsed, 1),
        "examples": [{"ref": refs[i], "hyp": hyps[i]} for i in range(min(5, n_samples))],
    }


def encoder_only():
    print("[#16] Encoder-only SFT in-memory", flush=True)
    asr = Qwen3ASRModel.from_pretrained(BASE_MODEL, dtype=torch.float32, device_map=None)
    model = asr.model
    trainable = frozen = 0
    names = []
    for name, param in model.named_parameters():
        is_encoder = any(token in name.lower() for token in ["audio", "encoder", "feature"])
        param.requires_grad = is_encoder
        if is_encoder:
            trainable += param.numel()
            names.append(name)
        else:
            frozen += param.numel()
    train = train_in_memory(model, asr.processor, n_train=100, epochs=3, lr=5e-6)
    asr.model = model.to("cuda")
    ev = eval_asr(asr, n_samples=80)
    result = {
        "trainable_params": trainable,
        "frozen_params": frozen,
        "trainable_ratio": round(trainable / (trainable + frozen) * 100, 4),
        "sample_trainable_names": names[:20],
        "train": train,
        "eval": ev,
    }
    (RESULTS / "encoder_only_sft_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    del asr, model
    torch.cuda.empty_cache()
    return result


def lr_smoke():
    print("[#17] FP32 LR smoke", flush=True)
    rows = []
    for lr in [2e-5, 1e-5, 5e-6, 2e-6]:
        print(f"  LR={lr}", flush=True)
        asr = Qwen3ASRModel.from_pretrained(BASE_MODEL, dtype=torch.float32, device_map=None)
        train = train_in_memory(asr.model, asr.processor, n_train=40, epochs=1, lr=lr)
        log_json = json.dumps(train["logs"], ensure_ascii=False).lower()
        rows.append({"lr": lr, "has_nan": "nan" in log_json, "train_loss": train["train_loss"], "logs": train["logs"]})
        del asr
        torch.cuda.empty_cache()
    result = {"precision": "fp32", "train_samples_per_lr": 40, "runs": rows}
    (RESULTS / "lr_stability_smoke.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main():
    out = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        out["encoder_only"] = encoder_only()
    except Exception as exc:
        out["encoder_only_error"] = repr(exc)
        torch.cuda.empty_cache()
    try:
        out["lr_smoke"] = lr_smoke()
    except Exception as exc:
        out["lr_smoke_error"] = repr(exc)
        torch.cuda.empty_cache()
    out["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (RESULTS / "remaining_training_tests_v2_summary.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
