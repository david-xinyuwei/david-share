# Qwen3-ASR Training and Inference Validation on Azure

[![Azure GPU](https://img.shields.io/badge/Azure-H100%20NVL-0078D4)](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/)
[![Qwen3-ASR](https://img.shields.io/badge/Model-Qwen3--ASR-7B68EE)](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
[![vLLM](https://img.shields.io/badge/Serving-vLLM-16A34A)](https://docs.vllm.ai/en/latest/models/supported_models/)
[![ASR](https://img.shields.io/badge/Workload-ASR%20Engineering-4B8BBE)](https://huggingface.co/tasks/automatic-speech-recognition)

> **Author**: Xinyu Wei (Wei Xinyu) — Microsoft AI and Apps Global Black Belt (GBB) Senior System Engineer

English | [中文版](README-CN.md)

This repo is a field guide and validation harness for a customer-owned ASR stack: Qwen/Gemma-style backbone, Hugging Face training stack, and high-throughput serving engines such as vLLM, SGLang, and TensorRT-LLM.

The point is not to claim that one public model solves the customer's production workload. The point is to show how to validate the exact model route, training bottlenecks, serving latency, long-audio behavior, and Azure GPU fit with runnable scripts and raw JSON evidence.

---

## 1. What We Actually Ran

The table below is the current public evidence. It is intentionally scoped to public Qwen samples and Azure H100 tests; no customer audio or private endpoint is included.

| Area | Evidence | Raw data |
|---|---|---|
| Qwen3-ASR 0.6B inference | Loaded and transcribed official Chinese and English public samples on Azure H100 NVL 95GB | `results/h100/h100_0.6b_full_benchmark.json` |
| Qwen3-ASR 1.7B inference | Loaded and transcribed the same public samples on Azure H100 NVL 95GB | `results/h100/h100_1.7b_full_benchmark.json` |
| H100 batch throughput | Batch size 1/4/8/16 sweep for both 0.6B and 1.7B | `results/h100/h100_model_comparison.json` |
| Long-audio behavior | 30s, 60s, 180s synthetic long-audio test on Qwen3-ASR-1.7B | `results/h100/h100_long_audio_test.json` |
| vLLM serving feasibility | First vLLM endpoint attempt failed due to package/API version mismatch | `results/h100/h100_vllm_serving_benchmark.json` |
| Harness regression | WER/CER script, endpoint benchmark script, and py_compile checks pass | `results/harness_test_results.json` |

### H100 Model Comparison

| Metric | Qwen3-ASR-0.6B | Qwen3-ASR-1.7B | Reading |
|---|---:|---:|---|
| Model load | 5.8s | 4.9s | Both load quickly once weights are cached |
| Single request latency | 0.826s | **0.185s** | 1.7B was faster on this short Chinese sample |
| Batch 4 throughput | 19.38 req/s | 19.21 req/s | Similar small-batch throughput |
| Batch 8 throughput | **35.05 req/s** | 28.93 req/s | 0.6B higher on batch 8 |
| Batch 16 throughput | **55.13 req/s** | 51.74 req/s | Both exceed 50 short requests/sec on one H100 |
| 10-round P50 | 0.172s | 0.174s | Stable steady-state latency |
| 10-round P95 | 0.215s | **0.174s** | 1.7B had tighter tail latency |
| Chinese CER on official sample | 0.0% | 0.0% | Smoke-quality only, not customer quality |
| English public sample latency | 1.195s | **0.954s** | 1.7B faster here |

**Important boundary:** CER=0% here only means the public sample matched the known expected transcript. It is not a customer-domain WER/CER result.

### Long-Audio Finding

| Audio | Duration | Transcribe time | RTF | Output chars | Finding |
|---|---:|---:|---:|---:|---|
| Repeated Chinese sample | 30s | 1.769s | 0.0590 | 98 | Good short/medium path |
| Repeated Chinese sample | 60s | 2.044s | 0.0341 | 196 | Good short/medium path |
| Repeated Chinese sample | 180s | 82.726s | 0.4596 | 16 | **Failure mode: output collapsed** |
| Official English sample | 15.1s | 1.202s | 0.0799 | 188 | Normal |

This is the most useful result for a meeting-transcription customer: **do not feed long meetings as one opaque request.** A production pipeline needs VAD, chunking, overlap, stitching, optional forced alignment, and speaker diarization.

---

## 2. Customer Requirements Mapped to Evidence

| Customer requirement | What this repo can already show | What still needs customer input |
|---|---|---|
| Qwen/Gemma backbone | Qwen3-ASR 0.6B/1.7B H100 inference and long-audio evidence | Exact customer checkpoint; Gemma route if they use Gemma 3n or a custom Gemma audio model |
| Training with HF ecosystem | Official Qwen3-ASR fine-tuning entry point and JSONL format are documented | Customer training command, Accelerate/DeepSpeed/FSDP config, failure logs |
| vLLM/SGLang/TensorRT-LLM serving | vLLM officially supports Qwen3-ASR transcription; transformers backend benchmark is done | Clean vLLM env benchmark; SGLang/TRT-LLM feasibility for the exact model |
| Data storage and throughput | Scripts and methodology to profile audio decode / dataloader / endpoint throughput | Customer data layout, storage path, audio hours, codec, train/eval manifest |
| Training stability and speed | Training diagnosis checklist and official Qwen3-ASR SFT route | Real training logs, checkpoint behavior, multi-node topology |
| Quantized training stability | Decision table for BF16 vs QLoRA/FP8 validation | A real fine-tuning run and quantized training config |
| Inference latency and cost | H100 batch throughput, RTF, long-audio failure mode | Current baseline cost, target SLA, region/SKU pricing |
| Accuracy improvement | CER script and public-sample smoke CER | Customer or public eval dataset before/after fine-tuning |

---

## 3. Qwen3-ASR Fine-Tuning Path

Qwen3-ASR is similar in broad shape to audio-capable multimodal LLMs: audio waveform enters an audio frontend/encoder, becomes audio embeddings, and the decoder generates text. But for training, use the **official Qwen3-ASR fine-tuning path** instead of guessing from Phi-4-mm.

Official source: https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning

The official fine-tuning README says the script fine-tunes Qwen3-ASR using JSONL audio-text pairs and supports multi-GPU training via `torchrun`.

### Training Data Format

Each line is one audio-transcript pair:

```jsonl
{"audio":"/data/wavs/utt0001.wav","text":"language Chinese<asr_text>这是训练文本。"}
{"audio":"/data/wavs/utt0002.wav","text":"language English<asr_text>This is a test sentence."}
```

Use language prefixes when known:

```text
language Chinese<asr_text>...
language English<asr_text>...
language None<asr_text>...
```

### Single-GPU Fine-Tune

```bash
python qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-1.7B \
  --train_file ./train.jsonl \
  --output_dir ./qwen3-asr-finetuning-out \
  --batch_size 32 \
  --grad_acc 4 \
  --lr 2e-5 \
  --epochs 1 \
  --save_steps 200 \
  --save_total_limit 5
```

### Multi-GPU Fine-Tune

```bash
export CUDA_VISIBLE_DEVICES=0,1
torchrun --nproc_per_node=2 qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-1.7B \
  --train_file ./train.jsonl \
  --output_dir ./qwen3-asr-finetuning-out \
  --batch_size 32 \
  --grad_acc 4 \
  --lr 2e-5 \
  --epochs 1 \
  --save_steps 200
```

### Training Optimization Checklist

| Layer | What to tune | Metric |
|---|---|---|
| Data quality | transcript normalization, language prefix, bad-audio filtering | WER/CER and hard samples |
| Data throughput | `num_workers`, `pin_memory`, `persistent_workers`, `prefetch_factor`, local cache | samples/sec, audio-hours/sec, dataloader wait |
| GPU efficiency | BF16, FlashAttention 2, batch size, grad accumulation | step time, GPU utilization, HBM |
| Stability | save/resume, checkpoint interval, NCCL logs, loss spike monitoring | resume success, failure interval |
| Quantization | BF16 baseline first, then QLoRA/FP8 only with same data/eval | loss curve, WER/CER delta, memory |

### Accuracy Validation

The correct before/after loop is:

```text
same eval audio + same ground truth
    -> base Qwen3-ASR transcript
    -> fine-tuned checkpoint transcript
    -> WER/CER/hotword comparison
```

A public proxy dataset such as FLEURS can prove the training harness. Customer data is still required for domain-specific accuracy claims.

---

## 4. Inference Optimization After Fine-Tuning

Start with the transformers backend to confirm quality, then move to vLLM for serving optimization.

### Transformers Backend

Use this for correctness and debugging:

```python
from qwen_asr import Qwen3ASRModel
import torch

model = Qwen3ASRModel.from_pretrained(
    "qwen3-asr-finetuning-out/checkpoint-200",
    dtype=torch.bfloat16,
    device_map="cuda:0",
    max_inference_batch_size=32,
    max_new_tokens=512,
)

result = model.transcribe(audio="sample.wav", language="Chinese")
print(result[0].text)
```

### vLLM Backend

vLLM explicitly lists Qwen3-ASR under transcription models:

| vLLM route | Architecture | Example |
|---|---|---|
| Transcription | `Qwen3ASRForConditionalGeneration` | `Qwen/Qwen3-ASR-1.7B` |
| Realtime transcription | `Qwen3ASRRealtimeGeneration` | `Qwen/Qwen3-ASR-0.6B` |

Official Qwen command:

```bash
pip install -U qwen-asr[vllm]
qwen-asr-serve Qwen/Qwen3-ASR-1.7B \
  --gpu-memory-utilization 0.8 \
  --host 0.0.0.0 \
  --port 8000
```

Important: create a clean environment. In our H100 system environment, `qwen-asr` and vLLM package APIs conflicted (`vllm.inputs.data` missing), so the server did not start. That is a real deployment lesson: **pin the Qwen/vLLM/Transformers versions together and test the endpoint before promising vLLM production throughput.**

### SGLang and TensorRT-LLM Boundary

| Engine | Current support statement |
|---|---|
| vLLM | Official support for Qwen3-ASR transcription/realtime transcription is documented |
| SGLang | High-performance LLM/multimodal serving framework, but no confirmed Qwen3-ASR transcription endpoint in the docs checked here |
| TensorRT-LLM | Useful for decoder-heavy LLM paths, but full audio frontend + ASR pipeline support must be validated per model |

Do not claim SGLang or TensorRT-LLM supports the customer's ASR model until the exact checkpoint runs with the target audio endpoint contract.

---

## 5. Reproduce the Current Evidence

### Local Harness

```bash
python3 scripts/run_harness_tests.py
python3 scripts/eval_asr_metrics.py --reference ref.txt --hypothesis hyp.txt --output results/asr_metrics.json
python3 scripts/benchmark_endpoint.py --url http://127.0.0.1:8000/v1/audio/transcriptions --audio sample.wav
```

### Qwen3-ASR Smoke Test

```bash
python3 scripts/qwen3_asr_transformers_smoke.py \
  --model Qwen/Qwen3-ASR-0.6B \
  --audio https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_zh.wav \
  --language Chinese \
  --output results/qwen3_asr_smoke.json
```

### H100 Benchmark Results

Raw files:

```text
results/h100/h100_0.6b_full_benchmark.json
results/h100/h100_1.7b_full_benchmark.json
results/h100/h100_model_comparison.json
results/h100/h100_long_audio_test.json
results/h100/h100_vllm_serving_benchmark.json
```

---

## 6. What to Ask the Customer Onsite

1. What exact Qwen/Gemma checkpoint are you training?
2. Is the architecture dedicated ASR, audio LLM, Gemma audio, or custom audio encoder + LLM?
3. What is the training command and HF stack: Accelerate, Transformers Trainer, TRL, DeepSpeed, FSDP, or custom?
4. What is the current data layout: object store, disk, NFS, local cache, feature cache?
5. What fails in training: data loader, OOM, NCCL, checkpoint, quantized training, or eval WER?
6. Which serving path is production: vLLM, SGLang, TensorRT-LLM, TensorRT, or custom endpoint?
7. What are the current RTF, P50/P95, throughput, GPU utilization, and cost per audio hour?
8. Can they provide 30-60 minutes of de-identified audio with human transcript and hotwords?

---

## 7. Current Limitations

- We have not yet run Qwen3-ASR fine-tuning in this repo.
- We have not yet run FLEURS or customer-data before/after WER/CER.
- We have not yet validated Gemma audio models.
- vLLM serving is officially supported, but our first endpoint attempt failed due to package API mismatch.
- SGLang and TensorRT-LLM remain feasibility checks for ASR, not confirmed recommendations.
- Public samples do not represent the customer's meeting audio, device microphones, accents, noise, diarization, or hotwords.

---

## References

| Topic | Source |
|---|---|
| Qwen3-ASR model card | https://huggingface.co/Qwen/Qwen3-ASR-1.7B |
| Qwen3-ASR GitHub | https://github.com/QwenLM/Qwen3-ASR |
| Qwen3-ASR official fine-tuning | https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning |
| vLLM supported models | https://docs.vllm.ai/en/latest/models/supported_models/ |
| SGLang docs | https://docs.sglang.io/ |
| TensorRT-LLM multimodal support | https://nvidia.github.io/TensorRT-LLM/features/multi-modality.html |
| Hugging Face Accelerate | https://huggingface.co/docs/accelerate/index |
| Hugging Face Transformers | https://huggingface.co/docs/transformers/index |
| Hugging Face TRL | https://huggingface.co/docs/trl/index |
| FLEURS dataset | https://huggingface.co/datasets/google/fleurs |
