# Claude 5.5 on Microsoft Foundry: Thinking, Effort, Prompt Caching, Latency and Coding Accuracy

[![Models](https://img.shields.io/badge/models-Opus%20%C2%B7%20Sonnet%20%C2%B7%20Haiku%205.5-0078D4)](#purpose)
[![Measured](https://img.shields.io/badge/measured-2026--10--26%20to%2010--27-0078D4)](#results)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml)

Author: Xinyu Wei · [中文](README_CN.md)

## Purpose

**What this measures.** How Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5 perform as deployed in Microsoft Foundry with the [Hosted on Azure](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options) option: model version 2, an Anthropic-operated service running on Azure infrastructure, in GlobalStandard deployments. For each coding request we measure how long the first visible text and the full answer take, whether the code passes the problem's own unit tests, and what the request costs at list price. The request settings in the table below change all of these, and some combinations are rejected with HTTP 400; a successful HTTP response shows none of this.

**Completed ACA run:** 650/650 requests retained, 624 measured answers graded. Performance comes first below, followed by correctness. [Full results](docs/results.md#aca-gateway-snapshot).

**Current test method.** Linux VM client → LiteLLM on Azure Container Apps → Foundry, with the client, gateway and Foundry resource in East US 2. The client uses the gateway key; LiteLLM uses its managed identity to call Foundry. Prompt caching is enabled with top-level `cache_control`. Each model has one request in flight, so this measures individual requests, not load.

**Historical gateway check (2026-10-24).** A Windows client sent a five-turn conversation through LiteLLM on Azure Container Apps in Japan East to the same deployments; LiteLLM used its own managed identity and was set not to drop parameters or retry. Those times include Japan-to-US network latency and are not results from the current East US 2 run. See [the results page](docs/results.md#gateway-test-2026-10-24).

<img src="images/topology-en.svg" width="900" alt="Current cache-enabled test path: a Linux VM client sends streaming requests through LiteLLM on Azure Container Apps in East US 2 to the three Microsoft Foundry Claude deployments. Prompt caching is at Foundry; the client records timing and native usage." />

The figure shows the East US 2 gateway path, not the historical direct-VM result path. The [runner](gateway-cache/aca_cache_matrix.py) uses the [12-problem manifest](data/gateway-cache-problems.json): 26 accepted mode/effort cells, two identical requests per problem/cell, plus 26 warm-ups (650 requests collected). Top-level `cache_control` is `ephemeral`, TTL `1h`; request 1 writes and request 2 is checked for native cache reads. These are repeated requests, not conversation turns or a cache-disabled comparison. The complete performance table reports each request number separately, with code-test outcomes for all measured answers. Historical results retain their dates and paths. Original explanatory diagram with unmodified [Azure icons](images/icon-sources.json).

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

[![Table 1. Complete thinking-mode and effort matrix.](images/parameter-support-en.svg)](images/parameter-support-en.svg)

The 54 `adaptive`/`between_tools`/`disabled` × effort cells were individually probed; 26 were accepted, including five omitted-effort cells. For `enabled`, one request per model used `budget_tokens: 1024` and omitted effort; the HTTP 400 rejects the mode itself, so all effort cells say not supported. The cache column states applicability only: a rejected thinking mode makes the request inapplicable; it does not mean the model lacks caching. Default effort values are from the [effort documentation](https://platform.claude.com/docs/en/build-with-claude/effort).

Historical cache scope: all five accepted model/mode rows read cache at effort low; adaptive also read cache in the high-effort switch scenario. The separate ACA performance section reports the later full mode/effort coverage. Applicability and parameter acceptance alone do not establish cache-enabled performance. Fixed historical matrix controls: `max_tokens: 128000`, `stream: true`; `temperature`, `top_p`, `top_k` omitted. No `thinking` field is documented to select adaptive; the three omitted-thinking/omitted-effort probes returned 200.

**Table 2. Complete prompt-cache settings.**

[![Table 2. Complete prompt-cache settings.](images/cache-settings-en.svg)](images/cache-settings-en.svg)

Sources: [probe requests](evidence/coding-matrix-20261026/probe/probe_results.jsonl), [cache requests](evidence/coding-matrix-20261026/cache/cache_results.jsonl) and [prompt-caching documentation](https://platform.claude.com/docs/en/build-with-claude/prompt-caching). Table 2 uses two repetitions per scenario: Opus adaptive, Sonnet between_tools, Haiku disabled, effort low; first writes are separate from turns 2-4. Read share is read tokens / (uncached + written + read input tokens), aggregated within each model/scenario/turn. New conversations reuse the files but change the question. The 512-token boundary and four-breakpoint limit are documented, not boundary-sweep measurements. All cache markers use `type: ephemeral`; reads cost 0.05x base input on Opus/Sonnet and 0.1x on Haiku (documented prices). These are historical direct-VM observations, not evidence for the later ACA run.

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

**Sources.** Accepted values and the HTTP 400 messages come from our probe ([results](docs/results.md#parameter-probe-2026-10-26)). What each setting does, the defaults, the rules for `between_tools` and `disabled`, and the advice to set `max_tokens` to 128,000 for agentic coding on Sonnet 5.5 come from Claude's [thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) and [effort](https://platform.claude.com/docs/en/build-with-claude/effort) pages; cache rules and price multipliers from [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching); prices from [pricing](https://platform.claude.com/docs/en/about-claude/pricing); hosting options and Foundry setup from [Claude in Microsoft Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry); all read on 2026-10-26. The *Choose it when* row is our reading of these 18 problems, not general advice.

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

**Cache evidence.** 304 measured pairs completed; 302 show native cache hits. The other 2 crossed the shutdown/restart interval and rewrote expired entries. They remain in request, cost and correctness counts but not cache-hit performance statistics. Hit pairs read at least 100.0% of the preceding cache write; 0 reused a response message ID. This proves those cache reads, not a general speedup. Responses report `inference_geo: global` and an East US 2 region header; that is not a regional-inference guarantee.

**Cost and limits.** The full run cost $76.17 at recorded [list prices](coding-matrix/pricing.py), including warm-ups, writes, reads, output and truncated answers; infrastructure is excluded and this is not an invoice. Pair metrics exclude warm-ups and incomplete or non-hit pairs, never the correctness denominator. Full distributions and counts remain in [the facts](evidence/gateway-cache-20261026/interim-facts.json).

[All 26 configurations and paired observations](docs/results.md#aca-gateway-snapshot).

**Evidence boundary.** Per-request outbound audit is not retained for the current batch. Earlier gateway traces cannot replace it. Parameter evidence and the separate audit are in [Results](docs/results.md#aca-gateway-snapshot).

### Code correctness after performance

**Method.** The same 624 measured answers, excluding only warm-ups, were graded with the official SWE-bench harness 5.0.2 at commit `02e7a74ffd0b707aab73d203fe87bdc7c76afc8e`. The official `extract_diff` function extracted predictions; no answer repair or new model call was used. Each cell/repeat has a separate run ID. All 12 selected gold controls passed. [Frozen inputs, native reports and verifier](evidence/gateway-score-20261027/verification.json).

Overall: 245/624 (39.26%) resolved; 257 patch-application failures, 108 unresolved test results and 14 truncated empty answers. These stay in the denominator. Different model/mode populations make the aggregate unsuitable as a fair overall ranking; each matched cell has 24 answers. This is a 12-instance subset, not the full SWE-bench Lite score.

**Ambiguity retained.** 6 official `no_tests_collected` flags remain unresolved. Each associated log first collected 92 top-level tests, includes nested zero-collection output, and shows `NameError: cached_eval`; none was silently removed or relabeled. [Six source-linked reviews](evidence/gateway-score-20261027/ambiguous-review.json). The [environment inventory](evidence/gateway-score-20261027/environment.json) was captured after evaluation, not as in-run telemetry.

**Evidence and replay.** [Facts](evidence/gateway-cache-20261026/interim-facts.json), [export hashes and redactions](evidence/gateway-cache-20261026/_export_manifest.json), [Opus](evidence/gateway-cache-20261026/responses_opus.jsonl), [Sonnet](evidence/gateway-cache-20261026/responses_sonnet.jsonl), [Haiku](evidence/gateway-cache-20261026/responses_haiku.jsonl). The metrics-only projection omits prompt/answer bodies, thinking signatures, private endpoints and other headers; it is not a correctness-scoring dataset. Replay instructions are in [Testing](docs/testing.md#aca-snapshot-replay).

**Historical results only.** The following direct-VM measurements belong to the retired method. In particular, the 21-cell coding matrix omitted `cache_control` and does not meet the current ACA cache-enabled protocol. The Japan East gateway check is separately dated. None of these numbers is a result from the current East US 2 ACA run.

Words used in the results:

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

**Where each part ran.**

| Part | Where | Detail |
|---|---|---|
| Client: probe, matrix, cache test | Linux VM `Standard_D4s_v5`, East US 2 | Ubuntu 24.04, kernel 7.0.0-1017-azure, Python 3.12.3, httpx 0.28.1, azure-identity 1.25.1; Entra token from the VM's managed identity; TCP connect to the endpoint 9.67 ms median before the matrix |
| Models | Foundry resource in East US 2 | `claude-opus-5-5` 40,000 tokens per minute; `claude-sonnet-5-5` and `claude-haiku-5-5` 80,000 each; version 2, GlobalStandard, so a request may be served outside East US 2 |
| Unit tests | Docker on the same VM | `--network none`, 1.5 CPUs, 3 GB; the toolchains of Aider's benchmark image: Python 3.11, Go 1.21.5, Rust, Node 20, OpenJDK 21, CMake and Boost |

**What each matrix request sent.** One streamed Messages request per answer; the `system` and `content` values are shortened here:

```json
{
  "model": "claude-sonnet-5-5",
  "max_tokens": 128000,
  "stream": true,
  "thinking": {"type": "between_tools"},
  "output_config": {"effort": "low"},
  "system": "Act as an expert software developer. …",
  "messages": [{"role": "user", "content": "I have *added these files to the chat* so you can go ahead and edit them. …"}]
}
```

Only `model`, `thinking.type` and `output_config.effort` change between cells. There is no `cache_control`, no tool and no `temperature`, `top_p` or `top_k`. The full system prompt and a complete user message are quoted in [the results page](docs/results.md#coding-matrix-2026-10-26); all 18 are in [problems.json](evidence/coding-matrix-20261026/matrix/problems.json).

**How each number is measured, and the scripts.**

| Number | From → to, or how | Script |
|---|---|---|
| Accepted values | HTTP 200 or 400 for a one-word prompt sent with each value | [`probe.py`](coding-matrix/probe.py) |
| First visible text, first event, full answer | request written → first `text_delta`, `message_start`, end of stream; clock on the VM | [`claude_api.py`](coding-matrix/claude_api.py) `stream_message` |
| Completed, thinking and output tokens | status, `stop_reason` and `usage` of each stream | [`bench.py`](coding-matrix/bench.py) |
| Pass | the exercise's unit tests, offline in Docker | [`judge.py`](coding-matrix/judge.py) |
| P50, P95, intervals, cost per 1,000 | nearest rank; bootstrap over problems; mean list-price cost × 1,000 | [`analyze.py`](coding-matrix/analyze.py) |
| Cache reads and writes, conversation cost | `usage` of each turn; the same tokens priced as if nothing were cached | [`cache_test.py`](coding-matrix/cache_test.py), [`cache_analyze.py`](coding-matrix/cache_analyze.py) |

**Do not read these grids as a general ranking of the three models.** Opus answered all 18 problems correctly in every cell, so this test cannot separate its effort levels. With 18 problems, a Sonnet or Haiku cell's 95% interval spans 30 to 44 points (for example Sonnet `between_tools` · high: 44 of 54, 65% to 94%). The problems are short single-file exercises. Each row is one model and thinking mode, each column an effort level; *not accepted* means the API returned HTTP 400. P95, full-answer times, token counts and every interval are on [the results page](docs/results.md#results-per-cell).

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

What stands out:
- **The platform answered every request.** All 1,155 matrix requests returned HTTP 200, none with 429 or 5xx, and 1,130 of the 1,134 measured requests completed. Of the other four, three Haiku `adaptive` · max answers spent all 128,000 output tokens on thinking (`stop_reason: max_tokens`), and one Sonnet `adaptive` · max stream sent `message_start` and two pings, then nothing until the client's 600 s read timeout ended it at 661 s.
- **Without thinking, text starts in under half a second.** Sonnet `between_tools` and Haiku `disabled` showed the first visible text after 0.44 s P50 and 0.74 s P95 over 324 requests. The first event came after 0.47 s P50 over all requests, and between 0.39 and 0.53 s P50 in each cell; the rest of the wait is thinking, which is not streamed. At effort max the first visible text took 51.4 s (Opus), 190 s (Sonnet) and 121 s (Haiku), P50.
- **Thinking raised Haiku's pass rate, not Sonnet's.** At the same three effort levels, Haiku passed 47.5% with `adaptive` and 35.2% with `disabled`: +12.3 points (95% interval +2.5 to +23.5; 9 problems better, 2 worse, 7 equal). Sonnet: 75.9% against 78.4% with `between_tools`, -2.5 points (-7.4 to +1.9).
- **Higher effort mostly bought time and cost.** Opus cost $23.34 per 1,000 requests at low and $355.75 at max for the same 54 passes. Sonnet's eight cells passed 40 to 44 times each, inside one another's intervals.
- **The problem mattered more than the setting.** Over all its cells Sonnet passed `java/house` 1 time in 24 and `javascript/promises` 3 times in 24; Haiku never passed 6 of the 18 problems. Opus passed every problem every time.

**Prompt caching in a four-turn coding conversation.** Each conversation sends the same instructions and three httpx source files (about 15,500 tokens) as the system prompt, then four questions in turn: how an `Auth` subclass takes part in a request, a new `BearerTokenAuth` class, pytest tests for it, and a commit message. Opus uses `adaptive`, Sonnet `between_tools` and Haiku `disabled`, effort low, two repetitions per scenario. Each scenario changes one thing; results are the range over the three models:

| Scenario | What changed | Result |
|---|---|---|
| Automatic caching | top-level `cache_control` on every turn | turns 2–4 read 94–97% of the prompt from cache; the conversation cost 52–53% less than the same tokens without cache |
| Breakpoint after the files, new conversation | `cache_control` on the repository block; then a second conversation with the same files and a new question | the new conversation read 15,440–15,442 tokens from cache and cost 76–80% less |
| Automatic caching only, new conversation | top-level `cache_control`; then a second conversation with the same files | read 0 tokens and wrote a new entry: 20–21% more than without cache |
| Top-level effort change | effort low → high on turn 3 | turn 3 still read 95–97% of the prompt from cache |
| Per-message effort | the same change as an effort-only system message, beta header `mid-conversation-output-config-2026-07-01` | turn 3 read 95–97% from cache |
| Thinking mode change (Sonnet, Haiku) | thinking off → `adaptive` on turn 3 | turn 3 read 0 tokens and rewrote 16,609–17,138; turn 4 read 95–96% again |
| 6.5 minutes idle, 5-minute TTL | default TTL | turn 2 read 0 tokens and rewrote 16,145–16,158 |
| 6.5 minutes idle, 1-hour TTL | `"ttl": "1h"` | turn 2 read 15,490–15,493 tokens |
| Pre-warm | a non-streaming request with `max_tokens: 0`, then the first question | the first question read 15,440–15,444 tokens (99.7% of its prompt) |
| Cold and warm, same prompt | five pairs, one-word answer | first visible text P50 at about 15,500 tokens: Opus 1.51 → 1.38 s, Sonnet 1.03 → 0.89 s, Haiku 0.75 → 0.71 s; at about 53,300: Sonnet 0.94 → 0.92 s, Haiku 0.85 → 0.87 s. The warm request cost 4–8% of the cold one |

Claude's [effort page](https://platform.claude.com/docs/en/build-with-claude/effort) says that changing the top-level effort between requests invalidates cache breakpoints. In this test, with automatic caching, turn 3 still read the cached prefix; we did not find out why, so treat it as an observation on these deployments on 2026-10-26. The per-message form, which the docs say keeps the cache, behaved the same. All 264 cache requests returned HTTP 200. Per-turn read shares and costs are on [the results page](docs/results.md#prompt-caching-2026-10-26).

**Through a LiteLLM gateway (2026-10-24).** An earlier test sent a five-turn source-review conversation through LiteLLM 1.106.2 on Azure Container Apps in Japan East to the same East US 2 resource, in ten configurations at effort medium. All 50 requests completed, and the gateway's outbound log showed the model, thinking mode, effort, `stream`, `max_tokens` and cache markers of every request reaching Foundry unchanged. First visible text P50 was 0.78 to 0.95 s with thinking off and up to 9.32 s with `adaptive`. The gateway and the models were in different regions, so these times include a round trip between Japan and the eastern United States and do not measure the gateway's own overhead. Its full tables are on [the results page](docs/results.md#gateway-test-2026-10-24).

**Measured runs.**

| Run | When, UTC | What | Requests | List-price cost | Result |
|---|---|---|---:|---:|---|
| `probe` | 2026-10-26 08:11–08:12 | accepted values, one-word prompt | 102 | $0.05 | 50 × HTTP 200, 52 × HTTP 400 |
| `smoke` | 2026-10-26 08:35 | one problem in each of the 21 cells, `max_tokens` 32,000 | 21 | $0.14 | 21 completed |
| `pilot-32k` | 2026-10-26 08:37–09:04 | the matrix with `max_tokens` 32,000 | 173 | $5.59 | stopped: 7 answers hit 32,000 tokens and 4 hit the output-token-per-minute limit (HTTP 429); not used in the results |
| `matrix` | 2026-10-26 09:04–14:11 | 21 cells × 18 problems × 3, plus 21 warm-ups | 1,155 | $55.36 | 1,130 of 1,134 completed; no 429 |
| `cache` | 2026-10-26 13:04–14:57 | caching scenarios | 264 | $6.70 | 264 × HTTP 200 |
| `gateway` | 2026-10-24 | five-turn conversation through LiteLLM, ten configurations | 50 | $0.79 | 50 completed |

The 2026-10-26 runs cost $67.85 at list prices. Their records are in [`evidence/coding-matrix-20261026/`](evidence/coding-matrix-20261026/), with the endpoint and VM names replaced; the 2026-10-24 records are in [`evidence/`](evidence/).

**Limits.**
- **One client, one region, one day, one request at a time per deployment.** No concurrency, load or soak test, and no client outside Azure.
- **Public exercises, first attempt, no tools.** As in Aider's benchmark the model sees the stub and the instructions but not the tests. `between_tools` differs from `disabled` only in tool loops, which this test never ran.
- **Ceiling and sample size.** Opus passed all 54 answers in every cell, and 18 problems give wide intervals; a difference of a few answers between two cells is within noise.
- **Thinking display.** 610 matrix requests used thinking tokens and 0 streamed any thinking text, so the first visible text includes all thinking. `display: "summarized"` was not tested.
- **Routing.** GlobalStandard deployments may serve a request outside East US 2, and all 1,155 matrix responses reported `usage.inference_geo` as `global`; other client locations or deployment types will give other latencies.
- **Cost.** List prices on 2026-10-26, not an Azure invoice.
- **Gateway.** The retained 2026-10-24 gateway results used another region and do not characterize the current East US 2 ACA path.

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
