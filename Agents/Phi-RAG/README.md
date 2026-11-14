# Phi-RAG: RAG with Phi Models

> [!NOTE]
> **Archived.** This project predates June 2026 and uses models or APIs that have since been superseded (Phi-2 and Phi-3). It stays here so existing links keep working; check current documentation before reusing the steps. Newer related work: [Foundry-IQ](../Foundry-IQ/).

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI Lead Senior System Engineer

**English** | [中文](README-CN.md)

## Overview

Implementation of Retrieval-Augmented Generation (RAG) using Microsoft Phi models on Azure, demonstrating efficient knowledge retrieval and generation.

## Key Topics

- RAG pipeline architecture
- Phi model integration
- Azure AI Search configuration
- Document chunking and embedding

## Project Structure

- [`v3-chromadb/db.py`](v3-chromadb/db.py)
- [`v3-chromadb/keyword_generator.py`](v3-chromadb/keyword_generator.py)
- [`v3-chromadb/llm.py`](v3-chromadb/llm.py)
- [`v3-chromadb/main.py`](v3-chromadb/main.py)

## License

MIT
