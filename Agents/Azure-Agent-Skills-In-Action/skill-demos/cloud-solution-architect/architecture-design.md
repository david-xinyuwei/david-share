# Cloud Solution Architect Skill — Live Demo

> This document was produced by an AI agent loaded with the `cloud-solution-architect` skill
> from [microsoft/skills](https://github.com/microsoft/skills). It follows the skill's
> **7-step Architecture Review Workflow** to design a production RAG Agent system on Azure.

## Step 1: Identify Requirements

**Functional**: Multi-tenant RAG agent that answers questions from enterprise documents,
supports 50+ concurrent users, with citation-backed answers.

**Non-functional**:

| Requirement | Target |
|-------------|--------|
| Availability | 99.9% (composite SLA) |
| Latency (p95) | < 3 seconds end-to-end |
| Throughput | 100 requests/min sustained |
| Data residency | Single region (East US) |
| RTO / RPO | 4 hours / 1 hour |
| Cost | < $2,000/month for dev/test |

## Step 2: Select Architecture Style

Using the skill's selection criteria:

| Criterion | Assessment | Style Fit |
|-----------|------------|-----------|
| Domain complexity | Medium (RAG pipeline + agent orchestration) | **Web-Queue-Worker** |
| Team autonomy | Single team | **Web-Queue-Worker** |
| Data volume | ~10 GB documents (not TB+) | Not Big Data |
| Latency requirements | Near real-time chat | Event-driven elements |

**Selected**: **Web-Queue-Worker** with event-driven elements for async document ingestion.

Rationale: The core request flow (user → web → LLM → response) is synchronous and moderate
complexity. Document ingestion is async (web → queue → worker). This avoids Microservices
overhead for a single-team project.

## Step 3: Choose Technology Stack

Using the skill's Technology Choices Decision Framework:

| Area | Choice | Rationale |
|------|--------|-----------|
| **Compute (web)** | Azure Container Apps | Managed, auto-scale to zero, simpler than AKS for single-team |
| **Compute (worker)** | Azure Functions (consumption) | Event-triggered document processing, pay-per-execution |
| **AI orchestration** | Azure AI Foundry (gpt-4.1-mini) | Managed LLM endpoint, built-in content safety |
| **Vector search** | Azure AI Search | Integrated vector + keyword hybrid search, semantic ranker |
| **Document storage** | Azure Blob Storage | Cost-effective for PDFs/docs, lifecycle management |
| **Metadata store** | Azure Cosmos DB (serverless) | Low-latency JSON, auto-indexing, serverless cost model |
| **Messaging** | Azure Service Bus (queue) | Reliable document ingestion queue, dead-letter support |
| **Identity** | Microsoft Entra ID + Managed Identity | Zero-credential architecture, RBAC |
| **Observability** | Application Insights + Log Analytics | Distributed tracing, custom metrics, alerting |
| **Networking** | Azure Front Door | Global L7 LB, WAF, SSL offload |
| **IaC** | Bicep | Native ARM, type-safe, modular |

## Step 4: Apply Design Patterns

Selected from the skill's 44 cloud design patterns:

| Pattern | Applied Where | WAF Pillar |
|---------|--------------|------------|
| **Cache-Aside** | LLM response cache (Redis) for repeated queries | PE |
| **Queue-Based Load Leveling** | Service Bus queue buffers document ingestion bursts | R, PE |
| **Retry** | All external calls (AI Search, OpenAI) with exponential backoff + jitter | R |
| **Circuit Breaker** | OpenAI calls — fail fast when quota exhausted | R |
| **Bulkhead** | Separate Container Apps revisions for chat vs admin API | R |
| **Claim Check** | Large documents stored in Blob, only reference passed through queue | R, PE |
| **Gateway Offloading** | Front Door handles SSL, WAF, rate limiting | OE, S |
| **Health Endpoint Monitoring** | `/health` endpoint on Container Apps for readiness/liveness | R, OE |
| **Valet Key** | SAS tokens for direct Blob upload from browser (document ingestion) | S, PE |
| **External Configuration Store** | App Configuration for feature flags and prompt templates | OE |

## Step 5: Address Cross-Cutting Concerns

| Concern | Implementation |
|---------|---------------|
| **Identity & access** | Entra ID for users, Managed Identity for service-to-service, RBAC on all resources |
| **Monitoring** | Application Insights SDK in Container Apps + Functions, custom `rag_latency_ms` metric, Log Analytics workspace |
| **Security** | Private endpoints for Cosmos DB + AI Search, Key Vault for any external API keys, Front Door WAF policy |
| **CI/CD** | GitHub Actions: `bicep build` → `az deployment` → Container Apps revision, canary 10% → 100% |

## Step 6: Validate Against WAF Pillars

| Pillar | Assessment | Score |
|--------|------------|-------|
| **Reliability** | Queue-based ingestion, retry + circuit breaker on LLM, health probes, zone-redundant Container Apps | ✅ Strong |
| **Security** | Zero-credential (managed identity), private endpoints, WAF, Entra RBAC, no secrets in code | ✅ Strong |
| **Cost Optimization** | Container Apps scale-to-zero, Functions consumption, Cosmos serverless, AI Search Basic tier | ✅ Good |
| **Operational Excellence** | IaC (Bicep), CI/CD, structured logging, Application Insights, feature flags | ✅ Good |
| **Performance Efficiency** | Cache-Aside for repeated queries, hybrid search, streaming LLM responses, CDN for static | ✅ Good |

**WAF Tradeoffs** (from skill's tradeoff matrix):
- Reliability ↔ Cost: Zone-redundant Container Apps adds ~20% cost → acceptable at $2K budget
- Security ↔ Performance: Private endpoints add ~2ms latency → negligible vs 3s LLM latency
- Performance ↔ Cost: Redis cache ($50/mo) saves repeated OpenAI calls ($0.15/1K tokens) → ROI positive at >300 queries/day

## Step 7: Document Decisions

### ADR-001: Container Apps over AKS

**Status**: Accepted

**Context**: Need managed compute for a single-team RAG application.

**Decision**: Use Azure Container Apps instead of AKS. Scale-to-zero reduces cost
during off-hours. Dapr integration available if needed later.

**Consequences**:
- (+) Lower operational burden, no cluster management
- (+) Built-in autoscaling, revision management
- (-) Less control over networking and scheduling than AKS
- (-) If workload grows to 50+ microservices, may need to migrate to AKS

### ADR-002: Hybrid Search over Pure Vector

**Status**: Accepted

**Context**: RAG retrieval quality depends on matching user intent to document chunks.

**Decision**: Use Azure AI Search hybrid (vector + BM25 keyword) with semantic ranker reranking.

**Consequences**:
- (+) Higher relevance than vector-only (Microsoft benchmarks show 5-15% improvement)
- (+) Handles exact keyword matches (product codes, error numbers) that vectors miss
- (-) Semantic ranker adds ~200ms latency and cost
- (-) Requires maintaining both vector and inverted indexes

### ADR-003: Serverless Cosmos DB over PostgreSQL

**Status**: Accepted

**Context**: Need a metadata store for document records, user sessions, and conversation history.

**Decision**: Use Cosmos DB serverless (NoSQL API) instead of Azure Database for PostgreSQL.

**Consequences**:
- (+) No minimum cost when idle, pay per RU consumed
- (+) Sub-10ms reads for session lookups
- (+) Automatic indexing, no schema migrations
- (-) No SQL joins — must denormalize or use change feed
- (-) Serverless has 50 RU/s burst limit per partition, may need provisioned at scale

---

## Performance Antipatterns Avoided

From the skill's antipattern catalog:

| Antipattern | How We Avoid It |
|-------------|-----------------|
| **Busy Database** | Cosmos for metadata only; heavy search done in AI Search; LLM in separate service |
| **Chatty I/O** | Batch embedding calls (up to 16 chunks per request), bulk indexing to AI Search |
| **No Caching** | Redis Cache-Aside for repeated queries and embedding results |
| **Synchronous I/O** | Async/await everywhere (Python asyncio), streaming LLM responses |
| **Retry Storm** | Circuit breaker on OpenAI with 30s cool-down, jitter on retries |

---

## Architecture Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Front Door  │────▶│ Container    │────▶│ Azure OpenAI    │
│  (WAF, SSL)  │     │ Apps (Chat)  │     │ (gpt-4.1-mini)  │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │                      ▲
                           ▼                      │
                    ┌──────────────┐        ┌─────┴───────┐
                    │ Azure AI     │        │ Redis Cache  │
                    │ Search       │        │ (Cache-Aside)│
                    │ (hybrid)     │        └─────────────┘
                    └──────────────┘
                           ▲
                           │ Index
                    ┌──────┴───────┐     ┌─────────────────┐
                    │ Azure        │◀────│ Service Bus      │
                    │ Functions    │     │ (ingestion queue)│
                    │ (worker)     │     └────────┬────────┘
                    └──────────────┘              │
                           │              ┌──────┴───────┐
                           ▼              │ Blob Storage  │
                    ┌──────────────┐     │ (documents)   │
                    │ Cosmos DB    │     └──────────────┘
                    │ (metadata)   │
                    └──────────────┘
```

---

## Skill Verification

| Skill Feature | Used in This Design | Evidence |
|---------------|-------------------|----------|
| 10 design principles | Principles 1,2,3,4,6,7,8,9,10 applied | See technology choices and pattern selections |
| 6 architecture styles | Web-Queue-Worker selected with rationale | Step 2 |
| 44 cloud design patterns | 10 patterns applied with WAF mapping | Step 4 |
| Technology choice framework | 11 technology decisions documented | Step 3 |
| Performance antipatterns | 5 antipatterns explicitly avoided | Antipatterns section |
| WAF pillar review | All 5 pillars assessed with tradeoffs | Step 6 |
| Architecture review workflow | All 7 steps completed | Full document |

**Verdict**: The `cloud-solution-architect` skill provides a comprehensive, structured framework
that transforms an AI agent from "generic Azure advice" into a systematic architecture reviewer.
Without this skill, the agent would likely produce a flat list of Azure services without
design pattern mapping, WAF tradeoff analysis, or ADR documentation.
