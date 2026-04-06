# Azure OpenAI Priority Processing: Standard vs Priority PAYGO Benchmark

**Author**: Xinyu Wei | **Date**: 2026-04-05 | **Model**: gpt-5.4 (2026-03-05) | **Region**: swedencentral

## Executive Summary

[Priority Processing](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/priority-processing) is a new Azure OpenAI feature (preview) that provides **guaranteed token generation speed** on GlobalStandard/DataZoneStandard deployments at 1.75x standard pricing.

**Key findings** (IQR-denoised, 216 records across 3 independent test runs):

| Output Tokens | N | Std TPS P50±σ | Pri TPS P50±σ | **ΔTPS** | Std E2E | Pri E2E | **ΔE2E** |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| ≤30 | 14 | 51.3±2.2 | 50.2±2.0 | -2% ❌ | 1.4s | 1.3s | -7% |
| 50 | 40 | 39.4±8.4 | 52.4±13.0 | **+33%** | 2.6s | 2.3s | -14% |
| 100 | 28 | 45.2±5.3 | 65.2±8.2 | **+44%** | 3.6s | 2.9s | -20% |
| 200 | 45 | 45.8±5.5 | 60.1±3.8 | **+31%** | 5.8s | 4.5s | -21% |
| 500 | 55 | 44.9±6.8 | 63.3±3.7 | **+41%** | 12.0s | 8.9s | -26% |
| 1000 | 25 | 43.9±1.7 | 62.4±6.2 | **+42%** | 24.3s | 17.2s | **-29%** |

**TTFT** (N=99 per tier, IQR denoised):

| Tier | TTFT P50 | TTFT P95 | Mean±σ |
|---|:---:|:---:|:---:|
| Standard | 1296 ms | 1449 ms | 1300±81 ms |
| **Priority** | **1221 ms** | **1281 ms** | **1224±34 ms** |
| **Δ** | **-75 ms (-5.8%)** | **-168 ms** | **σ halved** |

> Priority Processing improves TPS by **+31~44%** for outputs ≥50 tokens, reduces E2E by **14~29%**, and **halves TTFT variance** (σ: 81→34 ms). No benefit for ≤30 token outputs.

![Priority Processing Benchmark](images/priority_processing_benchmark.png)

---

## 1. What is Priority Processing?

Priority Processing is a pay-as-you-go option that provides **guaranteed token generation speed (TPS)** without requiring PTU commitment.

| Aspect | Standard PAYGO | **Priority PAYGO** | PTU |
|--------|:---:|:---:|:---:|
| TPS guarantee | Best-effort | **99% > 50 TPS** (gpt-5.4) | Guaranteed |
| Pricing | Base rate | **1.75x Base** | Fixed monthly |
| Commitment | None | **None** | Monthly/Annual |
| TTFT improvement | — | **~6% + σ halved** | Yes |
| Long context (>128K) | Normal | Downgraded to Standard | Normal |

**Supported models** (as of 2026-04):

| Model | Latency Target | Regions |
|---|:---:|---|
| gpt-5.4 (2026-03-05) | 99% > 50 TPS | polandcentral, southcentralus, swedencentral |
| gpt-5.2 (2025-12-11) | 99% > 50 TPS | 20+ regions |
| gpt-5.1 (2025-11-13) | 99% > 50 TPS | 20+ regions |
| gpt-4.1 (2025-04-14) | 99% > 80 TPS | 20+ regions |

> Source: [Microsoft Learn — Priority Processing](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/priority-processing)

---

## 2. What Priority Accelerates (and What It Doesn't)

```
E2E = TTFT (prefill) + GenTime (decode)
              ↑                ↑
        ~6% faster       +31~44% faster
        σ halved          (main benefit)
```

Priority's primary benefit is **faster token generation (decode phase)**, not faster first-token (prefill phase). The E2E improvement scales with output length because GenTime's share of E2E increases.

| Component | Standard | Priority | Impact |
|---|:---:|:---:|:---:|
| TTFT (prefill) | 1296 ms | 1221 ms | -6%, σ halved |
| GenTime (decode) | Varies | **+31~44% faster** | Main benefit |
| E2E (total) | Varies | -14~29% | Scales with output length |

---

## 3. When to Use Priority Processing

