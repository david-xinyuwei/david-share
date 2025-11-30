# Azure OpenAI GPT-5 vs AWS Bedrock Claude Sonnet 4.5 Competitive Analysis

**Date: November 30, 2025**

---

## 1. Pricing Comparison

### PayGo (Pay-as-you-go)

| Item | Azure GPT-5 Global | AWS Claude Sonnet 4.5 | Azure Advantage |
|--------|-------------------|----------------------|-----------|
| Input | $1.25/M | $3.00/M | **-58%** |
| Cached Input | $0.13/M | $0.30/M | **-57%** |
| Output | $10.00/M | $15.00/M | **-33%** |
| Cache Write Surcharge | None | +25% ($3.75/M) | **No Surcharge** |

> Source: [Azure OpenAI Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/) | [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)

### PTU (Provisioned Throughput)

| Model | Deployment Type | Min PTUs | Price per PTU |
|------|---------|---------|------------|
| GPT-5 | Global Provisioned | 15 | $1.00/hr |
| GPT-5 | Data Zone Provisioned | 15 | $1.10/hr |
| GPT-5 | **Regional Provisioned (Japan)** | 50 | $2.00/hr |

---

## 2. Azure Core Advantages

### 2.1 Japan Regional PTU

- **Single Region Deployment**: Regional PTU provides dedicated capacity within a single region in Japan (e.g., Tokyo).
- **vs. AWS CRIS**: AWS Cross-Region Inference automatically routes traffic between Tokyo and Osaka (both within Japan, but not pinned to a single specific region).

### 2.2 PTU Prompt Caching

| Feature | Azure PTU | AWS Bedrock |
|------|----------|-------------|
| Cache Hit Cost | **$0** | $0.30/M |
| Cache Quota Usage | **Does not consume TPM** | N/A |
| First Write Surcharge | None | +25% |

**Key Point**: For PTU users, cache hits are completely free and do not consume throughput quota (TPM).

### 2.3 AI Gateway (New Release)

Microsoft Foundry integrated AI Gateway provides:
- Token Rate Limiting
- Quota Management
- Centralized API Governance
- **First 100K calls free**

---

## 3. Best Scenarios

| Scenario | Why Azure | Expected Cache Hit Rate |
|------|---------------|-----------------|
| **Coding Assistant** | Long System Prompt + Stable Tool Definitions, Static Prefix | 60-80% |
| **Agent Tool Pipeline** | Fixed Tool Definitions, `previous_response_id` keeps prefix consistent | 50-70% |
| **Batch Document Processing** | Same template processing multiple documents, exact prefix match | 80-90% |
| **RAG Knowledge Base** | Heavy context injection, Stable System Prompt | 40-60% |

**Unsuitable Scenarios**:
- Standard Multi-turn Chat (Frequent user/assistant alternation causes prefix to change constantly, making cache hits difficult).

---

## 4. Cost Savings Estimation

### Scenario: 100-User Coding Assistant

**Assumptions**:
- 100 Developers × 30 requests/day × 22 working days = 66,000 requests/month
- Per request: 5,000 tokens Input + 500 tokens Output
- Cache Hit Rate: 70%

**Monthly Token Volume**:
- Input: 330M tokens (99M Uncached + 231M Cached)
- Output: 33M tokens

| Cost Item | Azure PayGo | AWS Bedrock PayGo |
|--------|------------|-------------------|
| Uncached Input (30%) | 99M × $1.25 = $124 | 99M × $3.00 = $297 |
| Cached Input (70%) | 231M × $0.13 = $30 | 231M × $0.30 = $69 |
| Output | 33M × $10 = $330 | 33M × $15 = $495 |
| **Monthly Total** | **$484** | **$861** |
| **Annual Total** | **$5,808** | **$10,332** |

**Annual Savings**: $4,524 (44%)

> Note: This is a PayGo vs. PayGo comparison.

---

### Scenario B: 500-User AI-First Team (Global PTU)

**Assumptions**:
- 500 Developers × **300 requests/day** (heavy Copilot usage) × 22 working days = **3,300,000 requests/month**
- Per request: 5,000 tokens Input + 500 tokens Output
- Cache Hit Rate: 70%
- Azure: **Global PTU (15 PTU minimum)**

> 💡 Heavy usage (300 req/day) reflects AI-first development teams using coding assistants intensively.

**Monthly Token Volume**:
- Input: 16,500M tokens (4,950M Uncached + 11,550M Cached)
- Output: 1,650M tokens

