# MAI-Image-2 vs MAI-Image-2e vs GPT-Image-1.5: Azure AI Image Generation Benchmark

## Executive Summary

This benchmark compares three Azure image generation models across 5 configurations (11 prompts × 2 rounds = 110 API calls) with fairness controls (warmup, order reversal, symmetric wait). All models are in preview as of April 2026.

**Model Profiles:**

| | MAI-Image-2 | MAI-Image-2e | GPT-Image-1.5 |
|---|:---:|:---:|:---:|
| **Provider** | Microsoft AI (first-party) | Microsoft AI (first-party) | OpenAI via Azure |
| **API** | `/mai/v1/` (dedicated) | `/mai/v1/` (dedicated) | `/openai/deployments/` (standard) |
| **Quality control** | Single fixed tier | Single fixed tier | 3 tiers (low/med/high) |
| **Avg latency** | 21.1s | 17.4s | 13.1s (low) / 21.3s (med) / 44.0s (high) |
| **Output pricing** | USD 33/1M tokens | **USD 19.50/1M tokens** | USD 32/1M tokens |
| **Image editing** | ❌ | ❌ | ✅ |
| **Flexible resolution** | ✅ (768–1366px) | ✅ (768–1366px) | ❌ (3 fixed sizes) |
| **Max prompt** | 32K tokens | 32K tokens | 4K tokens |
| **Status** | Preview | Preview | Preview |

**Key takeaway:** GPT-Image-1.5 at `quality=low` is the fastest (13.1s) with competitive image quality. MAI-Image-2e offers the lowest output token price (USD 19.50/1M) and Microsoft first-party independence from OpenAI. MAI-Image-2 provides the smoothest photorealistic output but at the highest cost (USD 33/1M) with no speed advantage over GPT-medium. Choose based on your priority: speed → GPT-low, cost → MAI-2e, editing → GPT, first-party → MAI.

> **Sources:** MAI API — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python) | MAI-Image-2 pricing — [Tech Community 2026-04-02](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-mai-transcribe-1-mai-voice-1-and-mai-image-2-in-microsoft-foundry/4507787) | MAI-Image-2e pricing — [Tech Community 2026-04-14](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-mai-image-2-efficient-faster-more-efficient-image-generation/4510918) | GPT-Image-1.5 pricing — [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)

---

A comprehensive latency benchmark comparing **5 configurations** of Azure image generation models: **MAI-Image-2**, **MAI-Image-2e** (Efficient), and **GPT-Image-1.5** at three quality levels (low / medium / high), using identical prompts and resolution.

## Key Results

| Model | Quality | Avg Latency | Avg File Size | Pass Rate |
|-------|:-------:|:-----------:|:-------------:|:---------:|
| GPT-Image-1.5 | low | **13.1s** | 1,772 KB | 22/22 |
| MAI-Image-2e | N/A (single tier) | **17.4s** | 1,631 KB | 22/22 |
| MAI-Image-2 | N/A (single tier) | **21.1s** | 1,575 KB | 22/22 |
| GPT-Image-1.5 | medium | 21.3s | 1,936 KB | 22/22 |
| GPT-Image-1.5 | high | 44.0s | 2,075 KB | 22/22 |

> - GPT-Image-1.5 (low) is the fastest at 13.1s — 33% faster than MAI-Image-2e.
> - MAI-Image-2 ≈ GPT-Image-1.5 (medium) in latency (~21s).
> - MAI models have **no quality parameter** — they output a single, fixed quality tier.

## Fair Comparison Design

### Alignment Dimensions

| Dimension | All 5 Groups | Status |
|-----------|:------------:|:------:|
| Prompt | Same 11 Surreal-style prompts | ✅ Aligned |
| Resolution | 1024×1024 | ✅ Aligned |
| Output Format | PNG (b64_json) | ✅ Aligned |
| Network | Same machine (East US) | ✅ Aligned |
| Test Date | 2026-04-19 | ✅ Aligned |
| Warmup | 1 throwaway request per group | ✅ Aligned |
| Inter-call Wait | 5s between every API call (symmetric) | ✅ Aligned |
| **Quality** | MAI: not applicable / GPT: low, medium, high | 🔀 **Difference** |
| **Model** | MAI-Image-2 / MAI-Image-2e / GPT-Image-1.5 | 🔀 Variable |

