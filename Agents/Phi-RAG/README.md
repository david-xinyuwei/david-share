# Phi-RAG: RAG with Phi Models

> [!NOTE]
> **Archived.** This project predates June 2026 and uses models or APIs that have since been superseded (Phi-2 and Phi-3). It stays here so existing links keep working; check current documentation before reusing the steps. Newer related work: [Foundry-IQ](../Foundry-IQ/).

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

## Overview

Implementation of Retrieval-Augmented Generation (RAG) using Microsoft Phi models on Azure, demonstrating efficient knowledge retrieval and generation.

## Key Topics

- RAG pipeline architecture
- Phi model integration
- Azure AI Search configuration
- Document chunking and embedding

## Project Structure

| File | Description |
|------|-------------|
| `v3-chromadb/db.py` | Db |
| `v3-chromadb/keyword_generator.py` | Keyword Generator |
| `v3-chromadb/llm.py` | Llm |
| `v3-chromadb/main.py` | Main |

## License

MIT
