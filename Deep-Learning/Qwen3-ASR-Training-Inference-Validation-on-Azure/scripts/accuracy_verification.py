#!/usr/bin/env python3
"""Accuracy verification: same audio, three inference modes, compare CER against ground truth.
Proves that vLLM/CUDA Graph acceleration is lossless.
"""
import json, re, time, subprocess, glob
from pathlib import Path
import numpy as np

VLLM_BIN = "/root/miniconda3/envs/asr-vllm/bin/python"
RESULTS = Path("/root/asr_results")
N_SAMPLES = 20  # enough to verify, fast enough to complete

def normalize(text):
    text = text.strip().lower()
    text = re.sub(r'[\u3000\s]+', ' ', text)
    text = re.sub(r'[，。！？、；：,.!?;:\"\'()\[\]{}<>《》""''\-·…—]+', '', text)
    return text.replace(' ', '')

def char_cer(ref, hyp):
    """Simple CER: edit_distance(ref_chars, hyp_chars) / len(ref_chars)"""
    r = list(normalize(ref))
    h = list(normalize(hyp))
    if not r:
        return 0.0 if not h else 1.0
    # DP edit distance
    d = [[0]*(len(h)+1) for _ in range(len(r)+1)]
    for i in range(len(r)+1): d[i][0] = i
    for j in range(len(h)+1): d[0][j] = j
    for i in range(1, len(r)+1):
        for j in range(1, len(h)+1):
            d[i][j] = min(d[i-1][j]+1, d[i][j-1]+1, d[i-1][j-1]+(0 if r[i-1]==h[j-1] else 1))
    return d[len(r)][len(h)] / len(r)

# Load ground truth from FLEURS
from datasets import load_dataset
ds = load_dataset("google/fleurs", "cmn_hans_cn", split="test")
ds = ds.select(range(N_SAMPLES))
refs = [s["transcription"] for s in ds]
wav_paths = sorted(glob.glob("/root/asr_results/fleurs_wav/*.wav"))[:N_SAMPLES]
print(f"Testing {N_SAMPLES} samples against ground truth")

# ============================================================
# Mode 1: Transformers direct (baseline, known good)
# ============================================================
print("\n[Mode 1] Transformers direct inference...")
import torch
from qwen_asr import Qwen3ASRModel

model = Qwen3ASRModel.from_pretrained("Qwen/Qwen3-ASR-1.7B", dtype=torch.bfloat16, device_map="cuda")
tf_hyps = []
t0 = time.time()
for p in wav_paths:
    r = model.transcribe([p])
    tf_hyps.append(r[0].text)
tf_time = time.time() - t0
del model
torch.cuda.empty_cache()
time.sleep(3)

tf_cers = [char_cer(ref, hyp) for ref, hyp in zip(refs, tf_hyps)]
print(f"  CER: mean={np.mean(tf_cers)*100:.2f}% | time={tf_time:.1f}s")

# ============================================================
# Mode 2: vLLM CUDA Graph ON (default)
# ============================================================
print("\n[Mode 2] vLLM CUDA Graph ON...")
# Start server
subprocess.run(f"nohup {VLLM_BIN} -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-ASR-1.7B --port 8201 --max-model-len 4096 > /tmp/vllm_acc_cg.log 2>&1 &", shell=True)

import urllib.request
for i in range(90):
    try:
        urllib.request.urlopen("http://localhost:8201/health", timeout=3)
        break
    except:
        time.sleep(3)
else:
    print("  ERROR: vLLM CUDA Graph server failed to start")
    subprocess.run("pkill -f 'vllm.*8201'", shell=True)
    cg_hyps = [""] * N_SAMPLES
    cg_time = 0