### Why Quality Is a Difference, Not an Alignment

MAI-Image-2 and MAI-Image-2e accept only 4 API parameters: `model`, `prompt`, `width`, `height`. **There is no `quality` parameter** ([source](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python)). GPT-Image-1.5 supports `quality` with values `low`, `medium`, `high`, which controls the number of output image tokens (more tokens = more detail = slower). To fairly assess where MAI's fixed quality falls relative to GPT's tiers, we test GPT at all three levels.

### Fairness Controls

- **Warmup**: 1 throwaway request per model/quality group before timing starts
- **Order reversal**: Round 1 runs groups A→E, Round 2 runs E→A
- **Symmetric wait**: 5s between every API call regardless of model
- **2 rounds**: Each data point is the average of 2 measurements

## Per-Prompt Latency Comparison

| # | Prompt | MAI-2 | MAI-2e | GPT low | GPT med | GPT high |
|:-:|:-------|:-----:|:------:|:-------:|:-------:|:--------:|
| 1 | Chrome kimono metallic maiden | 20.5s | 17.8s | 13.8s | 19.9s | 45.7s |
| 2 | Portal into mythical forest | 20.9s | 17.3s | 13.3s | 21.0s | 43.8s |
| 3 | Tiny astronaut hatching on moon | 19.7s | 17.3s | 12.6s | 20.3s | 40.4s |
| 4 | LOTR tiny red dragon macro | 21.2s | 17.2s | 11.7s | 20.8s | 41.4s |
| 5 | Fluffy creature fantasy | 20.8s | 16.5s | 12.3s | 21.6s | 44.4s |
| 6 | Hidden jungle cenote | 22.0s | 19.2s | 13.2s | 22.7s | 42.2s |
| 7 | Tech-savvy girl holographic UI | 20.7s | 17.4s | 12.8s | 21.4s | 46.1s |
| 8 | Universe fractal worlds | 23.2s | 19.4s | 15.2s | 23.8s | 47.1s |
| 9 | Fractal mythical creature | 23.1s | 17.0s | 13.2s | 20.4s | 44.6s |
| 10 | Angry cat playing drums | 20.5s | 15.9s | 12.8s | 21.0s | 44.5s |
| 11 | Monkey playing music | 19.1s | 16.6s | 13.1s | 21.7s | 44.0s |
| **AVG** | | **21.1s** | **17.4s** | **13.1s** | **21.3s** | **44.0s** |

> Each cell is the average of 2 rounds. Round 1 order: A→E. Round 2 order: E→A (reversed).

## Side-by-Side Image Comparison

### Test 1: Chrome Kimono Metallic Maiden

| MAI-Image-2 (20.5s) | MAI-Image-2e (17.8s) | GPT-1.5 low (13.8s) | GPT-1.5 med (19.9s) | GPT-1.5 high (45.7s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/01_test.png) | ![](images/mai-image-2e/01_test.png) | ![](images/gpt-image-1.5-low/01_test.png) | ![](images/gpt-image-1.5-medium/01_test.png) | ![](images/gpt-image-1.5-high/01_test.png) |

### Test 2: Portal into Mythical Forest

| MAI-Image-2 (20.9s) | MAI-Image-2e (17.3s) | GPT-1.5 low (13.3s) | GPT-1.5 med (21.0s) | GPT-1.5 high (43.8s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/02_test.png) | ![](images/mai-image-2e/02_test.png) | ![](images/gpt-image-1.5-low/02_test.png) | ![](images/gpt-image-1.5-medium/02_test.png) | ![](images/gpt-image-1.5-high/02_test.png) |

### Test 3: Tiny Astronaut on Moon

| MAI-Image-2 (19.7s) | MAI-Image-2e (17.3s) | GPT-1.5 low (12.6s) | GPT-1.5 med (20.3s) | GPT-1.5 high (40.4s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/03_test.png) | ![](images/mai-image-2e/03_test.png) | ![](images/gpt-image-1.5-low/03_test.png) | ![](images/gpt-image-1.5-medium/03_test.png) | ![](images/gpt-image-1.5-high/03_test.png) |

### Test 4: LOTR Tiny Red Dragon

