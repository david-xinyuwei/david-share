# GPT-Image-2 Token Bucket Benchmark on Azure OpenAI

This repository investigates the **token size bucket** mechanism in OpenAI's GPT-Image-2 model, deployed via Azure OpenAI Service. We provide hands-on benchmark data answering the key question: **How does the `quality` parameter affect output token consumption and cost?**

## Executive Summary

GPT-Image-2 (`v2026-04-21`) introduces a variable token billing system — unlike GPT-Image-1.5 which used fixed token counts, GPT-Image-2 dynamically allocates output tokens based on the `quality` parameter.

| Quality | Output Tokens | Latency (s) | Cost per Image (USD) | Ratio vs Low |
|:--------|:-------------|:-----------|:---------------------|:-------------|
| **low** | 208 | ~15–21 | $0.006 | 1.0x |
| **medium** | 805 | ~30–59 | $0.024 | 3.9x |
| **high** | 3,171 | ~174 | $0.095 | 15.2x |

> **Test conditions**: gpt-image-2 `v2026-04-21`, Azure OpenAI `api-version=2025-04-01-preview`, GlobalStandard deployment, `1024x1024`, East US 2 region. Cost calculated at USD 30/1M output image tokens ([source: OpenAI API Pricing](https://openai.com/api/pricing/)).

**Key finding**: The `quality` parameter is the primary lever controlling output token count. Token counts are **consistent across different prompts** at the same quality level — both a simple "red dot" and a complex photorealistic scene produced identical token counts (208/805/3171) for the same quality setting.

## Background

### What is the "Token Size Bucket"?

The [Introducing GPT-Image-2 in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openais-gpt-image-2-in-microsoft-foundry/4514417) blog describes a **Mode 2 — Token size bucket selection** mechanism:

- The routing layer selects from **six token size buckets**: 16, 24, 36, 48, 64, 96
- These map to legacy size tiers: `smimage`, `image`, `xlimage`
- The system analyzes prompt complexity, detail requirements, and scene type to automatically select a bucket

**This is NOT a user-configurable parameter.** There is no `token_bucket` or `output_token_count` API parameter. Users influence token allocation through:

1. **`quality` parameter** (low / medium / high) — primary control
2. **`size` parameter** (1024x1024, 1024x1536, 1536x1024) — resolution control
3. **Prompt complexity** — the system may adjust allocation based on prompt analysis

### Model Information

| Property | Value | Source |
|:---------|:------|:-------|
| Model | gpt-image-2 | [Azure Model Catalog](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure) |
| Version | 2026-04-21 | `az cognitiveservices account list-models` |
| Status | Generally Available | Model catalog |
| Format | OpenAI | Azure deployment |
| Deprecation | 2027-04-21 | Model catalog |
| Pricing (Output Image) | USD 30 / 1M tokens | [OpenAI API Pricing](https://openai.com/api/pricing/) |
| Pricing (Input Text) | USD 5 / 1M tokens | [OpenAI API Pricing](https://openai.com/api/pricing/) |
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

### Cost Analysis

Using [OpenAI pricing](https://openai.com/api/pricing/) (USD 30/1M output image tokens, USD 5/1M input text tokens):

| Quality | Output Tokens | Output Cost | Input Cost (9 tok) | **Total Cost/Image** |
|:--------|:-------------|:-----------|:-------------------|:--------------------|
| low | 208 | $0.00624 | $0.000045 | **$0.006** |
| medium | 805 | $0.02415 | $0.000045 | **$0.024** |
| high | 3,171 | $0.09513 | $0.000045 | **$0.095** |

> At scale (e.g., 10,000 images/month): low = $62, medium = $242, high = $952

### Generated Images — Visual Comparison

#### Prompt 1: "A simple red circle on white background"

| Low (208 tokens) | Medium (805 tokens) | High (3,171 tokens) |
|:---:|:---:|:---:|
| ![low](images/red_dot/red_dot_low.png) | ![medium](images/red_dot/red_dot_medium.png) | ![high](images/red_dot/red_dot_high.png) |

#### Prompt 2: "A photorealistic golden retriever puppy..."

| Low (208 tokens) | Medium (805 tokens) | High (3,171 tokens) |
|:---:|:---:|:---:|
| ![low](images/dog/dog_low.png) | ![medium](images/dog/dog_medium.png) | ![high](images/dog/dog_high.png) |

## How to Choose the Right Quality

| Use Case | Recommended Quality | Why |
|:---------|:-------------------|:----|
| Thumbnails / previews | **low** | 15x cheaper than high, fast (~15s) |
| Marketing / social media | **medium** | Good balance of quality and cost |
| Print / professional | **high** | Maximum detail, but 15x more tokens |
| Prototyping / iteration | **low** | Fast feedback loop, minimal cost |
| A/B testing at scale | **low** or **medium** | Cost-efficient for bulk generation |

## Known Limitations

1. **Sample size**: 2 prompts × 3 quality levels. A production benchmark should test 20+ diverse prompts.
2. **Single resolution**: Only 1024×1024 tested. 1024×1536 and 1536×1024 may produce different token counts.
3. **No repeat runs**: Each combination tested once. Variance analysis requires multiple runs.
4. **Preview API**: Using `2025-04-01-preview` — behavior may change in GA.
5. **Region**: East US 2 only. Latency varies by region.

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
| `scripts/benchmark_gpt_image2.py` | Main benchmark — tests quality levels, saves images + token data |

## References

- [Introducing GPT-Image-2 in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openais-gpt-image-2-in-microsoft-foundry/4514417) — TC Blog describing token bucket mechanism
- [OpenAI API Pricing](https://openai.com/api/pricing/) — GPT-Image-2 pricing
- [Azure OpenAI Image Generation](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e) — API documentation
- [Azure Foundry Models](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure) — Model catalog

---

*Author: Xinyu Wei — Tested on Azure OpenAI, April 22, 2026*

[![Running on Azure](https://img.shields.io/badge/Running%20on-Microsoft%20Azure-blue?logo=microsoft-azure)](https://azure.microsoft.com)
