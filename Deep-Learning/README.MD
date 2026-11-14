# Deep Learning

Projects on training, fine-tuning, serving and measuring models: fine-tuning and reinforcement learning, inference optimization, precision and quantization, GPU selection on NVIDIA and AMD, and distributed training. Most were run on Azure GPU VMs. Each folder is a self-contained project with its own README.

[Back to the main page](../README.md)

- [Fine-tuning, RL and alignment](#fine-tuning-rl-and-alignment)
- [Inference optimization and serving](#inference-optimization-and-serving)
- [Model sizing, deployment and evaluation on Azure](#model-sizing-deployment-and-evaluation-on-azure)
- [Precision and quantization](#precision-and-quantization)
- [GPUs and clusters](#gpus-and-clusters)
- [Training efficiency and distributed training](#training-efficiency-and-distributed-training)
- [Model architecture and concepts](#model-architecture-and-concepts)
- [Archive](#archive)

## Fine-tuning, RL and alignment

| Project | What it covers |
|---|---|
| [LLM-Fine-Tuning-and-Alignment](LLM-Fine-Tuning-and-Alignment/) | Complete guide to fine-tuning and alignment: SFT hyperparameters, SFT/ReFT/RLHF/DPO/PPO compared, LoRA/QLoRA/GaLore, DPO theory and practice |
| [LLM-RL-Training-and-Reasoning](LLM-RL-Training-and-Reasoning/) | RL training and reasoning: PPO and GRPO, reward design, the DeepSeek-R1 training architecture, and SFT + GRPO code with training logs |
| [AI-Foundry-Custom-Code-Training](AI-Foundry-Custom-Code-Training/) | Foundry Custom Code Training: hello world, SFT and GRPO with your own script, data and container on managed GPU compute |
| [Foundry-Agent-Post-Training-Deep-Dive](Foundry-Agent-Post-Training-Deep-Dive/) | Agent post-training on Foundry as announced at Build 2026: distillation, SFT, reinforcement fine-tuning and the low-level training API |
| [AIPC-Decision-Model-Finetune](AIPC-Decision-Model-Finetune/) | Fine-tuning a decision model, which picks an answer instead of generating text, and optimizing its inference on the edge |
| [AIPC-Agent-Training](AIPC-Agent-Training/) | Agent training flywheel for AI PCs |
| [Agent-Lighting](Agent-Lighting/) | Agent Lightning: end-to-end training of reasoning agents |
| [Qwen3-ASR-Training-Inference-Validation-on-Azure](Qwen3-ASR-Training-Inference-Validation-on-Azure/) | Validating an ASR model route on Azure: training bottlenecks, serving latency on vLLM, SGLang and TensorRT-LLM, and long-audio behavior |
| [DenseMixer-Better-MoE-Fine-Tuning](DenseMixer-Better-MoE-Fine-Tuning/) | DenseMixer for MoE fine-tuning |
| [EXAONE-Multi-LoRA-on-Azure](EXAONE-Multi-LoRA-on-Azure/) | vLLM multi-LoRA serving for EXAONE on Azure |
| [Multi-LoRA-adapter](Multi-LoRA-adapter/) | Multi-LoRA adapters in vLLM: switching, performance and chat templates |
| [SmolLM-Full-Fine-Tuning](SmolLM-Full-Fine-Tuning/) | Full fine-tuning of SmolLM |
| [Unsloth-Full-SFT](Unsloth-Full-SFT/) | Full fine-tuning with Unsloth, from adapters to full SFT |
| [Fine-Tuning-Tools-Axolotl-LLaMA-Factory](Fine-Tuning-Tools-Axolotl-LLaMA-Factory/) | Axolotl and LLaMA-Factory fine-tuning tool guides |
| [Fine-Tuning-Sentence-Embeddings](Fine-Tuning-Sentence-Embeddings/) | Fine-tuning a sentence-embedding model for domain-specific RAG |
| [Knowledge-Distillation](Knowledge-Distillation/) | Knowledge distillation techniques |
| [4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice](4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice/) | Azure OpenAI end-to-end fine-tuning in four steps |
| [Pre-Training-Methods-Explained](Pre-Training-Methods-Explained/) | Pre-training vs SFT, continued pre-training and synthetic instruction pre-training |
| [Make-High-Quality-Dataset-From-WARC](Make-High-Quality-Dataset-From-WARC/) | Building a pre-training dataset from WARC web archives |

## Inference optimization and serving

| Project | What it covers |
|---|---|
| [LLM-Inference-Optimization-on-Azure-GPU-VMs](LLM-Inference-Optimization-on-Azure-GPU-VMs/) | Three-layer inference optimization (serving framework, kernels, PD and fake-prefill workload) for MiMo-V2.5-Pro on ND MI300X v5: measured gains, 8K–256K context scaling, prefill replicas and accuracy checks |
| [Speculative-Decoding](Speculative-Decoding/) | Speculative decoding for open-model deployment: when to enable it, and MTP, DFlash 2 and draft-model adaptation compared |
| [Disaggregated-LLM-Inference](Disaggregated-LLM-Inference/) | Prefill/decode disaggregation: the six-layer stack, the major implementations, and a functional validation with SGLang and NVIDIA Dynamo on H100 |
| [vLLM-Architecture-and-Inference-Engines](vLLM-Architecture-and-Inference-Engines/) | vLLM internals (PagedAttention, continuous batching, CUDA graphs), FlashInfer vs FlashAttention benchmarks and other engines |
| [SGLang-vs-LLM](SGLang-vs-LLM/) | SGLang and vLLM inference engines compared |
| [KV-Cache-Deep-Dive](KV-Cache-Deep-Dive/) | KV cache from fundamentals to production sizing |
| [TurboQuant-Sub4bit-KV-Cache-Quantization](TurboQuant-Sub4bit-KV-Cache-Quantization/) | TurboQuant: KV cache at 3.5 bits per channel with near-zero accuracy loss |
| [KV-Cache-Quantization](KV-Cache-Quantization/) | KV cache quantization with FP8 and INT8 |
| [Network-Attached-KV-Cache](Network-Attached-KV-Cache/) | Scaling inference on consumer GPUs with a network-attached KV cache |
| [FlashAttention-3](FlashAttention-3/) | FlashAttention-3 explained |
| [MInference](MInference/) | MInference for long-context acceleration |
| [Budget-Forcing-Inference](Budget-Forcing-Inference/) | Budget forcing for thinking models |
| [torch-compile-tryon](torch-compile-tryon/) | torch.compile acceleration for a virtual try-on model |
| [AI-Inference-Workshop](AI-Inference-Workshop/) | AI inference workshop materials |
| [CPU2GPU](CPU2GPU/) | Methodology for moving inference workloads from CPU to GPU |

## Model sizing, deployment and evaluation on Azure

| Project | What it covers |
|---|---|
| [OSS-Model-Capacity-Planning-on-NVIDIA-GPUs](OSS-Model-Capacity-Planning-on-NVIDIA-GPUs/) | Reproducible capacity study with NVIDIA AIConfigurator for ND/NC H100: model, workload, service objectives and ranked configurations |
| [LLM-Memory-Estimation](LLM-Memory-Estimation/) | Inference memory estimation tool, with training and inference memory theory |
| [Managed-Compute-Private-Endpoint](Managed-Compute-Private-Endpoint/) | Locking down an open model on Foundry Managed Compute with a private endpoint, validated end to end |
| [OSS-Model-SWE-bench-Evaluation-Playbook](OSS-Model-SWE-bench-Evaluation-Playbook/) | SWE-bench Verified evaluation for open coding models: generation, official scoring, retesting of disputed results and troubleshooting |
| [AI-Foundry-Model-Performance](AI-Foundry-Model-Performance/) | Performance evaluation of Azure Machine Learning and Foundry model-catalog models |
| [Qwen3-Inference-Benchmark](Qwen3-Inference-Benchmark/) | Qwen3 and Qwen3.5 inference benchmark on Azure H100 |
| [Qwen3.5-122B-Azure-vs-AWS-Benchmark](Qwen3.5-122B-Azure-vs-AWS-Benchmark/) | Qwen3.5-122B-A10B-FP8 on 2× H100 NVL with SGLang: reproduction guide and Azure results |
| [Qwen3-VL-Product-Tagging-on-Azure](Qwen3-VL-Product-Tagging-on-Azure/) | Qwen3-VL for fashion retail on one Azure GPU: product image and text in, catalog-ready JSON tags out |
| [Qwen-Virtual-TryOn-Inference-Benchmark](Qwen-Virtual-TryOn-Inference-Benchmark/) | Qwen-Image-Edit virtual try-on inference benchmark |
| [Qwen-Reranker](Qwen-Reranker/) | Qwen3-Reranker-0.6B on Azure NC H100: vLLM assertion and stability fixes |
| [DeepSeek-R1-on-Azure](DeepSeek-R1-on-Azure/) | DeepSeek models on Azure |
| [OAI-OSS-on-Azure](OAI-OSS-on-Azure/) | OpenAI open-weight models on Azure |
| [Llama-4](Llama-4/) | Llama 4 on Azure Machine Learning and Foundry |
| [Fara-7B-Azure-Demo](Fara-7B-Azure-Demo/) | Fara-7B on Azure H100 with a Streamlit demo |

## Precision and quantization

| Project | What it covers |
|---|---|
| [Large-MoE-Precision-and-Deployment-Guide](Large-MoE-Precision-and-Deployment-Guide/) | Component-level precision for large MoE models (weights, activations, matmul operands, KV cache) across BF16, NVFP4 and FP8 releases, with BF16 and MXFP4-emulation runs on MI300X |
| [NVFP4](NVFP4/) | NVFP4 on NVIDIA Blackwell: analysis and engineering practice |
| [Quantization-Methods-Comparison-and-Practice](Quantization-Methods-Comparison-and-Practice/) | AutoRound, GPTQ and AWQ compared, AutoRound in practice, and the effect of the calibration dataset |
| [Ultra-Low-Bit-Quantization-Experiments](Ultra-Low-Bit-Quantization-Experiments/) | 1-bit BitNet, 2-bit VPTQ and quantization-threshold experiments |
| [Automatic-Mixed-Precision-in-AI](Automatic-Mixed-Precision-in-AI/) | Automatic mixed precision in training and inference |
| [BF16-FP16-RL](BF16-FP16-RL/) | BF16 vs FP16 for reinforcement learning |
| [GGUF-LoRA](GGUF-LoRA/) | GGUF LoRA adapters for CPU inference |

## GPUs and clusters

| Project | What it covers |
|---|---|
| [NC-RTX-Pro-6000V6-BSE-Benchmark](NC-RTX-Pro-6000V6-BSE-Benchmark/) | Azure GPU VM selection guide: H100, A100, RTX 6000 and A10 FP8 benchmarks plus the NC RTX PRO 6000 BSE VM |
| [Azure-AMD-MI300X-Guide](Azure-AMD-MI300X-Guide/) | AMD MI300X on Azure: benchmarks, inference and a PoC deployment handbook |
| [MI300X-vs-H200-Inference-Benchmark](MI300X-vs-H200-Inference-Benchmark/) | MI300X vs H200 for dense and MoE model inference |
| [MI300X-ROCm-Host-Driver-AllReduce-Regression](MI300X-ROCm-Host-Driver-AllReduce-Regression/) | Eight-GPU AllReduce on ND MI300X v5 fell from about 315 GB/s to 42 GB/s after the VM's AMDGPU driver and ROCm/RCCL were upgraded together |
| [Azure-GPU-Hours-Monitoring](Azure-GPU-Hours-Monitoring/) | Allocated vs actually used GPU hours per VM, owner, hour and day: DCGM, Azure Monitor Agent, Log Analytics and five KQL views |
| [Azure-CycleCloud-for-AI-Training](Azure-CycleCloud-for-AI-Training/) | Azure CycleCloud with Slurm for multi-node AI training: architecture and suitability analysis |
| [GPU-3D-Rendering-and-Reconstruction](GPU-3D-Rendering-and-Reconstruction/) | GPU architecture from 3D rendering to AI inference, for inference engineers |
| [NVIDIA-Groq-LPU-Architecture](NVIDIA-Groq-LPU-Architecture/) | NVIDIA Groq LPU architecture, from TSP to the Vera Rubin platform |
| [Install-CUDA](Install-CUDA/) | Installing NVIDIA drivers and the CUDA toolkit step by step |

## Training efficiency and distributed training

| Project | What it covers |
|---|---|
| [Distributed-Training-Parallelism-Guide](Distributed-Training-Parallelism-Guide/) | DP, TP, PP and ZeRO explained, with PyTorch, NVIDIA and DeepSpeed distributed training |
| [DeepEP](DeepEP/) | DeepSeek DeepEP: communication optimization for MoE expert parallelism |
| [Easy-way-to-Understand-Training](Easy-way-to-Understand-Training/) | Training concepts explained intuitively |
| [How-to-Run-Training-Faster](How-to-Run-Training-Faster/) | Techniques to speed up training |
| [Optimizers](Optimizers/) | Choosing a training optimizer |
| [Padding-Free](Padding-Free/) | Padding-free training in practice |
| [Pretraining-Frameworks-Megatron-Nanotron](Pretraining-Frameworks-Megatron-Nanotron/) | Pre-training with Megatron-DeepSpeed (GPT-2) and Hugging Face Nanotron |
| [Training-Proposal](Training-Proposal/) | Customer AI training proposal |

## Model architecture and concepts

| Project | What it covers |
|---|---|
| [Phi-Model-Family](Phi-Model-Family/) | Phi-4, Phi-3.5 MoE/mini and Phi-3: architecture, quantization and fine-tuning |
| [Gemma3n-MatFormer](Gemma3n-MatFormer/) | Gemma 3n and the MatFormer nested architecture |
| [ModernBERT](ModernBERT/) | ModernBERT architecture |
| [Implementing-llama3-from-scratch](Implementing-llama3-from-scratch/) | Implementing Llama 3 from scratch |
| [LLM-Hallucinations-Analysis-and-Mitigation](LLM-Hallucinations-Analysis-and-Mitigation/) | Why LLMs hallucinate and how to mitigate it |
| [Thinking-GenAI](Thinking-GenAI/) | Notes on where generative AI is heading |
| [UniAD](UniAD/) | UniAD autonomous-driving model: FlashAttention-2 optimization package |
| [VAD-Training](VAD-Training/) | VAD: vectorized scene representation for autonomous-driving perception |

## Archive

These projects stay in place so existing links keep working. The models, APIs or tool versions they use have since been superseded; check current documentation before reusing the steps.

| Project | What it covered |
|---|---|
| [7-Inference-Frameworks-for-LLM](7-Inference-Frameworks-for-LLM/) | Seven LLM inference frameworks compared; see [vLLM-Architecture-and-Inference-Engines](vLLM-Architecture-and-Inference-Engines/) |
| [AI-on-PC](AI-on-PC/) | Validating AI models on a PC; see [AIPC-Decision-Model-Finetune](AIPC-Decision-Model-Finetune/) |
| [Function-Call-Training](Function-Call-Training/) | Training a Phi-3 model for function calling |
| [LLM-Inference-performance-test](LLM-Inference-performance-test/) | LLM inference performance test |
| [Llama-3.1-Fine-Tuning-Guide](Llama-3.1-Fine-Tuning-Guide/) | Llama 3.1 fine-tuning: 8B single-GPU LoRA and 70B multi-GPU FSDP |
| [LoRA-Training-Different-LM-Modules](LoRA-Training-Different-LM-Modules/) | LoRA applied to different model modules |
| [Pytorch-PEFT-SFT-to-ONNX](Pytorch-PEFT-SFT-to-ONNX/) | PyTorch PEFT SFT exported to ONNX |
| [Script-For-DS671B](Script-For-DS671B/) | Scripts for DeepSeek 671B inference; see [DeepSeek-R1-on-Azure](DeepSeek-R1-on-Azure/) |
