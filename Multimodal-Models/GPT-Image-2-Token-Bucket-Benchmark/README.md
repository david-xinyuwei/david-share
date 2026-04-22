# GPT-Image-2 Benchmark: Token Usage, Latency, and Quality Analysis on Azure OpenAI

This repository investigates the **token size bucket** mechanism in OpenAI's GPT-Image-2 model, deployed via Azure OpenAI Service. We provide hands-on benchmark data answering the key question: **How do `quality` and `size` parameters affect output token consumption and latency?**

## Executive Summary

GPT-Image-2 (`v2026-04-21`) uses a **deterministic token allocation** based on two factors: `quality` and `size`. Output tokens are **completely independent of prompt content** — the same quality+size combination always produces the exact same token count.

### Output Token Matrix (3 sizes × 3 qualities = 9 combinations)

| Size ↓ \ Quality → | low | medium | high |
|:-------------------|:---:|:------:|:----:|
| **1024×1024** (square) | 208 | 805 | 3,171 |
| **1024×1536** (portrait) | 365 | 1,415 | 5,574 |
| **1536×1024** (landscape) | 358 | 1,401 | 5,546 |

### Latency Matrix (seconds)

| Size ↓ \ Quality → | low | medium | high |
|:-------------------|:---:|:------:|:----:|
| **1024×1024** | 19.6 | 59.7 | 187.9 |
| **1024×1536** | 23.8 | 49.9 | 128.0 |
| **1536×1024** | 27.3 | 46.9 | 128.9 |

> **Test conditions**: gpt-image-2 `v2026-04-21`, Azure OpenAI `api-version=2025-04-01-preview`, GlobalStandard deployment (capacity=9), East US 2 region. Prompt: "A golden retriever puppy in a sunlit meadow" (16 input tokens). Each combination tested once. Latency measured end-to-end from the client (WSL on Windows, East US region).

**Key findings**:

1. **Output tokens = f(size, quality) only** — prompt content has zero effect. Verified with 4 different prompts (3–20 words) at 1024×1024 low: all returned exactly 208 tokens.
2. **Portrait/Landscape tokens are ~1.75× square** — matching the 1.5× pixel ratio (1,572,864 vs 1,048,576 pixels).
3. **Portrait ≈ Landscape** — 1024×1536 and 1536×1024 produce nearly identical tokens (365 vs 358, 1415 vs 1401, 5574 vs 5546), with slight directional variance.
4. **Latency is determined by quality and size**, not by prompt content — high quality takes 2–10× longer than low. Size also affects latency (portrait/landscape may differ from square by 10–30%).

## Background

### What is the "Token Size Bucket"?

GPT-Image-2 includes an **intelligent routing layer** that automatically selects the optimal generation configuration. It operates in two modes:

| Mode | How it works | Tiers |
|:-----|:------------|:------|
| **Mode 1** — Legacy size selection | Selects from 3 legacy size tiers; suitable for teams migrating from legacy APIs without changing existing code | `smimage`, `image`, `xlimage` |
| **Mode 2** — Token tier selection | Selects from 6 token tiers to optimize output quality and efficiency for a given request | 16, 24, 36, 48, 64, 96 |

