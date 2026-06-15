# Phi-RAG: RAG with Phi Models

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

## 概述

Implementation of Retrieval-Augmented Generation (RAG) using Microsoft Phi models on Azure, demonstrating efficient knowledge retrieval and generation.

## 核心主题

- RAG pipeline architecture
- Phi model integration
- Azure AI Search configuration
- Document chunking and embedding

## 项目结构

| 文件 | 描述 |
|------|------|
| `v3-chromadb/db.py` | Db |
| `v3-chromadb/keyword_generator.py` | Keyword Generator |
| `v3-chromadb/llm.py` | Llm |
| `v3-chromadb/main.py` | Main |

## 快速开始

### 前提条件

- Python 3.10+
- Azure 订阅（用于云资源）
- CUDA 兼容 GPU（推荐）

### 环境搭建

```bash
git clone <this-repo-url>
cd Phi-RAG
pip install -r requirements.txt
```

## 在 Azure 上运行

本项目设计在 Azure GPU VM 上运行。详细配置请参考脚本和 Notebook。

## 许可证

MIT
