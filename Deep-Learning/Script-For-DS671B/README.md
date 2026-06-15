# Scripts for DeepSeek 671B

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

## Overview

Utility scripts for running and benchmarking DeepSeek 671B model inference on Azure GPU VMs.

## Key Topics

- DeepSeek 671B model deployment
- Multi-GPU inference setup
- Performance benchmarking scripts

## Project Structure

| File | Description |
|------|-------------|
| `callapi.py` | Callapi |
| `gpuvm.py` | Gpuvm |

## Getting Started

### Prerequisites

- Python 3.10+
- Azure subscription (for cloud resources)
- CUDA-compatible GPU (recommended)

### Setup

```bash
git clone <this-repo-url>
cd Script-For-DS671B
pip install -r requirements.txt
```

## Running on Azure

This project is designed to run on Azure GPU VMs. Refer to the scripts and notebooks for specific configuration details.

## License

MIT
