# From a Python GPU Kernel to Machine Code: Tile, Layout, MLIR, NVVM and ROCDL

[![Area: DL Algorithm Insights](https://img.shields.io/badge/Area-DL%20Algorithm%20Insights-0078D4)](../README.md) ![Type: Article](https://img.shields.io/badge/Type-Article-6E7781) ![Language: 中文](https://img.shields.io/badge/Language-%E4%B8%AD%E6%96%87-8250DF) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](../../LICENSE)

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI Lead Senior System Engineer

This article is currently available in Chinese only: **[README-CN.md](README-CN.md)**.

It follows a GPU kernel written in Python all the way down to machine code: how tiles and data layouts are expressed, how the kernel is lowered through MLIR, and the NVVM and ROCDL paths to NVIDIA and AMD GPUs.

[Back to DL Algorithm Insights](../README.md)
