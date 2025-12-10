# Foundry IQ - Azure AI Search Knowledge Retrieval Guide

> **Foundry IQ** is a new capability of Azure AI Search announced at Microsoft Ignite 2025. It enables Agentic RAG through Knowledge Sources and Knowledge Bases, providing intelligent document retrieval, automatic vectorization, and answer generation.

**Demo Repository**: [farzad528/azure-ai-search-knowledge-retrieval-demo](https://github.com/farzad528/azure-ai-search-knowledge-retrieval-demo)  
**Live Demo**: https://azure-ai-search-knowledge-retrieval.vercel.app/

---

## 🎯 Foundry IQ Overview (Concepts)

**Foundry IQ** (Knowledge Store API) is a new feature layer of Azure AI Search, introduced in API version `2025-11-01-preview`:

| Concept | Description | Analogy |
|---------|-------------|---------|
| **Knowledge Source** | Data source connector (Blob/Web/Index) | Like Data Source + Indexer + Skillset bundled |
| **Knowledge Base** | Unified query endpoint aggregating multiple Sources | Like Azure OpenAI "On Your Data" |
| **Retrieve API** | One-stop query: retrieval + LLM answer generation | Automated RAG Pipeline |

### Core Value

```
Traditional RAG Pipeline:
  User Query → Manual Embedding → Vector Search → Reranking → Build Prompt → Call LLM → Return Answer
  (Requires extensive code)

Foundry IQ:
  User Query → Knowledge Base /retrieve API → Return Answer + Citations
  (Single API call)
```

---

## 📌 What is Foundry IQ? (Entity Definition)

> ⚠️ **Important Clarification**: Foundry IQ is NOT a standalone Azure product, service, or SDK.

| Aspect | Description |
|--------|-------------|
| **What it IS** | A set of new REST APIs within Azure AI Search service |
| **What it is NOT** | NOT a standalone product, NOT a separate service, NOT an SDK |
| **Commercial Entity** | Azure AI Search (billed as AI Search usage) |
| **API Version** | `2025-11-01-preview` |
| **GA Status** | ❌ Public Preview - No SLA, NOT recommended for production |
| **SDK Support** | No dedicated SDK; use native `fetch` or REST clients |

### Supported LLMs for Query Planning

Only specific models support the agentic query planning feature:

| Model | Support | Notes |
|-------|---------|-------|
| gpt-4o | ✅ | Recommended |
| gpt-4.1 | ✅ | When available |
| gpt-5 series | ✅ | Future support |
| gpt-4-turbo | ❌ | Not supported |
| gpt-35-turbo | ❌ | Not supported |
| Other models | ❌ | Query planning requires specific models |

---

## 🚀 Why Foundry IQ? (Agentic Retrieval)

Single-shot RAG (one query hits one index once) quickly runs into limits when questions are:
- **Ambiguous** - unclear what the user really wants
- **Multi-step** - requires reasoning across multiple documents
- **Cross-system** - spans several data sources

### How Agentic Retrieval Works

Foundry IQ uses an **agentic retrieval engine** that treats retrieval as a **reasoning task**, not just keyword lookup:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agentic Retrieval Engine                      │
├─────────────────────────────────────────────────────────────────┤
│  1. PLAN      │ AI plans how to search based on the question    │
│  2. DECOMPOSE │ Rewrites and breaks down complex questions      │
│  3. SEARCH    │ Reaches into multiple sources in parallel       │
│  4. EVALUATE  │ Checks if it has enough signal                  │
│  5. ITERATE   │ Searches again if needed                        │
│  6. SYNTHESIZE│ Combines results with citations                 │
└─────────────────────────────────────────────────────────────────┘
```

### Retrieval Reasoning Effort

Developers control behavior through a simple `queryReasoningEffort` setting:

| Level | Behavior | Use Case |
|-------|----------|----------|
| **Low** | Fast, lightweight lookups | Simple factual queries |
| **Medium** | Balanced planning and search | General questions |
| **High** | Iterative search, richer planning | Complex multi-step questions |

### Real Evidence: Activity Response Analysis

When you call the `/retrieve` API, the `activity` field reveals exactly how Agentic Retrieval works:

**Query:** "What is the optimal chunk size for RAG?"

```json
"activity": [
  {
    "type": "modelQueryPlanning",      // Step 1: AI plans search strategy
    "inputTokens": 1455,
    "outputTokens": 102,
    "elapsedMs": 2341
  },
  {
    "type": "azureBlob",               // Step 2: First sub-query
    "knowledgeSourceName": "blob-demo-vector",
    "azureBlobArguments": {
      "search": "Optimal chunk size for Retrieval-Augmented Generation (RAG)"
    }
  },
  {
    "type": "azureBlob",               // Step 3: Second sub-query (decomposed)
    "azureBlobArguments": {
      "search": "Factors influencing chunk size in RAG"
    }
  },
  {
    "type": "azureBlob",               // Step 4: Third sub-query
    "azureBlobArguments": {
      "search": "Best practices for determining chunk size in RAG"
    }
  },
  {
    "type": "agenticReasoning",        // Step 5: Evaluate and reason
    "retrievalReasoningEffort": { "kind": "low" },
    "reasoningTokens": 741
  },
  {
    "type": "modelAnswerSynthesis",    // Step 6: Synthesize final answer
    "inputTokens": 2985,
    "outputTokens": 82,
    "elapsedMs": 2796
  }
]
```

**What this proves:**

| Claim | Evidence |
|-------|----------|
| "Plans how to search" | ✅ `modelQueryPlanning` step exists |
| "Decomposes complex questions" | ✅ 1 question → 3 sub-queries |
| "Searches multiple times" | ✅ 3 `azureBlob` calls with different queries |
| "Evaluates signal quality" | ✅ `agenticReasoning` step |
| "queryReasoningEffort control" | ✅ `retrievalReasoningEffort: {kind: "low"}` |
| "Synthesizes with citations" | ✅ `modelAnswerSynthesis` + `references` array |

### Real-World Impact

| Customer | Result |
|----------|--------|
| **AT&T** | 33% reduction in customer resolution times, 10% cut in handle time, scaled 71 AI solutions to 100,000 employees |
| **Ontario Power Generation** | Unlocked 40+ years of nuclear operating experience for data-driven decision-making |

---

## 🧠 Technical Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Azure AI Search Service                           │
│                    (Knowledge Store API - 2025-11-01-preview)            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Knowledge Bases                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │   │
│  │  │kb-azure-docs│  │kb-blob-only │  │kb-tech-docs │               │   │
│  │  │(Web + Blob) │  │(Blob Only)  │  │(Tech Docs)  │               │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │   │
│  └─────────┼────────────────┼────────────────┼──────────────────────┘   │
│            │                │                │                           │
│  ┌─────────┴────────────────┴────────────────┴──────────────────────┐   │
│  │                      Knowledge Sources                            │   │
│  │  ┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │web-azure-docs │  │blob-demo-vector │  │ blob-tech-docs  │     │   │
│  │  │(Bing Grounding│  │(Azure Blob +    │  │ (Azure Blob +   │     │   │
│  │  │ - Real-time)  │  │ Embedding)      │  │  Embedding)     │     │   │
│  │  └───────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                      │                                   │
│                    ┌─────────────────┴─────────────────┐                │
│                    │   Auto-Created Resources:         │                │
│                    │   • {source}-datasource           │                │
│                    │   • {source}-indexer              │                │
│                    │   • {source}-skillset             │                │
│                    │   • {source}-index (with vectors) │                │
│                    └───────────────────────────────────┘                │
│                                                                          │
└──────────────────────────────────────┬───────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Azure Blob      │  │ Azure OpenAI    │  │ Bing Grounding  │
│ Storage         │  │                 │  │ (Web Search)    │
│ (Managed ID)    │  │ • Embedding     │  │                 │
│ • demo-docs/    │  │ • Chat (GPT-4o) │  │ Real-time       │
│ • tech-docs/    │  │                 │  │ Internet Search │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Knowledge Source Types (Complete List)

Foundry IQ supports **6 types** of Knowledge Sources:

| Type | `kind` Value | Description | Embedding | Real-time |
|------|--------------|-------------|-----------|----------|
| **Azure Blob** | `azureBlob` | Azure Blob Storage containers | ✅ Configurable | Pre-indexed |
| **Search Index** | `searchIndex` | Wrap existing AI Search Index | Depends on index | Pre-indexed |
| **Indexed OneLake** | `indexedOneLake` | Microsoft Fabric Lakehouse | ✅ Configurable | Pre-indexed |
| **Indexed SharePoint** | `indexedSharePoint` | SharePoint indexed to AI Search | ✅ Configurable | Pre-indexed |
| **Remote SharePoint** | `remoteSharePoint` | SharePoint direct query (no indexing) | N/A | ✅ Real-time |
| **Web** | `web` | Internet search via Bing | N/A | ✅ Real-time |

### ⚠️ Web Knowledge Source: Under the Hood

> **Critical Discovery**: Web Knowledge Source is NOT a simple API wrapper. It uses **Grounding with Bing Search** service under the hood.

| Configuration | Underlying Service | Scope |
|--------------|-------------------|--------|
| No `domains` specified | **Grounding with Bing Search** | Entire public internet |
| `domains` array specified | **Grounding with Bing Custom Search** | Restricted to specified domains |

**Official Documentation Reference**:
> *"Web Knowledge Source, which uses Grounding with Bing Search and/or Grounding with Bing Custom Search, is a First Party Consumption Service"*
>
> *"Bing Custom Search is always the search provider for Web Knowledge Source"*

**Pricing**: Web Knowledge Source queries are billed through [Grounding with Bing Search pricing](https://azure.microsoft.com/pricing/details/ai-services/).

### ⚠️ Data Boundary Warning (Compliance)

> 🔴 **IMPORTANT for Enterprise Customers**:
>
> When using **Web Knowledge Source**, your data **leaves the Azure compliance boundary**:
> - Data flows through Bing Search infrastructure
> - **NOT covered** by Microsoft Data Protection Addendum (DPA)
> - May not meet regulatory requirements (GDPR, HIPAA, etc.)
> - Consider using `domains` restriction to limit exposure

**Recommendation for Sensitive Workloads**:
- Use `azureBlob`, `searchIndex`, or `indexedSharePoint` instead
- These keep data within Azure's compliance boundary

---

## 🚀 Quick Start

### Step 1: Clone the Demo Repository

```bash
git clone https://github.com/farzad528/azure-ai-search-knowledge-retrieval-demo.git
cd azure-ai-search-knowledge-retrieval-demo
```

### Step 2: Create Azure Resources

**Required Resources**:

| Resource | SKU Requirement | Notes |
|----------|-----------------|-------|
| Azure AI Search | **Standard** or higher | Basic does not support Knowledge Store |
| Azure OpenAI | - | Requires `text-embedding-3-large` + `gpt-4o` |
| Storage Account | (Optional) | For Blob Knowledge Source |

```bash
# Create AI Search (Must be Standard SKU!)
az search service create \
  --name <your-search-name> \
  --resource-group <your-rg> \
  --sku standard \
  --location eastus

# Enable Managed Identity (Recommended)
az search service update \
  --name <your-search-name> \
  --resource-group <your-rg> \
  --identity-type SystemAssigned
```

### Step 3: Configure Environment Variables

```bash
cp .env.example .env.local
```

Edit `.env.local`:

```bash
# Required
AZURE_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
AZURE_SEARCH_API_KEY=<your-admin-key>
AZURE_SEARCH_API_VERSION=2025-11-01-preview

NEXT_PUBLIC_AZURE_OPENAI_ENDPOINT=https://<your-aoai>.openai.azure.com
AZURE_OPENAI_API_KEY=<your-aoai-key>
```

### Step 4: Start the Demo

```bash
npm install
npm run dev
```

Open http://localhost:3000

---

## 📡 API Reference

### Knowledge Source API

**Create Blob Knowledge Source (with vectors)**:

```bash
curl -X PUT "https://<search>.search.windows.net/knowledgesources/<name>?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "api-key: <key>" \
  -d '{
    "name": "<name>",
    "kind": "azureBlob",
    "description": "My documents",
    "azureBlobParameters": {
      "connectionString": "ResourceId=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>",
      "containerName": "<container>",
      "ingestionParameters": {
        "embeddingModel": {
          "kind": "azureOpenAI",
          "azureOpenAIParameters": {
            "resourceUri": "https://<aoai>.openai.azure.com",
            "deploymentId": "text-embedding-3-large",
            "apiKey": "<aoai-key>",
            "modelName": "text-embedding-3-large"
          }
        }
      }
    }
  }'
