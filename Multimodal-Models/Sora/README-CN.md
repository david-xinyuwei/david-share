# Sora Video Generation on Azure

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

## 概述

Examples and utilities for using video generation models through Azure OpenAI, including API integration and batch processing.

## 核心主题

- Azure OpenAI video generation API
- Batch video processing
- Parameter optimization for video quality

## 项目结构

| 文件 | 描述 |
|------|------|
| `azure-api/demo.py` | Demo |
| `azure-api/sora_client.py` | Sora Client |

## 快速开始

### 前提条件

- Python 3.10+
- Azure 订阅（用于云资源）
- CUDA 兼容 GPU（推荐）

### 环境搭建

```bash
git clone <this-repo-url>
cd Sora
pip install -r requirements.txt
```

## 在 Azure 上运行

本项目设计在 Azure GPU VM 上运行。详细配置请参考脚本和 Notebook。

## 许可证

MIT
