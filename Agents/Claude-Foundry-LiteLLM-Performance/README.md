# Claude 5.5 through LiteLLM on Microsoft Foundry: Parameters, Prompt Cache and Performance

[![Models](https://img.shields.io/badge/models-Opus%20%C2%B7%20Sonnet%20%C2%B7%20Haiku%205.5-0078D4)](#purpose)
[![Measured](https://img.shields.io/badge/measured-2026--10--26%20to%2010--27-0078D4)](#results)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml)

Author: Xinyu Wei · [中文](README_CN.md)

## Purpose

**Question.** Which Claude settings reach Microsoft Foundry through LiteLLM, does the upstream prompt cache actually get reused, and what latency, output rate and cost does each configuration produce? This repository provides measured requests, evidence checks and reproduction steps for Opus 5.5, Sonnet 5.5 and Haiku 5.5. The tested deployments used [Hosted on Azure](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options), model version 2, GlobalStandard. Public coding problems provide controlled inputs, not evidence about your production workload.

**Completed ACA run:** 650/650 requests retained, 624 measured answers graded. Performance comes first below, followed by correctness. [Full results](docs/results.md#aca-gateway-snapshot).

**Current test method.** Linux VM client → LiteLLM on Azure Container Apps → Foundry, with the client, gateway and Foundry resource in East US 2. The client uses the gateway key; LiteLLM uses its managed identity to call Foundry. Prompt caching is enabled with top-level `cache_control`. Each model has one request in flight, so this measures individual requests, not load.

<img src="images/topology-en.svg" width="900" alt="Current cache-enabled test path: a Linux VM client sends streaming requests through LiteLLM on Azure Container Apps in East US 2 to the three Microsoft Foundry Claude deployments. Prompt caching is at Foundry; the client records timing and native usage." />

Original test-topology diagram using unmodified [Azure icons](images/icon-sources.json).

**Responsibility and scope.** LiteLLM forwards requests; the upstream model service owns the prompt cache. These scripts collect and verify evidence. Operators must validate their own gateway version, routes and workload. Production capacity, historical incident resolution and an AWS comparison are not established. Earlier direct and cross-region runs remain separate in [Results](docs/results.md#historical-evidence).

## Results

### ACA gateway: performance results

**Complete collection, not universal success.** All 650/650 requests are retained: 26 warm-ups and 624 measured answers. The run reached `COMPLETED` at `2026-10-27T08:37:15.795+00:00`. Failures and truncations remain in the counts. [Collection verification](evidence/gateway-cache-20261026/collection-status.json).

**Question and method.** For coding prompts sent through the East US 2 ACA LiteLLM gateway, does the identical second request read the cache written by the first, and what timing and cost were observed? The client and gateway were in East US 2; the Foundry resource was also in East US 2. One request was in flight per model. This is a cache-write versus cache-read pair, not a cache-disabled control or a gateway-overhead experiment.

**Input.** [12 public SWE-bench Lite BM25-13K problems](data/gateway-cache-problems.json), with the source revision and prompt hashes in [run.json](evidence/gateway-cache-20261026/run.json). This is a selected-subset experiment, not a full SWE-bench leaderboard score or customer production data. The [runner](gateway-cache/aca_cache_matrix.py) uses 26 mode/effort cells, two identical requests per problem/cell and one warm-up per cell. Fixed: `max_tokens: 128000`, `stream: true`, top-level `cache_control: {"type": "ephemeral", "ttl": "1h"}`. Timing starts immediately before the client sends the request; first text is the first non-empty text delta, not a ping or thinking event.

**Captured input settings.** The following fields are from measured request `opus|adaptive|low|django__django-12184|r1`, not its warm-up. The problem manifest above pins the public input reconstruction; this metrics projection omits prompt bodies.

```json
{
  "model": "claude-opus-5-5",
  "max_tokens": 128000,
  "stream": true,
  "thinking": {
    "type": "adaptive"
  },
  "output_config": {
    "effort": "low"
  },
  "cache_control": {
    "type": "ephemeral",
    "ttl": "1h"
  }
}
```

The runner prepends a deterministic system identifier per problem/configuration to isolate each pair's cache. The problem text is shared across configurations, but these identifiers differ. This controlled reuse is not an estimate of production cache-hit rate.

**Metric definitions.** TTFT is `timing.first_text`, the first non-empty visible text, not metadata or thinking. E2E is `timing.end`, through the end of the response stream. The client clock starts immediately before HTTP; credential acquisition, pacing and application/tool work are excluded. End-to-end output rate is `usage.output_tokens / timing.end` for each request, including thinking tokens; its P50 is not a ratio of medians or isolated decode speed. Costs include input, cache writes/reads and output at the recorded list prices, not infrastructure or an invoice.

**All measured configurations, performance first.** A pair is the same problem and configuration sent twice: an observed cache write followed by a native cache hit, with both answers completed. Each state below uses one request from every eligible pair. P50/P95 use nearest rank; with at most 12 requests per state, P95 is the largest observation, not a production tail guarantee. `default` means effort was omitted. Compare matching configurations; generated output lengths may differ, so a timing or cost difference cannot be attributed entirely to caching.

#### Opus 5.5

**Latency by configuration.**

| Model / thinking.type / output_config.effort | Cache state | TTFT P50 / P95 (s) | E2E P50 / P95 (s) | Valid requests |
|---|---|---:|---:|---:|
| Opus 5.5<br>`adaptive` / `low` | First write | 1.19 / 9.06 | 6.94 / 14.4 | 12 |
| Opus 5.5<br>`adaptive` / `low` | Cache hit | 1.08 / 14.7 | 7.84 / 20.0 | 12 |
| Opus 5.5<br>`adaptive` / `medium` | First write | 6.92 / 31.5 | 11.6 / 37.2 | 12 |
| Opus 5.5<br>`adaptive` / `medium` | Cache hit | 7.15 / 29.3 | 11.3 / 35.3 | 12 |
| Opus 5.5<br>`adaptive` / `high` | First write | 9.13 / 94.5 | 14.0 / 101 | 12 |
| Opus 5.5<br>`adaptive` / `high` | Cache hit | 7.53 / 228 | 11.7 / 239 | 12 |
| Opus 5.5<br>`adaptive` / `xhigh` | First write | 18.9 / 110 | 24.7 / 117 | 12 |
| Opus 5.5<br>`adaptive` / `xhigh` | Cache hit | 19.6 / 380 | 24.5 / 389 | 12 |
| Opus 5.5<br>`adaptive` / `max` | First write | 232 / 1027 | 247 / 1036 | 11 |
| Opus 5.5<br>`adaptive` / `max` | Cache hit | 236 / 913 | 249 / 922 | 11 |
| Opus 5.5<br>`adaptive` / `default` | First write | 7.03 / 65.8 | 12.0 / 72.3 | 11 |
| Opus 5.5<br>`adaptive` / `default` | Cache hit | 8.02 / 28.5 | 15.0 / 34.3 | 11 |

**Output rate and cost for the same requests.**

| Model / thinking.type / output_config.effort | Cache state | E2E output rate P50 (tokens/s, thinking included) | Mean cost (USD/request) | Valid requests |
|---|---|---:|---:|---:|
| Opus 5.5<br>`adaptive` / `low` | First write | 103.53 | $0.158921 | 12 |
| Opus 5.5<br>`adaptive` / `low` | Cache hit | 103.75 | $0.023222 | 12 |
| Opus 5.5<br>`adaptive` / `medium` | First write | 108.44 | $0.173419 | 12 |
| Opus 5.5<br>`adaptive` / `medium` | Cache hit | 111.76 | $0.036952 | 12 |
| Opus 5.5<br>`adaptive` / `high` | First write | 110.21 | $0.200936 | 12 |
| Opus 5.5<br>`adaptive` / `high` | Cache hit | 110.93 | $0.097379 | 12 |
| Opus 5.5<br>`adaptive` / `xhigh` | First write | 112.87 | $0.248050 | 12 |
| Opus 5.5<br>`adaptive` / `xhigh` | Cache hit | 114.35 | $0.183598 | 12 |
| Opus 5.5<br>`adaptive` / `max` | First write | 123.30 | $1.008633 | 11 |
| Opus 5.5<br>`adaptive` / `max` | Cache hit | 121.91 | $0.785095 | 11 |
| Opus 5.5<br>`adaptive` / `default` | First write | 109.83 | $0.186835 | 11 |
| Opus 5.5<br>`adaptive` / `default` | Cache hit | 109.88 | $0.037639 | 11 |

#### Sonnet 5.5

**Latency by configuration.**

| Model / thinking.type / output_config.effort | Cache state | TTFT P50 / P95 (s) | E2E P50 / P95 (s) | Valid requests |
|---|---|---:|---:|---:|
| Sonnet 5.5<br>`adaptive` / `low` | First write | 0.77 / 0.95 | 4.86 / 9.76 | 12 |
| Sonnet 5.5<br>`adaptive` / `low` | Cache hit | 0.76 / 1.15 | 4.88 / 9.01 | 12 |
| Sonnet 5.5<br>`adaptive` / `medium` | First write | 0.81 / 11.0 | 5.67 / 14.4 | 12 |
| Sonnet 5.5<br>`adaptive` / `medium` | Cache hit | 0.87 / 16.3 | 6.15 / 19.1 | 12 |
| Sonnet 5.5<br>`adaptive` / `high` | First write | 6.05 / 137 | 10.6 / 140 | 12 |
| Sonnet 5.5<br>`adaptive` / `high` | Cache hit | 7.44 / 119 | 10.7 / 122 | 12 |
| Sonnet 5.5<br>`adaptive` / `xhigh` | First write | 20.7 / 246 | 24.0 / 254 | 12 |
| Sonnet 5.5<br>`adaptive` / `xhigh` | Cache hit | 16.1 / 341 | 19.4 / 354 | 12 |
| Sonnet 5.5<br>`adaptive` / `max` | First write | 394 / 616 | 397 / 622 | 9 |
| Sonnet 5.5<br>`adaptive` / `max` | Cache hit | 364 / 743 | 367 / 751 | 9 |
| Sonnet 5.5<br>`adaptive` / `default` | First write | 6.86 / 86.8 | 10.8 / 90.2 | 12 |
| Sonnet 5.5<br>`adaptive` / `default` | Cache hit | 5.78 / 152 | 8.39 / 156 | 12 |
| Sonnet 5.5<br>`between_tools` / `low` | First write | 0.78 / 1.08 | 5.14 / 7.88 | 12 |
| Sonnet 5.5<br>`between_tools` / `low` | Cache hit | 0.76 / 0.91 | 4.51 / 8.22 | 12 |
| Sonnet 5.5<br>`between_tools` / `medium` | First write | 0.83 / 1.06 | 5.41 / 9.18 | 12 |
| Sonnet 5.5<br>`between_tools` / `medium` | Cache hit | 0.79 / 0.93 | 4.60 / 9.87 | 12 |
| Sonnet 5.5<br>`between_tools` / `high` | First write | 0.81 / 1.09 | 5.56 / 11.6 | 12 |
| Sonnet 5.5<br>`between_tools` / `high` | Cache hit | 0.82 / 1.18 | 7.03 / 13.1 | 12 |
| Sonnet 5.5<br>`between_tools` / `default` | First write | 0.79 / 1.15 | 4.88 / 13.6 | 12 |
| Sonnet 5.5<br>`between_tools` / `default` | Cache hit | 0.78 / 1.07 | 5.46 / 10.2 | 12 |

**Output rate and cost for the same requests.**

| Model / thinking.type / output_config.effort | Cache state | E2E output rate P50 (tokens/s, thinking included) | Mean cost (USD/request) | Valid requests |
|---|---|---:|---:|---:|
| Sonnet 5.5<br>`adaptive` / `low` | First write | 130.16 | $0.077371 | 12 |
| Sonnet 5.5<br>`adaptive` / `low` | Cache hit | 123.18 | $0.008869 | 12 |
| Sonnet 5.5<br>`adaptive` / `medium` | First write | 124.97 | $0.078745 | 12 |
| Sonnet 5.5<br>`adaptive` / `medium` | Cache hit | 124.24 | $0.010499 | 12 |
| Sonnet 5.5<br>`adaptive` / `high` | First write | 141.38 | $0.106288 | 12 |
| Sonnet 5.5<br>`adaptive` / `high` | Cache hit | 138.87 | $0.034861 | 12 |
| Sonnet 5.5<br>`adaptive` / `xhigh` | First write | 148.80 | $0.152607 | 12 |
| Sonnet 5.5<br>`adaptive` / `xhigh` | Cache hit | 149.31 | $0.109698 | 12 |
| Sonnet 5.5<br>`adaptive` / `max` | First write | 156.49 | $0.804891 | 9 |
| Sonnet 5.5<br>`adaptive` / `max` | Cache hit | 158.34 | $0.635133 | 9 |
| Sonnet 5.5<br>`adaptive` / `default` | First write | 140.69 | $0.100876 | 12 |
| Sonnet 5.5<br>`adaptive` / `default` | Cache hit | 141.88 | $0.035923 | 12 |
| Sonnet 5.5<br>`between_tools` / `low` | First write | 126.13 | $0.077653 | 12 |
| Sonnet 5.5<br>`between_tools` / `low` | Cache hit | 130.11 | $0.008496 | 12 |
| Sonnet 5.5<br>`between_tools` / `medium` | First write | 132.11 | $0.077994 | 12 |
| Sonnet 5.5<br>`between_tools` / `medium` | Cache hit | 133.30 | $0.009313 | 12 |
| Sonnet 5.5<br>`between_tools` / `high` | First write | 130.38 | $0.079108 | 12 |
| Sonnet 5.5<br>`between_tools` / `high` | Cache hit | 129.14 | $0.011469 | 12 |
| Sonnet 5.5<br>`between_tools` / `default` | First write | 130.06 | $0.078623 | 12 |
| Sonnet 5.5<br>`between_tools` / `default` | Cache hit | 133.11 | $0.010259 | 12 |

#### Haiku 5.5

**Latency by configuration.**

| Model / thinking.type / output_config.effort | Cache state | TTFT P50 / P95 (s) | E2E P50 / P95 (s) | Valid requests |
|---|---|---:|---:|---:|
| Haiku 5.5<br>`adaptive` / `low` | First write | 3.09 / 20.2 | 4.93 / 22.9 | 12 |
| Haiku 5.5<br>`adaptive` / `low` | Cache hit | 4.25 / 17.6 | 5.75 / 20.7 | 12 |
| Haiku 5.5<br>`adaptive` / `medium` | First write | 6.92 / 13.8 | 8.30 / 15.3 | 12 |
| Haiku 5.5<br>`adaptive` / `medium` | Cache hit | 6.93 / 14.2 | 8.02 / 16.8 | 12 |
| Haiku 5.5<br>`adaptive` / `high` | First write | 9.07 / 38.5 | 10.8 / 40.3 | 12 |
| Haiku 5.5<br>`adaptive` / `high` | Cache hit | 12.1 / 29.6 | 14.1 / 34.0 | 12 |
| Haiku 5.5<br>`adaptive` / `xhigh` | First write | 61.3 / 460 | 63.2 / 463 | 11 |
| Haiku 5.5<br>`adaptive` / `xhigh` | Cache hit | 53.4 / 235 | 57.0 / 237 | 11 |
| Haiku 5.5<br>`adaptive` / `max` | First write | 204 / 399 | 206 / 406 | 8 |
| Haiku 5.5<br>`adaptive` / `max` | Cache hit | 260 / 377 | 262 / 384 | 8 |
| Haiku 5.5<br>`adaptive` / `default` | First write | 5.49 / 15.5 | 7.40 / 18.4 | 12 |
| Haiku 5.5<br>`adaptive` / `default` | Cache hit | 6.22 / 11.6 | 8.07 / 14.2 | 12 |
| Haiku 5.5<br>`disabled` / `low` | First write | 0.48 / 0.83 | 2.29 / 3.37 | 12 |
| Haiku 5.5<br>`disabled` / `low` | Cache hit | 0.56 / 0.74 | 2.36 / 3.51 | 12 |
| Haiku 5.5<br>`disabled` / `medium` | First write | 0.54 / 0.73 | 2.42 / 3.47 | 12 |
| Haiku 5.5<br>`disabled` / `medium` | Cache hit | 0.50 / 0.60 | 2.64 / 4.31 | 12 |
| Haiku 5.5<br>`disabled` / `high` | First write | 0.49 / 0.72 | 2.67 / 4.51 | 12 |
| Haiku 5.5<br>`disabled` / `high` | Cache hit | 0.49 / 0.69 | 2.40 / 3.56 | 12 |
| Haiku 5.5<br>`disabled` / `default` | First write | 0.49 / 0.79 | 2.66 / 3.16 | 12 |
| Haiku 5.5<br>`disabled` / `default` | Cache hit | 0.45 / 0.59 | 2.41 / 4.38 | 12 |

**Output rate and cost for the same requests.**

| Model / thinking.type / output_config.effort | Cache state | E2E output rate P50 (tokens/s, thinking included) | Mean cost (USD/request) | Valid requests |
|---|---|---:|---:|---:|
| Haiku 5.5<br>`adaptive` / `low` | First write | 214.53 | $0.004254 | 12 |
| Haiku 5.5<br>`adaptive` / `low` | Cache hit | 211.44 | $0.001009 | 12 |
| Haiku 5.5<br>`adaptive` / `medium` | First write | 218.61 | $0.004638 | 12 |
| Haiku 5.5<br>`adaptive` / `medium` | Cache hit | 221.27 | $0.001248 | 12 |
| Haiku 5.5<br>`adaptive` / `high` | First write | 234.38 | $0.005884 | 12 |
| Haiku 5.5<br>`adaptive` / `high` | Cache hit | 230.84 | $0.002356 | 12 |
| Haiku 5.5<br>`adaptive` / `xhigh` | First write | 259.47 | $0.019081 | 11 |
| Haiku 5.5<br>`adaptive` / `xhigh` | Cache hit | 258.09 | $0.010969 | 11 |
| Haiku 5.5<br>`adaptive` / `max` | First write | 269.25 | $0.037720 | 8 |
| Haiku 5.5<br>`adaptive` / `max` | Cache hit | 265.15 | $0.032892 | 8 |
| Haiku 5.5<br>`adaptive` / `default` | First write | 218.12 | $0.004464 | 12 |
| Haiku 5.5<br>`adaptive` / `default` | Cache hit | 222.91 | $0.001171 | 12 |
| Haiku 5.5<br>`disabled` / `low` | First write | 177.01 | $0.003747 | 12 |
| Haiku 5.5<br>`disabled` / `low` | Cache hit | 183.87 | $0.000406 | 12 |
| Haiku 5.5<br>`disabled` / `medium` | First write | 172.51 | $0.003759 | 12 |
| Haiku 5.5<br>`disabled` / `medium` | Cache hit | 175.95 | $0.000443 | 12 |
| Haiku 5.5<br>`disabled` / `high` | First write | 181.72 | $0.003790 | 12 |
| Haiku 5.5<br>`disabled` / `high` | Cache hit | 172.20 | $0.000428 | 12 |
| Haiku 5.5<br>`disabled` / `default` | First write | 174.06 | $0.003728 | 12 |
| Haiku 5.5<br>`disabled` / `default` | Cache hit | 201.46 | $0.000475 | 12 |

### Completion and cache evidence

| Model | Retained / planned requests, warm-ups included | Completed requests | Truncated requests | Complete measured pairs | Cache-hit pairs |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 | 150/150 | 149 | 1 | 71 | 70 |
| Sonnet 5.5 | 250/250 | 244 | 6 | 117 | 117 |
| Haiku 5.5 | 250/250 | 243 | 7 | 116 | 115 |

**Cache evidence.** 304 measured pairs completed; 302 show native cache hits. The other 2 crossed the shutdown/restart interval and rewrote expired entries. They remain in request, cost and correctness counts but not cache-hit performance statistics. Hit pairs read at least 100.0% of the preceding cache write; 0 reused a response message ID. This proves those cache reads, not a general speedup. Responses report `inference_geo: global` and an East US 2 region header; that is not a regional-inference guarantee.

**Cost and limits.** The full run cost $76.17 at recorded [list prices](coding-matrix/pricing.py), including warm-ups, writes, reads, output and truncated answers; infrastructure is excluded and this is not an invoice. Pair metrics exclude warm-ups and incomplete or non-hit pairs, never the correctness denominator. Full distributions and counts remain in [the facts](evidence/gateway-cache-20261026/interim-facts.json).

[All 26 configurations and paired observations](docs/results.md#aca-gateway-snapshot).

### What the parameter evidence proves

**Transport is not task success.** Recorded physical attempts: 650; HTTP 200: 650; retries: 0. These counts include warm-ups and any recorded retry attempts. The completion table retains truncated answers; this small, paced run is not a capacity or reliability guarantee.

| Evidence layer | Available evidence | What it does not establish |
|---|---|---|
| Client request settings | `request_params` and `request_sha256` in the [captured requests](evidence/gateway-cache-20261026/responses_opus.jsonl), before the documented model-alias mapping | Not a wire capture of the gateway's outbound request |
| Upstream response | Native cache and thinking usage, with completed / truncated outcomes in [all records](evidence/gateway-cache-20261026/interim-facts.json) | Not proof that every accepted parameter was honored, or that effort monotonically controls tokens |
| Gateway outbound request | The [separate 2026-10-24 audit](docs/results.md#gateway-test-2026-10-24) correlates its own client requests with provider traces | Per-request outbound audit is not retained for the current batch; the older audit cannot fill this gap |

| thinking.type | Measured requests | Native thinking usage present / requests | Requests with positive thinking tokens |
|---|---:|---:|---:|
| `adaptive` | 432 | 432/432 | 353 |
| `between_tools` | 96 | 96/96 | 0 |
| `disabled` | 96 | 96/96 | 0 |

This is observed usage, not a model ranking. No tool loop was exercised, so zero thinking in `between_tools` does not test its between-tool behavior. A zero value in an adaptive request alone does not prove a dropped parameter. Acceptance/rejection probes from the older direct path remain historical, not a current gateway support matrix.

### Configuration guidance and checks

| Setting to check | Reproducible configuration | Observable check and limit |
|---|---|---|
| Gateway forwarding | Start from [config.yaml](deploy/config.yaml): `drop_params: false`; gateway/router retries are zero | Capture [provider traces](deploy/trace_hook.py) for the same call ID. Configuration text alone is not proof of forwarding; the matrix client can separately retry a 429 |
| Prompt caching | This matrix uses top-level `cache_control`, `type: ephemeral`, `ttl: 1h` | Check native write and read token counts. It did not compare TTL choices or cache disabled; choose production TTL against actual session gaps and write cost |
| Thinking and effort | Use the explicitly named configuration, preserving `default` as an omitted field | Compare matching rows plus their code-test outcomes. This public subset does not select a production-optimal effort |
| Output cap and streaming | Reproduction uses `max_tokens: 128000`, `stream: true` | Require a terminal stream and inspect `stop_reason`; the cap still caused truncation. Do not count HTTP 200 or the first event as a completed answer |

### Code correctness after performance

**Method.** The same 624 measured answers, excluding only warm-ups, were graded with the official SWE-bench harness 5.0.2 at commit `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`. The official `extract_diff` function extracted predictions; no answer repair or new model call was used. Each cell/repeat has a separate run ID. All 12 selected gold controls passed. [Frozen inputs, native reports and verifier](evidence/gateway-score-20261027/verification.json).

Overall: 245/624 (39.26%) resolved; 257 patch-application failures, 108 unresolved test results and 14 truncated empty answers. These stay in the denominator. Different model/mode populations make the aggregate unsuitable as a fair overall ranking; each matched cell has 24 answers. This is a 12-instance subset, not the full SWE-bench Lite score.

| Model | thinking.type | output_config.effort | Resolved / measured answers | Resolved (%) |
|---|---|---|---:|---:|
| Opus 5.5 | `adaptive` | `low` | 9/24 | 37.50 |
| Opus 5.5 | `adaptive` | `medium` | 19/24 | 79.17 |
| Opus 5.5 | `adaptive` | `high` | 19/24 | 79.17 |
| Opus 5.5 | `adaptive` | `xhigh` | 21/24 | 87.50 |
| Opus 5.5 | `adaptive` | `max` | 22/24 | 91.67 |
| Opus 5.5 | `adaptive` | `default` | 14/24 | 58.33 |
| Sonnet 5.5 | `adaptive` | `low` | 6/24 | 25.00 |
| Sonnet 5.5 | `adaptive` | `medium` | 5/24 | 20.83 |
| Sonnet 5.5 | `adaptive` | `high` | 8/24 | 33.33 |
| Sonnet 5.5 | `adaptive` | `xhigh` | 18/24 | 75.00 |
| Sonnet 5.5 | `adaptive` | `max` | 18/24 | 75.00 |
| Sonnet 5.5 | `adaptive` | `default` | 9/24 | 37.50 |
| Sonnet 5.5 | `between_tools` | `low` | 4/24 | 16.67 |
| Sonnet 5.5 | `between_tools` | `medium` | 5/24 | 20.83 |
| Sonnet 5.5 | `between_tools` | `high` | 7/24 | 29.17 |
| Sonnet 5.5 | `between_tools` | `default` | 7/24 | 29.17 |
| Haiku 5.5 | `adaptive` | `low` | 2/24 | 8.33 |
| Haiku 5.5 | `adaptive` | `medium` | 5/24 | 20.83 |
| Haiku 5.5 | `adaptive` | `high` | 8/24 | 33.33 |
| Haiku 5.5 | `adaptive` | `xhigh` | 12/24 | 50.00 |
| Haiku 5.5 | `adaptive` | `max` | 14/24 | 58.33 |
| Haiku 5.5 | `adaptive` | `default` | 4/24 | 16.67 |
| Haiku 5.5 | `disabled` | `low` | 3/24 | 12.50 |
| Haiku 5.5 | `disabled` | `medium` | 3/24 | 12.50 |
| Haiku 5.5 | `disabled` | `high` | 1/24 | 4.17 |
| Haiku 5.5 | `disabled` | `default` | 2/24 | 8.33 |

**Ambiguity retained.** 6 official `no_tests_collected` flags remain unresolved. Each associated log first collected 92 top-level tests, includes nested zero-collection output, and shows `NameError: cached_eval`; none was silently removed or relabeled. [Six source-linked reviews](evidence/gateway-score-20261027/ambiguous-review.json). The [environment inventory](evidence/gateway-score-20261027/environment.json) was captured after evaluation, not as in-run telemetry.

**Evidence and replay.** [Facts](evidence/gateway-cache-20261026/interim-facts.json), [export hashes and redactions](evidence/gateway-cache-20261026/_export_manifest.json), [Opus](evidence/gateway-cache-20261026/responses_opus.jsonl), [Sonnet](evidence/gateway-cache-20261026/responses_sonnet.jsonl), [Haiku](evidence/gateway-cache-20261026/responses_haiku.jsonl). The metrics-only projection omits prompt/answer bodies, thinking signatures, private endpoints and other headers; it is not a correctness-scoring dataset. Replay instructions are in [Testing](docs/testing.md#aca-snapshot-replay).

| You want to | Read |
|---|---|
| See every cell, problem, probe message and cache turn | [Results](docs/results.md) |
| Repeat the tests or run the offline checks | [Testing](docs/testing.md) |
| Check what each public script changed from the measured one | [Provenance](evidence/coding-matrix-20261026/provenance.json) |

## Steps

| Order | Execution location | Action and completion check |
|---|---|---|
| 1 | Azure configuration workstation | Prepare Foundry and ACA LiteLLM; verify the active image and identities in [gateway setup](docs/testing.md#gateway-setup) |
| 2 | Linux measurement client | Install dependencies and rebuild the hash-checked input |
| 3 | Same Linux client | Supply the HTTPS gateway origin and private key |
| 4 | Same Linux client | Run one cache pair and check native write/read evidence |
| 5 | Same Linux client | Run all frozen configurations into a new directory |
| 6 | Same Linux client | Analyze that directory, retaining failures and missing requests |

**Prerequisites and scope.** Use Bash on a Linux client with Python 3.12 or 3.13 and an existing ACA gateway. To reproduce the measured placement, use East US 2 for the client, gateway and Foundry resource; GlobalStandard still does not promise an inference region. Without a gateway, complete steps 1-4 of [gateway setup](docs/testing.md#gateway-setup), then return here. Allow the measurement client's actual egress /32 in ingress restrictions; a separate configuration workstation needs its own allowed /32. The gateway uses managed identity for Foundry; the client uses only the gateway key. Model calls and infrastructure incur charges. These reorganized public command blocks have not been run on a fresh cloud environment in this update.

**1. Prepare the client and frozen input.** Start in the parent of your checkout. Reuse an existing compatible Python environment; the conditional creates one only when no environment is active and no local one exists.

```bash
set -euo pipefail
test -d david-share || git clone --depth 1 --filter=blob:none https://github.com/david-xinyuwei/david-share.git
cd david-share/Agents/Claude-Foundry-LiteLLM-Performance
if [ -z "${VIRTUAL_ENV:-}" ]; then
  test -x .venv/bin/python || python3 -m venv .venv
  source .venv/bin/activate
fi
python -m pip install -r coding-matrix/requirements.txt pyarrow
RUN_ID="aca-$(date -u +%Y%m%d-%H%M%S)"
WORK="$PWD/private/$RUN_ID"
mkdir -p "$WORK"
python -B gateway-cache/build_swebench_problems.py \
  --manifest data/gateway-cache-problems.json --out "$WORK/problems.json"
```

Expect PASS, revision `8d4bee9605fd8d72f14373a7f64d070c92f575c8` and 12 problems. The builder checks the parquet, problem order, source commits and prompt hashes before writing the prepared JSON. A mismatch stops the run; do not substitute a newer dataset. The downloaded data and later responses stay under ignored `private/`.

**2. Configure the gateway, not the Foundry endpoint.** Get the HTTPS origin from Container Apps Ingress, without `/v1/messages` or `/anthropic`. Enter the key yourself; never put it in a command, screenshot or Git.

```bash
export GATEWAY_URL="https://<your-container-app-fqdn>"
read -r -s -p 'Gateway key (private): ' CLAUDE_GATEWAY_KEY
printf '\n'
export CLAUDE_GATEWAY_KEY
export CLAUDE_GATEWAY_BUDGET_ROOT="$WORK"
```

Aliases are `opus55-standard`, `sonnet55-standard` and `haiku55-standard` in `deploy/config.yaml`; the existing gateway adapter maps the runner's model names to them. No direct-Foundry fallback is used. Configure matching aliases before continuing.

**3. Verify one cache pair first.** This diagnostic plans one warm-up plus two measured requests. Its seed is separate from the full run, so it does not prewarm the full run's group prefix. Approve its model spend before executing.

```bash
GATE="$WORK/gate"
python -u gateway-cache/aca_cache_matrix.py --run-dir "$GATE" \
  --source coding-matrix --gateway-url "$GATEWAY_URL" --problems "$WORK/problems.json" \
  --probe-summary evidence/coding-matrix-20261026/matrix/probe_summary.json \
  --only-cells 'sonnet|adaptive|low' --only-problems 'django__django-15320' \
  --seed "$RUN_ID-gate" --repeats 2 --max-tokens 128000 --ttl 1h --budget-usd 5
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$GATE" --out "$GATE/facts.json"
python -c 'import json,sys; record=json.load(open(sys.argv[1], encoding="utf-8")); assert record["coverage"]["collection_complete"] and record["cache_hit_pairs"] == 1, record; print("CACHE_PAIR_VERIFIED")' "$GATE/facts.json"
```

Expect CACHE_PAIR_VERIFIED, two completed measured answers and native cache read after write. HTTP 200 alone is not enough. For 401/403 check the gateway key, ingress and gateway identity; for 400 inspect the actual parameter error; for 429 inspect the returned limit and pacing; for missing reads inspect the prefix, elapsed gap and route. A TCP check below 50 ms is only this runner's heuristic, not proof of location. Keep failures and their request identifiers.

**4. Run and analyze the full matrix.** Use the same shell and a new directory. The frozen probe fixes 26 configurations, 12 problems and two measured repeats, plus warm-ups: 650 planned requests. A new seed changes ordering and group identifiers while preserving the protocol and problem texts; results need not equal the published run. The example's USD 85 stop threshold is not a guaranteed cost cap because calls can be in flight. The adapter also stops at USD 95 accounted under WORK, reserving USD 5 of its USD 100 guard; check current prices before choosing budgets.

```bash
RUN="$WORK/matrix"
printf 'RUN_DIRECTORY=%s\n' "$RUN"
python -u gateway-cache/aca_cache_matrix.py --run-dir "$RUN" \
  --source coding-matrix --gateway-url "$GATEWAY_URL" --problems "$WORK/problems.json" \
  --probe-summary evidence/coding-matrix-20261026/matrix/probe_summary.json \
  --seed "$RUN_ID" --repeats 2 --max-tokens 128000 --ttl 1h --budget-usd 85
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$RUN" --out "$RUN/facts.json"
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$RUN" --out "$RUN/facts.json" --check
unset CLAUDE_GATEWAY_KEY
```

The analyzer reads this RUN, not the published fixture. Expect `facts match`; separately check `coverage.collection_complete`, all 26 cells, transport errors, truncations and native cache pairs in facts.json. BUDGET_STOP or missing requests is not completion. The foreground process can be interrupted with Ctrl+C; this does not stop cloud resources. Use the printed directory in another terminal for `tail -F <run-directory>/progress.log`, or read its run.json for a snapshot. Keep the same inputs, seed and run directory when resuming; first re-enter the private key. [New-answer grading and separate outbound audit](docs/testing.md#fresh-aca-analysis) are separate stages, not covered by `facts match`.

**Only inspecting saved results?** Use [offline replay](docs/testing.md#aca-snapshot-replay); it needs no Azure credentials or model calls. Deployment, input reconstruction, fresh collection and offline replay have distinct acceptance checks.