> Sources: [TC Blog — Introducing GPT-Image-2 in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openais-gpt-image-2-in-microsoft-foundry/4514417) · [Azure Cloud Tech WeChat, April 22, 2026](https://mp.weixin.qq.com/s/YeAMajFSgdu5BN_PRR_RKw)

**This is NOT a user-configurable parameter.** There is no `token_bucket` or `output_token_count` API parameter. Users influence token allocation through:

1. **`quality` parameter** (low / medium / high) — primary control
2. **`size` parameter** (1024x1024, 1024x1536, 1536x1024) — resolution control
3. **Prompt complexity** — the system may adjust allocation based on prompt analysis

### GPT-Image-2 New Capabilities

GPT-Image-2 introduces several significant improvements over GPT-Image-1.x:

| Capability | Details |
|:-----------|:--------|
| **Real-world intelligence** | Knowledge cutoff: December 2025. The model can search the web, review its own outputs, and generate multiple images from a single prompt |
| **Multilingual text rendering** | Enhanced support for Japanese, Korean, Chinese, Hindi, and Bengali — can render localized text directly in generated images |
| **4K resolution support** | Supports custom sizes up to 4K, enabling rich, detailed, photorealistic output at production quality |
| **Smart routing layer** | Two-mode routing (Mode 1 + Mode 2) automatically selects the optimal generation configuration |
| **Image editing** | Built-in `/images/edits` endpoint for incremental modifications to existing images |

> Source: [OpenAI GPT-image-2 正式上线 Microsoft Foundry — Azure Cloud Tech WeChat, April 22, 2026](https://mp.weixin.qq.com/s/YeAMajFSgdu5BN_PRR_RKw)

### Model Information

| Property | Value | Source |
|:---------|:------|:-------|
| Model | gpt-image-2 | [Azure Model Catalog](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure) |
| Version | 2026-04-21 | `az cognitiveservices account list-models` |
| Status | Generally Available | Model catalog |
| Format | OpenAI | Azure deployment |
| Deprecation | 2027-04-21 | Model catalog |
| API Capabilities | imageGenerations, imageEdits, convo2im | Model capabilities |

### API Response Structure

GPT-Image-2 returns a richer response structure compared to GPT-Image-1.5:

```json
{
  "created": 1776825308,
  "background": "opaque",
  "data": [{ "b64_json": "<base64 image data>" }],
  "output_format": "png",
  "quality": "low",
  "size": "1024x1024",
  "usage": {
    "input_tokens": 9,
    "input_tokens_details": {
      "image_tokens": 0,
      "text_tokens": 9
    },
    "output_tokens": 208,
    "total_tokens": 217
  }
}
```

New fields compared to GPT-Image-1.5:
- `background`: "opaque" (or "transparent" if requested)
- `output_format`: "png" / "jpeg"
- `usage.input_tokens_details`: Breakdown of text vs image input tokens
- Full `usage` object with `output_tokens` (GPT-Image-1.5 used `num_output_tokens` in `data[0]`)

## Methodology

### Test Design

- **Model**: gpt-image-2 `v2026-04-21` on Azure OpenAI (East US 2)
- **API Version**: `2025-04-01-preview`
- **Deployment**: GlobalStandard, capacity=9
- **Size**: 1024x1024 (held constant)
- **Quality levels**: low, medium, high
- **Prompts**:
  1. Simple: *"A simple red circle on white background"* (minimal complexity)
  2. Complex: *"A photorealistic golden retriever puppy sitting in a sunlit meadow with wildflowers, shallow depth of field, professional photography"* (high complexity)

### Variable Control

| Variable | Status | Value |
|:---------|:-------|:------|
| Model | Fixed | gpt-image-2 |
| Size | Fixed | 1024x1024 |
| n | Fixed | 1 |
| Quality | **Variable** | low / medium / high |
| Prompt | **Variable** | Simple / Complex |

## Results

### Token Usage by Quality Level

| Prompt | Quality | Input Tokens | Output Tokens | Total Tokens |
|:-------|:--------|:------------|:-------------|:-------------|
| Simple ("red dot") | low | 9 | **208** | 217 |
| Simple ("red dot") | medium | 9 | **805** | 814 |
| Simple ("red dot") | high | 9 | **3,171** | 3,180 |
| Complex ("golden retriever") | low | 32 | **208** | 240 |
| Complex ("golden retriever") | medium | 32 | **805** | 837 |
| Complex ("golden retriever") | high | 32 | **3,171** | 3,203 |

**Key observations**:

1. **Output tokens are determined solely by `quality`**, not by prompt complexity. Both simple and complex prompts produce identical output tokens at each quality level.
2. **Input tokens scale with prompt length** — 9 tokens for a 5-word prompt vs 32 tokens for a 20-word prompt.
3. **Token ratios**: low : medium : high = 1 : 3.87 : 15.24

### Generated Images — Visual Comparison

#### Prompt: "A golden retriever puppy in a sunlit meadow" (same prompt across all 9 combinations)

**1024×1024 (Square)**

| Low (208 tokens, 19.6s) | Medium (805 tokens, 59.7s) | High (3,171 tokens, 187.9s) |
|:---:|:---:|:---:|
| ![](images/matrix/1024x1024_low.png) | ![](images/matrix/1024x1024_medium.png) | ![](images/matrix/1024x1024_high.png) |

**1024×1536 (Portrait)**

| Low (365 tokens, 23.8s) | Medium (1,415 tokens, 49.9s) | High (5,574 tokens, 128.0s) |
|:---:|:---:|:---:|
| ![](images/matrix/1024x1536_low.png) | ![](images/matrix/1024x1536_medium.png) | ![](images/matrix/1024x1536_high.png) |

**1536×1024 (Landscape)**

| Low (358 tokens, 27.3s) | Medium (1,401 tokens, 46.9s) | High (5,546 tokens, 128.9s) |
|:---:|:---:|:---:|
| ![](images/matrix/1536x1024_low.png) | ![](images/matrix/1536x1024_medium.png) | ![](images/matrix/1536x1024_high.png) |

#### Earlier tests — different prompts at 1024×1024

**11 diverse prompts, all at medium quality, 1024×1024** — verifying output tokens are prompt-independent:

| # | Prompt | Input Tokens | Output Tokens | Latency (s) |
|:--|:-------|:------------|:-------------|:-----------|
| 01 | Chrome kimono maiden, metallic flowers, cinematic lighting | 17 | **805** | 61.3 |
| 02 | A portal into a mythical forest on a bedroom wall | 20 | **805** | 62.0 |
| 03 | A tiny astronaut hatching from an egg on the moon | 17 | **805** | 63.8 |
| 04 | Cute fluffy creature fantasy, dreamlike, surrealism | 21 | **805** | 60.3 |
| 05 | A hidden cenote in a lush jungle, turquoise waters | 18 | **805** | 64.0 |
| 06 | Girl with silver pixie-cut hair, holographic interface | 20 | **805** | 66.0 |
| 07 | Universe, LSD, Fractal Worlds, Giant Eyes | 16 | **805** | 71.0 |
| 08 | Close up render of a mythical creature, spiraling fractals | 19 | **805** | 59.7 |
| 09 | An angry cat playing drums | 11 | **805** | 62.3 |
| 10 | A monkey playing music in a jazz club | 14 | **805** | 64.5 |
| 11 | Watercolor painting of Venice canals at sunset | 17 | **805** | 64.2 |

> **11/11 returned exactly 805 output tokens.** Input tokens ranged from 11 to 21, latency varied 59.7–71.0s (σ=3.1s). This confirms output tokens are **deterministic and prompt-independent**.

| | | |
|:---:|:---:|:---:|
| ![01](images/diverse_prompts/01_medium.png) | ![02](images/diverse_prompts/02_medium.png) | ![03](images/diverse_prompts/03_medium.png) |
| *01: Chrome kimono* | *02: Mythical forest portal* | *03: Astronaut egg on moon* |
| ![04](images/diverse_prompts/04_medium.png) | ![05](images/diverse_prompts/05_medium.png) | ![06](images/diverse_prompts/06_medium.png) |
| *04: Fluffy creature* | *05: Hidden cenote* | *06: Silver pixie-cut girl* |
| ![07](images/diverse_prompts/07_medium.png) | ![08](images/diverse_prompts/08_medium.png) | ![09](images/diverse_prompts/09_medium.png) |
| *07: Fractal universe* | *08: Fractal creature* | *09: Angry cat drums* |
| ![10](images/diverse_prompts/10_medium.png) | ![11](images/diverse_prompts/11_medium.png) | |
| *10: Jazz monkey* | *11: Venice watercolor* | |

#### Additional verification — simple prompts at 1024×1024

Prompt: "A simple red circle on white background"

| Low (208 tokens) | Medium (805 tokens) | High (3,171 tokens) |
|:---:|:---:|:---:|
| ![low](images/red_dot/red_dot_low.png) | ![medium](images/red_dot/red_dot_medium.png) | ![high](images/red_dot/red_dot_high.png) |

Prompt 2: "A photorealistic golden retriever puppy sitting in a sunlit meadow with wildflowers..."

| Low (208 tokens) | Medium (805 tokens) | High (3,171 tokens) |
|:---:|:---:|:---:|
| ![low](images/dog/dog_low.png) | ![medium](images/dog/dog_medium.png) | ![high](images/dog/dog_high.png) |

> All three 1024×1024 low results above returned exactly 208 output tokens — confirming that **prompt content does not affect token count**.

## Conclusions

Based on 26 API calls across 3 sizes × 3 qualities + 11 diverse prompts:

### 1. Output tokens are a deterministic function of (size, quality) only

Output tokens are **not influenced by prompt content**. We tested 11 completely different prompts (from "an angry cat playing drums" to complex cinematic photography descriptions) at medium + 1024×1024 — all 11 returned exactly 805 output tokens with zero variance. The mapping is a fixed lookup table:

| Size ↓ \ Quality → | low | medium | high |
|:-------------------|:---:|:------:|:----:|
| **1024×1024** | 208 | 805 | 3,171 |
| **1024×1536** | 365 | 1,415 | 5,574 |
| **1536×1024** | 358 | 1,401 | 5,546 |

### 2. Latency is determined by quality and size, with minor prompt influence

We tested extreme prompt lengths at medium + 1024×1024:

| Prompt | Chars | Input Tokens | Latency |
|:-------|:------|:------------|:--------|
| "cat" (shortest) | 3 | 7 | 60.6s |
| 11 diverse prompts | 20–60 | 11–21 | 59.7–71.0s |
| 800+ char Japanese temple scene (longest) | 959 | 170 | 67.1s |

Input tokens varied **24×** (7 vs 170), but latency only differed by **~10%** (60.6s vs 67.1s). Prompt length has a minor effect on latency, but `quality` and `size` are the dominant factors (low ~20s vs medium ~60s vs high ~130–188s).

| "cat" (3 chars, 7 input tokens, 60.6s) | Japanese temple scene (959 chars, 170 input tokens, 67.1s) |
|:---:|:---:|
| ![cat](images/extreme_length/cat_short_medium.png) | ![temple](images/extreme_length/temple_long_medium.png) |

> Both images produced exactly **805 output tokens** despite 24× difference in prompt length.

### 3. The TC Blog's "token size bucket" is not prompt-driven

The [TC Blog](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openais-gpt-image-2-in-microsoft-foundry/4514417) describes Mode 2 as the routing layer selecting from six token buckets based on prompt analysis. Our testing shows that **in practice, the bucket selection is fully determined by the `quality` and `size` parameters** — prompt complexity plays no role. Users do not need to worry about bucket selection; they only need the lookup table above.

### 4. Image Edit benchmark (time, cost, and rendered outputs)

We tested the edit API at 1024x1024 with the same input image and prompt:

- Input image: `images/matrix/1024x1024_medium.png`
- Prompt: `Add cool sunglasses to the dog`
- Endpoint: `/images/edits`
- API version: `2025-04-01-preview`

| Quality | Input Tokens | Output Tokens | Total Tokens | Latency | Estimated Cost / image (USD) |
|:--------|:------------:|:-------------:|:------------:|:-------:|:-----------------------------:|
| low | 1,037 | 208 | 1,245 | 55.3s | 0.0114 |
| medium | 1,037 | 805 | 1,842 | 92.5s | 0.0293 |
| high | 1,037 | 3,171 | 4,208 | 239.7s | 0.1003 |

> Cost formula (estimate): `input_tokens * 5/1M + output_tokens * 30/1M` (source: [OpenAI API Pricing](https://openai.com/api/pricing/)). Azure official GPT-Image-2 pricing may differ when published.

| low (55.3s) | medium (92.5s) | high (239.7s) |
|:---:|:---:|:---:|
| ![edit low](images/edit_test/dog_sunglasses_low.png) | ![edit medium](images/edit_test/dog_sunglasses_medium.png) | ![edit high](images/edit_test/dog_sunglasses_high.png) |

Key observation: for image edits, `input_tokens` stayed fixed at 1,037 for all quality levels (image tokens dominate), while `output_tokens` followed the same quality bucket pattern as image generation (208/805/3171 at 1024x1024).

## How Token Data Was Collected

Output token counts are **returned directly by the Azure OpenAI API** in the response body, not calculated or estimated by the client.

### API Response Structure

When you call the image generation endpoint, the response includes a `usage` object:

```json
{
  "created": 1776825422,
  "background": "opaque",
  "data": [{ "b64_json": "<base64 image>" }],
  "output_format": "png",
  "quality": "medium",
  "size": "1024x1024",
  "usage": {
    "input_tokens": 9,
    "input_tokens_details": {
      "image_tokens": 0,
      "text_tokens": 9
    },
    "output_tokens": 805,
    "total_tokens": 814
  }
}
```

### Code to Extract Token Usage

```python
import requests, json

endpoint = "https://YOUR_RESOURCE.openai.azure.com"
api_key = "YOUR_KEY"
url = f"{endpoint}/openai/deployments/gpt-image-2/images/generations?api-version=2025-04-01-preview"

resp = requests.post(url,
    headers={"api-key": api_key, "Content-Type": "application/json"},
    json={"prompt": "a cat", "quality": "medium", "size": "1024x1024", "n": 1},
    timeout=300,
)
data = resp.json()

# Token usage is in the response body — server-side authoritative data
usage = data["usage"]
print(f"Input tokens:  {usage['input_tokens']}")
print(f"Output tokens: {usage['output_tokens']}")   # This is the billing metric
print(f"Total tokens:  {usage['total_tokens']}")

# Verify internal consistency
assert usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]
```

### Why This Data Is Authoritative

| Aspect | Explanation |
|:-------|:-----------|
| **Source** | `response.usage.output_tokens` — returned by Azure OpenAI server, same field used for billing |
| **Format** | Identical to the `usage` object in Chat Completions API — standard OpenAI convention |
| **Consistency** | `total_tokens = input_tokens + output_tokens` holds for all 26 calls |
| **Not client-side** | Token count is not derived from image file size, base64 length, or client-side tokenizer |
| **Determinism** | 11 different prompts at the same quality+size all returned the exact same `output_tokens` value |

## How to Choose the Right Quality

| Use Case | Recommended Quality | Why |
|:---------|:-------------------|:----|
| Thumbnails / previews | **low** | 15× fewer tokens, fast (~20s) |
| Marketing / social media | **medium** | Good balance of detail and speed |
| Print / professional | **high** | Maximum detail, but 15× more tokens and ~3 min latency |
| Prototyping / iteration | **low** | Fast feedback loop, minimal token usage |
| A/B testing at scale | **low** or **medium** | Low token consumption for bulk generation |

## Known Limitations

1. **No repeat runs**: Each size×quality combination tested once. Variance analysis requires multiple runs per combination.
2. **Single prompt per matrix**: The 3×3 matrix used one prompt. Token determinism verified with 4 prompts only at 1024×1024 low.
3. **Preview API**: Using `2025-04-01-preview` — behavior may change in GA.
4. **Region**: East US 2 only. Latency varies by region and load.
5. **Latency is end-to-end**: Includes network RTT from client, not pure generation time.

## Reproducing the Benchmark

### Prerequisites

- Azure subscription with Azure OpenAI access
- GPT-Image-2 model access (limited access — [apply here](https://aka.ms/oai/gptimage1access))
- Python 3.8+ with `openai` package

### Setup

```bash
git clone https://github.com/david-share/Multimodal-Models.git
cd Multimodal-Models/GPT-Image-2-Token-Bucket-Benchmark
pip install openai azure-identity
```

### Deploy the Model

```bash
az cognitiveservices account deployment create \
  --name YOUR_RESOURCE_NAME \
  --resource-group YOUR_RG \
  --deployment-name gpt-image-2 \
  --model-name gpt-image-2 \
  --model-version "2026-04-21" \
  --model-format OpenAI \
  --sku-capacity 9 \
  --sku-name GlobalStandard
```

### Run the Benchmark

```bash
export AZURE_OPENAI_ENDPOINT="https://YOUR_RESOURCE.openai.azure.com/"
export AZURE_OPENAI_KEY="YOUR_KEY"

python scripts/benchmark_gpt_image2.py \
  --endpoint $AZURE_OPENAI_ENDPOINT \
  --key $AZURE_OPENAI_KEY \
  --deployment gpt-image-2
```

### Script Inventory

| Script | Purpose |
|:-------|:--------|
| `scripts/benchmark_gpt_image2.py` | Basic benchmark — 2 prompts × 3 qualities, saves images + token data |
| `scripts/benchmark_size_quality_matrix.py` | 3×3 size×quality matrix — maps output tokens for all 9 combinations |
| `scripts/verify_token_determinism.py` | Runs 11 diverse prompts at fixed quality+size to prove token determinism |
| `scripts/benchmark_gpt_image2_edit.py` | Edit API benchmark — tests low/medium/high edits, saves rendered outputs + token/latency CSV |

## References

- [Introducing GPT-Image-2 in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openais-gpt-image-2-in-microsoft-foundry/4514417) — TC Blog describing token bucket mechanism (Mode 1 / Mode 2 routing)
- [OpenAI GPT-image-2 正式上线 Microsoft Foundry（企业级国际版）](https://mp.weixin.qq.com/s/YeAMajFSgdu5BN_PRR_RKw) — Azure Cloud Tech WeChat official account, April 22, 2026 (Chinese); describes new capabilities, routing modes, industry applications
- [Azure OpenAI Image Generation](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e) — API documentation
- [Azure Foundry Models](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure) — Model catalog

---

*Author: Xinyu Wei — Tested on Azure OpenAI, April 22, 2026*

[![Running on Azure](https://img.shields.io/badge/Running%20on-Microsoft%20Azure-blue?logo=microsoft-azure)](https://azure.microsoft.com)
