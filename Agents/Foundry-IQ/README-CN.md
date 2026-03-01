# Foundry IQ - Azure AI Search 知识检索指南

> **Foundry IQ** 是微软在 Ignite 2025 发布的下一代 RAG 方案 —— 一个**统一的智能体知识层**。它是智能体获取知识的单一端点，通过自动化的数据源路由和高级 Agentic 检索提供更好的上下文，同时尊重用户权限。

**演示仓库**: [farzad528/azure-ai-search-knowledge-retrieval-demo](https://github.com/farzad528/azure-ai-search-knowledge-retrieval-demo)  
**在线演示**: https://azure-ai-search-knowledge-retrieval.vercel.app/

---

## 在 Azure 上运行

本项目完全基于 **Azure AI Search** 的 **Foundry IQ** 知识层构建。

| 项目 | 详情 |
|---|---|
| **Azure 服务** | [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/) — Foundry IQ (Knowledge Store API) |
| **API 版本** | `2025-11-01-preview` |
| **计算资源** | 无需 GPU VM — 全托管云服务，按查询付费 |

---

## 🎯 Foundry IQ 概述（核心概念）

### 痛点：每个项目都要交 RAG 税

传统 RAG 给每个新项目带来沉重的负担。每个团队都必须从头重建：

- 数据连接和分块逻辑
- 向量化和向量数据库
- 路由和权限控制
- 企业治理和访问控制

这导致组织内充斥着**碎片化、重复的流水线**，都在试图回答同一个问题：*模型需要什么上下文才能有效响应？*

### 解决方案：统一的知识层

**Foundry IQ** 将这些工作转移到**可复用的知识库**中。不再需要为每个智能体编写检索逻辑，而是：

1. 围绕某个主题定义知识库（员工政策、产品文档、客服内容）
2. 任意数量的智能体和应用都可以连接到同一个知识库
3. 无需管理路由或为每个数据源实现不同的检索策略

### 核心概念

| 概念 | 说明 | 价值 |
|------|------|------|
| **知识源** | 数据源连接器（Blob/SharePoint/Web/Index） | 自动索引、分块、向量化 |
| **知识库** | 以主题为中心的集合，为多个智能体提供 Grounding | 可复用，所有智能体共用一个 API |
| **Agentic 检索** | 自我反思的查询引擎，使用 AI 进行规划、搜索、综合 | 多步推理，不仅仅是关键词查找 |
| **检索 API** | 一站式查询，带引用和执行元数据 | 一次调用完成整个 RAG |

### 核心价值主张

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        传统 RAG（每个项目都要做）                           │
├────────────────────────────────────────────────────────────────────────────┤
│  项目 A: 数据连接 → 分块 → 向量化 → 向量库 → 路由                          │
│  项目 B: 数据连接 → 分块 → 向量化 → 向量库 → 路由                          │
│  项目 C: 数据连接 → 分块 → 向量化 → 向量库 → 路由                          │
│                         （到处都是重复工作）                                │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                        Foundry IQ（统一知识层）                             │
├────────────────────────────────────────────────────────────────────────────┤
│                      ┌─────────────────────┐                                │
│  项目 A ────────────►│                     │                                │
│  项目 B ────────────►│      知识库         │◄──── M365 SharePoint           │
│  项目 C ────────────►│   （单一 API）      │◄──── Azure Blob Storage        │
│  项目 D ────────────►│                     │◄──── 网页（必应搜索）          │
│                      └─────────────────────┘◄──── OneLake / Fabric IQ       │
│                    （接入知识，而不是重建 RAG）                             │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 📌 Foundry IQ 是什么？（实体定义）

> ⚠️ **重要澄清**：Foundry IQ **不是**独立的 Azure 产品、服务或 SDK。

| 维度 | 说明 |
|------|------|
| **是什么** | Azure AI Search 服务的一组新 REST API |
| **不是什么** | 不是独立产品、不是独立服务、不是 SDK |
| **商业实体** | Azure AI Search（按 AI Search 用量计费） |
| **API 版本** | `2025-11-01-preview` |
| **GA 状态** | ❌ 公开预览版 - 无 SLA，不建议生产使用 |
| **SDK 支持** | 无专用 SDK；使用原生 `fetch` 或 REST 客户端调用 |

### 支持 Query Planning 的 LLM 模型

只有特定模型支持 Agentic Query Planning（智能查询规划）功能：

| 模型 | 支持 | 备注 |
|------|------|------|
| gpt-4o | ✅ | 支持 |
| gpt-4.1 | ✅ | 支持 |
| gpt-5 系列 | ✅ | 支持 |
| gpt-4-turbo | ❌ | 不支持 |
| gpt-35-turbo | ❌ | 不支持 |
| 其他模型 | ❌ | Query Planning 需要特定模型 |

---

## 🚀 为什么选择 Foundry IQ？（Agentic 检索）

单次 RAG（一个查询只命中一个索引一次）在以下情况会很快遇到瓶颈：
- **模糊查询** - 不清楚用户真正想要什么
- **多步问题** - 需要跨多个文档进行推理
- **跨系统** - 涉及多个数据源

### Agentic 检索的工作原理

Foundry IQ 使用 **Agentic 检索引擎**，将检索视为**推理任务**，而不仅仅是关键词查找：

```
┌─────────────────────────────────────────────────────────────────┐
│                      Agentic 检索引擎                            │
├─────────────────────────────────────────────────────────────────┤
│  1. 规划      │ AI 根据问题规划搜索策略                          │
│  2. 分解      │ 改写并分解复杂问题                               │
│  3. 搜索      │ 并行访问多个数据源                               │
│  4. 评估      │ 检查是否有足够的信息                             │
│  5. 迭代      │ 如果需要，继续搜索                               │
│  6. 综合      │ 整合结果并附上引用                               │
└─────────────────────────────────────────────────────────────────┘
```

### 检索推理力度

开发者通过简单的 `queryReasoningEffort` 设置控制行为：

| 级别 | 行为 | 使用场景 |
|------|------|----------|
| **低** | 快速、轻量级查找 | 简单事实性问题 |
| **中** | 平衡的规划和搜索 | 一般性问题 |
| **高** | 迭代搜索、更丰富的规划 | 复杂多步问题 |

### 真实证据：Activity 响应分析

调用 `/retrieve` API 时，`activity` 字段完整展示了 Agentic 检索的工作过程：

**查询：** "What is the optimal chunk size for RAG?"

```json
"activity": [
  {
    "type": "modelQueryPlanning",      // 第1步：AI 规划搜索策略
    "inputTokens": 1455,
    "outputTokens": 102,
    "elapsedMs": 2341
  },
  {
    "type": "azureBlob",               // 第2步：第一个子查询
    "knowledgeSourceName": "blob-demo-vector",
    "azureBlobArguments": {
      "search": "Optimal chunk size for Retrieval-Augmented Generation (RAG)"
    }
  },
  {
    "type": "azureBlob",               // 第3步：分解后的第二个子查询
    "azureBlobArguments": {
      "search": "Factors influencing chunk size in RAG"
    }
  },
  {
    "type": "azureBlob",               // 第4步：第三个子查询
    "azureBlobArguments": {
      "search": "Best practices for determining chunk size in RAG"
    }
  },
  {
    "type": "agenticReasoning",        // 第5步：评估和推理
    "retrievalReasoningEffort": { "kind": "low" },
    "reasoningTokens": 741
  },
  {
    "type": "modelAnswerSynthesis",    // 第6步：综合生成最终答案
    "inputTokens": 2985,
    "outputTokens": 82,
    "elapsedMs": 2796
  }
]
```

**这证明了什么：**

| 官方宣传 | 实验证据 |
|----------|----------|
| "规划如何搜索" | ✅ `modelQueryPlanning` 步骤存在 |
| "分解复杂问题" | ✅ 1 个问题 → 3 个子查询 |
| "多次搜索" | ✅ 3 次 `azureBlob` 调用，查询词不同 |
| "评估信息质量" | ✅ `agenticReasoning` 步骤 |
| "queryReasoningEffort 控制" | ✅ `retrievalReasoningEffort: {kind: "low"}` |
| "带引用综合答案" | ✅ `modelAnswerSynthesis` + `references` 数组 |

---

## 🧠 技术架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Azure AI Search 服务                              │
│                    (知识存储 API - 2025-11-01-preview)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         知识库                                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │   │
│  │  │kb-azure-docs│  │kb-blob-only │  │kb-tech-docs │               │   │
│  │  │(网页+Blob)  │  │(纯Blob)     │  │(技术文档)   │               │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │   │
│  └─────────┼────────────────┼────────────────┼──────────────────────┘   │
│            │                │                │                           │
│  ┌─────────┴────────────────┴────────────────┴──────────────────────┐   │
│  │                         知识源                                    │   │
│  │  ┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │web-azure-docs │  │blob-demo-vector │  │ blob-tech-docs  │     │   │
│  │  │(必应搜索      │  │(Azure Blob +    │  │ (Azure Blob +   │     │   │
│  │  │ - 实时)       │  │ 向量化)         │  │  向量化)        │     │   │
│  │  └───────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                      │                                   │
│                    ┌─────────────────┴─────────────────┐                │
│                    │   自动创建的资源:                  │                │
│                    │   • {source}-datasource           │                │
│                    │   • {source}-indexer              │                │
│                    │   • {source}-skillset             │                │
│                    │   • {source}-index (含向量字段)   │                │
│                    └───────────────────────────────────┘                │
│                                                                          │
└──────────────────────────────────────┬───────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Azure Blob      │  │ Azure OpenAI    │  │ 必应搜索        │
│ 存储            │  │                 │  │ (网页搜索)      │
│ (托管标识)      │  │ • 向量化模型    │  │                 │
│ • demo-docs/    │  │ • 对话模型      │  │ 实时互联网搜索  │
│ • tech-docs/    │  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 知识源类型（完整列表）

Foundry IQ 支持 **6 种**知识源类型：

| 类型 | `kind` 值 | 说明 | 向量化 | 实时性 |
|------|-----------|------|--------|--------|
| **Azure Blob** | `azureBlob` | Azure Blob 存储容器 | ✅ 可配置 | 预索引 |
| **搜索索引** | `searchIndex` | 封装现有 AI Search 索引 | 取决于索引 | 预索引 |
| **索引 OneLake** | `indexedOneLake` | Microsoft Fabric Lakehouse | ✅ 可配置 | 预索引 |
| **索引 SharePoint** | `indexedSharePoint` | SharePoint 索引到 AI Search | ✅ 可配置 | 预索引 |
| **远程 SharePoint** | `remoteSharePoint` | SharePoint 直接查询（无索引） | 不适用 | ✅ 实时 |
| **网页** | `web` | 通过必应搜索互联网 | 不适用 | ✅ 实时 |

### ⚠️ Web 知识源：底层实现揭秘

> **关键发现**：Web 知识源**不是**简单的 API 封装，它底层使用的是 **Grounding with Bing Search** 服务。

| 配置方式 | 底层服务 | 搜索范围 |
|----------|----------|----------|
| 未指定 `domains` | **Grounding with Bing Search** | 整个公网 |
| 指定 `domains` 数组 | **Grounding with Bing Custom Search** | 限定域名 |

**官方文档原文**：
> *"Web Knowledge Source, which uses Grounding with Bing Search and/or Grounding with Bing Custom Search, is a First Party Consumption Service"*
>
> *"Bing Custom Search is always the search provider for Web Knowledge Source"*

**计费**：Web 知识源查询按 [Grounding with Bing Search 定价](https://azure.microsoft.com/pricing/details/ai-services/) 计费。

### ⚠️ 数据边界警告（合规性）

> 🔴 **企业客户注意**：
>
> 使用 **Web 知识源**时，您的数据**会离开 Azure 合规边界**：
> - 数据流经必应搜索基础设施
> - **不受** Microsoft 数据保护附录 (DPA) 保护
> - 可能不满足监管要求（GDPR、HIPAA 等）
> - 建议使用 `domains` 限制以降低风险

**敏感工作负载建议**：
- 改用 `azureBlob`、`searchIndex` 或 `indexedSharePoint`
- 这些类型的数据保持在 Azure 合规边界内

---

## 🚀 快速开始

### 第一步：克隆演示仓库

```bash
git clone https://github.com/farzad528/azure-ai-search-knowledge-retrieval-demo.git
cd azure-ai-search-knowledge-retrieval-demo
```

### 第二步：创建 Azure 资源

**必需资源**:

| 资源 | SKU 要求 | 说明 |
|------|----------|------|
| Azure AI Search | **Standard** 或更高 | Basic 不支持知识存储 |
| Azure OpenAI | - | 需要 `text-embedding-3-large` + `gpt-4o` |
| 存储账户 | （可选） | 用于 Blob 知识源 |

```bash
# 创建 AI Search（必须是 Standard SKU！）
az search service create \
  --name <你的搜索服务名> \
  --resource-group <你的资源组> \
  --sku standard \
  --location eastus

# 启用托管标识（推荐）
az search service update \
  --name <你的搜索服务名> \
  --resource-group <你的资源组> \
  --identity-type SystemAssigned
```

### 第三步：配置环境变量

```bash
cp .env.example .env.local
```

编辑 `.env.local`:

```bash
# 必填
AZURE_SEARCH_ENDPOINT=https://<你的搜索服务>.search.windows.net
AZURE_SEARCH_API_KEY=<你的管理密钥>
AZURE_SEARCH_API_VERSION=2025-11-01-preview

NEXT_PUBLIC_AZURE_OPENAI_ENDPOINT=https://<你的AOAI>.openai.azure.com
AZURE_OPENAI_API_KEY=<你的AOAI密钥>
```

### 第四步：启动演示

```bash
npm install
npm run dev
```

打开 http://localhost:3000

---

## 📡 API 详解

### 知识源 API

**创建 Blob 知识源（带向量化）**:

```bash
curl -X PUT "https://<搜索服务>.search.windows.net/knowledgesources/<名称>?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "api-key: <密钥>" \
  -d '{
    "name": "<名称>",
    "kind": "azureBlob",
    "description": "我的文档",
    "azureBlobParameters": {
      "connectionString": "ResourceId=/subscriptions/<订阅ID>/resourceGroups/<资源组>/providers/Microsoft.Storage/storageAccounts/<存储账户>",
      "containerName": "<容器名>",
      "ingestionParameters": {
        "embeddingModel": {
          "kind": "azureOpenAI",
          "azureOpenAIParameters": {
            "resourceUri": "https://<AOAI>.openai.azure.com",
            "deploymentId": "text-embedding-3-large",
            "apiKey": "<AOAI密钥>",
            "modelName": "text-embedding-3-large"
          }
        }
      }
    }
  }'
```

**关键点**:
- 使用 `kind` 而非 `type`
- 使用 `containerName` 而非 `container`
- **必须配置 `embeddingModel`** 才会创建向量字段

### 知识库 API

**创建知识库**:

```bash
curl -X PUT "https://<搜索服务>.search.windows.net/knowledgebases/<名称>?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "api-key: <密钥>" \
  -d '{
    "name": "<名称>",
    "description": "我的知识库",
    "knowledgeSources": [{"name": "<知识源名称>"}],
    "models": [{
      "kind": "azureOpenAI",
      "azureOpenAIParameters": {
        "resourceUri": "https://<AOAI>.openai.azure.com",
        "deploymentId": "gpt-4o",
        "apiKey": "<AOAI密钥>",
        "modelName": "gpt-4o"
      }
    }]
  }'
```

**关键点**:
- `knowledgeSources` 是对象数组 `[{"name": "..."}]`，不是字符串数组

### 检索 API（查询）

```bash
curl -X POST "https://<搜索服务>.search.windows.net/knowledgebases('<名称>')/retrieve?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "api-key: <密钥>" \
  -d '{
    "messages": [{
      "role": "user",
      "content": [{"type": "text", "text": "RAG 的最佳分块大小是多少？"}]
    }]
  }'
```

**响应结构**:

```json
{
  "response": [{
    "content": [{"type": "text", "text": "最佳分块大小是 512-1024 个令牌..."}]
  }],
  "activity": [
    {"type": "modelQueryPlanning", "elapsedMs": 2000},
    {"type": "azureBlob", "knowledgeSourceName": "blob-demo-vector", "count": 3}
  ],
  "references": [...]
}
```

---

## ⚠️ 踩坑记录

### 1. API 字段名：`type` → `kind`

```diff
- "type": "azureBlob"
+ "kind": "azureBlob"
```

### 2. 没有向量字段

**原因**：未配置 `embeddingModel`

**解决**：在 `ingestionParameters` 中添加完整的 `embeddingModel` 配置

### 3. 存储连接失败（托管标识）

**原因**：使用 AccountKey 格式，但存储账户禁用了密钥访问

**解决**：使用 ResourceId 格式：
```
ResourceId=/subscriptions/{订阅ID}/resourceGroups/{资源组}/providers/Microsoft.Storage/storageAccounts/{存储账户}
```

**前提**：AI Search 需要 `Storage Blob Data Reader` 角色

### 4. knowledgeSources 格式

```diff
- "knowledgeSources": ["my-source"]
+ "knowledgeSources": [{"name": "my-source"}]
```

### 5. WSL 文件系统问题

在 `/mnt/c/` 或 `/mnt/g/` 下运行 Node.js 项目可能遇到 `.next` 目录锁定问题。

**解决**：将项目复制到 WSL 内部：
```bash
rsync -av --exclude='.next' --exclude='node_modules' /mnt/g/path/to/project/ ~/project/
```

---

## 📊 测试验证

### 测试环境

| 资源 | 配置 |
|------|------|
| Azure AI Search | aisearch-foundry-iq（Standard，美国东部） |
| Azure OpenAI | aoai-davidai-di（text-embedding-3-large + gpt-4o） |
| 存储 | safoundryiqdemo（托管标识） |

### 创建的知识源

| 知识源 | 类型 | 数据源 | 向量化 |
|--------|------|--------|--------|
| web-azure-docs | 必应 | 互联网 | 不适用 |
| blob-demo-vector | Blob | demo-docs（RAG文档） | 3072维 |
| blob-tech-docs | Blob | tech-docs（K8s/MLOps） | 3072维 |

### 创建的知识库

| 知识库 | 知识源 | 用途 |
|--------|--------|------|
| kb-azure-docs | 网页 + Blob | 混合检索 |
| kb-blob-only | blob-demo-vector | 纯 Blob |
| kb-tech-docs | blob-tech-docs | 技术文档 |

### 测试结果

| 测试 | 查询 | 预期 | 实际 | 状态 |
|------|------|------|------|------|
| 向量检索 | "RAG chunk size" → kb-blob-only | 512-1024 tokens | 匹配 | 通过 |
| 数据隔离 | "K8s deployment" → kb-tech-docs | Rolling/Blue-Green/Canary | 匹配 | 通过 |
| 数据隔离 | "K8s deployment" → kb-blob-only | 无结果 | "找不到相关信息" | 通过 |

---

## 🔗 参考资料

- **演示仓库**：[farzad528/azure-ai-search-knowledge-retrieval-demo](https://github.com/farzad528/azure-ai-search-knowledge-retrieval-demo)
- **Foundry IQ 博客**：[为智能体解锁无处不在的知识](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/foundry-iq-unlocking-ubiquitous-knowledge-for-agents/4470812)
- **Azure AI Search 文档**：[learn.microsoft.com/azure/search/](https://learn.microsoft.com/azure/search/)
- **API 版本**：`2025-11-01-preview`

---

## 📄 许可证

MIT

---

*作者：魏新宇（微软 AI GBB）| 验证日期：2025-12-09*