if 'cg_hyps' not in dir():
    # Send transcription requests
    cg_hyps = []
    t0 = time.time()
    for p in wav_paths:
        try:
            import io
            boundary = "----Boundary"
            body = io.BytesIO()
            body.write(f"--{boundary}\r\n".encode())
            body.write(b"Content-Disposition: form-data; name=\"model\"\r\n\r\n")
            body.write(b"Qwen/Qwen3-ASR-1.7B\r\n")
            body.write(f"--{boundary}\r\n".encode())
            body.write(b"Content-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n")
            body.write(b"Content-Type: audio/wav\r\n\r\n")
            with open(p, "rb") as f:
                body.write(f.read())
            body.write(b"\r\n")
            body.write(f"--{boundary}--\r\n".encode())
            data = body.getvalue()
            req = urllib.request.Request("http://localhost:8201/v1/audio/transcriptions",
                data=data, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            cg_hyps.append(result.get("text", ""))
        except Exception as e:
            cg_hyps.append(f"ERROR:{e}")
    cg_time = time.time() - t0

subprocess.run("pkill -f 'vllm.*8201'", shell=True)
time.sleep(10)

cg_cers = [char_cer(ref, hyp) for ref, hyp in zip(refs, cg_hyps)]
print(f"  CER: mean={np.mean(cg_cers)*100:.2f}% | time={cg_time:.1f}s")

# ============================================================
# Mode 3: vLLM enforce-eager (CUDA Graph OFF)
# ============================================================
print("\n[Mode 3] vLLM --enforce-eager (CUDA Graph OFF)...")
subprocess.run(f"nohup {VLLM_BIN} -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-ASR-1.7B --port 8202 --max-model-len 4096 --enforce-eager > /tmp/vllm_acc_eager.log 2>&1 &", shell=True)

for i in range(90):
    try:
        urllib.request.urlopen("http://localhost:8202/health", timeout=3)
        break
    except:
        time.sleep(3)
else:
    print("  ERROR: vLLM eager server failed to start")
    eager_hyps = [""] * N_SAMPLES

if 'eager_hyps' not in dir():
    eager_hyps = []
    t0 = time.time()
    for p in wav_paths:
        try:
            body = io.BytesIO()
            body.write(f"--{boundary}\r\n".encode())
            body.write(b"Content-Disposition: form-data; name=\"model\"\r\n\r\n")
            body.write(b"Qwen/Qwen3-ASR-1.7B\r\n")
            body.write(f"--{boundary}\r\n".encode())
            body.write(b"Content-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n")
            body.write(b"Content-Type: audio/wav\r\n\r\n")
            with open(p, "rb") as f:
                body.write(f.read())
            body.write(b"\r\n")
            body.write(f"--{boundary}--\r\n".encode())
            data = body.getvalue()
            req = urllib.request.Request("http://localhost:8202/v1/audio/transcriptions",
                data=data, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            eager_hyps.append(result.get("text", ""))
        except Exception as e:
            eager_hyps.append(f"ERROR:{e}")
    eager_time = time.time() - t0
else:
    eager_time = 0

subprocess.run("pkill -f 'vllm.*8202'", shell=True)

eager_cers = [char_cer(ref, hyp) for ref, hyp in zip(refs, eager_hyps)]
print(f"  CER: mean={np.mean(eager_cers)*100:.2f}% | time={eager_time:.1f}s")

# ============================================================
# Comparison
# ============================================================
print("\n" + "="*60)
print("ACCURACY COMPARISON (same 20 samples, same ground truth)")
print("="*60)
print(f"  Transformers:        CER={np.mean(tf_cers)*100:.2f}%  ({tf_time:.1f}s)")
print(f"  vLLM CUDA Graph ON:  CER={np.mean(cg_cers)*100:.2f}%  ({cg_time:.1f}s)")
print(f"  vLLM CUDA Graph OFF: CER={np.mean(eager_cers)*100:.2f}%  ({eager_time:.1f}s)")
print(f"\n  Text match (TF vs CG ON): {sum(1 for a,b in zip(tf_hyps, cg_hyps) if normalize(a)==normalize(b))}/{N_SAMPLES}")
print(f"  Text match (TF vs CG OFF): {sum(1 for a,b in zip(tf_hyps, eager_hyps) if normalize(a)==normalize(b))}/{N_SAMPLES}")
print("="*60)

# Check for ERROR responses
cg_errors = sum(1 for h in cg_hyps if h.startswith("ERROR"))
eager_errors = sum(1 for h in eager_hyps if h.startswith("ERROR"))
if cg_errors or eager_errors:
    print(f"\n⚠️  vLLM errors: CG={cg_errors}/{N_SAMPLES}, Eager={eager_errors}/{N_SAMPLES}")
    print("  First CG error:", next((h for h in cg_hyps if h.startswith("ERROR")), "none"))

# Save results
result = {
    "n_samples": N_SAMPLES,
    "transformers": {"cer_mean": round(float(np.mean(tf_cers)), 4), "time_s": round(tf_time, 1)},
    "vllm_cuda_graph_on": {"cer_mean": round(float(np.mean(cg_cers)), 4), "time_s": round(cg_time, 1), "errors": cg_errors},
    "vllm_cuda_graph_off": {"cer_mean": round(float(np.mean(eager_cers)), 4), "time_s": round(eager_time, 1), "errors": eager_errors},
    "text_match_tf_vs_cg": sum(1 for a,b in zip(tf_hyps, cg_hyps) if normalize(a)==normalize(b)),
    "text_match_tf_vs_eager": sum(1 for a,b in zip(tf_hyps, eager_hyps) if normalize(a)==normalize(b)),
    "examples": [{"ref": refs[i], "tf": tf_hyps[i], "cg": cg_hyps[i], "eager": eager_hyps[i]} for i in range(min(5, N_SAMPLES))],
}
json.dump(result, open(RESULTS / "accuracy_verification.json", "w"), indent=2, ensure_ascii=False)
print(f"\nSaved: {RESULTS / 'accuracy_verification.json'}")