| MAI-Image-2 (21.2s) | MAI-Image-2e (17.2s) | GPT-1.5 low (11.7s) | GPT-1.5 med (20.8s) | GPT-1.5 high (41.4s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/04_test.png) | ![](images/mai-image-2e/04_test.png) | ![](images/gpt-image-1.5-low/04_test.png) | ![](images/gpt-image-1.5-medium/04_test.png) | ![](images/gpt-image-1.5-high/04_test.png) |

### Test 5: Fluffy Fantasy Creature

| MAI-Image-2 (20.8s) | MAI-Image-2e (16.5s) | GPT-1.5 low (12.3s) | GPT-1.5 med (21.6s) | GPT-1.5 high (44.4s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/05_test.png) | ![](images/mai-image-2e/05_test.png) | ![](images/gpt-image-1.5-low/05_test.png) | ![](images/gpt-image-1.5-medium/05_test.png) | ![](images/gpt-image-1.5-high/05_test.png) |

### Test 6: Hidden Jungle Cenote

| MAI-Image-2 (22.0s) | MAI-Image-2e (19.2s) | GPT-1.5 low (13.2s) | GPT-1.5 med (22.7s) | GPT-1.5 high (42.2s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/06_test.png) | ![](images/mai-image-2e/06_test.png) | ![](images/gpt-image-1.5-low/06_test.png) | ![](images/gpt-image-1.5-medium/06_test.png) | ![](images/gpt-image-1.5-high/06_test.png) |

### Test 7: Tech-Savvy Girl with Holographic UI

| MAI-Image-2 (20.7s) | MAI-Image-2e (17.4s) | GPT-1.5 low (12.8s) | GPT-1.5 med (21.4s) | GPT-1.5 high (46.1s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/07_test.png) | ![](images/mai-image-2e/07_test.png) | ![](images/gpt-image-1.5-low/07_test.png) | ![](images/gpt-image-1.5-medium/07_test.png) | ![](images/gpt-image-1.5-high/07_test.png) |

### Test 8: Universe Fractal Worlds

| MAI-Image-2 (23.2s) | MAI-Image-2e (19.4s) | GPT-1.5 low (15.2s) | GPT-1.5 med (23.8s) | GPT-1.5 high (47.1s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/08_test.png) | ![](images/mai-image-2e/08_test.png) | ![](images/gpt-image-1.5-low/08_test.png) | ![](images/gpt-image-1.5-medium/08_test.png) | ![](images/gpt-image-1.5-high/08_test.png) |

### Test 9: Fractal Mythical Creature

| MAI-Image-2 (23.1s) | MAI-Image-2e (17.0s) | GPT-1.5 low (13.2s) | GPT-1.5 med (20.4s) | GPT-1.5 high (44.6s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/09_test.png) | ![](images/mai-image-2e/09_test.png) | ![](images/gpt-image-1.5-low/09_test.png) | ![](images/gpt-image-1.5-medium/09_test.png) | ![](images/gpt-image-1.5-high/09_test.png) |

### Test 10: Angry Cat Playing Drums

| MAI-Image-2 (20.5s) | MAI-Image-2e (15.9s) | GPT-1.5 low (12.8s) | GPT-1.5 med (21.0s) | GPT-1.5 high (44.5s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/10_test.png) | ![](images/mai-image-2e/10_test.png) | ![](images/gpt-image-1.5-low/10_test.png) | ![](images/gpt-image-1.5-medium/10_test.png) | ![](images/gpt-image-1.5-high/10_test.png) |

### Test 11: Monkey Playing Music

| MAI-Image-2 (19.1s) | MAI-Image-2e (16.6s) | GPT-1.5 low (13.1s) | GPT-1.5 med (21.7s) | GPT-1.5 high (44.0s) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/11_test.png) | ![](images/mai-image-2e/11_test.png) | ![](images/gpt-image-1.5-low/11_test.png) | ![](images/gpt-image-1.5-medium/11_test.png) | ![](images/gpt-image-1.5-high/11_test.png) |

## API Comparison

### Request Parameters

