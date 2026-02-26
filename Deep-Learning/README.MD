# Deep Learning

A comprehensive collection of 106 projects covering quantization, fine-tuning, inference optimization, training parallelism, GPU benchmarks, and more.

> Projects marked with ⭐ were consolidated from multiple related projects during the 2026-02 restructuring.

---

## Table of Contents

| # | Category | Count |
|---|----------|-------|
| 1 | [Quantization & Data Types](#1-quantization--data-types) | 13 |
| 2 | [Fine-Tuning & Training Techniques](#2-fine-tuning--training-techniques) | 26 |
| 3 | [RLHF, Alignment & Reasoning](#3-rlhf-alignment--reasoning) | 7 |
| 4 | [Inference Optimization](#4-inference-optimization) | 18 |
| 5 | [Training Parallelism & Distributed Systems](#5-training-parallelism--distributed-systems) | 10 |
| 6 | [GPU Benchmarks & Hardware](#6-gpu-benchmarks--hardware) | 15 |
| 7 | [Model Architecture & Understanding](#7-model-architecture--understanding) | 17 |

---

## 1. Quantization & Data Types

Quantization techniques, mixed precision training, and data type optimization.

| Project | Description |
|---------|-------------|
| [1-Bit-LLMs](1-Bit-LLMs/) | 1-bit quantization for LLMs (BitNet) |
| [Automatic-Mixed-Precision-in-AI](Automatic-Mixed-Precision-in-AI/) | AMP training and inference |
| [Autoround-and-Quantization-Methods-Performance-Comparisons](Autoround-and-Quantization-Methods-Performance-Comparisons/) | Comparison of AutoRound, GPTQ, AWQ and other methods |
| [AutoRound-Quantize](AutoRound-Quantize/) | Intel AutoRound quantization tool |
| [BF16-FP16-RL](BF16-FP16-RL/) | BF16 vs FP16 in reinforcement learning |
| [Dataset-affect-for-Quantization](Dataset-affect-for-Quantization/) | How calibration datasets affect quantization quality |
| [GGUF-LoRA](GGUF-LoRA/) | GGUF format with LoRA adapters |
| [Inference-DataType-BF16-FP16](Inference-DataType-BF16-FP16/) | BF16 vs FP16 inference comparison |
| [NVFP4](NVFP4/) | NVIDIA FP4 quantization |
| [Phi3-Quantization-and-Fine-Tuning](Phi3-Quantization-and-Fine-Tuning/) | Phi-3 quantization and fine-tuning |
| [QLoRA-Performance](QLoRA-Performance/) | QLoRA performance analysis |
| [quantization_threshold_experiment](quantization_threshold_experiment/) | Quantization threshold experiments |
| [Quantization-2-bit-VPTQ](Quantization-2-bit-VPTQ/) | 2-bit VPTQ quantization |

---

## 2. Fine-Tuning & Training Techniques

LoRA, SFT, full fine-tuning, dataset preparation, and training pipelines.

| Project | Description |
|---------|-------------|
| [4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice](4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice/) | Azure OpenAI end-to-end fine-tuning guide |
| [AIPC-Agent-Training](AIPC-Agent-Training/) | Agent training on AI PCs |
| [Comparison-of-Various-Fine-Tuning-Methods](Comparison-of-Various-Fine-Tuning-Methods/) | Comparison of LoRA, QLoRA, full FT, and more |
| [Continue-Pre-training](Continue-Pre-training/) | Continued pre-training techniques |
| [DenseMixer-Better-MoE-Fine-Tuning](DenseMixer-Better-MoE-Fine-Tuning/) | DenseMixer for MoE model fine-tuning |
| [Difference-PreTraining-with-SFT](Difference-PreTraining-with-SFT/) | Pre-training vs SFT comparison |
| [EXAONE-Multi-LoRA-on-Azure](EXAONE-Multi-LoRA-on-Azure/) | EXAONE multi-LoRA deployment on Azure |
| [Fine-Tuning-Sentence-Embeddings](Fine-Tuning-Sentence-Embeddings/) | Sentence embedding fine-tuning |
| [Fine-tuning-with-Axolotl](Fine-tuning-with-Axolotl/) | Fine-tuning using Axolotl framework |
| [Function-Call-Training](Function-Call-Training/) | Training models for function calling |
| [GA-LoRA-implements-full-fine-tuning-and-addresses-overfitting](GA-LoRA-implements-full-fine-tuning-and-addresses-overfitting/) | GA-LoRA: full fine-tuning effect with LoRA efficiency |
| [Knowledge-Distillation](Knowledge-Distillation/) | Knowledge distillation techniques |
| ⭐ [Llama-3.1-Fine-Tuning-Guide](Llama-3.1-Fine-Tuning-Guide/) | Llama 3.1 fine-tuning: 8B single-GPU LoRA + 70B multi-GPU FSDP |
| [LLaMA-Factory-Usage](LLaMA-Factory-Usage/) | LLaMA-Factory framework usage guide |
| ⭐ [LLM-Fine-Tuning-Best-Practices](LLM-Fine-Tuning-Best-Practices/) | Fine-tuning best practices + base vs instruct model selection |
| [LoRA-Training-Different-LM-Modules](LoRA-Training-Different-LM-Modules/) | LoRA applied to different model modules |
| [Make-High-Quality-Dataset-From-WARC](Make-High-Quality-Dataset-From-WARC/) | Building training datasets from WARC archives |
| [Multi-LoRA-adapter](Multi-LoRA-adapter/) | Multi-LoRA adapter serving |
| [Phi-3.5-MoE-and-Mini-Fine-tuning](Phi-3.5-MoE-and-Mini-Fine-tuning/) | Phi-3.5 MoE and Mini fine-tuning |
| [Pretrain-on-Synthetic-Instructions](Pretrain-on-Synthetic-Instructions/) | Pre-training on synthetic instruction data |
| [Pytorch-PEFT-SFT-to-ONNX](Pytorch-PEFT-SFT-to-ONNX/) | PyTorch PEFT/SFT model export to ONNX |
| ⭐ [SFT-GRPO-Training-Pipeline](SFT-GRPO-Training-Pipeline/) | SFT + GRPO training pipeline with selection and embedded code approaches |
| [SFT-on-RTX-6000-Pro](SFT-on-RTX-6000-Pro/) | SFT training on RTX 6000 Pro |
| [SmolLM-Full-Fine-Tuning](SmolLM-Full-Fine-Tuning/) | SmolLM full fine-tuning |
| [Unsloth-Full-SFT](Unsloth-Full-SFT/) | Full SFT with Unsloth |
| [VAD-Training](VAD-Training/) | Voice Activity Detection training |

---

## 3. RLHF, Alignment & Reasoning

DPO, PPO, GRPO, reward modeling, and reasoning enhancement.

| Project | Description |
|---------|-------------|
| [DPO-DeepSpeed-FSDP](DPO-DeepSpeed-FSDP/) | DPO training with DeepSpeed and FSDP |
| [DPO-vs-PPO](DPO-vs-PPO/) | Comparison of DPO and PPO alignment methods |
| [GRPO-Phi-4-Training](GRPO-Phi-4-Training/) | GRPO training for Phi-4 |
| [GSPO-vs-GRPO](GSPO-vs-GRPO/) | GSPO vs GRPO comparison |
| [LLM-Alignment-DPO-RHLF-CPO](LLM-Alignment-DPO-RHLF-CPO/) | LLM alignment: DPO, RLHF, CPO, and SimPO |
| [LLM-Math-Reasoning-RL](LLM-Math-Reasoning-RL/) | Reinforcement learning for math reasoning |
| [SLM-DeepSeek-R1](SLM-DeepSeek-R1/) | DeepSeek-R1 reasoning model analysis |

---

## 4. Inference Optimization

vLLM, FlashAttention, KV cache, speculative decoding, and serving frameworks.

| Project | Description |
|---------|-------------|
| [7-Inference-Frameworks-for-LLM](7-Inference-Frameworks-for-LLM/) | Comparison of 7 LLM inference frameworks |
| [AI-Inference-Workshop](AI-Inference-Workshop/) | AI inference workshop materials |
| [Budget-Forcing-Inference](Budget-Forcing-Inference/) | Budget-forcing inference strategies |
| [Estimate-Inference-Memory](Estimate-Inference-Memory/) | Estimating inference memory requirements |
| [FlashAttention-3](FlashAttention-3/) | FlashAttention 3 analysis |
| [FlashInfer-vs-FlashAttention-Benchmark](FlashInfer-vs-FlashAttention-Benchmark/) | FlashInfer vs FlashAttention benchmark |
| [KV-Cache-Quantization](KV-Cache-Quantization/) | KV cache quantization techniques |
| [LLM-Inference-performance-test](LLM-Inference-performance-test/) | LLM inference performance testing |
| [MInference](MInference/) | MInference for long-context acceleration |
| [Network-Attached-KV-Cache](Network-Attached-KV-Cache/) | Network-attached KV cache architecture |
| [Padding-Free](Padding-Free/) | Padding-free training and inference |
| [Qwen-Virtual-TryOn-Inference-Benchmark](Qwen-Virtual-TryOn-Inference-Benchmark/) | Qwen virtual try-on inference benchmark |
| [SGLang-vs-LLM](SGLang-vs-LLM/) | SGLang vs other LLM serving frameworks |
| [Speculative-Decoding-EAGLE3](Speculative-Decoding-EAGLE3/) | EAGLE-3 speculative decoding |
| [torch-compile-tryon](torch-compile-tryon/) | torch.compile optimization for try-on models |
| ⭐ [vLLM-Architecture-and-Performance-Deep-Dive](vLLM-Architecture-and-Performance-Deep-Dive/) | vLLM architecture, attention mechanisms, and PagedAttention deep dive |
| [vLLM-ExLlamaV2-llama.cpp](vLLM-ExLlamaV2-llama.cpp/) | vLLM vs ExLlamaV2 vs llama.cpp comparison |
| [vLLM-V1](vLLM-V1/) | vLLM V1 engine analysis |

---

## 5. Training Parallelism & Distributed Systems

DeepSpeed, FSDP, tensor/pipeline/expert parallelism, and distributed training.

| Project | Description |
|---------|-------------|
| [Deep-Speed-ZeRO-Policy](Deep-Speed-ZeRO-Policy/) | DeepSpeed ZeRO optimization stages |
| [DeepEP](DeepEP/) | DeepEP expert parallelism |
| [Easy-way-to-Understand-Training](Easy-way-to-Understand-Training/) | Intuitive explanation of training concepts |
| [How-to-Run-Training-Faster](How-to-Run-Training-Faster/) | Training acceleration techniques |
| [LLM-Training-Parallelism-Explained](LLM-Training-Parallelism-Explained/) | DP, TP, PP, and ZeRO explained |
| [Megatron+Deepspeed-Pretrain-GPT2](Megatron+Deepspeed-Pretrain-GPT2/) | Megatron-DeepSpeed GPT-2 pre-training |
| [Nanotron](Nanotron/) | Nanotron distributed training framework |
| [NVIDIA-GPU-Distributed-Training](NVIDIA-GPU-Distributed-Training/) | NVIDIA GPU distributed training guide |
| [PyTorch-Distributed-Training](PyTorch-Distributed-Training/) | PyTorch distributed training patterns |
| [Training-Proposal](Training-Proposal/) | Training proposal and planning |

---

## 6. GPU Benchmarks & Hardware

Performance benchmarks, GPU selection guides, and hardware-specific tests.

| Project | Description |
|---------|-------------|
| [AI-Foundry-Model-Performance](AI-Foundry-Model-Performance/) | AI Foundry model performance testing |
| [AI-on-PC](AI-on-PC/) | Running AI models on PC hardware |
| ⭐ [Azure-AMD-MI300X-Benchmark-and-Inference](Azure-AMD-MI300X-Benchmark-and-Inference/) | AMD MI300X benchmarks + SFT and inference on Azure |
| [Azure-NC-NV-GPU-VM-Selection-Guide](Azure-NC-NV-GPU-VM-Selection-Guide/) | Azure GPU VM selection guide |
| [CPU2GPU](CPU2GPU/) | CPU to GPU migration guide |
| [GPU-benchmarking](GPU-benchmarking/) | General GPU benchmarking |
| [H100-A100-RTX6000-FP8-Benchmark](H100-A100-RTX6000-FP8-Benchmark/) | H100 vs A100 vs RTX6000 FP8 benchmark |
| [Install-CUDA](Install-CUDA/) | CUDA installation guide |
| [L20-H200](L20-H200/) | L20 and H200 GPU analysis |
| [NC-RTX-Pro-6000V6-BSE-Benchmark](NC-RTX-Pro-6000V6-BSE-Benchmark/) | NC RTX Pro 6000 v6 BSE benchmark |
| [PoC-Handbook-for-Azure-AMD-MI300X](PoC-Handbook-for-Azure-AMD-MI300X/) | PoC handbook for Azure AMD MI300X |
| [Qwen3-235B-Multi-Node-vLLM-Benchmark](Qwen3-235B-Multi-Node-vLLM-Benchmark/) | Qwen3 235B multi-node vLLM benchmark |
| [Qwen-32B-vLLM-FlashInfer-Benchmark](Qwen-32B-vLLM-FlashInfer-Benchmark/) | Qwen 32B vLLM FlashInfer benchmark |
| [RTX-Pro-6000D-Performance](RTX-Pro-6000D-Performance/) | RTX Pro 6000D performance testing |
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
| [Memory-comsuption-in-Training-and-Inference](Memory-comsuption-in-Training-and-Inference/) | Memory consumption analysis for training and inference |
| [ModernBERT](ModernBERT/) | ModernBERT architecture |
| [OAI-OSS-on-Azure](OAI-OSS-on-Azure/) | OpenAI OSS models on Azure |
| [Optimizers](Optimizers/) | Training optimizers comparison |
| [Phi4](Phi4/) | Phi-4 model analysis |
| [Qwen-Reranker](Qwen-Reranker/) | Qwen reranker model |
| [SLM-limitation](SLM-limitation/) | Small Language Model limitations |
| [SLM-Win-LLM](SLM-Win-LLM/) | When SLMs beat LLMs |
| [Thinking-GenAI](Thinking-GenAI/) | Thinking about GenAI concepts |
| [UniAD](UniAD/) | UniAD unified autonomous driving |