```

**Key Points**:
- Use `kind` not `type`
- Use `containerName` not `container`
- **Must configure `embeddingModel`** to create vector fields

### Knowledge Base API

**Create Knowledge Base**:

```bash
curl -X PUT "https://<search>.search.windows.net/knowledgebases/<name>?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "api-key: <key>" \
  -d '{
    "name": "<name>",
    "description": "My Knowledge Base",
    "knowledgeSources": [{"name": "<source-name>"}],
    "models": [{
      "kind": "azureOpenAI",
      "azureOpenAIParameters": {
        "resourceUri": "https://<aoai>.openai.azure.com",
        "deploymentId": "gpt-4o",
        "apiKey": "<aoai-key>",
        "modelName": "gpt-4o"
      }
    }]
  }'
```

**Key Points**:
- `knowledgeSources` is an array of objects `[{"name": "..."}]`, not strings

### Retrieve API (Query)

```bash
curl -X POST "https://<search>.search.windows.net/knowledgebases('<name>')/retrieve?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "api-key: <key>" \
  -d '{
    "messages": [{
      "role": "user",
      "content": [{"type": "text", "text": "What is the optimal chunk size for RAG?"}]
    }]
  }'
```

**Response Structure**:

```json
{
  "response": [{
    "content": [{"type": "text", "text": "The optimal chunk size is 512-1024 tokens..."}]
  }],
  "activity": [
    {"type": "modelQueryPlanning", "elapsedMs": 2000},
    {"type": "azureBlob", "knowledgeSourceName": "blob-demo-vector", "count": 3}
  ],
  "references": [...]
}
```

---

## ⚠️ Gotchas & Troubleshooting

### 1. API Schema: `type` → `kind`

```diff
- "type": "azureBlob"
+ "kind": "azureBlob"
```

### 2. No Vector Fields Created

**Cause**: `embeddingModel` not configured

**Solution**: Add complete `embeddingModel` configuration in `ingestionParameters`

### 3. Storage Connection Failed (Managed Identity)

**Cause**: Using AccountKey format, but Storage has key access disabled

**Solution**: Use ResourceId format:
```
ResourceId=/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Storage/storageAccounts/{account}
```

**Prerequisite**: AI Search needs `Storage Blob Data Reader` role

### 4. knowledgeSources Format

```diff
- "knowledgeSources": ["my-source"]
+ "knowledgeSources": [{"name": "my-source"}]
```

### 5. WSL File System Issues

Running Node.js projects under `/mnt/c/` or `/mnt/g/` may encounter `.next` directory locking issues.

**Solution**: Copy project to WSL internal filesystem:
```bash
rsync -av --exclude='.next' --exclude='node_modules' /mnt/g/path/to/project/ ~/project/
```

---

## 📊 Verification Results

### Test Environment

| Resource | Configuration |
|----------|---------------|
| Azure AI Search | aisearch-foundry-iq (Standard, East US) |
| Azure OpenAI | aoai-davidai-di (text-embedding-3-large + gpt-4o) |
| Storage | safoundryiqdemo (Managed Identity) |

### Knowledge Sources Created

| Source | Type | Data Source | Embedding |
|--------|------|-------------|-----------|
| web-azure-docs | Bing | Internet | N/A |
| blob-demo-vector | Blob | demo-docs (RAG docs) | 3072-dim |
| blob-tech-docs | Blob | tech-docs (K8s/MLOps) | 3072-dim |

### Knowledge Bases Created

| KB | Sources | Purpose |
|----|---------|---------|
| kb-azure-docs | web + blob | Hybrid retrieval |
| kb-blob-only | blob-demo-vector | Blob only |
| kb-tech-docs | blob-tech-docs | Technical docs |

### Test Results

| Test | Query | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Vector Retrieval | "RAG chunk size" → kb-blob-only | 512-1024 tokens | Matched | Pass |
| Data Isolation | "K8s deployment" → kb-tech-docs | Rolling/Blue-Green/Canary | Matched | Pass |
| Data Isolation | "K8s deployment" → kb-blob-only | No result | "Could not find" | Pass |

---

## 🔗 References

- **Demo Repository**: [farzad528/azure-ai-search-knowledge-retrieval-demo](https://github.com/farzad528/azure-ai-search-knowledge-retrieval-demo)
- **Foundry IQ Blog**: [Unlocking Ubiquitous Knowledge for Agents](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/foundry-iq-unlocking-ubiquitous-knowledge-for-agents/4470812)
- **Azure AI Search Docs**: [learn.microsoft.com/azure/search/](https://learn.microsoft.com/azure/search/)
- **API Version**: `2025-11-01-preview`

---

## 📄 License

MIT

---

*Author: Xinyu Wei (Microsoft AI GBB) | Verified: 2025-12-09*