| Cost Item | Azure Global PTU | AWS Bedrock PayGo |
|--------|-----------------|-------------------|
| PTU Cost | 15 × $1.00 × 720hr = **$10,800** | N/A |
| Uncached Input (30%) | **$0** (included in PTU) | 4,950M × $3.00 = $14,850 |
| Cached Input (70%) | **$0** (PTU cache hits free) | 11,550M × $0.30 = $3,465 |
| Output | **$0** (included in PTU) | 1,650M × $15 = $24,750 |
| **Monthly Total** | **$10,800** | **$43,065** |
| **Annual Total** | **$129,600** | **$516,780** |

**Annual Savings**: $387,180 (75%)

**Key Insight**: At this scale, Azure Global PTU provides:
- **Fixed predictable cost** ($10,800/mo) vs. variable AWS spending ($43,065/mo)
- **Cache hits are completely free** (no $0.30/M charge)
- **Guaranteed latency SLA** + no throttling
- **Break-even at ~1.5M requests/mo** — this scenario (3.3M) is well above

---

### Scenario C: Japan Data Residency (Regional PTU) — Compliance-Driven

> ⚠️ **This scenario is driven by compliance requirements, not pure cost optimization.**
> Customers requiring strict single-region data residency in Japan have only one option: Azure Regional PTU.
> The comparison below is Azure Regional PTU vs. AWS (the only viable alternatives for Japan).

**Assumptions**:
- Large enterprise requiring **Japan single-region data residency** (e.g., FSI, Healthcare, Government)
- 2,000 Developers × **300 requests/day** (heavy usage) × 22 working days = **13,200,000 requests/month**
- Per request: 5,000 tokens Input + 500 tokens Output
- Cache Hit Rate: 70%
- Azure: **Regional PTU Japan (50 PTU minimum)**

> 💡 At 13.2M requests/mo, this exceeds the Regional PTU break-even point (~10M), making PTU cost-effective.

**Monthly Token Volume**:
- Input: 66,000M tokens (19,800M Uncached + 46,200M Cached)
- Output: 6,600M tokens

| Cost Item | Azure Regional PTU (Japan) | AWS Bedrock PayGo (CRIS Tokyo↔Osaka) |
|--------|---------------------------|--------------------------------------|
| PTU Cost | 50 × $2.00 × 720hr = **$72,000** | N/A |
| Uncached Input (30%) | **$0** (included in PTU) | 19,800M × $3.00 = $59,400 |
| Cached Input (70%) | **$0** (PTU cache hits free) | 46,200M × $0.30 = $13,860 |
| Output | **$0** (included in PTU) | 6,600M × $15 = $99,000 |
| **Monthly Total** | **$72,000** | **$172,260** |
| **Annual Total** | **$864,000** | **$2,067,120** |

**Annual Savings vs AWS**: $1,203,120 (58%)

**Key Insight**:
| Dimension | Azure Regional PTU | AWS CRIS |
|-----------|-------------------|----------|
| **Compliance** | ✅ Single region (Tokyo only) | ❌ Routes between Tokyo↔Osaka |
| **Cost** | $72,000/mo | $172,260/mo |
| **Verdict** | **Wins on both compliance AND cost (58% savings)** | — |

> 💡 For compliance-driven customers, Azure Regional PTU is the **only option that meets strict single-region requirements** while saving **$1.2M annually** vs AWS.

---

### PTU Break-even Summary

| Deployment Type | Min PTUs | Monthly Cost | Break-even Point (vs Azure PayGo) | Example Team Size |
|-----------------|----------|--------------|-----------------------------------|-------------------|
| Global Provisioned | 15 | $10,800/mo | ~1.5M requests/mo | 230 devs @ 300 req/day |
| Data Zone Provisioned | 15 | $11,880/mo | ~1.6M requests/mo | 245 devs @ 300 req/day |
| Regional (Japan) | 50 | $72,000/mo | ~10M requests/mo | 1,500 devs @ 300 req/day |

**When to Use PTU**:
| Scenario | Recommendation |
|----------|----------------|
| Light usage (30 req/day) | PayGo — PTU rarely cost-effective |
| Heavy usage (300 req/day), < 230 devs | PayGo |
| Heavy usage (300 req/day), 230-1,500 devs | Global PTU (Best Value) |
| Japan Data Residency + Heavy usage | Regional PTU (58% savings vs AWS) |

**PTU Additional Benefits** (not reflected in pure cost comparison):
- **Guaranteed Latency SLA**
- **Cache Hits = $0 + Zero TPM Consumption**
- **No throttling during traffic spikes**

---

## 5. Summary

**Azure Key Selling Points**:
1. PayGo unit price is 33-58% lower.
2. Japan Regional PTU offers single-region deployment.
3. PTU Cache Hits = $0 + Zero TPM Consumption.
4. AI Gateway first 100K calls free.

**Target Customers**:
- Cost-sensitive.
- Require Japan Data Residency.
- High-frequency repetitive calls (Coding, Agent, Batch Processing).
- Existing Azure ecosystem investment.
