# Companion Code for *Edge-Side AI: Training, Optimizing and Deploying Small Models*

English | [中文](README-CN.md)

> **Author**: Xinyu Wei (魏新宇) — Senior AI System Engineer, Microsoft AI GBB  
> **Publisher**: China Machine Press (机械工业出版社), 2026

This folder collects every code listing that appears in the book《边缘侧AI小模型训练、优化与部署》, plus snapshots of the full david-share projects the book cites, organised by chapter for readers to download alongside the book.

## Layout

| Folder | Chapter | Content |
|---|---|---|
| — | Chapter 1: AI on Edge — value, capabilities and adoption path | no code |
| [`Chapter2-Dataset-Preparation/`](Chapter2-Dataset-Preparation/) | Chapter 2: Preparing and Augmenting High-Quality Datasets for the Edge | 20 listings/samples, 2 project snapshots |
| [`Chapter3-Training-and-Deployment/`](Chapter3-Training-and-Deployment/) | Chapter 3: Training and Deploying Models on the Edge | 19 listings/samples, 4 project snapshots |
| [`Chapter4-Fine-Tuning/`](Chapter4-Fine-Tuning/) | Chapter 4: Fine-Tuning Models for the Edge | 15 listings/samples, 2 project snapshots |
| [`Chapter5-Inference-and-Training-Optimization/`](Chapter5-Inference-and-Training-Optimization/) | Chapter 5: Efficient Inference and Performance Optimization on the Edge | 9 listings/samples, 1 project snapshots |
| [`Chapter6-Multimodal-Assistant-CSharp/`](Chapter6-Multimodal-Assistant-CSharp/) | Chapter 6: Building a Multimodal AI Assistant on the AI PC | 9 listings/samples |
| [`Chapter7-Vision-Language-Models/`](Chapter7-Vision-Language-Models/) | Chapter 7: Vision-Language Models and Computer Vision on the Edge | 9 listings/samples, 3 project snapshots |

Inside each chapter folder:

- `N.N.N_*.py / .sh / .cs / .json / .yaml` — the listings of the corresponding section, cleaned up from the printed text into parseable files; step-by-step listings are merged and omitted imports are marked 补充.
- `samples/` — data samples, prompt templates and run outputs shown in the book.
- `notes/` — formulas that the book typesets as code blocks.
- `projects/` — snapshots of the full david-share projects the book cites (scripts, notebooks, write-ups); original locations are listed in each chapter README and images link back to them.
- `README-CN.md` / `README.md` — section → file map and the differences from the printed text.

## Repository links cited in the book

| Where | Printed link | Current folder |
|---|---|---|
| §3.1.2 | `Deep-Learning/SmolLM-Full-Fine-Tuning` | [`Deep-Learning/SmolLM-Full-Fine-Tuning`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/SmolLM-Full-Fine-Tuning) (copy under `Chapter3-Training-and-Deployment/projects/`) |
| §3.2.2 | `Deep-Learning/SLM-DeepSeek-R1` | [`Deep-Learning/LLM-RL-Training-and-Reasoning`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/LLM-RL-Training-and-Reasoning) (copy under `Chapter3-Training-and-Deployment/projects/`) |
| §3.6.3 | `davidwei-ai/AIPC-Agent-Training` | [`Deep-Learning/AIPC-Agent-Training`](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/AIPC-Agent-Training) (copy under `Chapter3-Training-and-Deployment/projects/`) |

## Usage

```bash
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Code-of-Book-Edge-AI/Chapter3-Training-and-Deployment
pip install -r requirements.txt
python 3.2.2_sft_phi4_reasoning.py
```

All experiments in the book were run on Azure GPU VMs (NVIDIA A100 80GB / H100); Chapter 6 is a C#/WPF sample for Windows AI PCs. Adjust model/data paths and memory-related settings before running.

## License

MIT
