# GPT-4o vs GPT-5.1: Raw Results of an Earlier Migration Benchmark

[![Area: Agents](https://img.shields.io/badge/Area-Agents-0078D4)](../README.md) ![Type: Article](https://img.shields.io/badge/Type-Article-6E7781) ![Language: English](https://img.shields.io/badge/Language-English-8250DF) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](../../LICENSE)

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI Lead Senior System Engineer

This folder holds the raw output of a comparison run on 2026-01-22: [`benchmark_results.json`](benchmark_results.json), stored with Git LFS. The script that produced it is not included. For the maintained migration benchmarks, see [AOAI-Model-Migration-Benchmark](../AOAI-Model-Migration-Benchmark/) and [Model-And-Router-Benchmark](../Model-And-Router-Benchmark/).

## What was run

- 7 scenarios, 5 runs each, so 35 streaming requests per model.
- Short tasks: Chinese intent classification, English sentiment analysis. Medium tasks: Chinese and English RAG extraction, code explanation. Long tasks: a Chinese customer-service reply, an English product description.
- Each prompt carries about 1,030 tokens of padding with a fixed prompt cache key, so that prompt caching applies.

## Summary as recorded in the file

| Metric (35 requests per model) | gpt-4o | gpt-5.1 |
|---|---|---|
| Correct answers | 35 / 35 | 35 / 35 |
| Average end-to-end latency (s) | 1.45 | 1.72 |
| Average time to first token (s) | 0.54 | 0.97 |
| Share of input tokens served from the prompt cache | 95.9% | 74.3% |
| Total cost of the 35 requests (USD) | 0.0603 | 0.0258 |

Per-scenario values are in the JSON file. In 6 of the 7 scenarios gpt-4o had the lower average latency; in the long English product description, gpt-5.1 was faster (2.01 s vs 2.67 s).
