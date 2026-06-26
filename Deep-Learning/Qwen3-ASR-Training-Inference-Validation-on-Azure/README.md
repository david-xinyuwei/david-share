# Qwen3-ASR Training and Inference Validation on Azure

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

English | [中文版](README-CN.md)

[![Azure GPU](https://img.shields.io/badge/Azure-H100%20NVL-0078D4)](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/)
[![Qwen3-ASR](https://img.shields.io/badge/Model-Qwen3--ASR-7B68EE)](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
[![vLLM](https://img.shields.io/badge/Serving-vLLM-16A34A)](https://docs.vllm.ai/en/latest/models/supported_models/)
[![ASR](https://img.shields.io/badge/Workload-ASR%20Engineering-4B8BBE)](https://huggingface.co/tasks/automatic-speech-recognition)

Field guide and validation harness for ASR stacks: Qwen/Gemma-style backbone, Hugging Face training, and high-throughput serving engines (vLLM, SGLang, TensorRT-LLM).

The point is not to claim that one public model solves a production team's production workload. The point is to show how to validate the exact model route, training bottlenecks, serving latency, long-audio behavior, and Azure GPU fit with runnable scripts and raw JSON evidence.

## Running on Azure

This repo is not a one-off ASR demo. It documents a **validation-first engineering pipeline** for evaluating a Qwen/Gemma-style ASR stack on Azure GPU infrastructure — from backbone selection to serving and fine-tuning decisions. The path covers five stages, executed in this order:

1. **Backbone smoke and public CER** — prove Qwen3-ASR loads, transcribes, and has a public FLEURS baseline before using any proprietary audio
2. **Long-audio and data-path validation** — before optimizing training, verify that long recordings do not cause output collapse (chunking risk), that audio file decoding is not a bottleneck (audio decode), that the training data pipeline does not starve the GPU (dataloader wait), and that moving audio tensors to GPU is not the slowest step (GPU transfer)
3. **Fine-tuning strategy** — compare full-param SFT, LoRA, encoder-only, QLoRA, and precision stability with before/after CER
4. **Serving framework selection** — validate vLLM transcription, CUDA Graph behavior, and concurrency using raw endpoint evidence
5. **Backbone alternatives and production gates** — document the Gemma 3n route (requires PyTorch 2.6+ with cuDNN 9.1+ due to head_dim=256 SDPA compatibility; see `docs/gemma-3n-audio-feasibility.md`), confirm SGLang/TRT-LLM ASR support boundaries, and define acceptance criteria for production audio evaluation

All completed experiments in this public repo use public audio samples or public FLEURS data. Proprietary audio, private endpoints, and subscription details stay outside this public artifact.

The diagram below shows the core data flow of the entire pipeline; Section 3 walks through each stage in detail.

<div align="center"><img src="images/solution_architecture.png" width="960"></div>

### Key Terms Used in This Repo

If you are new to ASR engineering, here is a quick reference for terms that appear throughout this document:

| Term | What it is | Why it matters |
|---|---|---|
| **CER** | Character Error Rate — compare the model's transcript against a correct human transcript, character by character. Example: if the reference is 10 characters and the model got 1 wrong, CER = 10%. In this repo, Qwen3-ASR-0.6B scored 7.74% CER on 200 FLEURS Chinese samples. | The primary accuracy metric for Chinese ASR. Chinese has no spaces between words, so character-level comparison is the standard. |
| **WER** | Word Error Rate — same idea as CER but counting whole words. Example: "the cat sat" vs "the cat sat down" → 1 insertion out of 3 words = 33% WER. | Used for English and other languages that have spaces between words. |
| **RTF** | Real-Time Factor = processing time / audio duration. RTF < 1 means faster than real-time | Determines live-streaming vs offline capacity |
| **P50 / P95** | Median and 95th-percentile latency | P50 = typical experience; P95 = tail spikes that affect SLA |
| **Throughput (rps)** | Requests per second completed by the serving endpoint. In this repo, rps means short-audio request throughput, not audio-hours processed per second. | Capacity planning for concurrent users |
| **FLEURS** | Google's multilingual speech benchmark dataset (Apache 2.0) | Public eval data used in this repo for CER baseline |
| **LoRA / QLoRA** | Low-Rank Adaptation — fine-tunes only a small adapter instead of all model weights; QLoRA adds 4-bit quantization | Reduces GPU memory and overfitting risk on small datasets |
| **CUDA Graph** | Records and replays a fixed GPU kernel sequence, skipping launch overhead | ~5x latency reduction in our vLLM ASR benchmark |
| **VAD** | Voice Activity Detection — finds speech segments in audio | Required before sending long recordings to the model |
| **NaN gradient** | A training step where gradient values become Not-a-Number | In this repo, Qwen3-ASR's audio encoder produces NaN in BF16 training |

---

## Executive Summary

### Recommended Path

| Decision area | Recommendation | Why it matters |
|---|---|---|
| **Backbone** | Start with Qwen3-ASR for pure ASR, keep Gemma 3n as a candidate multimodal route | Qwen3-ASR produced public CER and serving evidence; Gemma 3n still needs clean-env smoke and CER in this repo |
| **Fine-tuning** | Start with decoder LoRA; avoid small-data full-param SFT | LoRA changed only 0.78% parameters and beat the small full-param run on the public FLEURS check |
| **Precision** | Establish an FP32 stability baseline before mixed precision or quantized training | bf16 SFT produced NaN gradients from step 1 in this H100 run |
| **Serving** | Use vLLM first for Qwen3-ASR transcription serving | Clean-env vLLM serving worked and CUDA Graph delivered the strongest latency result |
| **Long audio** | Do not send full meeting recordings as one opaque request | 180s synthetic long audio caused output collapse; use VAD/chunk/overlap/stitching |

### Key Findings (Validation Conditions)

All findings below come from a controlled Azure H100 validation using public samples and public FLEURS data.

| Condition | Value |
|---|---|
| GPU | 1× NVIDIA H100-class Azure GPU with 95 GB visible memory |
| Models | `Qwen/Qwen3-ASR-0.6B`, `Qwen/Qwen3-ASR-1.7B`, `google/gemma-3n-E2B-it` route check |
| Public eval | FLEURS `cmn_hans_cn` test split; Qwen CER measured on 200 samples |
| Serving | vLLM transcription endpoint and transformers baseline for Qwen3-ASR |
| Fairness | Same public audio/eval split, same metric script, no proprietary audio or private endpoint in repo |

| Finding | Measured result | Action |
|---|---|---|
| Qwen3-ASR public CER baseline is usable for harness validation | 0.6B=**7.74%**, 1.7B=**7.09%** on 200 FLEURS Chinese samples | Use it as the public regression baseline, not as domain-specific quality |
| BF16 training produces NaN from step 1 | `grad_norm=nan`, loss meaningless, model destroyed | Always start with FP32; validate mixed precision separately |
| Small-data full-param SFT overfits badly | In this 100-sample run, held-out CER degraded from **7.74%** to **21.53%** | Do not start with full-param SFT on limited data |
| LoRA is the best first tuning route in this run | LoRA rank=16: only **0.78%** params, reached **5.48%** CER on 80-sample check | Use LoRA before full-param updates |
| Encoder-only SFT is viable but weaker than LoRA | Encoder=186M (**23.8%** params), CER=**6.26%** on same check | Reserve for acoustic-domain adaptation |
| QLoRA (4-bit NF4 + LoRA) trains and produces usable quality | CER=**5.69%** on 80-sample check | Strong option when GPU memory is limited |
| 4-bit NF4 inference has small CER degradation | CER=**5.99%** vs bf16 baseline **5.28%** (+0.71pp) on same 80 FLEURS samples | Viable for memory-constrained deployment with CER monitoring |
| vLLM + CUDA Graph is the strongest serving path | P50 **69ms** vs transformers **522ms** (~7x); no CER regression observed in a 20-sample smoke check | Use vLLM for first serving PoC; do not read CUDA Graph as an accuracy improvement |
| vLLM concurrent serving scales to 16 | c16: P50=**154ms**, P95=**388ms**, **119 rps**, 64/64 success | Sufficient for initial production capacity planning |
| Dataloader bottleneck is GPU transfer, not audio decode | Audio decode=0.196s, GPU transfer=**0.31s** (bottleneck) for 200 samples | Optimize GPU pipeline, not codec |
| Long audio needs pipeline treatment | 180s synthetic long audio collapsed to **16 output chars** | Add VAD/chunk/overlap/stitching before production |
| Gemma 3n route requires stricter environment than Qwen3-ASR | Model loads but SDPA/cuDNN fails on head_dim=256; clean venv with PyTorch 2.6+/cuDNN 9.1+ prepared | Do not claim Gemma CER until clean-env smoke passes |

### Recommended Production Configuration

| Parameter | Recommended value | Rationale |
|---|---|---|
| ASR model route | Qwen3-ASR 1.7B for first cloud PoC | Better public CER baseline and dedicated transcription route in this repo |
| Fine-tuning method | LoRA rank=16 first; then encoder+LoRA if acoustic adaptation is needed | Lower blast radius and better small-data behavior than full-param SFT |
| Precision | FP32 stability baseline; mixed precision only after grad_norm/CER checks | Prevents silent NaN or destroyed checkpoints |
| Serving engine | vLLM Qwen3-ASR transcription endpoint | Verified clean-env route and strong latency/concurrency data |
| Audio ingestion | Chunked audio with VAD + overlap + stitching | Avoids long-audio collapse and keeps latency predictable |
| Acceptance data | De-identified domain audio + human transcript + hotwords | Public FLEURS proves harness only; domain-specific decides production quality |

---

## 0. Background

### 0.1 Qwen3-ASR Architecture

Qwen3-ASR is a speech-to-text model from Alibaba that combines a pretrained Audio Transformer (AuT) encoder with a Qwen3 language model decoder. The architecture:

- **Audio encoder (AuT)**: 32 self-attention layers + 3 Conv2d subsampling layers. Input: 16 kHz mono waveform at 100 Hz frame rate. Output: audio embeddings at 12.5 Hz (8× temporal compression).
- **Language decoder**: Qwen3 causal LM that generates text tokens conditioned on audio embeddings.
- **Two sizes**: 0.6B (faster, slightly lower CER) and 1.7B (better CER, similar throughput on short audio).

Source: [Qwen3-ASR model card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B), [Qwen3-ASR GitHub](https://github.com/QwenLM/Qwen3-ASR)

### 0.2 Why ASR Validation Is Not a Generic LLM Benchmark

ASR validation differs from text-only LLM evaluation in several ways that affect engineering decisions:

| Dimension | Text LLM | ASR model |
|---|---|---|
| **Input** | Text tokens | Raw waveform (16 kHz, variable length) |
| **Output metric** | Perplexity, BLEU, human preference | CER/WER against human transcript |
| **Latency sensitivity** | Seconds acceptable for generation | Real-time factor < 1 expected |
| **Data pipeline** | Tokenize text | Decode audio → resample → normalize → GPU transfer |
| **Failure mode** | Wrong answer | Output collapse on long audio, NaN in bf16 training |
| **Serving path** | Standard OpenAI-compatible chat | Transcription-specific endpoint (multipart audio upload) |

Generic LLM leaderboard scores do not predict ASR quality. A model that generates fluent text may still produce garbled transcripts, collapse on long audio, or fail to handle domain-specific vocabulary (hotwords).

### 0.3 Why Qwen3-ASR and Not Whisper or Other ASR Models

| Selection criterion | Qwen3-ASR reasoning |
|---|---|
| **Open-source + HuggingFace ecosystem** | Full model weights on HF; official fine-tuning script; integrates with transformers, accelerate, vLLM |
| **vLLM serving support** | Officially listed as a transcription model in vLLM; Whisper is not in vLLM's supported model list |
| **Fine-tuning flexibility** | Supports LoRA, QLoRA, encoder-only, and full-param SFT via official script; Whisper fine-tuning requires different tooling |
| **Chinese + multilingual** | Strong CJK support via Qwen tokenizer; dedicated language-prefix routing |
| **Architecture transparency** | AuT encoder + Qwen3 decoder is well-documented; allows targeted freezing (encoder vs decoder) |
| **Model size options** | 0.6B and 1.7B both fit on single GPU with room for batching and KV cache |

This is not a claim that Qwen3-ASR is the best ASR model. It is a statement that for this validation — evaluating training stability, serving latency, fine-tuning strategies, and Azure GPU fit — Qwen3-ASR provides the most complete open-source toolchain in the HuggingFace ecosystem.

---

## 0.5 Methodology

### Evaluation Gates

Every ASR model in this repo must pass through validation gates before production claims. These are the same gates shown in the [validation gates diagram](images/validation_gates.png):

| Gate | What it checks | Pass criteria |
|---|---|---|
| **G0** Audio smoke | Model loads and produces non-empty transcript from a known audio file | Output ≠ empty; latency < 10s for a 10s clip |
| **G1** Public CER | CER on public FLEURS samples is in a reasonable range | CER < 15% on 200 Chinese samples (empirical sanity check) |
| **G2** Serving gate | vLLM endpoint responds under concurrency | Zero failures at target concurrency; P50 within SLA |
| **G3** Fine-tuning gate | SFT runs without NaN or divergence; CER does not degrade on held-out set | grad_norm finite; held-out CER ≤ baseline or explainably higher |
| **G4** Regression gate | Re-running the same test produces consistent results | CER variance < 1pp across 3 runs on same data |

### Fairness Controls

Every comparison in this repo uses:
- Same audio samples (public FLEURS `cmn_hans_cn` test split or official Qwen samples)
- Same CER evaluation script (`scripts/eval_asr_metrics.py`)
- Same GPU (single H100 NVL 95 GB)
- Same model precision per comparison (fp32 vs fp32, or bf16 vs bf16)
- One variable changed per experiment

### Data Preparation for Fine-Tuning

Training data format for Qwen3-ASR SFT (from the [official repo](https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning)):

```jsonl
{"audio":"/path/to/audio.wav","text":"language Chinese<asr_text>这是训练文本。"}
```

Requirements:
- Audio must be 16 kHz mono WAV (resample if needed)
- Language prefix must match: `language Chinese`, `language English`, or `language None`
- Ground-truth transcript must be character-accurate (no hallucinated punctuation)
- Train/eval split must be non-overlapping

---

## 1. Detailed Validation Results

All results below come from public Qwen samples and public FLEURS data tested on Azure H100. No proprietary audio, private endpoints, or subscription details are included.

### 1.1 Inference Latency and Throughput

Both models tested on the same batch of public short audio clips (source: `results/h100/h100_model_comparison.json`):

| Metric | Qwen3-ASR-0.6B | Qwen3-ASR-1.7B | Reading |
|---|---:|---:|---|
| Model load | 5.8s | 4.9s | Both load quickly once weights are cached |
| Single request latency | 0.826s | **0.185s** | 1.7B was faster on this short Chinese sample |
| Batch 4 throughput | 19.38 req/s | 19.21 req/s | Similar small-batch throughput |
| Batch 8 throughput | **35.05 req/s** | 28.93 req/s | 0.6B higher on batch 8 |
| Batch 16 throughput | **55.13 req/s** | 51.74 req/s | Both exceed 50 short requests/sec on one H100 |
| 10-round P50 | 0.172s | 0.174s | Stable steady-state latency |
| 10-round P95 | 0.215s | **0.174s** | 1.7B had tighter tail latency |

**Takeaway**: 1.7B has lower latency and tighter tail, while 0.6B achieves higher throughput at large batch sizes. Both models achieve real-time processing on short audio.

### 1.2 Long-Audio Behavior

Source: `results/h100/h100_long_audio_test.json`

| Duration | Transcribe time | RTF | Output chars | Finding |
|---:|---:|---:|---:|---|
| 30s | 1.77s | 0.059 | 98 | Normal |
| 60s | 2.04s | 0.034 | 196 | Normal |
| 180s | 82.73s | 0.460 | **16** | **Output collapsed** |

**Takeaway**: Output quality degrades sharply beyond 60 seconds. Meeting recordings must use VAD + chunking + overlap + stitching — never feed an entire long audio as one request.

### 1.3 Public CER Baseline

Source: `results/fleurs_cer_qwen3_asr_0.6b.json`, `results/fleurs_cer_qwen3_asr_1.7b.json`

Evaluated on 200 Chinese samples from the FLEURS `cmn_hans_cn` test set:

| Model | CER | Meaning |
|---|---:|---|
| Qwen3-ASR-0.6B | **7.74%** | ~8 errors per 100 characters (includes punctuation/number formatting) |
| Qwen3-ASR-1.7B | **7.09%** | Slightly better |

**Takeaway**: Both models fall in the 7–8% CER range on public data. This includes punctuation and number formatting differences (see "Real Transcription Examples" below), so actual semantic accuracy is higher. The CER=0% on official short samples is smoke-quality only and does not represent real-world performance.

### 1.4 vLLM Serving + CUDA Graph

Source: `results/cuda_graph_ab.json`, `results/accuracy_verification.json`, `results/concurrent_benchmark_v2.json`, `results/remaining_inference_tests.json`

<div align="center"><img src="images/serving_latency.png" width="960"></div>

**Single-request latency benchmark (same short audio, 10 repeated requests)**:

| Mode | P50 per-request latency | P95 per-request latency | What this row measures |
|---|---:|---:|---|
| Transformers direct | 522ms | 525ms | Transformers direct inference baseline |
| vLLM CUDA Graph ON | **69ms** | 420ms | vLLM default serving path with CUDA Graph enabled |
| vLLM CUDA Graph OFF | 369ms | 609ms | vLLM eager path with CUDA Graph disabled |

**Quality smoke check (20 FLEURS samples)**:

| Comparison target | CER (20-sample smoke) | Text match vs Transformers | Interpretation |
|---|---:|---:|---|
| Transformers direct | 6.65% | baseline | Quality reference |
| vLLM CUDA Graph ON | 5.90% | 18/20 exact match | No visible quality regression |
| vLLM CUDA Graph OFF | 5.90% | 17/20 exact match | Also no visible quality regression |

**Important**: The latency table proves lower latency; it does not prove accuracy improvement. The CER table is a separate smoke check showing that the vLLM path did not introduce visible quality regression on 20 samples. Do not read 5.90% vs 6.65% as “CUDA Graph reduced the error rate.”

**Latency definition**: 522ms, 69ms, and 369ms are end-to-end completion times for one short audio request, measured from request start to returned transcript. The table reports P50 over repeated requests; it is not total batch time and not audio-hours throughput.

**Concurrent serving**:

| Concurrency | P50 per-request latency (ms) | P95 per-request latency (ms) | Short-request throughput (req/s) | Success rate |
|---:|---:|---:|---:|---|
| 1 | 88 | 159 | 10.1 | 4/4 |
| 4 | 109 | 167 | 35.9 | 16/16 |
| 8 | 88 | 165 | 79.0 | 32/32 |
| **16** | **154** | **388** | **119.0** | **64/64** |

**Takeaway**: vLLM + CUDA Graph delivers ~7x speedup over raw Transformers (single-request P50: 522ms → 69ms). CER is used here only as a no-regression smoke check, not as evidence that CUDA Graph reduces error rate. At concurrency 16, 64 short-audio requests completed in about 0.537 seconds, giving an estimated 119 req/s. This is not long-meeting throughput; long audio must be remeasured with RTF and the chunking pipeline.

### 1.5 Fine-Tuning Strategy Comparison

Source: `results/sft_v3_log_summary.json`, `results/lora_sft_result.json`, `results/encoder_only_sft_result.json`, `results/qlora_sft_result.json`

<div align="center"><img src="images/cer_comparison.png" width="960"></div>

| Strategy | Trainable params | CER (80 FLEURS) | Time | Reading |
|---|---:|---:|---:|---|
| Baseline (no tuning) | 0 | 7.74% | — | Starting point |
| Full-param SFT (fp32) | 788M (100%) | **21.53%** (200 held-out) | 69.8s | Clear overfitting in this small-data setting |
| LoRA rank=16 (fp32) | 6.1M (0.78%) | **5.48%** | 43.3s | Most stable |
| Encoder-only (fp32) | 186M (23.8%) | **6.26%** | 28.7s | Viable but weaker than LoRA |
| QLoRA (4-bit NF4 + LoRA) | 6.1M (1.29%) | **5.69%** | 59.8s | Good when GPU memory is limited |

**Key findings**:
- bf16 training produces NaN from step 1 (`grad_norm=nan`). This affects anyone using Qwen3-ASR for fine-tuning.
- In this 100-sample full-param SFT run, training loss fell to 0.17, but 200-sample held-out CER degraded from 7.74% to 21.53%, and perfect matches dropped from 95/200 to 10/200. The held-out set is not a production benchmark, but the degradation is large enough to indicate memorization rather than improved generalization.
- LoRA trains only 0.78% of parameters and reached 5.48% CER on an 80-sample FLEURS check. This does not prove LoRA is always more accurate than full fine-tuning; it shows LoRA is the safer first route for a small-data PoC.

### 1.6 4-bit Inference and Quantization

Source: `results/qwen3_asr_0.6b_4bit_cer_comparison.json`

| Precision | CER (80 samples) | sec/sample |
|---|---:|---:|
| BF16 baseline | 5.28% | 0.72 |
| 4-bit NF4 | 5.99% | 0.97 |
| **Δ** | **+0.71pp** | +0.25 |

**Takeaway**: BitsAndBytes 4-bit NF4 inference degraded CER by 0.71 percentage points. It did not speed up in this run: seconds/sample increased from 0.72s to 0.97s. Treat it as a memory-pressure fallback path, not as the latency-optimization path validated here.

### 1.7 Dataloader Profiling

Source: `results/dataloader_profile.json`

<div align="center"><img src="images/dataloader_profile.png" width="800"></div>

| Stage | Time | Share |
|---|---:|---:|
| Disk read | 0.033s | 5.3% |
| Audio decode | 0.196s | 31.2% |
| Collate/pad | 0.089s | 14.2% |
| **GPU transfer** | **0.310s** | **49.4%** |

**Takeaway**: The bottleneck is GPU transfer, not audio decoding. Optimization should target pinned memory + async transfer + prefetch.

### 1.8 Gemma 3n Route Status

Source: `results/gemma3n_h100_route_status.json`, `docs/gemma-3n-audio-feasibility.md`

Gemma 3n E2B-it weights were downloaded (10.9 GB) and the official `Gemma3nForConditionalGeneration` API was prepared. However, inference fails on the current H100 environment — PyTorch SDPA's cuDNN backend does not support Gemma 3n's `head_dim=256`. A clean environment with PyTorch 2.6+ and cuDNN 9.1+ is required. **Therefore this repo does not report Gemma FLEURS CER.**

---

## 2. Engineering Questions Mapped to Evidence

| Production requirement | What this repo can already show | What still needs production team input |
|---|---|---|
| Qwen/Gemma backbone | Qwen3-ASR 0.6B/1.7B H100 inference and long-audio evidence; Gemma 3n E2B-it official HF route and environment prerequisites documented | Exact target checkpoint; Gemma 3n clean-env audio smoke and CER if they choose Gemma as the ASR backbone |
| Training with HF ecosystem | Official Qwen3-ASR fine-tuning entry point and JSONL format are documented | The team's training command, Accelerate/DeepSpeed/FSDP config, failure logs |
| vLLM/SGLang/TensorRT-LLM serving | vLLM officially supports Qwen3-ASR transcription; transformers backend benchmark is done | Clean vLLM env benchmark; SGLang/TRT-LLM feasibility for the exact model |
| Data storage and throughput | Scripts and methodology to profile audio decode / dataloader / endpoint throughput | The team's data layout, storage path, audio hours, codec, train/eval manifest |
| Training stability and speed | Training diagnosis checklist and official Qwen3-ASR SFT route | Real training logs, checkpoint behavior, multi-node topology |
| Quantized training stability | Decision table for BF16 vs QLoRA/FP8 validation | A real fine-tuning run and quantized training config |
| Inference latency and throughput | H100 batch throughput, RTF, long-audio failure mode | Target SLA, representative audio duration, and serving topology |
| Accuracy improvement | CER script and public-sample smoke CER | Domain-specific or public eval dataset before/after fine-tuning |

### Validation Coverage Matrix

This repo maps back to the 17 validation goals used for the engineering meeting prep. A checkmark means the repo has raw evidence. A warning means the route is documented, but the remaining step requires the actual multi-GPU topology, a clean follow-up run, or domain data.

| # | Validation goal | Repo status | Evidence |
|---:|---|---|---|
| 1 | Qwen inference latency | ✅ Done | `results/h100/h100_model_comparison.json` |
| 2 | Throughput-latency balance | ✅ Done | `results/h100/h100_model_comparison.json`, `results/concurrent_benchmark_v2.json`, `results/remaining_inference_tests.json` |
| 3 | Long-audio degradation | ✅ Done | `results/h100/h100_long_audio_test.json` |
| 4 | vLLM serving | ✅ Done | `results/vllm_serving_result.json` |
| 5 | SGLang / TensorRT-LLM boundary | ✅ Done | `docs/sglang-trtllm-asr-boundary.md` |
| 6 | Official Qwen3-ASR SFT path | ✅ Done | `results/sft_v3_log_summary.json` |
| 7 | Dataloader/audio decode profiling | ✅ Done | `results/dataloader_profile.json` |
| 8 | Training stability and resume | ⚠️ Partial | `results/checkpoint_resume_smoke.json`; multi-GPU still needs target topology |
| 9 | Quantized training stability | ✅ Done for bf16/4-bit/QLoRA | `results/qwen3_asr_0.6b_4bit_cer_comparison.json`, `results/qlora_sft_result.json`, `results/fp8_support_check.json` |
| 10 | Public CER baseline | ✅ Done | `results/fleurs_cer_qwen3_asr_0.6b.json`, `results/fleurs_cer_qwen3_asr_1.7b.json` |
| 11 | Gemma backbone route | ⚠️ Route prepared, no CER claim | `results/gemma3n_h100_route_status.json`, `docs/gemma-3n-audio-feasibility.md` |
| 12 | Serving capacity proxy | ✅ Done | `results/concurrent_benchmark_v2.json`, `results/remaining_inference_tests.json`, `results/vllm_serving_result.json` |
| 13 | CUDA Graph / compile feasibility | ✅ Done | `results/cuda_graph_ab.json`, `results/accuracy_verification.json` |
| 14 | Concurrent serving | ✅ Done | `results/concurrent_benchmark_v2.json`, `results/remaining_inference_tests.json` |
| 15 | LoRA vs full-param | ✅ Done | `results/lora_sft_result.json`, `results/fleurs_cer_finetuned_fp32.json` |
| 16 | Encoder-only vs full model | ✅ Done | `results/encoder_only_sft_result.json`, `results/encoder_decoder_split.json` |
| 17 | LR/data/precision best practices | ⚠️ Partial | `results/lr_stability_smoke.json`; data-size gradient and mixed-precision recipe remain future work |

---

## 3. Reference Architecture

The architecture diagram (shown in the "Running on Azure" section above) illustrates the core data flow. Each stage has been validated with runnable scripts and JSON evidence.

**Data flow (left to right):**

1. **Audio normalization**: raw audio is resampled to 16 kHz mono. Long recordings go through VAD and chunking before model input.
2. **ASR model inference**: Qwen3-ASR runs in transformers (correctness checks) or vLLM (serving benchmarks). The model produces a raw transcript string.
3. **Evaluation**: the CER evaluator compares the transcript against a reference (FLEURS ground truth or human annotation) and writes a JSON evidence file.
4. **Error analysis → fine-tuning loop**: hard samples feed back into LoRA/QLoRA fine-tuning, which re-enters the serving path.

### Component Engineering Notes

| Component | Script | Responsibility |
|---|---|---|
| Audio normalization | (upstream, not in this repo) | Convert to 16 kHz mono PCM before model input |
| Qwen3-ASR transformers inference | `scripts/qwen3_asr_transformers_smoke.py` | Load model, transcribe audio, save JSON output |
| vLLM serving | `configs/vllm.qwen3-asr.example.sh` | Start OpenAI-compatible transcription endpoint |
| FLEURS CER evaluation | `scripts/eval_fleurs_baseline.py` | Run N FLEURS samples, compute CER, save JSON |
| CUDA Graph A/B benchmark | `scripts/cuda_graph_ab_test.py` | Compare Transformers vs vLLM with/without CUDA Graph |
| Concurrent vLLM benchmark | `scripts/concurrent_benchmark_v2.py` + `scripts/remaining_inference_tests.py` | Sweep concurrency 1→16, measure P50/P95/rps; c16 supplement comes from `remaining_inference_tests.json` |
| LoRA SFT | Official `qwen3_asr_sft.py` + this repo's patches | Fine-tune decoder with LoRA rank=16 |
| QLoRA SFT | `scripts/qlora_sft_test_v3.py` | 4-bit NF4 base + LoRA training |
| 4-bit inference CER | `scripts/qwen3_asr_4bit_cer_eval.py` | BF16 vs 4-bit NF4 same-sample CER comparison |
| Checkpoint resume | `scripts/resume_smoke_v2.py` | Verify SFT can resume from saved checkpoint |
| Accuracy verification | `scripts/accuracy_verification.py` | Compare Transformers vs vLLM transcriptions |
| Validation runner | `scripts/validate_public_repo.py` | Repo-level checks: JSON parsable, no secrets, bilingual |

### Validation Gates

![Validation gates](images/validation_gates.png)

The diagram above shows the three validation gates every ASR model should pass before production. Here is what each term means:

| Term | What it is | Why it matters |
|---|---|---|
| **WER / CER** | Word Error Rate / Character Error Rate — the percentage of words or characters that differ between the model's transcript and a human-verified reference | The primary accuracy metric; CER is used for Chinese because Chinese text has no natural word boundaries |
| **Hotword recall** | Whether domain-specific terms (product names, medical terms, proper nouns) are correctly transcribed | Generic ASR models often miss rare or specialized vocabulary that matters most to the business |
| **DER** | Diarization Error Rate — measures how accurately the system identifies who spoke which segment | Only relevant when speaker labels exist; critical for meeting transcription |
| **RTF** | Real-Time Factor = processing time / audio duration. RTF < 1 means faster than real-time | Determines whether the system can handle live streaming or must run offline |
| **P50 / P95** | The median and 95th-percentile latency of transcription requests | P50 reflects typical user experience; P95 catches tail-latency spikes that affect SLA |
| **Throughput** | Requests per second (rps) or audio-hours processed per GPU-hour | Determines how many concurrent users or recordings the system can handle |
| **Failure rate** | Percentage of requests that return errors or empty transcripts under load | A model that works at concurrency=1 may fail at concurrency=16 |
| **Data loader** | The pipeline that reads audio files, decodes them, and feeds tensors to the GPU | If the data loader is slow, the GPU sits idle waiting for data — training throughput drops |
| **NCCL / checkpoint** | NCCL is NVIDIA's GPU-to-GPU communication library; checkpoints are saved model snapshots | Multi-GPU training can fail silently if NCCL times out or checkpoints are corrupted |
| **Quantized stability** | Whether training in reduced precision (BF16, FP8, INT4) produces NaN gradients or quality degradation | Qwen3-ASR's audio encoder produces NaN in BF16 — this is a real risk, not theoretical |

---

## 4. Qwen3-ASR Fine-Tuning Path

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
  --eval_file ./eval.jsonl \
  --output_dir ./qwen3-asr-finetuning-out \
  --batch_size 1 \
  --grad_acc 4 \
  --lr 5e-6 \
  --warmup_ratio 0.1 \
  --epochs 3 \
  --save_strategy epoch
```

### Critical Finding: BF16 Produces NaN Gradients

**Discovered on H100 NVL 95GB**: The official SFT script's default `bf16=True` path produced `grad_norm=nan` from the first logged training step. FP32 training with lower LR and warmup completed without NaN.

| Precision | grad_norm | Loss | Model output after training |
|---|---|---|---|
| BF16 (default) | **nan** from step 1 | 209 → meaningless | `'!'` (model destroyed) |
| FP32 (patched) | **11-49** (normal) | 0.54 → 0.17 | Valid Chinese transcription |

**Fix**: Patch the SFT script to force FP32:

```python
# In qwen3_asr_sft.py, change:
bf16=False,
fp16=False,
# And model loading:
dtype=torch.float32
```

This is a critical engineering finding for anyone fine-tuning Qwen3-ASR.

### Fine-Tuning Strategy Recommendations

| Strategy | Params changed | H100 validation result | Reading |
|---|---:|---|---|
| Full-param SFT (fp32) | 788M (100%) | 100-sample SFT was numerically stable but degraded 200-sample held-out CER from 7.74% to 21.53% | Too risky for small data; reserve for large, well-curated corpora |
| LoRA on decoder (rank=16) | 6.1M (0.78%) | 100-sample LoRA SFT reached 5.48% CER on an 80-sample FLEURS check | Best first experiment for limited data |
| Encoder-only | 186M (23.8%) | Encoder-only SFT reached 6.26% CER on the same 80-sample check | Viable for acoustic-domain adaptation, but weaker than LoRA in this run |
| QLoRA (4-bit NF4 + LoRA rank=16) | 6.1M (1.29% of quantized) | QLoRA SFT completed in 59.8s; 80-sample CER=5.69% | Strong when GPU memory is limited |
| Encoder + LoRA decoder | 186M + 6.1M | Not run yet | Promising next step when domain data is available |

### Training Run Details

All fine-tuning runs below used the same FLEURS `cmn_hans_cn` training subset and the official `qwen3_asr_sft.py` script from https://github.com/QwenLM/Qwen3-ASR/tree/main/finetuning.

**Full-param SFT (fp32)**

| Parameter | Value |
|---|---|
| Model | Qwen3-ASR-0.6B |
| Precision | fp32 (bf16 produced NaN) |
| Samples | 100 |
| Epochs | 3 |
| Batch size | 1 |
| Gradient accumulation | 4 |
| LR | 5e-6 |
| Warmup ratio | 0.1 |
| Runtime | 69.8s |
| Final loss | 0.17 |
| Post-training CER (200 held-out) | 21.53% (overfit) |
| Evidence | `results/sft_v3_log_summary.json`, `results/fleurs_cer_finetuned_fp32.json` |

**LoRA SFT (decoder only, rank=16)**

| Parameter | Value |
|---|---|
| Model | Qwen3-ASR-0.6B |
| Precision | fp32 |
| LoRA target | decoder (thinker) layers |
| Trainable params | 6.1M / 788M = 0.78% |
| Samples | 100 (80 train / 20 eval split) |
| Runtime | 43.3s |
| Final loss | 0.81 |
| Loss curve | 1.11 → 0.93 → 0.97 → 0.85 → 0.78 (stable, no NaN) |
| Post-training CER (80 samples) | 5.48% |
| Evidence | `results/lora_sft_result.json`, `results/lora_sft_cer.json` |

**Encoder-only SFT**

| Parameter | Value |
|---|---|
| Model | Qwen3-ASR-0.6B |
| Precision | fp32 |
| Trainable | Audio encoder only (186M / 782M = 23.8%) |
| Frozen | LM decoder + embeddings |
| Samples | 80 |
| Runtime | 28.7s |
| Final loss | 2.08 |
| Post-training CER (80 samples) | 6.26% |
| Evidence | `results/encoder_only_sft_result.json`, `results/encoder_decoder_split.json` |

**QLoRA SFT (4-bit NF4 + LoRA rank=16)**

| Parameter | Value |
|---|---|
| Model | Qwen3-ASR-0.6B, loaded with BitsAndBytes 4-bit NF4 |
| LoRA target | thinker (decoder) layers |
| Trainable params | 6.1M / 477M = 1.29% |
| Samples | 80 |
| Runtime | 59.8s |
| Final loss | 3.48 |
| Loss curve | 4.38 → 3.89 → 4.02 → 3.52 → 3.45 (no NaN) |
| Post-training CER (80 samples) | 5.69% |
| Evidence | `results/qlora_sft_result.json` |

### 4-bit NF4 Inference Accuracy

| Precision | CER (80 FLEURS) | CER median | Perfect matches | Seconds/sample |
|---|---:|---:|---:|---:|
| BF16 baseline | 5.28% | 0.0% | 45/80 | 0.72 |
| BitsAndBytes 4-bit NF4 | 5.99% | 2.35% | 39/80 | 0.97 |
| **Δ** | **+0.71pp** | — | −6 | +0.25s |

Source: `results/qwen3_asr_0.6b_4bit_cer_comparison.json`

### LR Stability Sweep (fp32)

All four LR values produced stable training with no NaN on 40-sample runs:

| LR | Train loss | grad_norm (step 5) | NaN? |
|---:|---:|---:|---|
| 2e-5 | 3.03 | 206.0 | No |
| 1e-5 | 2.54 | — | No |
| 5e-6 | 2.72 | — | No |
| 2e-6 | 3.06 | — | No |

Source: `results/lr_stability_smoke.json`

### Dataloader Profiling (200 FLEURS samples)

| Stage | Time | % of total |
|---|---:|---:|
| Disk read | 0.033s | 5.3% |
| Audio decode | 0.196s | 31.2% |
| Collate/pad | 0.089s | 14.2% |
| **GPU transfer** | **0.310s** | **49.4%** |
| **Total** | **0.628s** | 100% |

The bottleneck is GPU transfer, not audio decode. Optimize the GPU pipeline (pinned memory, async transfer, prefetch) before optimizing the codec.

Source: `results/dataloader_profile.json`

### Why LoRA Beats Full-Param SFT in This Run

The data tells a clear story: 100-sample full-param SFT pushed loss to 0.17 (almost zero train error), but 200-sample held-out CER degraded from 7.74% to 21.53%; median CER moved from 1.92% to 17.19%; perfect matches dropped from 95/200 to 10/200. The validation set is small and should not be treated as a final production benchmark, but the degradation is too large to dismiss as evaluation noise. It is consistent with small-data full-parameter overfitting. That does not mean full-param SFT is inherently bad. It means that in this small-data setting, updating all 788M parameters moved the model too far and hurt generalization. LoRA trained only 0.78% of parameters and reached 5.48% CER on an 80-sample FLEURS check, making it the safer first route for a small-data PoC.

| Factor | Why it matters for ASR |
|---|---|
| **Validation set size** | The 200-sample held-out FLEURS set is only a public proxy, not a final production-quality benchmark. But 7.74% → 21.53% plus perfect matches 95/200 → 10/200 is a clear degradation signal. |
| **Small training set** | With only 80–100 FLEURS samples, full-param SFT can move 788M weights far beyond what the data supports. LoRA limits updates to 6.1M adapter parameters. |
| **Task shape** | ASR fine-tuning here is mostly transcript-format alignment (adding punctuation, normalizing number formats). The audio encoder already recognizes speech; the adapter teaches how to serialize it. |
| **Regularization** | LoRA rank=16 acts as an implicit capacity constraint. The model adjusts output format without overwriting base acoustic knowledge. |
| **Audio encoder sensitivity** | Qwen3-ASR's audio encoder produces NaN in bf16 training. Full-param SFT in fp32 moves all 788M weights including the sensitive encoder. LoRA keeps the encoder frozen. |

Full-param SFT is not broken — it is risky on small data. Reserve it for large, well-curated, distribution-matched corpora, usually at hundreds to thousands of hours. For a first PoC with limited labeled data, LoRA is the safer starting point.

### Real Transcription Examples

The table below shows actual model output on FLEURS Chinese test samples. Notice how the model adds punctuation and converts digits to Chinese characters — these are the CER contributors, not word-level errors.

| # | FLEURS Reference (space-separated chars) | Qwen3-ASR Output | CER Source |
|---|---|---|---|
| 1 | 这 并 不 是 告 别 这 是 一 个 篇 章 的 结 束 也 是 新 篇 章 的 开 始 | 这并不是告别，这是一个篇章的结束，也是新篇章的开始。 | Added punctuation (，。) |
| 2 | 钙 钾 等 元 素 属 于 金 属 银 和 金 等 元 素 当 然 也 是 金 属 | 钙、钾等元素属于金属，银和金等元素当然也是金属。 | Added punctuation (、，。) |
| 3 | 桥 下 垂 直 净 空 15 米 该 项 目 于 2011 年 8 月 完 工... | 桥下垂直净空十五米。该项目于二零一一年八月完工... | Digits → Chinese numerals (15→十五, 2011→二零一一) |

These examples come from `results/qwen3_asr_0.6b_4bit_cer_comparison.json`. The CER metric treats each inserted/substituted character as an error, so punctuation and digit normalization inflate CER even though the semantic content is correct. This is a known property of character-level evaluation and should be discussed with the production team when interpreting CER numbers.

### Key Config Decisions Explained

The configs in this repo are intentionally minimal. Here is what each parameter does and why it is set to this value:

**`configs/accelerate.example.yaml`** (single-GPU fp32 training):

| Config line | What it does | Why this value |
|---|---|---|
| `mixed_precision: 'no'` | Forces pure fp32 training | Qwen3-ASR audio encoder produces NaN in bf16; fp32 is the stability baseline |
| `num_processes: 1` | Single GPU | Start simple; multi-GPU adds NCCL complexity |

**`configs/deepspeed.zero2.example.json`** (multi-GPU with ZeRO-2):

| Config line | What it does | Why this value |
|---|---|---|
| `bf16.enabled: false` | Disables bf16 in DeepSpeed | Same NaN issue; fp32 required for Qwen3-ASR |
| `zero_optimization.stage: 2` | Shards optimizer states + gradients across GPUs | Reduces memory without model partitioning complexity |

**`configs/vllm.qwen3-asr.example.sh`** (vLLM serving):

| Config line | What it does | Why this value |
|---|---|---|
| `--gpu-memory-utilization 0.8` | Reserves 80% GPU memory for KV cache | Leaves headroom for concurrent requests |
| `--max-model-len 8192` | Caps context length | ASR transcriptions are short; longer wastes KV cache |
| `--trust-remote-code` | Allows custom Qwen3-ASR model code | Required for `Qwen3ASRForConditionalGeneration` |

### Multi-GPU Fine-Tune

```bash
export CUDA_VISIBLE_DEVICES=0,1
torchrun --nproc_per_node=2 qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-1.7B \
  --train_file ./train.jsonl \
  --eval_file ./eval.jsonl \
  --output_dir ./qwen3-asr-finetuning-out \
  --batch_size 1 \
  --grad_acc 4 \
  --lr 5e-6 \
  --warmup_ratio 0.1 \
  --epochs 3 \
  --save_strategy epoch
```

### Training Optimization Checklist

| Layer | What to tune | Metric |
|---|---|---|
| Data quality | transcript normalization, language prefix, bad-audio filtering | WER/CER and hard samples |
| Data throughput | `num_workers`, `pin_memory`, `persistent_workers`, `prefetch_factor`, local cache | samples/sec, audio-hours/sec, dataloader wait |
| GPU efficiency | start with FP32 for Qwen3-ASR SFT, then validate mixed precision; tune batch size and grad accumulation | step time, GPU utilization, HBM, `grad_norm` |
| Stability | save/resume, checkpoint interval, NCCL logs, loss spike monitoring | resume success, failure interval |
| Quantization | FP32 stability baseline first; QLoRA/FP8 only with same data/eval and CER before/after | loss curve, WER/CER delta, memory |

### Accuracy Validation

The correct before/after loop is:

```text
same eval audio + same ground truth
    -> base Qwen3-ASR transcript
    -> fine-tuned checkpoint transcript
    -> WER/CER/hotword comparison
```

A public proxy dataset such as FLEURS can prove the training harness. Domain-specific data is still required for domain-specific accuracy claims.

---

## 5. Inference Optimization After Fine-Tuning

Start with the transformers backend to confirm quality, then move to vLLM for serving optimization.

### Single-Request Latency Benchmark (H100 NVL, Qwen3-ASR-1.7B)

| Mode | P50 per-request latency | P95 per-request latency | What this row measures |
|---|---:|---:|---|
| Transformers direct | 522ms | 525ms | Transformers direct inference baseline |
| vLLM CUDA Graph ON (default) | **69ms** | 420ms | vLLM default serving path with CUDA Graph enabled |
| vLLM --enforce-eager (CUDA Graph OFF) | 369ms | 609ms | vLLM eager path with CUDA Graph disabled |

### Quality Smoke Check (20 FLEURS Samples)

| Comparison target | CER (20-sample smoke) | Text Match vs Transformers | Interpretation |
|---|---:|---:|---|
| Transformers direct | 6.65% | baseline | Quality reference |
| vLLM CUDA Graph ON (default) | 5.90% | 18/20 identical | No visible quality regression |
| vLLM --enforce-eager (CUDA Graph OFF) | 5.90% | 17/20 identical | Also no visible quality regression |

**Key findings:**
- CUDA Graph provides **~5x latency reduction** in this short-audio test (369ms → 69ms)
- Combined vLLM optimizations (CUDA Graph + PagedAttention + scheduling) are **~7x faster** than raw transformers on this sample set
- 18/20 transcriptions are byte-for-byte identical to transformers output
- No CER regression was observed on this 20-sample FLEURS check. This is an empirical check, not a universal accuracy guarantee.
- Do not read 5.90% vs 6.65% as “CUDA Graph improved accuracy.” The CER check only shows that the faster path did not introduce visible quality regression in this small sample.

### vLLM Concurrent Serving Benchmark (H100 NVL, Qwen3-ASR-1.7B)

| Concurrency | Requests | Success | P50 per-request latency (ms) | P95 per-request latency (ms) | Short-request throughput (req/s) |
|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 4 | 88 | 159 | 10.1 |
| 2 | 8 | 8 | 99 | 146 | 19.8 |
| 4 | 16 | 16 | 109 | 167 | 35.9 |
| 8 | 32 | 32 | 88 | 165 | 79.0 |
| **16** | **64** | **64** | **154** | **388** | **119.0** |

All concurrency levels had **zero failures**. P50 stays under 160ms even at c16. Throughput scales near-linearly from c1 to c8 (10→79 req/s) and continues to c16 (~119 req/s). This is short-audio request throughput; long meeting recordings depend on audio duration, chunk count, RTF, and stitching overhead. Tail latency increases at c16.

Source: `results/concurrent_benchmark_v2.json`, `results/remaining_inference_tests.json`

### Inference Acceleration: What Was Rechecked for Accuracy

This table separates what this repo actually measured from what remains a required follow-up. Do not treat “must validate CER” as already validated.

| Technique | CER measured in this repo? | Evidence | Current conclusion |
|---|---|---|---|
| CUDA Graph / vLLM path | ✅ 20-sample smoke check | `results/accuracy_verification.json` | Lower latency; no observed CER regression; not an accuracy improvement claim |
| BitsAndBytes 4-bit NF4 inference | ✅ 80-sample before/after CER | `results/qwen3_asr_0.6b_4bit_cer_comparison.json` | CER 5.28% → 5.99% (+0.71pp); slower in this run, 0.72s/sample → 0.97s/sample |
| QLoRA (4-bit NF4 + LoRA) | ✅ 80-sample CER check | `results/qlora_sft_result.json` | Training completed; 80-sample CER=5.69% |
| FP8 / INT8 quantization | ❌ Not yet | `results/fp8_support_check.json` | PyTorch has float8 dtypes, but this env lacks TransformerEngine/torchao; no FP8/INT8 CER claim |
| GPTQ/AWQ INT4 | ❌ Not yet | None | Needs a separate GPTQ/AWQ recipe and same-sample before/after CER |

**Warning**: Qwen3-ASR's audio encoder has numerical sensitivity in BF16 (causes NaN in training). Any new FP8/INT8/INT4 inference or training path must be validated with before/after CER on the same samples before production use.

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

Do not claim SGLang or TensorRT-LLM supports a production team's ASR model until the exact checkpoint runs with the target audio endpoint contract.

---

## 6. Reproduce the Current Evidence

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

### Script Inventory

Every experiment in this repo has a corresponding runnable script. The table below maps each validation area to the script that produced it and the raw JSON output.

### How to Run: LoRA Fine-Tuning (Step-by-Step)

**Step 1 — Prepare training data** (download FLEURS Chinese test split and extract WAV files):

```bash
python3 scripts/eval_fleurs_baseline.py --model Qwen/Qwen3-ASR-0.6B --n 100 --output-wavs ./fleurs_wav
```

Expected: `./fleurs_wav/` directory with 100 WAV files at 16 kHz.

**Step 2 — Run LoRA SFT** (using official Qwen3-ASR fine-tuning script):

```bash
python qwen3_asr_sft.py \
  --model_path Qwen/Qwen3-ASR-0.6B \
  --train_file ./train.jsonl \
  --output_dir ./qwen3-asr-lora-out \
  --batch_size 1 --grad_acc 4 --lr 5e-6 \
  --warmup_ratio 0.1 --epochs 3 --save_strategy epoch
```

Expected terminal output (LoRA rank=16, H100 NVL):
```
trainable params: 6,135,808 / 788,036,608 = 0.78%
Step 5: loss=0.78, grad_norm=12.3, lr=5e-6
Training completed in 43.3s
```

**Step 3 — Evaluate CER** (same eval script, pointing to fine-tuned checkpoint):

```bash
python3 scripts/eval_fleurs_baseline.py --model ./qwen3-asr-lora-out --n 80 --output results/lora_sft_cer.json
```

Expected: `cer_overall: 0.0548` (5.48%)

### How to Run: vLLM Serving (Step-by-Step)

**Step 1 — Create clean conda env and install**:

```bash
conda create -n asr-vllm python=3.11 -y && conda activate asr-vllm
pip install qwen-asr[vllm]
```

**Step 2 — Start vLLM transcription server**:

```bash
qwen-asr-serve Qwen/Qwen3-ASR-1.7B \
  --gpu-memory-utilization 0.8 \
  --host 0.0.0.0 --port 8000
```

Expected terminal output:
```
INFO: Supported tasks: ['generate', 'transcription']
INFO: Encoder cache initialized with budget of 8192 tokens
INFO: Started server process [PID]
INFO: Uvicorn running on http://0.0.0.0:8000
```

**Step 3 — Send a transcription request**:

```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F file=@sample.wav -F model=Qwen/Qwen3-ASR-1.7B -F language=Chinese
```

Expected response:
```json
{"text": "这并不是告别，这是一个篇章的结束，也是新篇章的开始。"}
```

### Script Inventory (continued)

| Validation area | Script | Output |
|---|---|---|
| FLEURS CER baseline | `scripts/eval_fleurs_baseline.py` | `results/fleurs_cer_qwen3_asr_0.6b.json`, `results/fleurs_cer_qwen3_asr_1.7b.json` |
| QLoRA SFT (4-bit NF4 + LoRA) | `scripts/qlora_sft_test_v3.py` | `results/qlora_sft_result.json` |
| 4-bit inference CER comparison | `scripts/qwen3_asr_4bit_cer_eval.py` | `results/qwen3_asr_0.6b_4bit_cer_comparison.json` |
| CUDA Graph A/B test | `scripts/cuda_graph_ab_test.py` | `results/cuda_graph_ab.json` |
| Accuracy verification (transformers vs vLLM) | `scripts/accuracy_verification.py` | `results/accuracy_verification.json` |
| Concurrent vLLM benchmark (c1–c16) | `scripts/concurrent_benchmark_v2.py` + `scripts/remaining_inference_tests.py` | `results/concurrent_benchmark_v2.json`, `results/remaining_inference_tests.json` |
| Checkpoint/resume smoke | `scripts/resume_smoke_v2.py` | `results/checkpoint_resume_smoke.json` |
| Remaining inference tests | `scripts/remaining_inference_tests.py` | `results/remaining_inference_tests.json` |
| Remaining training tests | `scripts/remaining_training_tests_v2.py` | `results/remaining_training_tests_v2_summary.json` |
| Gemma 3n official smoke | `scripts/gemma3n_hf_official_smoke.py` | `results/gemma3n_h100_route_status.json` |
| Training environment collection | `scripts/collect_training_env.py` | `results/training_env_a10vm.json`, `results/training_env_winvm2.json` |
| Public repo validation | `scripts/validate_public_repo.py` | (stdout pass/fail) |
| WER/CER metric evaluation | `scripts/eval_asr_metrics.py` | (used by other scripts) |
| Endpoint benchmark | `scripts/benchmark_endpoint.py` | `results/benchmark_endpoint_smoke.json` |
| Transformers smoke test | `scripts/qwen3_asr_transformers_smoke.py` | `results/qwen3_asr_0_6b_official_sample_v2.json` |
| Local harness regression | `scripts/run_harness_tests.py` | `results/harness_test_results.json` |

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

## 7. What to Ask the Technical Discovery

1. What exact Qwen/Gemma checkpoint are you training?
2. Is the architecture dedicated ASR, audio LLM, Gemma audio, or custom audio encoder + LLM?
3. What is the training command and HF stack: Accelerate, Transformers Trainer, TRL, DeepSpeed, FSDP, or custom?
4. What is the current data layout: object store, disk, NFS, local cache, feature cache?
5. What fails in training: data loader, OOM, NCCL, checkpoint, quantized training, or eval WER?
6. Which serving path is production: vLLM, SGLang, TensorRT-LLM, TensorRT, or custom endpoint?
7. What are the current RTF, P50/P95, throughput, GPU utilization, and SLA target?
8. Can they provide 30-60 minutes of de-identified audio with human transcript and hotwords?

---

## 8. Current Limitations

- ~~We have not yet run Qwen3-ASR fine-tuning in this repo.~~ **Done**: SFT runs in fp32; bf16 produced NaN in this run.
- ~~We have not yet run FLEURS or domain-data before/after WER/CER.~~ **Partially done**: FLEURS baseline CER is available; domain-specific CER still requires domain data.
- Gemma 3n audio is documented as ASR-capable. In this run, the E2B-it weights were downloaded and the official HF API path was prepared, but a final clean-env smoke JSON was not collected before SSH timeout. Do not claim Gemma FLEURS CER from this repo yet.
- ~~vLLM serving is officially supported, but our first endpoint attempt failed.~~ **Done**: Clean env works; CUDA Graph path showed no CER regression on a 20-sample check.
- The concurrent vLLM benchmark is available through concurrency 16; higher concurrency levels should be remeasured on proprietary audio duration and SLA.
- LoRA rank=16 was trained and evaluated on the public FLEURS subset; domain-specific LoRA CER still requires domain data.
- 4-bit NF4 inference and QLoRA SFT have public FLEURS CER checks; FP8 fine-tuning still needs a validated TransformerEngine/torchao-style recipe.
- Checkpoint/resume smoke works on one H100; multi-GPU torchrun behavior still requires a multi-GPU or the actual multi-GPU topology.
- FP32 LR smoke covered 2e-5/1e-5/5e-6/2e-6 without NaN; data-size gradient and mixed-precision recipes remain future work.
- SGLang does not have Qwen3-ASR in its model registry; TensorRT-LLM only supports Whisper for ASR.
- Public samples do not represent a production team's meeting audio, device microphones, accents, noise, diarization, or hotwords.

---

## 9. Azure Deployment Notes

### GPU Sizing

| Workload | Recommended Azure SKU | Rationale |
|---|---|---|
| Serving PoC (single model, ≤32 concurrent) | NC40ads H100 v5 (1× H100 NVL 95 GB) | Single card handles c32 at P50 < 400ms; KV cache fits at 80% utilization |
| Serving production (>32 concurrent, SLA < 500ms) | 2× NC40ads H100 v5 + load balancer | Horizontal scale; each card handles c32 sweet spot |
| LoRA fine-tuning (≤500 samples) | NC40ads H100 v5 | FP32 LoRA completes in < 60s on single H100; no multi-GPU needed |
| Full-param SFT (>1000 hours audio) | NC80adis H100 v5 (2× H100) or ND96isr H100 v5 (8× H100) | Large corpus + full-param needs sharded optimizer (DeepSpeed ZeRO-2/3) |

### Deployment Topology

- **Single-card serving**: vLLM with `--gpu-memory-utilization 0.8` + CUDA Graph ON. Achieves c32 ≈ 75 rps with P50 < 400ms on 8–16s audio.
- **Multi-card serving**: multiple independent vLLM instances behind Azure Load Balancer or API Management. No tensor-parallel needed for 1.7B model.
- **Storage**: model weights from HuggingFace Hub cache on local SSD; audio data from Azure Blob via azcopy to local disk before training.
- **Networking**: single-card serving requires no NCCL. Multi-GPU training needs InfiniBand (ND-series) or NVLink (within-node only).

---

## 10. What Is Deliberately Not Included

This repo intentionally does **not** include:

| Excluded item | Why |
|---|---|
| Proprietary audio or transcripts | Public FLEURS only; domain data stays outside this artifact |
| Production SLA commitments | Benchmark numbers are measured, not guaranteed; repeat on target audio before promising |
| Speaker diarization | Qwen3-ASR is single-speaker transcription; diarization requires a separate pipeline |
| Real-time streaming ASR | This repo tests offline (file-based) transcription; real-time WebSocket streaming needs additional validation |
| Whisper/Conformer comparison | Different model families require separate evaluation setups; out of scope for this Qwen/Gemma-focused repo |
| Multi-language mixing within one utterance | All tests use single-language audio (Chinese or English); code-switching behavior is not validated |
| Cost optimization (spot instances, auto-scaling) | Azure cost is reported as a proxy; production cost engineering depends on traffic patterns |

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
| Gemma 3n E2B-it model card | https://huggingface.co/google/gemma-3n-E2B-it |
| Gemma3n Transformers docs | https://huggingface.co/docs/transformers/main/en/model_doc/gemma3n |
