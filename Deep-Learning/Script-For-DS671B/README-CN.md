# Scripts for DeepSeek 671B

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

## 概述

Utility scripts for running and benchmarking DeepSeek 671B model inference on Azure GPU VMs.

## 核心主题

- DeepSeek 671B model deployment
- Multi-GPU inference setup
- Performance benchmarking scripts

## 项目结构

| 文件 | 描述 |
|------|------|
| `callapi.py` | Callapi |
| `gpuvm.py` | Gpuvm |

## 快速开始

### 前提条件

- Python 3.10+
- Azure 订阅（用于云资源）
- CUDA 兼容 GPU（推荐）

### 环境搭建

```bash
git clone <this-repo-url>
cd Script-For-DS671B
pip install -r requirements.txt
```

## 在 Azure 上运行

本项目设计在 Azure GPU VM 上运行。详细配置请参考脚本和 Notebook。

## 许可证

MIT
