# Official Sources

Verified on 2026-07-31.

| Source | Purpose |
|---|---|
| [mini-swe-agent v2.4.6](https://github.com/SWE-agent/mini-swe-agent/tree/v2.4.6) | Agent source version and YAML/CLI documentation entry point |
| [mini-swe-agent documentation](https://mini-swe-agent.com/latest/) | Quick start, configuration and batch usage |
| [SWE-bench](https://github.com/SWE-bench/SWE-bench) | Official benchmark and Docker harness |
| [SWE-bench evaluation guide](https://www.swebench.com/SWE-bench/guides/evaluation/) | Prediction schema and official harness CLI |
| [SWE-bench Docker setup guide](https://www.swebench.com/SWE-bench/guides/docker_setup/) | Host resources, cache levels and worker guidance |
| [SWE-bench commit f7bbbb2](https://github.com/SWE-bench/SWE-bench/commit/f7bbbb2ccdf479001d6467c9e34af59e44a840f9) | Fix for new-file-only test patches resetting the working tree |
| [SWE-bench Verified dataset](https://huggingface.co/datasets/princeton-nlp/SWE-Bench_Verified) | Human-validated 500-case dataset |
| [SWE-bench paper](https://arxiv.org/abs/2310.06770) | Benchmark definition and research context |
| [Docker Engine installation](https://docs.docker.com/engine/install/) | Required local evaluation runtime |

The official SWE-bench README recommends an x86_64 host with approximately 120GB free storage, 16GB RAM, and 8 CPU cores for local evaluation. Adjust harness workers to the resources available to Docker.
