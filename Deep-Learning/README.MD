# Deep Learning

A comprehensive collection of 77 projects covering quantization, fine-tuning, inference optimization, training parallelism, GPU benchmarks, and more.

> Projects marked with ⭐ were consolidated from multiple related projects during the 2026-02 restructuring.

---

## Table of Contents

| # | Category | Count |
|---|----------|-------|
| 1 | [Quantization & Data Types](#1-quantization--data-types) | 6 |
| 2 | [Fine-Tuning & Training Techniques](#2-fine-tuning--training-techniques) | 20 |
| 3 | [RLHF, Alignment & Reasoning](#3-rlhf-alignment--reasoning) | 4 |
| 4 | [Inference Optimization](#4-inference-optimization) | 17 |
| 5 | [Training Parallelism & Distributed Systems](#5-training-parallelism--distributed-systems) | 7 |
| 6 | [GPU Benchmarks & Hardware](#6-gpu-benchmarks--hardware) | 9 |
| 7 | [Model Architecture & Understanding](#7-model-architecture--understanding) | 14 |

---

## 1. Quantization & Data Types

Quantization techniques, mixed precision training, and data type optimization.

| Project | Description |
|---------|-------------|
| [Automatic-Mixed-Precision-in-AI](Automatic-Mixed-Precision-in-AI/) | AMP training and inference deep dive |
| [BF16-FP16-RL](BF16-FP16-RL/) | BF16 vs FP16 precision issues in reinforcement learning |
| [GGUF-LoRA](GGUF-LoRA/) | GGUF format with LoRA adapters for CPU inference |
| [NVFP4](NVFP4/) | NVIDIA Blackwell FP4 quantization analysis |
| ⭐ [Quantization-Methods-Comparison-and-Practice](Quantization-Methods-Comparison-and-Practice/) | AutoRound/GPTQ/AWQ comparison + AutoRound practice + calibration dataset impact |
| ⭐ [Ultra-Low-Bit-Quantization-Experiments](Ultra-Low-Bit-Quantization-Experiments/) | 1-bit BitNet + 2-bit VPTQ + quantization threshold experiments |

---

## 2. Fine-Tuning & Training Techniques

LoRA, SFT, full fine-tuning, pre-training, dataset preparation, and training pipelines.

| Project | Description |
|---------|-------------|
| [4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice](4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice/) | Azure OpenAI end-to-end fine-tuning guide |
| [AIPC-Agent-Training](AIPC-Agent-Training/) | Agent training on AI PCs |
| ⭐ [Comparison-of-Various-Fine-Tuning-Methods](Comparison-of-Various-Fine-Tuning-Methods/) | SFT/LoRA/QLoRA/DPO/PPO comparison + QLoRA analysis + GaLore experiments |
| [DenseMixer-Better-MoE-Fine-Tuning](DenseMixer-Better-MoE-Fine-Tuning/) | DenseMixer for MoE model fine-tuning |
| [EXAONE-Multi-LoRA-on-Azure](EXAONE-Multi-LoRA-on-Azure/) | EXAONE multi-LoRA deployment on Azure |
| [Fine-Tuning-Sentence-Embeddings](Fine-Tuning-Sentence-Embeddings/) | Sentence embedding fine-tuning |
| ⭐ [Fine-Tuning-Tools-Axolotl-LLaMA-Factory](Fine-Tuning-Tools-Axolotl-LLaMA-Factory/) | Axolotl + LLaMA-Factory fine-tuning tool guides |
| [Function-Call-Training](Function-Call-Training/) | Training models for function calling |
| [Knowledge-Distillation](Knowledge-Distillation/) | Knowledge distillation techniques |
| ⭐ [Llama-3.1-Fine-Tuning-Guide](Llama-3.1-Fine-Tuning-Guide/) | Llama 3.1 fine-tuning: 8B single-GPU LoRA + 70B multi-GPU FSDP |
| ⭐ [LLM-Fine-Tuning-Best-Practices](LLM-Fine-Tuning-Best-Practices/) | Fine-tuning best practices + base vs instruct model selection |
| [LoRA-Training-Different-LM-Modules](LoRA-Training-Different-LM-Modules/) | LoRA applied to different model modules |
| [Make-High-Quality-Dataset-From-WARC](Make-High-Quality-Dataset-From-WARC/) | Building training datasets from WARC archives |
| [Multi-LoRA-adapter](Multi-LoRA-adapter/) | Multi-LoRA adapter serving |
| ⭐ [Pre-Training-Methods-Explained](Pre-Training-Methods-Explained/) | Pre-training vs SFT + continued pre-training + synthetic instruction pre-training |
| [Pytorch-PEFT-SFT-to-ONNX](Pytorch-PEFT-SFT-to-ONNX/) | PyTorch PEFT/SFT model export to ONNX |
| [SFT-on-RTX-6000-Pro](SFT-on-RTX-6000-Pro/) | SFT training on RTX 6000 Pro |
| [SmolLM-Full-Fine-Tuning](SmolLM-Full-Fine-Tuning/) | SmolLM full fine-tuning |
| [Unsloth-Full-SFT](Unsloth-Full-SFT/) | Full SFT with Unsloth |
| [VAD-Training](VAD-Training/) | Voice Activity Detection training |

---

## 3. RLHF, Alignment & Reasoning

DPO, PPO, GRPO, reward modeling, and reasoning enhancement.

| Project | Description |
|---------|-------------|
| [DPO-DeepSpeed-FSDP](DPO-DeepSpeed-FSDP/) | 72B model DPO training with DeepSpeed and FSDP |
| ⭐ [GRPO-RL-Training-Pipeline](GRPO-RL-Training-Pipeline/) | SFT + GRPO pipeline + Phi-4 GRPO training + GSPO vs GRPO comparison |
| ⭐ [LLM-Alignment-DPO-PPO-CPO](LLM-Alignment-DPO-PPO-CPO/) | DPO vs PPO comparison + RLHF/DPO/CPO/SimPO alignment overview |
| [LLM-Math-Reasoning-RL](LLM-Math-Reasoning-RL/) | Reinforcement learning for math reasoning (DeepSeek-R1 architecture) |

---

## 4. Inference Optimization

vLLM, FlashAttention, KV cache, speculative decoding, and serving frameworks.

| Project | Description |
|---------|-------------|
| [7-Inference-Frameworks-for-LLM](7-Inference-Frameworks-for-LLM/) | Comparison of 7 LLM inference frameworks |
| [AI-Inference-Workshop](AI-Inference-Workshop/) | AI inference workshop materials |
| [Budget-Forcing-Inference](Budget-Forcing-Inference/) | Budget-forcing inference strategies |
| [FlashAttention-3](FlashAttention-3/) | FlashAttention 3 analysis |
| [FlashInfer-vs-FlashAttention-Benchmark](FlashInfer-vs-FlashAttention-Benchmark/) | FlashInfer vs FlashAttention benchmark |
| [KV-Cache-Quantization](KV-Cache-Quantization/) | KV cache quantization techniques |
| [LLM-Inference-performance-test](LLM-Inference-performance-test/) | LLM inference performance testing |
| ⭐ [LLM-Memory-Estimation](LLM-Memory-Estimation/) | Inference memory estimation tool + training/inference memory consumption theory |
| [MInference](MInference/) | MInference for long-context acceleration |
| [Network-Attached-KV-Cache](Network-Attached-KV-Cache/) | Network-attached KV cache architecture |
| [OSS-Model-SWE-bench-Evaluation-Playbook](OSS-Model-SWE-bench-Evaluation-Playbook/) | End-to-end SWE-bench Verified evaluation for OSS coding models, including generation, official scoring, frozen-dispute retesting, and troubleshooting |
| [Padding-Free](Padding-Free/) | Padding-free training and inference |
| [Qwen-Virtual-TryOn-Inference-Benchmark](Qwen-Virtual-TryOn-Inference-Benchmark/) | Qwen virtual try-on inference benchmark |
| [SGLang-vs-LLM](SGLang-vs-LLM/) | SGLang vs other LLM serving frameworks |
| [Speculative-Decoding-EAGLE3](Speculative-Decoding-EAGLE3/) | EAGLE-3 speculative decoding |
| [torch-compile-tryon](torch-compile-tryon/) | torch.compile optimization for try-on models |
| ⭐ [vLLM-Architecture-and-Inference-Engines](vLLM-Architecture-and-Inference-Engines/) | vLLM deep dive + V1 engine + ExLlamaV2/llama.cpp comparison + FlashInfer benchmark |

---

## 5. Training Parallelism & Distributed Systems

DeepSpeed, FSDP, tensor/pipeline/expert parallelism, and distributed training.

| Project | Description |
|---------|-------------|
| [DeepEP](DeepEP/) | DeepEP expert parallelism |
| ⭐ [Distributed-Training-Parallelism-Guide](Distributed-Training-Parallelism-Guide/) | DP/TP/PP/ZeRO explained + PyTorch distributed + NVIDIA distributed + DeepSpeed ZeRO |
| [Easy-way-to-Understand-Training](Easy-way-to-Understand-Training/) | Intuitive explanation of training concepts |
| [How-to-Run-Training-Faster](How-to-Run-Training-Faster/) | Training acceleration techniques |
| [Optimizers](Optimizers/) | Training optimizers comparison |
| ⭐ [Pretraining-Frameworks-Megatron-Nanotron](Pretraining-Frameworks-Megatron-Nanotron/) | Megatron-DeepSpeed GPT-2 + HuggingFace Nanotron pre-training |
| [Training-Proposal](Training-Proposal/) | Training proposal and planning |

---

## 6. GPU Benchmarks & Hardware

Performance benchmarks, GPU selection guides, and hardware-specific tests.

| Project | Description |
|---------|-------------|
| [AI-Foundry-Model-Performance](AI-Foundry-Model-Performance/) | AI Foundry model performance testing |
| [AI-on-PC](AI-on-PC/) | Running AI models on PC hardware |
| ⭐ [Azure-AMD-MI300X-Guide](Azure-AMD-MI300X-Guide/) | AMD MI300X benchmarks + inference + PoC deployment handbook |
| ⭐ [NC-RTX-Pro-6000V6-BSE-Benchmark](NC-RTX-Pro-6000V6-BSE-Benchmark/) | Azure GPU VM selection guide + H100/A100/RTX6000/A10 FP8 benchmark + NC RTX Pro 6000 BSE benchmark |
| [CPU2GPU](CPU2GPU/) | CPU to GPU migration guide |
| [Install-CUDA](Install-CUDA/) | CUDA installation guide |
| [MiMo-V2.5-Pro-MI300X-Accuracy-Evaluation](MiMo-V2.5-Pro-MI300X-Accuracy-Evaluation/) | Evidence-backed six-dataset accuracy evaluation with H200 reference alignment |
| [Qwen3-235B-Multi-Node-vLLM-Benchmark](Qwen3-235B-Multi-Node-vLLM-Benchmark/) | Qwen3 235B multi-node vLLM benchmark |
| [Script-For-DS671B](Script-For-DS671B/) | Scripts for DeepSeek 671B deployment |

---

## 7. Model Architecture & Understanding

Model internals, architecture analysis, and foundational concepts.

| Project | Description |
|---------|-------------|
| [Agent-Lighting](Agent-Lighting/) | Agent Lighting framework |
| [DeepSeek-R1-on-Azure](DeepSeek-R1-on-Azure/) | DeepSeek-R1 deployment on Azure |
| [Fara-7B-Azure-Demo](Fara-7B-Azure-Demo/) | Fara-7B model demo on Azure |
| [Gemma3n-MatFormer](Gemma3n-MatFormer/) | Gemma 3n and MatFormer architecture |
| [Implementing-llama3-from-scratch](Implementing-llama3-from-scratch/) | Building Llama 3 from scratch |
| [Llama-4](Llama-4/) | Llama 4 model analysis |
| ⭐ [LLM-Hallucinations-Analysis-and-Mitigation](LLM-Hallucinations-Analysis-and-Mitigation/) | LLM hallucination mechanisms + mitigation strategies |
| [ModernBERT](ModernBERT/) | ModernBERT architecture |
| [OAI-OSS-on-Azure](OAI-OSS-on-Azure/) | OpenAI OSS models on Azure |
| ⭐ [Phi-Model-Family](Phi-Model-Family/) | Phi-4 + Phi-3.5 MoE/Mini + Phi-3 quantization and fine-tuning |
| [Qwen-Reranker](Qwen-Reranker/) | Qwen reranker model |
| ⭐ [SLM-Capabilities-and-Fine-Tuning](SLM-Capabilities-and-Fine-Tuning/) | SLM vs LLM + SLM limitations + DeepSeek-R1 reasoning distillation to Phi-4 |
| [Thinking-GenAI](Thinking-GenAI/) | Thinking about GenAI concepts |
| [UniAD](UniAD/) | UniAD unified autonomous driving |
