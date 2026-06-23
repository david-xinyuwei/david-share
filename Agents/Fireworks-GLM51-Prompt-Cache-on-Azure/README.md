# Fireworks GLM-5.1 Prompt Cache on Azure

![Azure AI Foundry](https://img.shields.io/badge/Azure%20AI%20Foundry-Fireworks-0078D4) ![Model](https://img.shields.io/badge/Model-FW--GLM--5.1-2EA44F) ![Cache](https://img.shields.io/badge/Prompt%20Cache-Validated-6F42C1) ![Workload](https://img.shields.io/badge/Workload-AI%20Companion-6F42C1) ![Language](https://img.shields.io/badge/Docs-EN%20%7C%20CN-lightgrey)

A field guide for Microsoft teammates and customers: **which prompt and request settings improve Fireworks prompt-cache hit rate, by how much, and what evidence supports the recommendation**.

> Author: Wei Xinyu (Xinyu Wei), Microsoft AI and Apps Global Black Belt (GBB) Senior System Engineer

[English](README.md) | [中文版](README-CN.md)

---

## Executive Summary

The largest cache lever is **not** a model parameter. It is prompt layout: keep the prefix stable, keep memory order deterministic, and then use a stable session routing key.

Primary evidence comes from a catalog `FW-GLM-5.1` AI companion multi-turn test on Azure AI Foundry Fireworks PAYGO: **6 groups x 8 sessions x 8 turns = 384 successful streaming requests**. Custom full-weight customer models must still be revalidated on Provisioned/PTU.

| Setting / Control | What To Set | Cache Hit-Rate Lift | TTFT Impact | Recommendation |
|---|---|---:|---:|---|
| Stable prompt prefix | Put persona, policy, tools, and deterministic memory first; append volatile user/request data last | **1.30% -> 99.64%**, **+98.34 pp**, **76.65x** vs dynamic-prefix anti-pattern | P50 **0.969s -> 0.121s** (-87.5%); P95 **1.1221s -> 0.1689s** (-84.9%) | Always. This is the biggest lever. |
| Deterministic memory order | Serialize companion memory in the same order across turns | **26.67% -> 99.64%**, **+72.97 pp**, **3.74x** vs shuffled-memory anti-pattern | P50 **0.9995s -> 0.121s** (-87.9%); P95 **1.1872s -> 0.1689s** (-85.8%) | Required for AI companion, agent memory, and profile/context blocks. |
| `x-session-affinity` | Stable header value per user/session | In a warmed catalog run cache was already high: **99.63% -> 99.64%**, +0.01 pp | P95 **1.2434s -> 0.1689s** (-86.4%) vs no explicit affinity | Best default when the client can set headers; improves tail latency and cache locality. |
| `prompt_cache_key` | Stable request-body value per user/session | **1.30% -> 97.99%**, **+96.69 pp** vs dynamic-prefix anti-pattern | P50 **0.969s -> 0.1535s** (-84.2%); P95 **1.1221s -> 0.8557s** (-23.7%) | Use when request-body control is easier than custom headers. |
| `x-session-affinity` + `prompt_cache_key` | Stable value for both | **1.30% -> 98.63%**, **+97.33 pp** vs dynamic-prefix anti-pattern | P50 **0.969s -> 0.1465s** (-84.9%); P95 **1.1221s -> 0.6725s** (-40.1%) | Valid, but not better than `x-session-affinity` alone in this run. |
| `prompt_cache_isolation_key` | Keep stable only when namespace isolation is required | Not a cache-lift knob; varying it separates cache entries | Can reduce sharing if varied per request | Use for tenant/privacy isolation, not higher hit rate. |
| `temperature`, `top_p`, `max_tokens` | Generation controls | No measured cache-hit lift | Affect output shape, cost, and generation time | Tune after cache layout and routing are correct. |

**Field takeaway:** fix prompt layout first, then add a stable session routing key. Request parameters cannot rescue a prompt whose first tokens keep changing.

### Best-Practice Request Pattern

Use this shape in production code: stable prefix first, dynamic content last, and one stable routing key per user/session. The complete executable version is in `scripts/cache_friendly_request_example.py`.

```python
user_id = "user-123"          # Stable for the real end user.
conversation_id = "chat-456"  # Stable for the multi-turn conversation.
session_key = f"{user_id}:{conversation_id}"

# Keep this section byte/token-stable across turns.
stable_persona = """
You are a warm AI companion. Be concise, supportive, and practical.
Do not mention internal cache, routing, or benchmark details to the user.
""".strip()

# Serialize memory in deterministic order. Do not shuffle this list per request.
stable_memory_items = [
    "The user prefers short replies with one concrete next step.",
    "The user values gentle encouragement over direct criticism.",
    "The user is building a calmer evening routine.",
]
stable_memory = "\n".join(f"- {item}" for item in stable_memory_items)

static_app_policy = """
Prompt layout rules:
1. Stable persona and policy first.
2. Stable memory in deterministic order.
3. Conversation history in chronological order.
4. Current user message and volatile request context last.
""".strip()

# Only this tail should change every turn.
current_user_message = "I feel tired today. Help me decide one small next step."
volatile_tail_context = "request_id=req-789; client_time_bucket=2026-06-23T09:00Z"

messages = [
    {
        "role": "system",
        "content": f"{stable_persona}\n\nStable user memory:\n{stable_memory}\n\n{static_app_policy}",
    },
    {
        "role": "user",
        "content": f"{current_user_message}\n\nVolatile context, placed last:\n{volatile_tail_context}",
    },
]

payload = {
    "messages": messages,
    "temperature": 0,
    "max_tokens": 128,
    # Body-level cache/session routing key. Keep stable per user/session.
    "prompt_cache_key": session_key,
    # Ask Fireworks to return server TTFT and cached-token metrics.
    "perf_metrics_in_response": True,
}
headers = {
    "Content-Type": "application/json",
    # Header-level session routing key. Best measured tail TTFT in this run.
    "x-session-affinity": session_key,
}
```

Run it directly:

```bash
python scripts/cache_friendly_request_example.py \
  --endpoint "$FIREWORKS_AZURE_ENDPOINT" \
  --deployment "$FIREWORKS_DEPLOYMENT" \
  --bearer-token "$FIREWORKS_BEARER_TOKEN" \
  --user-id user-123 \
  --conversation-id chat-456

# Run the same user/session twice to observe cached_tokens increase on the repeat call.
python scripts/cache_friendly_request_example.py \
  --endpoint "$FIREWORKS_AZURE_ENDPOINT" \
  --deployment "$FIREWORKS_DEPLOYMENT" \
  --bearer-token "$FIREWORKS_BEARER_TOKEN" \
  --user-id user-123 \
  --conversation-id chat-456
```

The script is executable and prints `prompt_tokens`, `cached_tokens`, and `server_ttft_sec` when the deployment returns non-streaming perf metrics. In the tested Azure path, non-streaming responses returned token accounting but not body TTFT; use `streaming_ttft_loadtest.py` or `companion_multiturn_loadtest.py` for TTFT measurement.

Equivalent curl pattern:

```bash
SESSION_KEY="user-123:chat-456"

curl -sS "$FIREWORKS_AZURE_ENDPOINT/openai/deployments/$FIREWORKS_DEPLOYMENT/chat/completions?api-version=2025-04-01-preview" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $FIREWORKS_BEARER_TOKEN" \
  -H "x-session-affinity: $SESSION_KEY" \
  -d @- <<'JSON'
{
  "temperature": 0,
  "max_tokens": 128,
  "prompt_cache_key": "user-123:chat-456",
  "perf_metrics_in_response": true,
  "messages": [
    {
      "role": "system",
      "content": "Stable persona and policy first.\n\nStable user memory:\n- The user prefers short replies with one concrete next step.\n- The user values gentle encouragement over direct criticism.\n\nStatic app policy: keep dynamic request metadata at the end."
    },
    {
      "role": "user",
      "content": "I feel tired today. Help me decide one small next step.\n\nVolatile context, placed last: request_id=req-789."
    }
  ]
}
JSON
```

Avoid this anti-pattern:

```python
# Bad: timestamp/request_id before the stable persona destroys exact-prefix reuse.
system_prompt = f"""
request_id={request_id}; timestamp={now_iso}
You are a warm AI companion...
Stable user memory:
{stable_memory}
"""
```

---

## Scope Definition

| Dimension | Included | Excluded / Not Claimed |
|---|---|---|
| Model | Catalog `FW-GLM-5.1` on Azure AI Foundry Fireworks PAYGO | Customer merged full-weight custom model performance |
| Primary workload | Synthetic AI companion multi-turn sessions | Customer production traffic replay |
| Metrics | `cached_tokens`, cache ratio, streaming TTFT, output tokens/sec, non-streaming latency | Production SLA or PTU capacity guarantee |
| Custom model boundary | Full-weight PAYGO deployment returned a Provisioned-only requirement in the tested path | Claim that custom PTU cannot work |
| Purpose | Cache-hit tuning methodology and field guidance | Final sizing for a custom full-weight deployment |

Use this repo as a **catalog baseline and cache methodology reference**. Re-run the same tests on Provisioned/PTU for customer weights.

---

## Detailed Test Data

### 1. AI Companion Multi-Turn Prompt Layout Test

<div align="center">
  <img src="images/companion-multiturn-cache-ttft.png" width="960" alt="AI companion multi-turn prompt cache and TTFT summary" />
</div>

Primary workload: 8 sessions x 8 turns per group. Each row below has **N=64 requests** from one complete repeat.

| Group | Cache Ratio | TTFT avg | TTFT P50 | TTFT P90 | TTFT P95 | TTFT P99 | tok/s avg | tok/s P10 | tok/s P50 | tok/s P90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| No affinity | 99.63% | 0.2585s | 0.1330s | 0.6834s | 1.2434s | 1.4786s | 96.36 | 68.03 | 100.03 | 134.83 |
| `x-session-affinity` | 99.64% | 0.1196s | 0.1210s | 0.1664s | 0.1689s | 0.3515s | 96.48 | 67.15 | 93.39 | 126.32 |
| `prompt_cache_key` | 97.99% | 0.2974s | 0.1535s | 0.6942s | 0.8557s | 1.1058s | 93.32 | 72.29 | 93.39 | 118.62 |
| Affinity + key | 98.63% | 0.3165s | 0.1465s | 0.6520s | 0.6725s | 2.2374s | 88.04 | 56.60 | 92.67 | 119.64 |
| Dynamic prefix anti-pattern | 1.30% | 0.9089s | 0.9690s | 1.0944s | 1.1221s | 2.1601s | 84.02 | 22.73 | 92.67 | 127.66 |
| Shuffled memory anti-pattern | 26.67% | 0.9209s | 0.9995s | 1.0982s | 1.1872s | 1.4014s | 87.57 | 24.42 | 94.12 | 126.32 |

Interpretation:

- Stable prefix + stable session routing is the best measured configuration for companion-style prompts.
- `x-session-affinity` produced the best tail TTFT in this catalog run.
- `prompt_cache_key` worked, but its P95 tail was higher than `x-session-affinity`.
- Dynamic metadata at the front of the prompt destroyed cache reuse.
- Shuffling memory order preserved some shared prefix, but still lost most reusable cache.

### 2. Public Prompt-Diversity Baseline: HF UltraChat

This test uses 64 public first-user prompts from `HuggingFaceH4/ultrachat_200k`. It is not customer traffic replay. It shows the lower cache ratio expected when user prompts are diverse.

| Round | Success | Cache Ratio | TTFT avg | TTFT P50 | TTFT P90 | TTFT P95 | TTFT P99 | tok/s avg | tok/s P10 | tok/s P50 | tok/s P90 | Wall tok/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cold | 64/64 | 14.84% | 1.3866s | 1.0140s | 2.4134s | 3.2813s | 3.8921s | 47.55 | 29.91 | 42.86 | 56.86 | 873.41 |
| Warm | 64/64 | 44.07% | 1.4099s | 1.4170s | 1.5725s | 3.3578s | 3.5334s | 48.11 | 36.61 | 44.72 | 61.00 | 1018.59 |

Interpretation: prompt diversity naturally lowers cache ratio. Warm-up still improved cache ratio and wall throughput.

### 3. 64-Concurrency Smoke Test

This test uses non-streaming response latency, not TTFT. It confirms that a raised PAYGO catalog deployment can handle concurrent smoke traffic.

| Round | Success | Errors | Cache Ratio | P50 Response Latency | P95 Response Latency | Completion TPS | Requests/sec |
|---|---:|---:|---:|---:|---:|---:|---:|
| Round 1 | 64/64 | 0 | 71.53% | 4.7426s | 5.6835s | 616.70 | 9.64 |
| Warm Round 2 | 64/64 | 0 | 89.17% | 3.8579s | 4.5928s | 774.03 | 12.09 |

Interpretation: warm cache improved response latency and throughput, but this comparison can include backend warmup and connection reuse. Use it as a smoke test, not as a production SLA.

### 4. Small Cache Probe Matrix

This single-run probe validates exact-prefix mechanics before larger runs.

| Scenario | Prompt Tokens | Cached Tokens | Cache Ratio | Interpretation |
|---|---:|---:|---:|---|
| No affinity warm | 105 | 0 | 0.00% | First request warms cache |
| No affinity repeat | 105 | 104 | 99.05% | Repeated prefix hits cache |
| Affinity warm | 105 | 95 | 90.48% | Prefix was partly warmed by earlier probes |
| Affinity repeat | 105 | 104 | 99.05% | Stable session key hits cache |
| Prompt cache key warm | 105 | 0 | 0.00% | First request for key warms cache |
| Prompt cache key repeat | 105 | 104 | 99.05% | `prompt_cache_key` also hits cache |
| Same prefix, changed suffix | 107 | 96 | 89.72% | Stable prefix still reuses most cache |
| Changed prefix | 106 | 5 | 4.72% | Prefix change breaks cache |

Interpretation: these are point probes, not confidence intervals. They are useful for validating the mechanism before larger benchmarks.

---

## Test Methodology

### Metrics

| Metric | Meaning | Source |
|---|---|---|
| Cache ratio | `cached_tokens / prompt_tokens` | `usage.prompt_tokens_details.cached_tokens` |
| TTFT | Server time to first token | Fireworks streaming `perf_metrics["server-time-to-first-token"]` |
| Output tok/s | `completion_tokens / generation-duration` | Fireworks streaming `perf_metrics` |
| Response latency | End-to-end non-streaming request latency | Client-side timer in `loadtest_fireworks.py` |

Percentiles use linear interpolation as implemented in the scripts.

### Prompt Shape Used In The Companion Test

The benchmark uses fixed assistant responses so each turn has deterministic history. It measures prompt-cache behavior, not answer quality.

Cache-friendly shape:

```text
System:
  Stable companion persona
  Stable safety/style policy
  Stable user memory in deterministic order
  Static app instructions

History:
  Ordered previous user/assistant turns

Current user message:
  Appended at the end
```

Dynamic-prefix anti-pattern:

```text
System:
  Volatile request metadata: repeat/session/turn/timestamp
  Stable companion persona
  Stable user memory
  Static app instructions
```

Shuffled-memory anti-pattern:

```text
System:
  Stable companion persona
  Same memory facts, but order changes across turns
  Static app instructions
```

### Request Parameters Tested

| Parameter | Role in cache behavior | Official documentation signal |
|---|---|---|
| `x-session-affinity` | Header-level session routing hint | Fireworks recommends stable session routing because cache is replica-local |
| `prompt_cache_key` | Body-level session routing key | Fireworks API says same key routes to same backend and takes priority over `user` |
| `prompt_cache_isolation_key` | Cache namespace partition | Use for isolation; changing it prevents sharing between otherwise identical prompts |
| `user` | End-user identifier and fallback routing hint | Fireworks prompt-cache guide mentions `user`; API docs say `prompt_cache_key` takes priority |
| `temperature`, `top_p`, `max_tokens` | Generation controls | Affect output and cost, not prefix cache matching |

---

## Running On Azure

| Item | Value / Guidance |
|---|---|
| Platform | Azure AI Foundry Fireworks |
| Tested catalog model | `FW-GLM-5.1` |
| Tested deployment shape | `DataZoneStandard` PAYGO catalog deployment |
| Tested capacity | 400k TPM, 400 requests/minute in the test subscription |
| Auth | Microsoft Entra token in the original run; scripts also support API key |
| Custom full-weight model | Requires Provisioned/PTU in the tested path; PAYGO custom full-weight deployment returned a Provisioned-only error |
| Region / availability | Follow Microsoft Learn region availability and quota guidance for Fireworks on Foundry |
| Compliance caveat | Microsoft Learn says Fireworks on Foundry is excluded from EU Data Boundary commitments and FedRAMP is not achieved; customers must assess suitability |

---

## Custom Full-Weight Model Boundary

This repo does not benchmark a customer merged full-weight model. It validates cache mechanics and measurement methods on a catalog deployment.

In the tested Azure AI Foundry Fireworks path, registering a full-weight custom model succeeded, but a `FireworksCustom + DataZoneStandard` deployment attempt returned a Provisioned-only requirement. The practical implication is:

1. Use this repo to validate prompt layout, routing hints, metric collection, and reproducibility.
2. Do not use catalog PAYGO numbers as the final latency/cache claim for custom weights.
3. Re-run the companion test on Provisioned/PTU with customer weights, real session grouping, and the same metrics.

---

## Reproducing

### Prerequisites

- Python 3.10+
- `aiohttp`
- An Azure AI Foundry Fireworks deployment with a Chat Completions-compatible endpoint
- Either Microsoft Entra bearer token or API key

```bash
pip install -r requirements.txt
```

### Environment Variables

```bash
export FIREWORKS_AZURE_ENDPOINT="https://<your-ai-services-account>.cognitiveservices.azure.com/"
export FIREWORKS_DEPLOYMENT="<your-deployment-name>"
export FIREWORKS_BEARER_TOKEN="<entra-access-token>"
export FIREWORKS_API_KEY="<api-key>"  # only if local auth is enabled
```

### Cache Probe

```bash
python scripts/cache_probe.py \
  --endpoint "$FIREWORKS_AZURE_ENDPOINT" \
  --deployment "$FIREWORKS_DEPLOYMENT" \
  --output data/my-cache-probe.jsonl
```

### AI Companion Multi-Turn Benchmark

```bash
python scripts/companion_multiturn_loadtest.py \
  --endpoint "$FIREWORKS_AZURE_ENDPOINT" \
  --deployment "$FIREWORKS_DEPLOYMENT" \
  --sessions 8 \
  --turns 8 \
  --repeats 1 \
  --groups no_affinity x_session_affinity prompt_cache_key best_practice_both dynamic_prefix_antipattern shuffled_memory_antipattern \
  --concurrency 8 \
  --max-tokens 12 \
  --request-timeout 45 \
  --output-dir data/my-companion-run
```

This script writes request JSONL incrementally after each turn, so partial evidence survives if a streaming call stalls or times out.

### Streaming TTFT With Hugging Face Prompts

```bash
python scripts/streaming_ttft_loadtest.py \
  --endpoint "$FIREWORKS_AZURE_ENDPOINT" \
  --deployment "$FIREWORKS_DEPLOYMENT" \
  --prompt-count 64 \
  --concurrency 64 \
  --sessions 16 \
  --max-tokens 96 \
  --output-dir data/my-hf-streaming-run
```

### 64-Concurrency Smoke Test

```bash
python scripts/loadtest_fireworks.py \
  --endpoint "$FIREWORKS_AZURE_ENDPOINT" \
  --deployment "$FIREWORKS_DEPLOYMENT" \
  --concurrency 64 \
  --sessions 16 \
  --max-tokens 64 \
  --output data/my-loadtest.jsonl \
  --summary data/my-loadtest-summary.json
```

Use lower concurrency first if your deployment capacity is small.

---

## Data Files

| File | Description |
|---|---|
| `data/cache_lift_recommendations.json` | Setting-by-setting cache lift calculations used by the Executive Summary table |
| `data/companion_multiturn_summary.json` | AI companion multi-turn cache, TTFT, and anti-pattern comparison |
| `data/hf_ultrachat_streaming_summary.json` | Streaming TTFT and output tokens/sec results from public HF prompts |
| `data/hf_ultrachat_prompt_sample_metadata.json` | HF prompt IDs, hashes, and lengths without duplicating prompt text |
| `data/loadtest_summary.json` | 64-concurrency smoke summary |
| `data/cache_probe_results.json` | Small exact-prefix cache probe matrix |
| `data/custom_paygo_boundary.json` | Sanitized evidence of custom full-weight PAYGO Provisioned-only boundary |

Raw endpoint names, subscription IDs, resource groups, request IDs, and credentials are intentionally excluded.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| HTTP 401 | Wrong token or wrong audience | Use a token for `https://cognitiveservices.azure.com` or use an API key if local auth is enabled |
| HTTP 404 | Wrong endpoint, deployment name, or API path | Verify the deployment in Azure AI Foundry and check the endpoint URL |
| HTTP 429 | Deployment capacity too small for concurrency | Lower `--concurrency`, lower `--max-tokens`, or request higher quota |
| Missing TTFT metrics | `perf_metrics_in_response` not returned or non-streaming path hides body metrics | Use streaming scripts and inspect final chunks |
| Streaming stalls | Network/service long tail | Reduce concurrency, set lower `--request-timeout`, and keep incremental JSONL outputs |
| Cache remains low | Prefix changes, memory order changes, varying isolation key, or session moves across replicas | Compare against the companion anti-pattern groups |

---

## Limitations

- Catalog PAYGO results are not custom full-weight PTU results.
- The primary companion result is one complete repeat; repeat 2 was partial due to intermittent streaming stalls.
- Cache probe values are small point probes, not confidence intervals.
- HF UltraChat prompts are public and diverse, but not customer traffic replay.
- 64-concurrency latency is non-streaming response latency; companion and HF tables report streaming TTFT.
- Warm-round improvements can include prompt cache, replica/GPU warmup, and connection reuse effects.

---

## References

| Topic | Source | Why it matters |
|---|---|---|
| Fireworks prompt caching | https://docs.fireworks.ai/guides/prompt-caching | Exact prefix, static-first prompt structure, session routing, isolation key |
| Fireworks Chat Completions API | https://docs.fireworks.ai/api-reference/post-chatcompletions | `prompt_cache_key`, `prompt_cache_isolation_key`, `perf_metrics_in_response`, reasoning controls |
| Microsoft Learn: Fireworks models on Foundry | https://learn.microsoft.com/en-us/azure/foundry/how-to/fireworks/enable-fireworks-models | Azure deployment modes, region availability, data/privacy caveats |
| Fireworks Microsoft Foundry integration | https://docs.fireworks.ai/ecosystem/integrations/azure-foundry | PayGo, PTU, and custom model positioning |
| Azure AI Foundry Fireworks custom model import | https://learn.microsoft.com/en-us/azure/foundry/how-to/fireworks/import-custom-models | Custom model import and Provisioned deployment path |