| Feature | MAI-Image-2 / MAI-Image-2e | GPT-Image-1.5 |
|---------|:---------------------------:|:-------------:|
| API Path | `/mai/v1/images/generations` | `/openai/deployments/{name}/images/generations` |
| Auth | Entra ID + API Key | API Key + Entra ID |
| Parameters | `model`, `prompt`, `width`, `height` | `prompt`, `n`, `size`, `quality` |
| Quality control | **Not available** (single fixed tier) | `low` / `medium` / `high` |
| Resolution | Flexible: W≥768, H≥768, W×H≤1,048,576 | Fixed: 1024×1024 / 1792×1024 / 1024×1792 |
| Output format | PNG only | PNG / URL |
| Output count | 1 (fixed) | 1–10 |
| Max prompt | 32,000 tokens | 4,000 tokens |

> **Source**: MAI parameters from [Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python). GPT parameters from [Azure OpenAI docs](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e).

### Capability Comparison

| Capability | MAI-Image-2 | MAI-Image-2e | GPT-Image-1.5 |
|---|:---:|:---:|:---:|
| Text-to-image | ✅ | ✅ | ✅ |
| Image editing | ❌ | ❌ | ✅ |
| Inpainting | ❌ | ❌ | ✅ |
| Flexible aspect ratio | ✅ | ✅ | ❌ (fixed sizes) |
| Quality tiers | ❌ (single tier) | ❌ (single tier) | ✅ (low/med/high) |

### Pricing

| Model | Text Input | Image Output | Source |
|-------|:----------:|:------------:|:------:|
| MAI-Image-2 | USD 5 / 1M tokens | USD 33 / 1M tokens | [Tech Community 2026-04-02](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-mai-transcribe-1-mai-voice-1-and-mai-image-2-in-microsoft-foundry/4507787) |
| MAI-Image-2e | USD 5 / 1M tokens | USD 19.50 / 1M tokens | [Tech Community 2026-04-14](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-mai-image-2-efficient-faster-more-efficient-image-generation/4510918) |
| GPT-Image-1.5 | USD 5 / 1M tokens | USD 32 / 1M tokens | [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/) |

> GPT-Image-1.5 charges per token — `quality=low` generates fewer tokens (cheaper per image), `quality=high` generates more tokens (more expensive per image). MAI models have a single fixed tier.

### Rate Limits

| Model | Tier 1 RPM | Tier 6 RPM |
|-------|:----------:|:----------:|
| MAI-Image-2 | 9 | 90 |
| MAI-Image-2e | 18 | 180 |

> Source: [Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python)

## Choosing the Right Model

| Use Case | Recommended | Why |
|----------|:-----------:|-----|
| Fastest generation | GPT-Image-1.5 (low) | 13.1s avg latency |
| Speed + Microsoft first-party | MAI-Image-2e | 17.4s, no OpenAI dependency |
| Maximum detail | GPT-Image-1.5 (high) | Most output tokens, but 44s |
| Image editing / inpainting | GPT-Image-1.5 | MAI has no editing API |
| Flexible aspect ratios | MAI-Image-2 / 2e | Any W×H within pixel budget |
| Long prompts (>4K chars) | MAI-Image-2 / 2e | 32K token prompt support |
| Lowest cost at scale | MAI-Image-2e | USD 19.50/1M output tokens |

## How to Reproduce

### Prerequisites

- Azure subscription with Azure AI Services resource
- Deployments: MAI-Image-2, MAI-Image-2e (AI Services), gpt-image-1.5 (Azure OpenAI)
- Python 3.x with `requests`
- Azure CLI (`az`) logged in

### Run

```bash
git clone https://github.com/david-share/Multimodal-Models.git
cd Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark

# Edit scripts/benchmark_5way.py — set your endpoints and credentials
pip install requests
python scripts/benchmark_5way.py
```

## Repository Structure

```
.
├── README.md
├── README-CN.md
├── prompts.csv                          # 11 Surreal-style test prompts
├── data/
│   └── 5way_benchmark_results.json      # Raw benchmark data
├── scripts/
│   └── benchmark_5way.py                # 5-way benchmark script
└── images/
    ├── mai-image-2/                     # 11 images
    ├── mai-image-2e/                    # 11 images
    ├── gpt-image-1.5-low/              # 11 images
    ├── gpt-image-1.5-medium/           # 11 images
    └── gpt-image-1.5-high/             # 11 images
```