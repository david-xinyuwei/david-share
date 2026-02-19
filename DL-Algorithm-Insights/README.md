# DL-Algorithm-Insights

> **Deep learning algorithm concepts explained with real GPU experiment data and runnable demos.**

## 🎯 What Is This Series?

Each topic in this series takes **one algorithm concept** from real-world GPU experiments and explains it with:

- **Clear theory** — intuition first, math second
- **Real data** — from actual H100/A100 experiments, not textbook numbers
- **Runnable demo** — a minimal Python script you can run on your laptop (CPU-friendly, no GPU required)

**Target audience**: ML engineers, AI infrastructure engineers, and students who want to understand **why** things work, not just **how** to call the API.

---

## 📚 Topics

Core concepts in training, inference, optimization, and evaluation:

| # | Topic | Status |
|---|-------|:------:|
| 01 | **SSIM** — Structural Similarity Index | ⏳ |
| 02 | **LoRA** — Low-Rank Adaptation | ⏳ |
| 03 | **BF16 Numerical Accumulation** — Precision vs Performance | ⏳ |
| 04 | **Diffusion Distillation** — Trajectory & Progressive | ⏳ |
| 05 | **FlashAttention** — IO-Aware Exact Attention | ⏳ |
| 06 | **CFG** — Classifier-Free Guidance | ⏳ |
| 07 | **KV Cache & PagedAttention** — Memory-Efficient Inference | ⏳ |
| 08 | **Speculative Decoding** — Draft-Verify Acceleration | ⏳ |
| 09 | **FP8 Quantization** — Next-Gen Precision | ⏳ |
| 10 | **LPIPS** — Learned Perceptual Image Patch Similarity | ⏳ |

---

## 📂 Structure

Each topic follows a consistent structure:

```
XX-Topic-Name/
├── README.md          # English explanation
├── README-CN.md       # Chinese version
├── xxx_demo.py        # Minimal runnable demo (CPU-friendly)
├── images/            # Architecture diagrams & comparison charts
└── data/              # Small sample data for the demo
```

---

## 🏃 Quick Start

Every demo is designed to run on your laptop:

```bash
cd XX-Topic-Name/
pip install -r requirements.txt  # if exists
python xxx_demo.py
```

- **No GPU required** — all demos work on CPU
- **30 seconds** — results appear quickly
- **Self-contained** — no external data downloads needed

---

## 🧭 Philosophy

1. **One topic, one concept** — no concept soup
2. **Engineer-friendly** — intuition before formulas
3. **Evidence-based** — every claim backed by real experiment data
4. **Runnable** — if you can't run it, it's not explained well enough

---

**Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer
