# Measured Results

[README](../README.md) · [Testing](testing.md) · [中文](results_CN.md)

Current East US 2 ACA performance comes first, then parameter/cache evidence and correctness for all 624 measured answers. Historical direct, probe and cross-region gateway results remain separate; they neither pool with the current run nor fill its outbound-audit gap.

<a id="aca-gateway-snapshot"></a>

## ACA gateway: performance results

**Complete collection, not universal success.** All 650/650 requests are retained: 26 warm-ups and 624 measured answers. The run reached `COMPLETED` at `2026-10-27T08:37:15.795+00:00`. Failures and truncations remain in the counts. [Collection verification](../evidence/gateway-cache-20261026/collection-status.json).

**Question and method.** For coding prompts sent through the East US 2 ACA LiteLLM gateway, does the identical second request read the cache written by the first, and what timing and cost were observed? The client and gateway were in East US 2; the Foundry resource was also in East US 2. One request was in flight per model. This is a cache-write versus cache-read pair, not a cache-disabled control or a gateway-overhead experiment.

**Input.** [12 public SWE-bench Lite BM25-13K problems](../data/gateway-cache-problems.json), with the source revision and prompt hashes in [run.json](../evidence/gateway-cache-20261026/run.json). This is a selected-subset experiment, not a full SWE-bench leaderboard score or customer production data. The [runner](../gateway-cache/aca_cache_matrix.py) uses 26 mode/effort cells, two identical requests per problem/cell and one warm-up per cell. Fixed: `max_tokens: 128000`, `stream: true`, top-level `cache_control: {"type": "ephemeral", "ttl": "1h"}`. Timing starts immediately before the client sends the request; first text is the first non-empty text delta, not a ping or thinking event.

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

**Request numbers, not conversation turns.** Request 1 is the first identical-prompt submission and cache write; request 2 repeats that prompt and reads its cache. No answer history is appended, and there is no request 3 or 4 in this matrix. Each table cell names the request number. Cache-read share is the sum of native read tokens divided by all input tokens (uncached + write + read) for that request number. The last column grades both requests across all 12 problems: 24 answers per configuration, including failures, not just the performance subset.

| Model / thinking.type / output_config.effort | Valid performance samples (requests) | TTFT P50 / P95 (s) | E2E P50 / P95 (s) | E2E output rate P50 (tokens/s, thinking included) | Mean cost (USD/request) | Cache-read share of input (%) | Resolved / graded answers (requests 1+2, %) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Opus 5.5<br>`adaptive` / `low` | Request 1: 12<br>Request 2: 12 | Request 1: 1.19 / 9.06<br>Request 2: 1.08 / 14.7 | Request 1: 6.94 / 14.4<br>Request 2: 7.84 / 20.0 | Request 1: 103.53<br>Request 2: 103.75 | Request 1: $0.158921<br>Request 2: $0.023222 | Request 1: 0.00<br>Request 2: 99.98 | 9/24 (37.50%) |
| Opus 5.5<br>`adaptive` / `medium` | Request 1: 12<br>Request 2: 12 | Request 1: 6.92 / 31.5<br>Request 2: 7.15 / 29.3 | Request 1: 11.6 / 37.2<br>Request 2: 11.3 / 35.3 | Request 1: 108.44<br>Request 2: 111.76 | Request 1: $0.173419<br>Request 2: $0.036952 | Request 1: 0.00<br>Request 2: 99.98 | 19/24 (79.17%) |
| Opus 5.5<br>`adaptive` / `high` | Request 1: 12<br>Request 2: 12 | Request 1: 9.13 / 94.5<br>Request 2: 7.53 / 228 | Request 1: 14.0 / 101<br>Request 2: 11.7 / 239 | Request 1: 110.21<br>Request 2: 110.93 | Request 1: $0.200936<br>Request 2: $0.097379 | Request 1: 0.00<br>Request 2: 99.98 | 19/24 (79.17%) |
| Opus 5.5<br>`adaptive` / `xhigh` | Request 1: 12<br>Request 2: 12 | Request 1: 18.9 / 110<br>Request 2: 19.6 / 380 | Request 1: 24.7 / 117<br>Request 2: 24.5 / 389 | Request 1: 112.87<br>Request 2: 114.35 | Request 1: $0.248050<br>Request 2: $0.183598 | Request 1: 0.00<br>Request 2: 99.98 | 21/24 (87.50%) |
| Opus 5.5<br>`adaptive` / `max` | Request 1: 11<br>Request 2: 11 | Request 1: 232 / 1027<br>Request 2: 236 / 913 | Request 1: 247 / 1036<br>Request 2: 249 / 922 | Request 1: 123.30<br>Request 2: 121.91 | Request 1: $1.008633<br>Request 2: $0.785095 | Request 1: 0.00<br>Request 2: 99.98 | 22/24 (91.67%) |
| Opus 5.5<br>`adaptive` / `default` | Request 1: 11<br>Request 2: 11 | Request 1: 7.03 / 65.8<br>Request 2: 8.02 / 28.5 | Request 1: 12.0 / 72.3<br>Request 2: 15.0 / 34.3 | Request 1: 109.83<br>Request 2: 109.88 | Request 1: $0.186835<br>Request 2: $0.037639 | Request 1: 0.00<br>Request 2: 99.98 | 14/24 (58.33%) |
| Sonnet 5.5<br>`adaptive` / `low` | Request 1: 12<br>Request 2: 12 | Request 1: 0.77 / 0.95<br>Request 2: 0.76 / 1.15 | Request 1: 4.86 / 9.76<br>Request 2: 4.88 / 9.01 | Request 1: 130.16<br>Request 2: 123.18 | Request 1: $0.077371<br>Request 2: $0.008869 | Request 1: 0.00<br>Request 2: 99.98 | 6/24 (25.00%) |
| Sonnet 5.5<br>`adaptive` / `medium` | Request 1: 12<br>Request 2: 12 | Request 1: 0.81 / 11.0<br>Request 2: 0.87 / 16.3 | Request 1: 5.67 / 14.4<br>Request 2: 6.15 / 19.1 | Request 1: 124.97<br>Request 2: 124.24 | Request 1: $0.078745<br>Request 2: $0.010499 | Request 1: 0.00<br>Request 2: 99.98 | 5/24 (20.83%) |
| Sonnet 5.5<br>`adaptive` / `high` | Request 1: 12<br>Request 2: 12 | Request 1: 6.05 / 137<br>Request 2: 7.44 / 119 | Request 1: 10.6 / 140<br>Request 2: 10.7 / 122 | Request 1: 141.38<br>Request 2: 138.87 | Request 1: $0.106288<br>Request 2: $0.034861 | Request 1: 0.00<br>Request 2: 99.98 | 8/24 (33.33%) |
| Sonnet 5.5<br>`adaptive` / `xhigh` | Request 1: 12<br>Request 2: 12 | Request 1: 20.7 / 246<br>Request 2: 16.1 / 341 | Request 1: 24.0 / 254<br>Request 2: 19.4 / 354 | Request 1: 148.80<br>Request 2: 149.31 | Request 1: $0.152607<br>Request 2: $0.109698 | Request 1: 0.00<br>Request 2: 99.98 | 18/24 (75.00%) |
| Sonnet 5.5<br>`adaptive` / `max` | Request 1: 9<br>Request 2: 9 | Request 1: 394 / 616<br>Request 2: 364 / 743 | Request 1: 397 / 622<br>Request 2: 367 / 751 | Request 1: 156.49<br>Request 2: 158.34 | Request 1: $0.804891<br>Request 2: $0.635133 | Request 1: 0.00<br>Request 2: 99.98 | 18/24 (75.00%) |
| Sonnet 5.5<br>`adaptive` / `default` | Request 1: 12<br>Request 2: 12 | Request 1: 6.86 / 86.8<br>Request 2: 5.78 / 152 | Request 1: 10.8 / 90.2<br>Request 2: 8.39 / 156 | Request 1: 140.69<br>Request 2: 141.88 | Request 1: $0.100876<br>Request 2: $0.035923 | Request 1: 0.00<br>Request 2: 99.98 | 9/24 (37.50%) |
| Sonnet 5.5<br>`between_tools` / `low` | Request 1: 12<br>Request 2: 12 | Request 1: 0.78 / 1.08<br>Request 2: 0.76 / 0.91 | Request 1: 5.14 / 7.88<br>Request 2: 4.51 / 8.22 | Request 1: 126.13<br>Request 2: 130.11 | Request 1: $0.077653<br>Request 2: $0.008496 | Request 1: 0.00<br>Request 2: 99.98 | 4/24 (16.67%) |
| Sonnet 5.5<br>`between_tools` / `medium` | Request 1: 12<br>Request 2: 12 | Request 1: 0.83 / 1.06<br>Request 2: 0.79 / 0.93 | Request 1: 5.41 / 9.18<br>Request 2: 4.60 / 9.87 | Request 1: 132.11<br>Request 2: 133.30 | Request 1: $0.077994<br>Request 2: $0.009313 | Request 1: 0.00<br>Request 2: 99.98 | 5/24 (20.83%) |
| Sonnet 5.5<br>`between_tools` / `high` | Request 1: 12<br>Request 2: 12 | Request 1: 0.81 / 1.09<br>Request 2: 0.82 / 1.18 | Request 1: 5.56 / 11.6<br>Request 2: 7.03 / 13.1 | Request 1: 130.38<br>Request 2: 129.14 | Request 1: $0.079108<br>Request 2: $0.011469 | Request 1: 0.00<br>Request 2: 99.98 | 7/24 (29.17%) |
| Sonnet 5.5<br>`between_tools` / `default` | Request 1: 12<br>Request 2: 12 | Request 1: 0.79 / 1.15<br>Request 2: 0.78 / 1.07 | Request 1: 4.88 / 13.6<br>Request 2: 5.46 / 10.2 | Request 1: 130.06<br>Request 2: 133.11 | Request 1: $0.078623<br>Request 2: $0.010259 | Request 1: 0.00<br>Request 2: 99.98 | 7/24 (29.17%) |
| Haiku 5.5<br>`adaptive` / `low` | Request 1: 12<br>Request 2: 12 | Request 1: 3.09 / 20.2<br>Request 2: 4.25 / 17.6 | Request 1: 4.93 / 22.9<br>Request 2: 5.75 / 20.7 | Request 1: 214.53<br>Request 2: 211.44 | Request 1: $0.004254<br>Request 2: $0.001009 | Request 1: 0.00<br>Request 2: 99.98 | 2/24 (8.33%) |
| Haiku 5.5<br>`adaptive` / `medium` | Request 1: 12<br>Request 2: 12 | Request 1: 6.92 / 13.8<br>Request 2: 6.93 / 14.2 | Request 1: 8.30 / 15.3<br>Request 2: 8.02 / 16.8 | Request 1: 218.61<br>Request 2: 221.27 | Request 1: $0.004638<br>Request 2: $0.001248 | Request 1: 0.00<br>Request 2: 99.98 | 5/24 (20.83%) |
| Haiku 5.5<br>`adaptive` / `high` | Request 1: 12<br>Request 2: 12 | Request 1: 9.07 / 38.5<br>Request 2: 12.1 / 29.6 | Request 1: 10.8 / 40.3<br>Request 2: 14.1 / 34.0 | Request 1: 234.38<br>Request 2: 230.84 | Request 1: $0.005884<br>Request 2: $0.002356 | Request 1: 0.00<br>Request 2: 99.98 | 8/24 (33.33%) |
| Haiku 5.5<br>`adaptive` / `xhigh` | Request 1: 11<br>Request 2: 11 | Request 1: 61.3 / 460<br>Request 2: 53.4 / 235 | Request 1: 63.2 / 463<br>Request 2: 57.0 / 237 | Request 1: 259.47<br>Request 2: 258.09 | Request 1: $0.019081<br>Request 2: $0.010969 | Request 1: 0.00<br>Request 2: 99.98 | 12/24 (50.00%) |
| Haiku 5.5<br>`adaptive` / `max` | Request 1: 8<br>Request 2: 8 | Request 1: 204 / 399<br>Request 2: 260 / 377 | Request 1: 206 / 406<br>Request 2: 262 / 384 | Request 1: 269.25<br>Request 2: 265.15 | Request 1: $0.037720<br>Request 2: $0.032892 | Request 1: 0.00<br>Request 2: 99.98 | 14/24 (58.33%) |
| Haiku 5.5<br>`adaptive` / `default` | Request 1: 12<br>Request 2: 12 | Request 1: 5.49 / 15.5<br>Request 2: 6.22 / 11.6 | Request 1: 7.40 / 18.4<br>Request 2: 8.07 / 14.2 | Request 1: 218.12<br>Request 2: 222.91 | Request 1: $0.004464<br>Request 2: $0.001171 | Request 1: 0.00<br>Request 2: 99.98 | 4/24 (16.67%) |
| Haiku 5.5<br>`disabled` / `low` | Request 1: 12<br>Request 2: 12 | Request 1: 0.48 / 0.83<br>Request 2: 0.56 / 0.74 | Request 1: 2.29 / 3.37<br>Request 2: 2.36 / 3.51 | Request 1: 177.01<br>Request 2: 183.87 | Request 1: $0.003747<br>Request 2: $0.000406 | Request 1: 0.00<br>Request 2: 99.98 | 3/24 (12.50%) |
| Haiku 5.5<br>`disabled` / `medium` | Request 1: 12<br>Request 2: 12 | Request 1: 0.54 / 0.73<br>Request 2: 0.50 / 0.60 | Request 1: 2.42 / 3.47<br>Request 2: 2.64 / 4.31 | Request 1: 172.51<br>Request 2: 175.95 | Request 1: $0.003759<br>Request 2: $0.000443 | Request 1: 0.00<br>Request 2: 99.98 | 3/24 (12.50%) |
| Haiku 5.5<br>`disabled` / `high` | Request 1: 12<br>Request 2: 12 | Request 1: 0.49 / 0.72<br>Request 2: 0.49 / 0.69 | Request 1: 2.67 / 4.51<br>Request 2: 2.40 / 3.56 | Request 1: 181.72<br>Request 2: 172.20 | Request 1: $0.003790<br>Request 2: $0.000428 | Request 1: 0.00<br>Request 2: 99.98 | 1/24 (4.17%) |
| Haiku 5.5<br>`disabled` / `default` | Request 1: 12<br>Request 2: 12 | Request 1: 0.49 / 0.79<br>Request 2: 0.45 / 0.59 | Request 1: 2.66 / 3.16<br>Request 2: 2.41 / 4.38 | Request 1: 174.06<br>Request 2: 201.46 | Request 1: $0.003728<br>Request 2: $0.000475 | Request 1: 0.00<br>Request 2: 99.98 | 2/24 (8.33%) |

### Completion and cache evidence

| Model | Retained / planned requests, warm-ups included | Completed requests | Truncated requests | Complete measured pairs | Cache-hit pairs |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 | 150/150 | 149 | 1 | 71 | 70 |
| Sonnet 5.5 | 250/250 | 244 | 6 | 117 | 117 |
| Haiku 5.5 | 250/250 | 243 | 7 | 116 | 115 |

**Cache evidence.** 304 measured pairs completed; 302 show native cache hits. The other 2 crossed the shutdown/restart interval and rewrote expired entries. They remain in request, cost and correctness counts but not cache-hit performance statistics. Hit pairs read at least 100.0% of the preceding cache write; 0 reused a response message ID. This proves those cache reads, not a general speedup. Responses report `inference_geo: global` and an East US 2 region header; that is not a regional-inference guarantee.

**Cost and limits.** The full run cost $76.17 at recorded [list prices](../coding-matrix/pricing.py), including warm-ups, writes, reads, output and truncated answers; infrastructure is excluded and this is not an invoice. Pair metrics exclude warm-ups and incomplete or non-hit pairs, never the correctness denominator. Full distributions and counts remain in [the facts](../evidence/gateway-cache-20261026/interim-facts.json).

### All configuration denominators

| Model | thinking.type | output_config.effort | Retained / planned measured requests | Truncated requests, warm-ups included | Complete / planned pairs |
|---|---|---|---:|---:|---:|
| Opus 5.5 | `adaptive` | `low` | 24/24 | 0 | 12/12 |
| Opus 5.5 | `adaptive` | `medium` | 24/24 | 0 | 12/12 |
| Opus 5.5 | `adaptive` | `high` | 24/24 | 0 | 12/12 |
| Opus 5.5 | `adaptive` | `xhigh` | 24/24 | 0 | 12/12 |
| Opus 5.5 | `adaptive` | `max` | 24/24 | 1 | 11/12 |
| Opus 5.5 | `adaptive` | `default` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `adaptive` | `low` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `adaptive` | `medium` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `adaptive` | `high` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `adaptive` | `xhigh` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `adaptive` | `max` | 24/24 | 6 | 9/12 |
| Sonnet 5.5 | `adaptive` | `default` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `between_tools` | `low` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `between_tools` | `medium` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `between_tools` | `high` | 24/24 | 0 | 12/12 |
| Sonnet 5.5 | `between_tools` | `default` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `adaptive` | `low` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `adaptive` | `medium` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `adaptive` | `high` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `adaptive` | `xhigh` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `adaptive` | `max` | 24/24 | 7 | 8/12 |
| Haiku 5.5 | `adaptive` | `default` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `disabled` | `low` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `disabled` | `medium` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `disabled` | `high` | 24/24 | 0 | 12/12 |
| Haiku 5.5 | `disabled` | `default` | 24/24 | 0 | 12/12 |

### What the parameter evidence proves

**Transport is not task success.** Recorded physical attempts: 650; HTTP 200: 650; retries: 0. These counts include warm-ups and any recorded retry attempts. The completion table retains truncated answers; this small, paced run is not a capacity or reliability guarantee.

| Evidence layer | Available evidence | What it does not establish |
|---|---|---|
| Client request settings | `request_params` and `request_sha256` in the [captured requests](../evidence/gateway-cache-20261026/responses_opus.jsonl), before the documented model-alias mapping | Not a wire capture of the gateway's outbound request |
| Upstream response | Native cache and thinking usage, with completed / truncated outcomes in [all records](../evidence/gateway-cache-20261026/interim-facts.json) | Not proof that every accepted parameter was honored, or that effort monotonically controls tokens |
| Gateway outbound request | The [separate 2026-10-24 audit](results.md#gateway-test-2026-10-24) correlates its own client requests with provider traces | Per-request outbound audit is not retained for the current batch; the older audit cannot fill this gap |

| thinking.type | Measured requests | Native thinking usage present / requests | Requests with positive thinking tokens |
|---|---:|---:|---:|
| `adaptive` | 432 | 432/432 | 353 |
| `between_tools` | 96 | 96/96 | 0 |
| `disabled` | 96 | 96/96 | 0 |

This is observed usage, not a model ranking. No tool loop was exercised, so zero thinking in `between_tools` does not test its between-tool behavior. A zero value in an adaptive request alone does not prove a dropped parameter. Acceptance/rejection probes from the older direct path remain historical, not a current gateway support matrix.

### Configuration guidance and checks

| Setting to check | Reproducible configuration | Observable check and limit |
|---|---|---|
| Gateway forwarding | Start from [config.yaml](../deploy/config.yaml): `drop_params: false`; gateway/router retries are zero | Capture [provider traces](../deploy/trace_hook.py) for the same call ID. Configuration text alone is not proof of forwarding; the matrix client can separately retry a 429 |
| Prompt caching | This matrix uses top-level `cache_control`, `type: ephemeral`, `ttl: 1h` | Check native write and read token counts. It did not compare TTL choices or cache disabled; choose production TTL against actual session gaps and write cost |
| Thinking and effort | Use the explicitly named configuration, preserving `default` as an omitted field | Compare matching rows plus their code-test outcomes. This public subset does not select a production-optimal effort |
| Output cap and streaming | Reproduction uses `max_tokens: 128000`, `stream: true` | Require a terminal stream and inspect `stop_reason`; the cap still caused truncation. Do not count HTTP 200 or the first event as a completed answer |

### Code correctness after performance

**Method.** The same 624 measured answers, excluding only warm-ups, were graded with the official SWE-bench harness 5.0.2 at commit `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`. The official `extract_diff` function extracted predictions; no answer repair or new model call was used. Each cell/repeat has a separate run ID. All 12 selected gold controls passed. [Frozen inputs, native reports and verifier](../evidence/gateway-score-20261027/verification.json).

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

**Ambiguity retained.** 6 official `no_tests_collected` flags remain unresolved. Each associated log first collected 92 top-level tests, includes nested zero-collection output, and shows `NameError: cached_eval`; none was silently removed or relabeled. [Six source-linked reviews](../evidence/gateway-score-20261027/ambiguous-review.json). The [environment inventory](../evidence/gateway-score-20261027/environment.json) was captured after evaluation, not as in-run telemetry.

**Evidence and replay.** [Facts](../evidence/gateway-cache-20261026/interim-facts.json), [export hashes and redactions](../evidence/gateway-cache-20261026/_export_manifest.json), [Opus](../evidence/gateway-cache-20261026/responses_opus.jsonl), [Sonnet](../evidence/gateway-cache-20261026/responses_sonnet.jsonl), [Haiku](../evidence/gateway-cache-20261026/responses_haiku.jsonl). The metrics-only projection omits prompt/answer bodies, thinking signatures, private endpoints and other headers; it is not a correctness-scoring dataset. Replay instructions are in [Testing](testing.md#aca-snapshot-replay).

<a id="historical-evidence"></a>

## Historical observations: different paths and inputs

The following records preserve earlier direct and cross-region observations. They are not current ACA configuration recommendations or performance results.

<a id="historical-settings"></a>

**Historical request settings.** What each setting does, from Claude's documentation, and what the retained direct-VM runs sent. Accepted values come from that historical probe; these observations do not describe the current ACA run:

| Setting | What it does | Historical observation |
|---|---|---|
| `thinking.type: "adaptive"` | The model decides for each request whether to think before answering and for how long; `output_config.effort` steers how much. Sending no `thinking` field does the same on these three models | All three models, effort low to max |
| `thinking.type: "between_tools"` | Sonnet 5.5's lowest setting: no thinking before the answer. Short progress updates written between tool calls still come back as thinking blocks; without tools the answer is text only. Accepted at effort `high` or below | Sonnet, effort low, medium, high; no tools |
| `thinking.type: "disabled"` | Thinking off. Only Haiku 5.5 accepts it, at effort `high` or below; Opus 5.5 cannot turn thinking off | Haiku, effort low, medium, high |
| `thinking.display` | Whether thinking text comes back. The default on these models, `"omitted"`, returns thinking blocks with empty text and an encrypted signature, so the answer starts streaming sooner; the thinking tokens are still billed. `"summarized"` returns a summary | Not sent: 610 matrix answers used thinking tokens and none streamed thinking text |
| `output_config.effort` | How much work goes into the whole response, thinking included: `low`, `medium`, `high`, `xhigh`, `max`. A behavioral signal, not a token budget. Default when omitted: Opus and Haiku `medium`, Sonnet `high` | Every level each thinking mode accepted: 21 cells |
| `max_tokens` | Hard limit on output tokens, thinking included; an answer that reaches it stops with `stop_reason: "max_tokens"`. At most 128,000 on these models | 128,000 in the matrix; 1,000,000 returned HTTP 400 |
| No `cache_control` (the default) | Nothing is cached: caching is opt-in. "Automatic caching" also needs the top-level field; "automatic" means the breakpoint is placed for you, not that caching is on by default. The documented exceptions involve tools: in a tool-use loop, history sent back with tool results can be cached without a marker, and server-tool results are cached automatically | The coding matrix (1,155 requests) and the cache test's baseline (24 requests; each turn resent the same prefix of about 15,500 tokens): 0 cache reads and 0 cache writes in every response |
| `cache_control` at the top level | Automatic caching: the breakpoint goes on the last cacheable block and moves forward as the conversation grows | Cache test: most scenarios |
| `cache_control` on a content block | Explicit breakpoint: caches the prompt up to and including that block, in the order `tools`, `system`, `messages`. At most 4 breakpoints per request; a prompt under 512 tokens is not cached | Cache test: after the repository files |
| `cache_control.ttl` | How long an unused entry lives: `"5m"` by default, renewed on every read, or `"1h"`. Writes cost 1.25× the input price (5 minutes) or 2× (1 hour); reads cost 0.05× on Opus and Sonnet, 0.1× on Haiku | Both: 6.5 minutes idle before the second turn |
| Per-message effort | An effort-only `system` message changes effort for later turns without touching the top-level field, so the cached prefix stays valid. Beta, header `anthropic-beta: mid-conversation-output-config-2026-07-01`; Foundry is not among the platforms the effort page lists for it | One cache scenario; all 264 cache requests returned HTTP 200 |
| `temperature`, `top_p`, `top_k` | Sampling. On these models any non-default value returns HTTP 400 | Probe only: HTTP 400 in every mode tried; never sent in the matrix |
| `stream` | `true` returns server-sent events, the only way to time the first visible text | `true` on every timed request; the pre-warm request with `max_tokens: 0` is not streamed, as the API requires |
| Deployment type, chosen when the deployment is created | GlobalStandard may serve a request outside the resource's region; US Data Zone Standard keeps inference in the United States, like `inference_geo: "us"` on the Claude API. Sonnet 5.5 supports GlobalStandard only | GlobalStandard only; every matrix response reported `usage.inference_geo` `global` |

**Table 1. Complete thinking-mode and effort matrix.**

[![Table 1. Complete thinking-mode and effort matrix.](../images/parameter-support-en.svg)](../images/parameter-support-en.svg)

The 54 `adaptive`/`between_tools`/`disabled` × effort cells were individually probed; 26 were accepted, including five omitted-effort cells. For `enabled`, one request per model used `budget_tokens: 1024` and omitted effort; the HTTP 400 rejects the mode itself, so all effort cells say not supported. The cache column states applicability only: a rejected thinking mode makes the request inapplicable; it does not mean the model lacks caching. Default effort values are from the [effort documentation](https://platform.claude.com/docs/en/build-with-claude/effort).

Historical cache scope: all five accepted model/mode rows read cache at effort low; adaptive also read cache in the high-effort switch scenario. The separate ACA performance section reports the later full mode/effort coverage. Applicability and parameter acceptance alone do not establish cache-enabled performance. Fixed historical matrix controls: `max_tokens: 128000`, `stream: true`; `temperature`, `top_p`, `top_k` omitted. No `thinking` field is documented to select adaptive; the three omitted-thinking/omitted-effort probes returned 200.

**Table 2. Complete prompt-cache settings.**

[![Table 2. Complete prompt-cache settings.](../images/cache-settings-en.svg)](../images/cache-settings-en.svg)

Sources: [probe requests](../evidence/coding-matrix-20261026/probe/probe_results.jsonl), [cache requests](../evidence/coding-matrix-20261026/cache/cache_results.jsonl) and [prompt-caching documentation](https://platform.claude.com/docs/en/build-with-claude/prompt-caching). Table 2 uses two repetitions per scenario: Opus adaptive, Sonnet between_tools, Haiku disabled, effort low; first writes are separate from turns 2-4. Read share is read tokens / (uncached + written + read input tokens), aggregated within each model/scenario/turn. New conversations reuse the files but change the question. The 512-token boundary and four-breakpoint limit are documented, not boundary-sweep measurements. All cache markers use `type: ephemeral`; reads cost 0.05x base input on Opus/Sonnet and 0.1x on Haiku (documented prices). These are historical direct-VM observations, not evidence for the later ACA run.

**Not covered:** tool use, where `between_tools` and progress updates matter; `display: "summarized"`; US Data Zone deployments; and the separate `claude-opus-5-5-fast` model in the Foundry catalog.

**Historical per-model summary.** What each deployment accepted and how it did on the 18 problems in the retired direct-VM batch; not current ACA results:

| Question | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|
| Thinking modes the API accepted | `adaptive` only; `disabled` and `between_tools` return 400 | `adaptive`; `between_tools` at low, medium, high | `adaptive`; `disabled` at low, medium, high |
| Effort levels / default when omitted | low to max / medium | low to max / high | low to max / medium |
| First visible text, P50 of the fastest cell | 0.48 s (`adaptive` · low) | 0.39 s (`between_tools` · high) | 0.43 s (`disabled` · high) |
| Unit tests passed per cell, of 54 answers | 54 in every cell | 40 to 44 | 24 to 28 with `adaptive`; 17 to 21 with `disabled` |
| List-price cost per 1,000 requests | $23.34 to $355.75 | $13.04 to $356.49 | $0.69 to $22.26 |
| Choose it when (our reading of this test) | Answers must be right the first time. Start at `low`: every effort level passed all 54, and `low` was the fastest (0.48 s) and cheapest | You want most of Opus's accuracy at a lower price: `between_tools` passed as often as `adaptive`, started in under 0.5 s and cost $13.16–$13.76 per 1,000 requests | Cost matters most and a wrong answer can be retried. Keep thinking on: at the same effort levels `adaptive` passed 12.3 points more often than `disabled` |

**Historical scope.** The problems are public Exercism exercises from [Aider's polyglot benchmark](https://github.com/Aider-AI/polyglot-benchmark), each answered once, without tools and without seeing the tests; they are not your production tasks. The retired batch called Foundry directly, one request at a time per deployment. Its costs and accuracy are historical observations, not evidence for the current cache-enabled ACA path. Costs use list prices and were not reconciled with an Azure invoice.

**Sources.** Accepted values and the HTTP 400 messages come from our probe ([results](results.md#parameter-probe-2026-10-26)). What each setting does, the defaults, the rules for `between_tools` and `disabled`, and the advice to set `max_tokens` to 128,000 for agentic coding on Sonnet 5.5 come from Claude's [thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) and [effort](https://platform.claude.com/docs/en/build-with-claude/effort) pages; cache rules and price multipliers from [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching); prices from [pricing](https://platform.claude.com/docs/en/about-claude/pricing); hosting options and Foundry setup from [Claude in Microsoft Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry); all read on 2026-10-26. The *Choose it when* row is our reading of these 18 problems, not general advice.

| Term | Meaning |
|---|---|
| Cell | One model × thinking mode × effort level. Each cell answered the 18 problems three times: 54 answers |
| Thinking mode, effort level | Defined in the [historical request-settings table](#historical-settings) |
| First visible text | Seconds from just before the request is written to the first non-empty `text_delta`, timed on the VM. Thinking comes first and its text is not streamed (`display` omitted), so this wait includes all thinking |
| First event | Seconds to the first server-sent event, `message_start` |
| Full answer | Seconds to the end of the stream, completed requests only |
| Completed | HTTP 200, `message_stop` received, `stop_reason` `end_turn` and non-empty text |
| Pass | The files in the answer, written over the exercise's solution files, make its own unit tests exit 0 in an offline container (Aider's first-attempt rule) |
| By-problem 95% interval | 2.5th to 97.5th percentile over 5,000 resamples of the 18 problems (seed 20261026). The three answers to one problem are not independent, so the problem is the unit |
| Cost | List price × the token counts in the API's `usage`, cache writes and reads included |

| Part | Where | Detail |
|---|---|---|
| Client: probe, matrix, cache test | Linux VM `Standard_D4s_v5`, East US 2 | Ubuntu 24.04, kernel 7.0.0-1017-azure, Python 3.12.3, httpx 0.28.1, azure-identity 1.25.1; Entra token from the VM's managed identity; TCP connect to the endpoint 9.67 ms median before the matrix |
| Models | Foundry resource in East US 2 | `claude-opus-5-5` 40,000 tokens per minute; `claude-sonnet-5-5` and `claude-haiku-5-5` 80,000 each; version 2, GlobalStandard, so a request may be served outside East US 2 |
| Unit tests | Docker on the same VM | `--network none`, 1.5 CPUs, 3 GB; the toolchains of Aider's benchmark image: Python 3.11, Go 1.21.5, Rust, Node 20, OpenJDK 21, CMake and Boost |

| Number | From → to, or how | Script |
|---|---|---|
| Accepted values | HTTP 200 or 400 for a one-word prompt sent with each value | [`probe.py`](../coding-matrix/probe.py) |
| First visible text, first event, full answer | request written → first `text_delta`, `message_start`, end of stream; clock on the VM | [`claude_api.py`](../coding-matrix/claude_api.py) `stream_message` |
| Completed, thinking and output tokens | status, `stop_reason` and `usage` of each stream | [`bench.py`](../coding-matrix/bench.py) |
| Pass | the exercise's unit tests, offline in Docker | [`judge.py`](../coding-matrix/judge.py) |
| P50, P95, intervals, cost per 1,000 | nearest rank; bootstrap over problems; mean list-price cost × 1,000 | [`analyze.py`](../coding-matrix/analyze.py) |
| Cache reads and writes, conversation cost | `usage` of each turn; the same tokens priced as if nothing were cached | [`cache_test.py`](../coding-matrix/cache_test.py), [`cache_analyze.py`](../coding-matrix/cache_analyze.py) |

**Do not read these grids as a general ranking of the three models.** Opus answered all 18 problems correctly in every cell, so this test cannot separate its effort levels. With 18 problems, a Sonnet or Haiku cell's 95% interval spans 30 to 44 points (for example Sonnet `between_tools` · high: 44 of 54, 65% to 94%). The problems are short single-file exercises. Each row is one model and thinking mode, each column an effort level; *not accepted* means the API returned HTTP 400. P95, full-answer times, token counts and every interval are on [the results page](results.md#results-per-cell).

**Unit tests passed, of 54 answers**

| Model · thinking | low | medium | high | xhigh | max |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 · `adaptive` | 54/54 | 54/54 | 54/54 | 54/54 | 54/54 |
| Sonnet 5.5 · `adaptive` | 41/54 | 42/54 | 40/54 | 41/54 | 44/54 |
| Sonnet 5.5 · `between_tools` | 42/54 | 41/54 | 44/54 | not accepted | not accepted |
| Haiku 5.5 · `adaptive` | 24/54 | 26/54 | 27/54 | 28/54 | 28/54 |
| Haiku 5.5 · `disabled` | 19/54 | 17/54 | 21/54 | not accepted | not accepted |

**First visible text, P50, seconds**

| Model · thinking | low | medium | high | xhigh | max |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 · `adaptive` | 0.48 | 3.71 | 4.05 | 6.04 | 51.4 |
| Sonnet 5.5 · `adaptive` | 0.46 | 0.50 | 3.25 | 7.44 | 190 |
| Sonnet 5.5 · `between_tools` | 0.42 | 0.44 | 0.39 | not accepted | not accepted |
| Haiku 5.5 · `adaptive` | 4.13 | 4.62 | 8.21 | 14.9 | 121 |
| Haiku 5.5 · `disabled` | 0.46 | 0.45 | 0.43 | not accepted | not accepted |

**List-price cost per 1,000 requests, US dollars**

| Model · thinking | low | medium | high | xhigh | max |
|---|---:|---:|---:|---:|---:|
| Opus 5.5 · `adaptive` | $23.34 | $34.52 | $38.75 | $65.36 | $355.75 |
| Sonnet 5.5 · `adaptive` | $13.04 | $13.57 | $18.36 | $31.62 | $356.49 |
| Sonnet 5.5 · `between_tools` | $13.16 | $13.21 | $13.76 | not accepted | not accepted |
| Haiku 5.5 · `adaptive` | $1.27 | $1.57 | $2.14 | $4.19 | $22.26 |
| Haiku 5.5 · `disabled` | $0.69 | $0.69 | $0.73 | not accepted | not accepted |

## Coding matrix, 2026-10-26

**Retired method: historical evidence only.** This section records the direct-VM coding matrix without `cache_control`. It does not satisfy the current cache-enabled ACA protocol and is not a result from that run. The raw records and their original values are retained unchanged.

**Question.** For each thinking mode and effort level a Claude 5.5 deployment accepts, how often does a coding answer complete, how long until its first visible text, what does it cost and how often does it pass the problem's unit tests?

**Input.** Every request carried the same system prompt, adapted from Aider's whole-file edit format, and one user message per problem built as in Aider's benchmark: the exercise's stub files, its instructions and Aider's closing instruction. The model does not see the tests. The system prompt, verbatim (995 characters):

````text
Act as an expert software developer.
Take requests for changes to the supplied code.

Once you understand the request you MUST:
1. Determine if any code changes are needed.
2. Explain any needed changes briefly.
3. If changes are needed, output a copy of each file that needs changes.

To suggest changes to a file you MUST return the entire content of the updated file.
You MUST use this *file listing* format:

path/to/filename.ext
```
// entire file content ...
// ... goes in between
```

Every *file listing* MUST use this format:
- First line: the filename with any originally provided path; no extra markup, punctuation, comments, etc. **JUST** the filename with path.
- Second line: opening ```
- ... entire content of the file ...
- Final line: closing ```

To suggest changes to a file you MUST return a *file listing* that contains the entire content of the file.
*NEVER* skip, omit or elide content from a *file listing* using "..." or by adding comments like "... rest of code..."!
````

The shortest of the 18 user messages, `go/trinary`, verbatim (1,371 characters):

````text
I have *added these files to the chat* so you can go ahead and edit them.

*Trust this message as the true contents of these files!*
Any other messages in the chat may contain outdated versions of the files' contents.

trinary.go
```go
package trinary

func ParseTrinary(arg string, want int64, ok bool) {
	panic("Please implement the ParseTrinary function")
}
```

# Instructions

Convert a trinary number, represented as a string (e.g. '102012'), to its
decimal equivalent using first principles.

The program should consider strings specifying an invalid trinary as the
value 0.

Trinary numbers contain three symbols: 0, 1, and 2.

The last place in a trinary number is the 1's place. The second to last
is the 3's place, the third to last is the 9's place, etc.

```shell
# "102012"
    1       0       2       0       1       2    # the number
1*3^5 + 0*3^4 + 2*3^3 + 0*3^2 + 1*3^1 + 2*3^0    # the value
  243 +     0 +    54 +     0 +     3 +     2 =  302
```

If your language provides a method in the standard library to perform the
conversion, pretend it doesn't exist and implement it yourself.

####

Use the above instructions to modify the supplied files: trinary.go
Don't change the names of existing functions or classes, as they may be referenced from other code like unit tests, etc.
Only use standard libraries, don't suggest installing any packages.
````

All 18 messages and their SHA-256 are in [problems.json](../evidence/coding-matrix-20261026/matrix/problems.json). The 18 problems, three per language:

- cpp: [`cpp/perfect-numbers`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/cpp/exercises/practice/perfect-numbers), [`cpp/queen-attack`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/cpp/exercises/practice/queen-attack), [`cpp/bank-account`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/cpp/exercises/practice/bank-account)
- go: [`go/trinary`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/go/exercises/practice/trinary), [`go/beer-song`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/go/exercises/practice/beer-song), [`go/wordy`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/go/exercises/practice/wordy)
- java: [`java/pythagorean-triplet`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/java/exercises/practice/pythagorean-triplet), [`java/house`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/java/exercises/practice/house), [`java/dominoes`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/java/exercises/practice/dominoes)
- javascript: [`javascript/palindrome-products`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/javascript/exercises/practice/palindrome-products), [`javascript/space-age`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/javascript/exercises/practice/space-age), [`javascript/promises`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/javascript/exercises/practice/promises)
- python: [`python/simple-linked-list`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/python/exercises/practice/simple-linked-list), [`python/wordy`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/python/exercises/practice/wordy), [`python/proverb`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/python/exercises/practice/proverb)
- rust: [`rust/dot-dsl`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/rust/exercises/practice/dot-dsl), [`rust/doubly-linked-list`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/rust/exercises/practice/doubly-linked-list), [`rust/scale-generator`](https://github.com/Aider-AI/polyglot-benchmark/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/rust/exercises/practice/scale-generator)

**Varied and fixed.** Varied: the model, `thinking.type` and `output_config.effort`, over the 21 combinations the probe accepted. Fixed: `max_tokens` 128,000, `stream` true, no `cache_control`, no tool, no sampling parameter; 18 problems × 3 repeats per cell; one discarded warm-up per cell (`Write a Python function add(a, b) that returns the sum of two numbers. Reply with the code only.`); one request in flight per deployment, the three deployments in parallel; a seeded order that interleaves problems and cells, so a slow hour affects every cell alike. The client paced under 85% of each deployment's per-minute token and output-token limits; a 429 would have been resent after `Retry-After`, and none occurred. A 32,000-token pilot cut answers off at effort max, so the matrix ran with 128,000, the value Claude's effort page gives for agentic coding on Sonnet 5.5.

### Results per cell

Times are seconds. First visible text uses every request that returned text; full answer uses completed requests. Nearest-rank percentiles.

| Cell | Completed | First text P50 | First text P95 | Full answer P50 | Full answer P95 |
|---|---:|---:|---:|---:|---:|
| Opus · `adaptive` · low | 54/54 | 0.48 | 0.98 | 5.58 | 19.6 |
| Opus · `adaptive` · medium | 54/54 | 3.71 | 11.9 | 9.07 | 39.0 |
| Opus · `adaptive` · high | 54/54 | 4.05 | 20.4 | 9.85 | 54.0 |
| Opus · `adaptive` · xhigh | 54/54 | 6.04 | 74.7 | 12.7 | 89.7 |
| Opus · `adaptive` · max | 54/54 | 51.4 | 585 | 59.9 | 621 |
| Sonnet · `adaptive` · low | 54/54 | 0.46 | 0.93 | 5.22 | 17.3 |
| Sonnet · `adaptive` · medium | 54/54 | 0.50 | 0.87 | 5.53 | 17.4 |
| Sonnet · `adaptive` · high | 54/54 | 3.25 | 11.0 | 8.53 | 29.7 |
| Sonnet · `adaptive` · xhigh | 54/54 | 7.44 | 42.0 | 13.2 | 66.7 |
| Sonnet · `adaptive` · max | 53/54 | 190 | 585 | 199 | 616 |
| Sonnet · `between_tools` · low | 54/54 | 0.42 | 0.80 | 5.06 | 17.5 |
| Sonnet · `between_tools` · medium | 54/54 | 0.44 | 0.78 | 5.14 | 19.3 |
| Sonnet · `between_tools` · high | 54/54 | 0.39 | 0.74 | 5.56 | 19.8 |
| Haiku · `adaptive` · low | 54/54 | 4.13 | 18.1 | 6.75 | 31.3 |
| Haiku · `adaptive` · medium | 54/54 | 4.62 | 27.5 | 7.76 | 42.0 |
| Haiku · `adaptive` · high | 54/54 | 8.21 | 41.9 | 11.4 | 56.6 |
| Haiku · `adaptive` · xhigh | 54/54 | 14.9 | 118 | 17.8 | 134 |
| Haiku · `adaptive` · max | 51/54 | 121 | 421 | 125 | 424 |
| Haiku · `disabled` · low | 54/54 | 0.46 | 0.71 | 3.33 | 11.0 |
| Haiku · `disabled` · medium | 54/54 | 0.45 | 0.80 | 3.29 | 11.5 |
| Haiku · `disabled` · high | 54/54 | 0.43 | 0.69 | 3.62 | 12.2 |

| Cell | Thinking tokens P50 | Output tokens P50 | $ per 1,000 requests | Passed | By-problem 95% interval |
|---|---:|---:|---:|---:|---:|
| Opus · `adaptive` · low | 0 | 699 | $23.34 | 54/54 | 100% |
| Opus · `adaptive` · medium | 335 | 1,125 | $34.52 | 54/54 | 100% |
| Opus · `adaptive` · high | 372 | 1,203 | $38.75 | 54/54 | 100% |
| Opus · `adaptive` · xhigh | 656 | 1,579 | $65.36 | 54/54 | 100% |
| Opus · `adaptive` · max | 6,473 | 7,663 | $355.75 | 54/54 | 100% |
| Sonnet · `adaptive` · low | 0 | 820 | $13.04 | 41/54 | 56–94% |
| Sonnet · `adaptive` · medium | 0 | 923 | $13.57 | 42/54 | 61–93% |
| Sonnet · `adaptive` · high | 366 | 1,355 | $18.36 | 40/54 | 56–91% |
| Sonnet · `adaptive` · xhigh | 1,031 | 2,038 | $31.62 | 41/54 | 57–93% |
| Sonnet · `adaptive` · max | 30,403 | 32,129 | $356.49 | 44/54 | 63–96% |
| Sonnet · `between_tools` · low | 0 | 824 | $13.16 | 42/54 | 61–93% |
| Sonnet · `between_tools` · medium | 0 | 875 | $13.21 | 41/54 | 57–91% |
| Sonnet · `between_tools` · high | 0 | 939 | $13.76 | 44/54 | 65–94% |
| Haiku · `adaptive` · low | 786 | 1,709 | $1.27 | 24/54 | 26–65% |
| Haiku · `adaptive` · medium | 956 | 1,926 | $1.57 | 26/54 | 28–69% |
| Haiku · `adaptive` · high | 1,932 | 2,967 | $2.14 | 27/54 | 30–70% |
| Haiku · `adaptive` · xhigh | 3,744 | 4,740 | $4.19 | 28/54 | 30–72% |
| Haiku · `adaptive` · max | 33,505 | 34,821 | $22.26 | 28/54 | 30–74% |
| Haiku · `disabled` · low | 0 | 923 | $0.69 | 19/54 | 19–54% |
| Haiku · `disabled` · medium | 0 | 893 | $0.69 | 17/54 | 15–50% |
| Haiku · `disabled` · high | 0 | 1,019 | $0.73 | 21/54 | 19–61% |

### Requests that did not complete

- `haiku|adaptive|max|rust/scale-generator|r1`: `stop_reason` `max_tokens` after 499 s; 128,000 output tokens, no visible text.
- `haiku|adaptive|max|rust/scale-generator|r2`: `stop_reason` `max_tokens` after 497 s; 128,000 output tokens, no visible text.
- `haiku|adaptive|max|rust/doubly-linked-list|r3`: `stop_reason` `max_tokens` after 491 s; 128,000 output tokens, visible text from 489 s.
- `sonnet|adaptive|max|java/house|r2`: `message_start` at 0.71 s, then two pings and no further event; the client's 600 s read timeout ended it at 661 s. Scored as no code.

### By problem

Answers that passed over all cells of a model: Opus has 5 cells × 3 = 15 answers per problem, Sonnet and Haiku 8 × 3 = 24.

| Problem | Opus | Sonnet | Haiku |
|---|---:|---:|---:|
| `cpp/perfect-numbers` | 15/15 | 24/24 | 13/24 |
| `cpp/queen-attack` | 15/15 | 21/24 | 1/24 |
| `cpp/bank-account` | 15/15 | 23/24 | 13/24 |
| `go/trinary` | 15/15 | 14/24 | 0/24 |
| `go/beer-song` | 15/15 | 14/24 | 0/24 |
| `go/wordy` | 15/15 | 24/24 | 22/24 |
| `java/pythagorean-triplet` | 15/15 | 24/24 | 24/24 |
| `java/house` | 15/15 | 1/24 | 0/24 |
| `java/dominoes` | 15/15 | 24/24 | 0/24 |
| `javascript/palindrome-products` | 15/15 | 24/24 | 15/24 |
| `javascript/space-age` | 15/15 | 24/24 | 21/24 |
| `javascript/promises` | 15/15 | 3/24 | 0/24 |
| `python/simple-linked-list` | 15/15 | 23/24 | 20/24 |
| `python/wordy` | 15/15 | 24/24 | 19/24 |
| `python/proverb` | 15/15 | 24/24 | 19/24 |
| `rust/dot-dsl` | 15/15 | 16/24 | 1/24 |
| `rust/doubly-linked-list` | 15/15 | 24/24 | 22/24 |
| `rust/scale-generator` | 15/15 | 4/24 | 0/24 |

### By language

| Language | Opus | Sonnet | Haiku |
|---|---:|---:|---:|
| cpp | 45/45 | 68/72 | 27/72 |
| go | 45/45 | 52/72 | 22/72 |
| java | 45/45 | 49/72 | 24/72 |
| javascript | 45/45 | 51/72 | 36/72 |
| python | 45/45 | 71/72 | 58/72 |
| rust | 45/45 | 44/72 | 23/72 |

### Thinking on and off at the same effort

Both sides use effort low, medium and high, the levels where thinking can be off, on the same problems: 162 answers each. Intervals resample the problems.

| Model | `adaptive` | Thinking off | Difference, points | 95% interval | Problems better / worse / equal |
|---|---:|---:|---:|---:|---:|
| Sonnet 5.5 (`between_tools`) | 75.9% | 78.4% | -2.5 | -7.4 to +1.9 | 3 / 4 / 11 |
| Haiku 5.5 (`disabled`) | 47.5% | 35.2% | +12.3 | +2.5 to +23.5 | 9 / 2 / 7 |

## Parameter probe, 2026-10-26

**Question.** Which thinking modes, effort levels, sampling parameters, output limits and cache settings does each deployment accept? **Input.** One streamed request per value and model, `max_tokens` 1,024 unless the row changes it, with the user message `Reply with exactly one word: OK`; 102 requests on 2026-10-26 between 08:11 and 08:12 UTC. A cell lists the HTTP status; letters point to the messages below. The accepted thinking modes and efforts became the cells of the matrix.

| Request | Opus | Sonnet | Haiku |
|---|---|---|---|
| effort `"probe-invalid-value"` | 400 (a) | 400 (a) | 400 (a) |
| `adaptive`, effort low to max | 200 | 200 | 200 |
| `adaptive`, no effort | 200 | 200 | 200 |
| `disabled`, effort low, medium, high | 400 (b) | 400 (c) | 200 |
| `disabled`, effort xhigh, max | 400 (b) | 400 (c) | 400 (d, e) |
| `disabled`, no effort | 400 (b) | 400 (c) | 200 |
| `between_tools`, effort low, medium, high | 400 (f) | 200 | 400 (f) |
| `between_tools`, effort xhigh, max | 400 (f) | 400 (d, e) | 400 (f) |
| `between_tools`, no effort | 400 (f) | 200 | 400 (f) |
| no `thinking` field | 200 | 200 | 200 |
| `enabled` with `budget_tokens` 1,024 | 400 (g) | 400 (g) | 400 (g) |
| `adaptive` + `temperature` 0.5 | 400 (h) | 400 (h) | 400 (h) |
| `adaptive` + `top_p` 0.9 | 400 (i) | 400 (i) | 400 (i) |
| `adaptive` + `top_k` 40 | 400 (j) | 400 (j) | 400 (j) |
| thinking off + `temperature` 0.5 | not sent: no thinking-off mode | 400 (k) | 400 (k) |
| thinking off + `top_p` 0.9 | not sent: no thinking-off mode | 400 (l) | 400 (l) |
| thinking off + `top_k` 40 | not sent: no thinking-off mode | 400 (m) | 400 (m) |
| `max_tokens` 1,000,000 | 400 (n) | 400 (o) | 400 (p) |
| `max_tokens` 32,000 | 200 | 200 | 200 |
| system block with `cache_control` and `"ttl": "1h"` | 200 | 200 | 200 |
| top-level `cache_control` | 200 | 200 | 200 |
| four `max_tokens` 32,000 requests back to back | 200 | 200 | 200 |

HTTP 400 messages, verbatim:

- (a) `output_config.effort: Input should be 'low', 'medium', 'high', 'xhigh' or 'max'`
- (b) `"thinking.type.disabled" is not supported for this model. Use "thinking.type.adaptive" and "output_config.effort" to control thinking behavior.`
- (c) `To turn thinking off on this model, send "thinking": {"type": "between_tools"} instead of {"type": "disabled"}. The model does not think before responding. The short updates it writes between tool calls come back as thinking blocks.`
- (d) `output_config.effort 'xhigh' is not supported when thinking is disabled on this model. Use effort 'high' or below, or enable thinking.`
- (e) `output_config.effort 'max' is not supported when thinking is disabled on this model. Use effort 'high' or below, or enable thinking.`
- (f) `"thinking.type.between_tools" is not supported for this model.`
- (g) `"thinking.type.enabled" is not supported for this model. Use "thinking.type.adaptive" and "output_config.effort" to control thinking behavior.`
- (h) `` `temperature` may only be set to 1 when thinking is enabled or in adaptive mode. Please consult our documentation at https://platform.claude.com/docs/en/build-with-claude/extended-thinking ``
- (i) `` `top_p` must be greater than or equal to 0.95 or unset when thinking is enabled or in adaptive mode. Please consult our documentation at https://platform.claude.com/docs/en/build-with-claude/extended-thinking ``
- (j) `` `top_k` must be unset when thinking is enabled or in adaptive mode. Please consult our documentation at https://platform.claude.com/docs/en/build-with-claude/extended-thinking ``
- (k) `` `temperature` is deprecated for this model. ``
- (l) `` `top_p` is deprecated for this model. ``
- (m) `` `top_k` is deprecated for this model. ``
- (n) `max_tokens: 1000000 > 128000, which is the maximum allowed number of output tokens for claude-opus-5-5`
- (o) `max_tokens: 1000000 > 128000, which is the maximum allowed number of output tokens for claude-sonnet-5-5`
- (p) `max_tokens: 1000000 > 128000, which is the maximum allowed number of output tokens for claude-haiku-5-5`

**Thinking text.** Thinking tokens in this probe: Opus `adaptive_max` 30, Opus `adaptive_xhigh` 19, Sonnet `adaptive_max` 29, Haiku `adaptive_max` 30; every other accepted request answered without thinking. In the matrix, 610 requests used thinking tokens and none streamed thinking text: the thinking blocks arrived with a signature and no text, the documented `omitted` display.

## Prompt caching, 2026-10-26

**Question.** In a multi-turn coding conversation, how much of each prompt is read from cache, what does it save, and what breaks the cache?

**Input.** The system prompt has two blocks: `Conversation <nonce>. ` followed by the instructions below, then `Repository files:` followed by three httpx 0.28.1 source files (`_auth.py`, `_config.py`, `_urls.py`; 42,058 characters). The nonce makes every conversation start cold; a *second conversation* reuses the nonce of the one before it. A larger context of five files (152,546 characters) was used only for cold and warm pairs. The instructions, verbatim:

````text
You are a senior Python engineer pairing with a developer on the httpx code base.
The repository files you may read are included below. Answer concisely, show complete code when you write code,
and keep the existing style (type hints, docstrings, naming).
````

The four questions, verbatim, in order:

1. In five bullet points, explain how an Auth subclass takes part in sending a request: which methods are called, in what order, and how a response can trigger a retry.
2. Write a new Auth subclass BearerTokenAuth that takes a token-refresh callback, sends 'Authorization: Bearer <token>', and refreshes the token once when the server answers 401. Return the complete class.
3. Write pytest tests for BearerTokenAuth using httpx.MockTransport: one test for a normal request and one for refresh-on-401.
4. Write a git commit message (subject line plus a short body) for the change we made in this session.

The new-conversation question: `List the public classes defined in these files, with one line each on what they are for.` The cold and warm question: `Reply with the single word OK.`

**Fixed.** Effort low; Opus `adaptive`, Sonnet `between_tools`, Haiku `disabled` unless the scenario changes it; `max_tokens` 3,000 (256 for the pairs); 2 repetitions per scenario and 5 pairs per context; the client paced under 85% of each deployment's limits; each model's cache test started after its matrix requests had finished. 264 requests, all HTTP 200, 0 throttled.

| Scenario | What it changes |
|---|---|
| `none` | no `cache_control` |
| `auto` | top-level `cache_control` (automatic caching) on every turn |
| `auto_second` | a new conversation with the same instructions and files after `auto`, one question |
| `system_only` | one breakpoint at the end of the repository block |
| `system_only_second` | a new conversation after `system_only`, one question |
| `system_plus_auto` | repository breakpoint and top-level automatic caching |
| `system_plus_auto_second` | a new conversation after `system_plus_auto`, one question |
| `effort_switch` | `adaptive`, automatic caching, top-level effort low, low, high, low |
| `effort_switch_message` | the same switch as per-message effort with the beta header |
| `mode_switch` | automatic caching; thinking off, off, `adaptive`, `adaptive` (Sonnet, Haiku) |
| `prewarm` | a non-streaming `max_tokens: 0` request with the repository breakpoint, then the first question |
| `idle_5m` | automatic caching, default 5-minute TTL, 6.5 minutes idle before turn 2 |
| `idle_1h` | automatic caching with `"ttl": "1h"`, 6.5 minutes idle before turn 2 |
| `ttft_cold_repo` | cold request, repository context, one-word answer, five pairs |
| `ttft_warm_repo` | the same prompt again |
| `ttft_cold_large` | cold request, larger context (Sonnet, Haiku) |
| `ttft_warm_large` | the same prompt again |

### Share of each prompt read from cache

Read tokens / (uncached + written + read input tokens), mean of the repetitions. `—`: the model did not run that scenario.

| Scenario | Turn | Opus | Sonnet | Haiku |
|---|---:|---:|---:|---:|
| `none` | 1 | 0.0% | 0.0% | 0.0% |
| `none` | 2 | 0.0% | 0.0% | 0.0% |
| `none` | 3 | 0.0% | 0.0% | 0.0% |
| `none` | 4 | 0.0% | 0.0% | 0.0% |
| `auto` | 1 | 0.0% | 0.0% | 0.0% |
| `auto` | 2 | 96.1% | 95.9% | 95.9% |
| `auto` | 3 | 94.9% | 95.1% | 97.1% |
| `auto` | 4 | 94.3% | 94.7% | 96.0% |
| `auto_second` | 1 | 0.0% | 0.0% | 0.0% |
| `system_only` | 1 | 0.0% | 0.0% | 0.0% |
| `system_only` | 2 | 95.5% | 95.2% | 95.8% |
| `system_only` | 3 | 90.7% | 90.8% | 93.0% |
| `system_only` | 4 | 86.3% | 86.0% | 89.4% |
| `system_only_second` | 1 | 99.8% | 99.8% | 99.8% |
| `system_plus_auto` | 1 | 0.0% | 0.0% | 0.0% |
| `system_plus_auto` | 2 | 96.1% | 95.9% | 95.9% |
| `system_plus_auto` | 3 | 95.0% | 95.6% | 96.8% |
| `system_plus_auto` | 4 | 94.9% | 95.0% | 95.8% |
| `system_plus_auto_second` | 1 | 99.8% | 99.8% | 99.8% |
| `effort_switch` | 1 | 0.0% | 0.0% | 0.0% |
| `effort_switch` | 2 | 96.6% | 95.6% | 96.3% |
| `effort_switch` | 3 | 95.5% | 95.6% | 96.7% |
| `effort_switch` | 4 | 95.1% | 94.6% | 95.0% |
| `effort_switch_message` | 1 | 0.0% | 0.0% | 0.0% |
| `effort_switch_message` | 2 | 96.0% | 96.1% | 96.3% |
| `effort_switch_message` | 3 | 95.1% | 95.8% | 96.8% |
| `effort_switch_message` | 4 | 93.7% | 94.9% | 95.0% |
| `mode_switch` | 1 | — | 0.0% | 0.0% |
| `mode_switch` | 2 | — | 95.5% | 95.7% |
| `mode_switch` | 3 | — | 0.0% | 0.0% |
| `mode_switch` | 4 | — | 94.7% | 96.1% |
| `prewarm` | 1 | 0.0% | 0.0% | 0.0% |
| `prewarm` | 2 | 99.7% | 99.7% | 99.7% |
| `idle_5m` | 1 | 0.0% | 0.0% | 0.0% |
| `idle_5m` | 2 | 0.0% | 0.0% | 0.0% |
| `idle_1h` | 1 | 0.0% | 0.0% | 0.0% |
| `idle_1h` | 2 | 96.0% | 95.4% | 96.3% |
| `ttft_cold_repo` | 1 | 0.0% | 0.0% | 0.0% |
| `ttft_warm_repo` | 1 | 99.9% | 99.9% | 99.9% |
| `ttft_cold_large` | 1 | — | 0.0% | 0.0% |
| `ttft_warm_large` | 1 | — | 100.0% | 100.0% |

### Cost of each conversation against no cache

Mean list-price cost of the scenario's requests, compared with the same token counts priced as if nothing were cached. Negative is cheaper.

| Scenario | Opus | Sonnet | Haiku |
|---|---:|---:|---:|
| `none` | -0% | -0% | -0% |
| `auto` | -52% | -53% | -52% |
| `auto_second` | +20% | +21% | +21% |
| `system_only` | -50% | -51% | -51% |
| `system_only_second` | -80% | -76% | -76% |
| `system_plus_auto` | -52% | -54% | -52% |
| `system_plus_auto_second` | -77% | -78% | -78% |
| `effort_switch` | -51% | -51% | -46% |
| `effort_switch_message` | -49% | -52% | -45% |
| `mode_switch` | — | -27% | -27% |
| `prewarm` | -32% | -32% | -30% |
| `idle_5m` | +20% | +20% | +22% |
| `idle_1h` | +4% | +4% | +6% |
| `ttft_cold_repo` | +25% | +25% | +25% |
| `ttft_warm_repo` | -95% | -95% | -90% |
| `ttft_cold_large` | — | +25% | +25% |
| `ttft_warm_large` | — | -95% | -90% |

### Cold and warm requests

| Model | Context | Prompt tokens | First text P50 cold → warm, s | Cost cold → warm, US$ |
|---|---|---:|---:|---:|
| Opus 5.5 | three files | 15,459 | 1.51 → 1.38 | 0.0774 → 0.0032 |
| Sonnet 5.5 | three files | 15,456 | 1.03 → 0.89 | 0.0387 → 0.0016 |
| Sonnet 5.5 | five files | 53,313 | 0.94 → 0.92 | 0.1333 → 0.0054 |
| Haiku 5.5 | three files | 15,458 | 0.75 → 0.71 | 0.0019 → 0.0002 |
| Haiku 5.5 | five files | 53,313 | 0.85 → 0.87 | 0.0067 → 0.0005 |

Five pairs per row; differences of a tenth of a second are within the spread of single requests. Per-turn token counts are in [cache_facts.json](../evidence/coding-matrix-20261026/cache/cache_facts.json); every request is in [cache_results.jsonl](../evidence/coding-matrix-20261026/cache/cache_results.jsonl).

## Gateway test, 2026-10-24

**Question.** Through a LiteLLM gateway, does disabling up-front thinking or extending cache coverage change the time to the first visible text?

**Topology.** A Windows client (PowerShell 7.6.7, location not recorded) → LiteLLM 1.106.2 on Azure Container Apps in Japan East (1 vCPU, 2 GiB, one replica, one worker, managed identity) → the Foundry resource in East US 2. The gateway and the models were in different regions, so the times below include a round trip between Japan and the eastern United States and do not measure the gateway's own overhead.

### Input and method

The five prompts below are verbatim inputs; every configuration uses the same source material and order.

1. Explain the request flow from the desktop client to a Claude model on Azure. Which components are shown in the test target architecture, and which are our prototype implementation choices?

2. Using that flow and the supplied code, where could a timeout or incomplete streamed response originate? Separate what these files establish from what would require additional evidence.

3. Continuing your analysis, propose the smallest checks that preserve the client's /v1/messages interface and the three independent model routes. What must be verified before attributing an error to a model?

4. Turn those checks into a concise five-turn validation checklist. Include conversation-history integrity, actual prompt-cache usage, first visible text, full-response completion, and token accounting; do not invent measurements.

5. Review your checklist against the observer code. Which evidence can it already retain, what additional client evidence is needed, and what sensitive information must not be logged? End with the main limits of this small workflow test.

[Complete material and matrix](../data/matrix.json)

Five valid model/mode combinations, two cache configurations and five dependent turns per cell. Fixed medium, stream=true, max_tokens=4096, no tools, no retries and one in-flight request. System-only ran before conversation caching; no cache flush or extra pre-warming. Both phases used Haiku disabled, Sonnet between_tools, Opus adaptive, Sonnet adaptive, then Haiku adaptive. Later histories come from each cell itself and are not byte-identical across cells. The public runner follows the case order in matrix.json, which differs from this execution order.

### Observed results

The recorded experiment on 2026-10-24 completed **50/50 requests**; model cost at its recorded rates was **US$0.79**. First text spans client send to the first nonempty text_delta; P50 is the median of five turns.

<img src="../images/latency-en.svg" width="520" alt="First-text timing of five requests per configuration" />

Generated from the 50 recorded requests: each dot is one request and the horizontal axis is seconds. Small vertical offsets only distinguish turns and carry no metric value. Blue is adaptive; green has no up-front thinking. This is not a quality ranking. [Source](../evidence/requests.json)

**First visible text P50, seconds**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 9.321 | 7.293 |
| Sonnet 5.5<br>adaptive | 8.051 | 1.434 |
| Sonnet 5.5<br>between_tools | 0.954 | 0.893 |
| Haiku 5.5<br>adaptive | 4.235 | 2.910 |
| Haiku 5.5<br>disabled | 0.810 | 0.781 |

**Cache-read share across all five turns, %**

Cache-read share covers all five turns: total read tokens / (total uncached + written + read input tokens). Initial writes enter the denominator but are not hits; new prompts and history still need processing. System only reuses the fixed source; System + history also enables growing automatic conversation caching. This is neither last-turn hit rate nor the mean of per-turn percentages.

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 28.27 | 69.25 |
| Sonnet 5.5<br>adaptive | 33.52 | 67.68 |
| Sonnet 5.5<br>between_tools | 39.96 | 70.68 |
| Haiku 5.5<br>adaptive | 32.81 | 71.04 |
| Haiku 5.5<br>disabled | 47.47 | 72.44 |

Output rate includes thinking; visible rate subtracts thinking tokens. Both divide by full E2E time, not isolated decode time.

**Full completion P50, seconds**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 18.334 | 16.022 |
| Sonnet 5.5<br>adaptive | 15.233 | 8.604 |
| Sonnet 5.5<br>between_tools | 7.991 | 7.874 |
| Haiku 5.5<br>adaptive | 7.160 | 5.917 |
| Haiku 5.5<br>disabled | 3.553 | 3.983 |

**Output P50, tokens/s, including thinking**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 95.78 | 90.86 |
| Sonnet 5.5<br>adaptive | 117.84 | 115.29 |
| Sonnet 5.5<br>between_tools | 114.76 | 112.64 |
| Haiku 5.5<br>adaptive | 183.51 | 172.62 |
| Haiku 5.5<br>disabled | 153.96 | 156.55 |

**Visible output P50, tokens/s**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 55.50 | 58.30 |
| Sonnet 5.5<br>adaptive | 62.56 | 109.48 |
| Sonnet 5.5<br>between_tools | 114.76 | 112.64 |
| Haiku 5.5<br>adaptive | 96.37 | 111.11 |
| Haiku 5.5<br>disabled | 153.96 | 156.55 |

**Estimated model cost, USD**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 0.258394 | 0.193501 |
| Sonnet 5.5<br>adaptive | 0.110115 | 0.081004 |
| Sonnet 5.5<br>between_tools | 0.073466 | 0.060174 |
| Haiku 5.5<br>adaptive | 0.004840 | 0.003642 |
| Haiku 5.5<br>disabled | 0.002472 | 0.002288 |

The no-up-front-thinking modes produced zero thinking tokens in this tool-free workload. Sonnet between_tools is not a universal full-off switch; Opus 5.5 cannot disable thinking. With five samples, P95 is the maximum, not a production-tail estimate.

Higher cache share does not attribute all first-text improvements to caching: conversations generate independently, changing history and thinking usage. Sonnet adaptive produced thinking in 3/5 and 2/5 requests in the two cache groups. All timing is client-side; server queues, network time and model compute are not isolated.

### Timing boundaries

Times start at client send. Headers means completed response headers; first body byte is the first response-body byte, not the first byte of the HTTP exchange. First SSE can be metadata/heartbeat, not visible text. A thinking event does not mark the start of model compute; omitted display can defer or group events. Post-SSE wait is computed per request before taking P50, not by subtracting medians.

### Per-turn records

Total input, read, written, output and thinking columns are token counts. Total input = uncached + read + written; visible output = output - thinking. Full requests, responses and event timing are in the evidence file. Each P95 is the maximum of five turns.

#### Opus 5.5 / adaptive / system

`opus-adaptive-system`

Requests with thinking: 5/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 1.453 | 1.671 |
| First SSE | 1.455 | 1.671 |
| First text | 9.321 | 10.988 |
| Post-SSE wait | 8.027 | 9.960 |
| Full end | 18.334 | 20.904 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 9.171 | 17.495 |
| 2 | 10.773 | 18.334 |
| 3 | 7.071 | 15.864 |
| 4 | 9.321 | 18.717 |
| 5 | 10.988 | 20.904 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3838 | 1961 | 0 |
| 3 | 5654 | 1961 | 0 |
| 4 | 7169 | 1961 | 0 |
| 5 | 9071 | 1961 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1768 | 797 |
| 2 | 1756 | 959 |
| 3 | 1444 | 503 |
| 4 | 1837 | 783 |
| 5 | 1957 | 845 |

#### Sonnet 5.5 / adaptive / system

`sonnet-adaptive-system`

Requests with thinking: 3/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 1.187 | 1.621 |
| First SSE | 1.188 | 1.621 |
| First text | 8.051 | 9.531 |
| Post-SSE wait | 7.029 | 8.248 |
| Full end | 15.233 | 16.571 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 1.622 | 8.757 |
| 2 | 1.073 | 9.777 |
| 3 | 8.051 | 15.233 |
| 4 | 8.616 | 16.051 |
| 5 | 9.531 | 16.571 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3106 | 1961 | 0 |
| 3 | 4212 | 1961 | 0 |
| 4 | 6078 | 1961 | 0 |
| 5 | 7990 | 1961 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1038 | 0 |
| 2 | 1048 | 0 |
| 3 | 1795 | 842 |
| 4 | 1847 | 851 |
| 5 | 1995 | 1006 |

#### Sonnet 5.5 / between_tools / system

`sonnet-between-system`

Requests with thinking: 0/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.952 | 2.406 |
| First SSE | 0.953 | 2.406 |
| First text | 0.954 | 2.408 |
| Post-SSE wait | 0.001 | 0.001 |
| Full end | 7.991 | 10.073 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 2.408 | 7.808 |
| 2 | 0.700 | 7.991 |
| 3 | 0.995 | 7.783 |
| 4 | 0.865 | 8.285 |
| 5 | 0.954 | 10.073 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 1960 |
| 2 | 2900 | 1960 | 0 |
| 3 | 3877 | 1960 | 0 |
| 4 | 4892 | 1960 | 0 |
| 5 | 5935 | 1960 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 831 | 0 |
| 2 | 917 | 0 |
| 3 | 944 | 0 |
| 4 | 978 | 0 |
| 5 | 1144 | 0 |

#### Haiku 5.5 / adaptive / system

`haiku-adaptive-system`

Requests with thinking: 5/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.864 | 1.002 |
| First SSE | 0.865 | 1.003 |
| First text | 4.235 | 4.436 |
| Post-SSE wait | 3.260 | 3.590 |
| Full end | 7.160 | 7.461 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 4.262 | 7.328 |
| 2 | 4.235 | 7.160 |
| 3 | 3.822 | 6.641 |
| 4 | 2.105 | 4.804 |
| 5 | 4.436 | 7.461 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3622 | 1961 | 0 |
| 3 | 4996 | 1961 | 0 |
| 4 | 6198 | 1961 | 0 |
| 5 | 7070 | 1961 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1552 | 791 |
| 2 | 1314 | 680 |
| 3 | 1131 | 549 |
| 4 | 807 | 239 |
| 5 | 1410 | 691 |

#### Haiku 5.5 / disabled / system

`haiku-disabled-system`

Requests with thinking: 0/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.808 | 1.538 |
| First SSE | 0.809 | 1.554 |
| First text | 0.810 | 1.563 |
| Post-SSE wait | 0.001 | 0.008 |
| Full end | 3.553 | 4.804 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 1.563 | 4.389 |
| 2 | 0.810 | 3.553 |
| 3 | 0.753 | 3.234 |
| 4 | 0.742 | 3.413 |
| 5 | 0.874 | 4.804 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 1960 |
| 2 | 2753 | 1960 | 0 |
| 3 | 3360 | 1960 | 0 |
| 4 | 3910 | 1960 | 0 |
| 5 | 4477 | 1960 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 684 | 0 |
| 2 | 547 | 0 |
| 3 | 479 | 0 |
| 4 | 502 | 0 |
| 5 | 741 | 0 |

#### Opus 5.5 / adaptive / history

`opus-adaptive-conversation`

Requests with thinking: 5/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 1.435 | 1.677 |
| First SSE | 1.436 | 1.678 |
| First text | 7.293 | 8.749 |
| Post-SSE wait | 6.215 | 7.191 |
| Full end | 16.022 | 18.627 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 7.293 | 16.022 |
| 2 | 8.054 | 18.054 |
| 3 | 6.088 | 13.685 |
| 4 | 4.541 | 13.207 |
| 5 | 8.749 | 18.627 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 3817 | 2014 | 1799 |
| 3 | 5513 | 3813 | 1696 |
| 4 | 6748 | 5509 | 1235 |
| 5 | 8013 | 6744 | 1265 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1747 | 697 |
| 2 | 1636 | 653 |
| 3 | 1164 | 390 |
| 4 | 1200 | 299 |
| 5 | 1741 | 655 |

#### Sonnet 5.5 / adaptive / history

`sonnet-adaptive-conversation`

Requests with thinking: 2/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 1.154 | 1.432 |
| First SSE | 1.155 | 1.433 |
| First text | 1.434 | 8.586 |
| Post-SSE wait | 0.002 | 7.282 |
| Full end | 8.604 | 17.257 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 1.434 | 7.260 |
| 2 | 1.029 | 8.604 |
| 3 | 0.998 | 8.385 |
| 4 | 6.170 | 13.774 |
| 5 | 8.586 | 17.257 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 2905 | 2014 | 887 |
| 3 | 3905 | 2901 | 1000 |
| 4 | 4954 | 3901 | 1049 |
| 5 | 6559 | 4950 | 1605 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 837 | 0 |
| 2 | 942 | 0 |
| 3 | 980 | 0 |
| 4 | 1540 | 610 |
| 5 | 2021 | 846 |

#### Sonnet 5.5 / between_tools / history

`sonnet-between-conversation`

Requests with thinking: 0/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.879 | 0.984 |
| First SSE | 0.881 | 0.985 |
| First text | 0.893 | 0.986 |
| Post-SSE wait | 0.001 | 0.012 |
| Full end | 7.874 | 8.552 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 0.986 | 7.066 |
| 2 | 0.749 | 8.552 |
| 3 | 0.830 | 7.874 |
| 4 | 0.937 | 6.643 |
| 5 | 0.893 | 8.524 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 2013 |
| 2 | 2958 | 2013 | 941 |
| 3 | 3972 | 2954 | 1014 |
| 4 | 4930 | 3968 | 958 |
| 5 | 5735 | 4926 | 805 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 889 | 0 |
| 2 | 954 | 0 |
| 3 | 887 | 0 |
| 4 | 740 | 0 |
| 5 | 972 | 0 |

#### Haiku 5.5 / adaptive / history

`haiku-adaptive-conversation`

Requests with thinking: 5/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.969 | 1.123 |
| First SSE | 0.970 | 1.124 |
| First text | 2.910 | 4.020 |
| Post-SSE wait | 2.002 | 2.895 |
| Full end | 5.917 | 7.702 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 4.020 | 7.702 |
| 2 | 2.910 | 6.552 |
| 3 | 2.972 | 5.917 |
| 4 | 1.752 | 4.492 |
| 5 | 2.829 | 5.739 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 3557 | 2014 | 1539 |
| 3 | 4748 | 3553 | 1191 |
| 4 | 5787 | 4744 | 1039 |
| 5 | 6545 | 5783 | 758 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1487 | 687 |
| 2 | 1131 | 403 |
| 3 | 968 | 361 |
| 4 | 693 | 175 |
| 5 | 1044 | 370 |

#### Haiku 5.5 / disabled / history

`haiku-disabled-conversation`

Requests with thinking: 0/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.773 | 1.204 |
| First SSE | 0.778 | 1.205 |
| First text | 0.781 | 1.216 |
| Post-SSE wait | 0.001 | 0.011 |
| Full end | 3.983 | 4.276 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 1.216 | 4.276 |
| 2 | 0.755 | 3.983 |
| 3 | 0.781 | 3.603 |
| 4 | 0.759 | 3.354 |
| 5 | 0.942 | 4.184 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 2013 |
| 2 | 2867 | 2013 | 850 |
| 3 | 3516 | 2863 | 649 |
| 4 | 4151 | 3512 | 635 |
| 5 | 4754 | 4147 | 603 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 798 | 0 |
| 2 | 589 | 0 |
| 3 | 564 | 0 |
| 4 | 538 | 0 |
| 5 | 644 | 0 |

### Limits and sources

This is one fixed source-review workload, not production traffic. There is no answer-quality score, concurrency test or other effort level. Shorter answers or reduced reasoning can also affect timing; quality equivalence was not established.

[Requests and responses](../evidence/requests.json) · [Summary](../evidence/summary.json) · [Provenance and hashes](../evidence/provenance.json)

[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) · [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [LiteLLM v1.106.2 source](https://github.com/BerriAI/litellm/blob/v1.106.2/litellm/llms/anthropic/chat/transformation.py)
