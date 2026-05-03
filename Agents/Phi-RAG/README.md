# Phi-RAG: RAG with Phi Models

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

## Getting Started

### Prerequisites

- Python 3.10+
- Azure subscription (for cloud resources)
- CUDA-compatible GPU (recommended)

### Setup

```bash
git clone <this-repo-url>
cd Phi-RAG
pip install -r requirements.txt
```

## Running on Azure

This project is designed to run on Azure GPU VMs. Refer to the scripts and notebooks for specific configuration details.

## License

MIT
