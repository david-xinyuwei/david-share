# 🔬 DL Algorithm Insights

> **Deep Learning Algorithms Explained with Real-World Experiments and Runnable Demos**

This series takes a **practitioner-first** approach to deep learning algorithms. Each topic is a self-contained module that explains one algorithm concept in depth — with theory, intuition, real benchmark data from H100/A100 GPUs, and a minimal runnable demo you can execute locally without a GPU.

## 📖 Philosophy

Most algorithm tutorials fall into two camps:
- **Theory-only**: Math-heavy papers that engineers can't apply
- **Code-only**: Copy-paste recipes without understanding *why*

This series bridges both: **understand the math intuitively, then verify it with code and real data.**

## 📚 Topic Index

> Topics are ordered by dependency — later topics build on earlier ones.

| # | Topic | Key Concept | Demo |
|---|-------|-------------|------|
| 01 | SSIM — Structural Similarity | Image quality metric: luminance × contrast × structure | `ssim_demo.py` |
| 02 | LoRA — Low-Rank Adaptation | Efficient fine-tuning: W ≈ W₀ + BA | `lora_demo.py` |
| 03 | Diffusion Distillation | Reduce denoising steps: 50→8 via trajectory alignment | `distill_demo.py` |
| 04 | FlashAttention — IO-Aware Attention | Tiling + recomputation to avoid O(N²) memory | `flash_attn_demo.py` |
| 05 | BF16 Numerical Accumulation | Why mathematically equivalent ops give different results | `bf16_demo.py` |
| 06 | CFG — Classifier-Free Guidance | One parameter to control generation "creativity" | `cfg_demo.py` |
| 07 | KV Cache & PagedAttention | Why LLM inference eats so much memory | `kv_cache_demo.py` |
| 08 | Speculative Decoding | Let a small model "draft" for the large model | `spec_decode_demo.py` |
| 09 | FP8 Quantization | Cut precision in half — how much speed gain, how much quality loss? | `fp8_demo.py` |
| 10 | LPIPS — Learned Perceptual Similarity | Why deep features beat pixel-level metrics | `lpips_demo.py` |

> 📌 More topics will be added as the series grows.

## 🏗️ Structure

Each topic follows a consistent structure:

```
XX-Topic-Name/
├── README.md          # English: theory + intuition + real benchmark data
├── README-CN.md       # Chinese: 中文版
├── xxx_demo.py        # Minimal runnable demo (CPU-friendly, no GPU required)
├── images/            # Architecture diagrams, comparison charts
└── data/              # Real experiment data (JSON/CSV)
```

## 🎯 Who Is This For?

- **ML Engineers** who use frameworks daily but want to understand the algorithms underneath
- **System Engineers** working on AI infrastructure who need algorithm-level insights
- **Students** looking for intuitive explanations backed by real experiments

## 🔗 Relationship to Other Sections

| Section | Focus | This Section |
|---------|-------|-------------|
| [Deep-Learning/](../Deep-Learning/) | Engineering practice — production deployments, benchmarks, integrations | Algorithm theory — *why* things work, explained with demos |
| [Multimodal-Models/](../Multimodal-Models/) | End-to-end multimodal applications | Foundational concepts used *in* those applications |

## ✍️ Author

**Xinyu Wei (魏新宇)**
- Microsoft AI GBB Senior System Engineer
- Author of "Principles, Training, and Applications of Large Language Models"

---

*Each insight is backed by real experiments on Azure H100/A100 GPUs. No fabricated data, no hand-waving — just facts and code.*
