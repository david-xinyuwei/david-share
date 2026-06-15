# Chapter 7: Production Deployment

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

## 概述

Code examples for Chapter 7, covering production deployment strategies for AI applications on Azure.

## 核心主题

- Production deployment patterns
- Scaling and monitoring
- Cost optimization

## 项目结构

| 文件 | 描述 |
|------|------|
| `optimize-llama-2-gptq.ipynb` | Optimize Llama 2 Gptq (Notebook) |
| `osschat-successfully.ipynb` | Osschat Successfully (Notebook) |

## 快速开始

### 前提条件

- Python 3.10+
- Azure 订阅（用于云资源）
- CUDA 兼容 GPU（推荐）

### 环境搭建

```bash
git clone <this-repo-url>
cd Chapter7
pip install -r requirements.txt
```

## 在 Azure 上运行

本项目设计在 Azure GPU VM 上运行。详细配置请参考脚本和 Notebook。

## 许可证

MIT