| Scenario | Output Length | Priority ROI | Recommendation |
|---|:---:|:---:|---|
| Content generation (email, reports, code) | 500-2000 tok | ✅✅✅ | **Strong** — TPS +41%, E2E saves 3-7s |
| Streaming chat (user watches output) | 100-500 tok | ✅✅ | **Good** — faster perceived speed |
| High-concurrency bursts | Any >50 tok | ✅✅ | **Good** — TTFT P95 reduced 52% under load |
| RAG answer generation | 100-300 tok | ✅ | **Marginal** — E2E saves ~500ms |
| Intent classification / routing | <30 tok | ❌ | **Not recommended** — zero benefit, 75% price premium |

### Cost-Benefit Analysis

Priority costs 1.75x Standard. Is the speedup worth it?

| Output | E2E Saved | Cost Premium | Worth it? |
|:---:|:---:|:---:|:---:|
| 50 tok | 0.3s | +75% | Only if latency-critical |
| 200 tok | 1.3s | +75% | Yes for user-facing |
| 500 tok | 3.1s | +75% | **Yes** |
| 1000 tok | 7.1s | +75% | **Strongly yes** |

---

## 4. Concurrent Load Performance

Under 10-concurrent load (25 requests, output=200):

| Metric | Standard | Priority | Delta |
|---|:---:|:---:|:---:|
| TTFT P50 | 1452 ms | 1249 ms | -14% |
| **TTFT P95** | 3296 ms | **1590 ms** | **-52%** |
| E2E P50 | 5365 ms | 4227 ms | -21% |
| TPS P50 | 54.6 | 68.9 | +26% |
| Throughput | 1.6 req/s | 1.9 req/s | +19% |

> Priority's biggest advantage under load: **tail latency control** — TTFT P95 drops 52%. Standard suffers queue spikes; Priority maintains consistent latency.

---

## 5. Hybrid Architecture: PTU + Priority + Standard

```
Traffic Router (APIM)
       │
  ┌────┴────┬──────────┐
  ▼         ▼          ▼
PTU      Priority    Standard
(base)   (overflow)  (background)
──────   ─────────   ──────────
Steady   Peak/burst  Batch/async
Lowest   TPS SLA     Lowest cost
latency  No commit   
```

| Traffic Type | Route To | Reason |
|---|---|---|
| Steady baseline | PTU | Lowest latency + fixed cost |
| Peak overflow | **Priority PAYGO** | TPS guaranteed + no commitment |
| Background tasks | Standard PAYGO | Lowest cost |

---

## 6. Limitations

- **Region availability**: gpt-5.4 Priority only in 3 regions (polandcentral, southcentralus, swedencentral)
- **Ramp rate limit**: >50% TPM increase in <15 minutes may trigger downgrade
- **Long context**: Prompts >128K tokens automatically downgraded
- **Mini/Nano models**: Not supported (only flagship models: gpt-5.4, gpt-5.2, gpt-5.1, gpt-4.1)
- **`service_tier` response**: Not returned in `2025-04-01-preview` API version

---

## 7. Reproducing the Benchmark

### Prerequisites

- Python 3.10+
- Azure OpenAI deployment of gpt-5.4 (GlobalStandard) in a supported region
- `httpx` package

### Run

```bash
pip install httpx
python scripts/benchmark_priority_processing.py \
  --endpoint https://YOUR_ENDPOINT.openai.azure.com \
  --api-key YOUR_API_KEY \
  --deployment YOUR_DEPLOYMENT_NAME \
  --iterations 8 --warmup 2
```

### Data Files

| File | Description |
|------|-------------|
| `data/benchmark_priority_multilength.json` | 6 output lengths × 8 iter × 2 tiers (96 records) |
| `data/benchmark_priority_full_v3.json` | 6 scenarios × 5 iter × 2 tiers (60 records, short+long prompt) |

---

## 8. Methodology

- **Model**: gpt-5.4 (2026-03-05), GlobalStandard deployment
- **Region**: swedencentral (Priority Processing supported)
- **Parameters**: `reasoning_effort=none`, `stream=True`, `service_tier=default|priority`
- **Execution**: Standard/Priority **interleaved** per query (eliminate time bias)
- **Denoising**: IQR 1.5x outlier removal on TPS and E2E
- **Metrics**: TTFT, TPS (content chunks / generation time), E2E
- **Test environment**: Windows VM (East Asia) → swedencentral deployment
