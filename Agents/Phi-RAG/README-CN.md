# Phi-RAG: RAG with Phi Models

> [!NOTE]
> **已归档。** 本项目写于 2026 年 6 月之前，所用模型或 API 已有更新版本（Phi-2、Phi-3）。保留在这里是为了让已有链接继续可用；复用其中步骤前请先核对最新文档。新的相关项目：[Foundry-IQ](../Foundry-IQ/)。

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

## 许可证

MIT
