# SFT on RTX 6000 Pro

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

## 概述

Supervised Fine-Tuning (SFT) experiments and benchmarks on NVIDIA RTX 6000 Pro Ada Generation GPUs on Azure NC v6 series VMs.

## 核心主题

- Fine-tuning LLMs on professional GPUs
- Azure NC v6 VM configuration
- Training performance metrics
- LoRA and full fine-tuning comparison

## 快速开始

### 前提条件

- Python 3.10+
- Azure 订阅（用于云资源）
- CUDA 兼容 GPU（推荐）

### 环境搭建

```bash
git clone <this-repo-url>
cd SFT-on-RTX-6000-Pro
```

## 在 Azure 上运行

本项目设计在 Azure GPU VM 上运行。详细配置请参考脚本和 Notebook。

## 许可证

MIT
