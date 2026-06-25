#!/usr/bin/env python3
from __future__ import annotations

import glob, json, os, pathlib, subprocess, time

TRAIN20 = "/root/fleurs_sft/train20.jsonl"
SCRIPT = "/root/Qwen3-ASR/finetuning/qwen3_asr_sft.py"
PY = "/root/miniconda3/envs/asr-sft/bin/python"
OUT = f"/root/resume_test_{int(time.time())}"
pathlib.Path(TRAIN20).write_text("".join(pathlib.Path("/root/fleurs_sft/train.jsonl").read_text().splitlines(True)[:20]), encoding="utf-8")
cmd1 = f"{PY} {SCRIPT} --model_path Qwen/Qwen3-ASR-0.6B --train_file {TRAIN20} --eval_file {TRAIN20} --output_dir {OUT} --epochs 1 --batch_size 1 --grad_acc 4 --lr 5e-6 --warmup_ratio 0.1 --log_steps 2 --save_strategy steps --save_steps 2"
cmd2 = f"{PY} {SCRIPT} --model_path Qwen/Qwen3-ASR-0.6B --train_file {TRAIN20} --eval_file {TRAIN20} --output_dir {OUT} --epochs 2 --batch_size 1 --grad_acc 4 --lr 5e-6 --warmup_ratio 0.1 --log_steps 2 --save_strategy steps --save_steps 2 --resume 1"
first = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
second = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
ckpts = sorted(glob.glob(f"{OUT}/checkpoint-*"))
result = {
    "test": "checkpoint_resume_smoke_v2",
    "output_dir": OUT,
    "train_samples": 20,
    "first_returncode": first.returncode,
    "second_returncode": second.returncode,
    "checkpoints": [os.path.basename(p) for p in ckpts],
    "resume_marker": "[resume] resume_from_checkpoint" in (second.stdout + second.stderr),
    "latest_checkpoint": os.path.basename(ckpts[-1]) if ckpts else None,
    "first_tail": (first.stdout + first.stderr)[-1200:],
    "second_tail": (second.stdout + second.stderr)[-1600:],
}
pathlib.Path("/root/asr_results/checkpoint_resume_smoke.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(result, indent=2, ensure_ascii=False))
