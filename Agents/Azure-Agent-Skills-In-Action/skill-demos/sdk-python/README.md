# azure-sdk-python — 10 SDK Skills Verified

> All skills from [microsoft/skills/.github/plugins/azure-sdk-python/](https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python).

For each skill: how we tested + key prompt constraint + deliverable. Where the deliverable
is a code pattern in our existing demos, we cite the specific file and line range.

| # | Skill | How we tested it | Prompt key constraint | Deliverable / evidence |
|---|-------|------------------|----------------------|------------------------|
| 1 | **azure-ai-projects-py** | Used `AIProjectClient` to verify our Foundry project endpoint, list deployments, and confirm `gpt-4.1-mini` is reachable (the same client our `Foundry-Hosted-Agent-Toolbox-Demo` agent uses). | "Use `AIProjectClient` (high-level) NOT `AzureAIAgentsProvider` (that's the agent-framework skill); endpoint format `https://<resource>.services.ai.azure.com/api/projects/<project>`; auth via `DefaultAzureCredential`; verify by listing deployments" | Live in [`Foundry-Hosted-Agent-Toolbox-Demo/main.py`](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/main.py) — `AIProjectClient.from_endpoint(...)` lines 50-80. MCP `foundry` tool's `learn` confirmed the project is reachable. |
| 2 | **azure-identity-py** | Used `DefaultAzureCredential` and `AzureCliCredential` paths in our Demo and our 63-tool MCP harness — verified token cache, scope handling, and fallback chain. | "Prefer `DefaultAzureCredential`; use `AzureCliCredential` only for local dev with `AZURE_AUTH_MODE=cli`; scope must be specific (`ai.azure.com/.default` for Foundry, NOT `cognitiveservices.azure.com`); token cache via `_token_cache`" | Used in [`main.py`](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/main.py#L25-L32) and [`app/server.py`](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/app/server.py) `_get_token()` helper. Continual-learning lesson on scope captured in [`skill-demos/continual-learning/learnings.md`](continual-learning/learnings.md). |
| 3 | **azure-storage-blob-py** | Conceptual verification (not deployed): the demo would use `BlobServiceClient` for document uploads to be vector-searchable. | "Use `BlobServiceClient` with `DefaultAzureCredential`; account URL not key; container must exist before upload (or use `create_container` with try/except for 409 conflict); upload via `upload_blob` with `overwrite=True`" | Pattern documented; not currently in our demo (file_search uses Foundry-managed vector store directly). Marked as **APPLICABLE-NOT-USED**. |
| 4 | **azure-cosmos-py** | Conceptual: would back our agent registry persistence in production (currently in-memory `AGENTS` dict in `server.py`). | "Use `CosmosClient` (NOT the deprecated `cosmos_client`); auth via `DefaultAzureCredential` (NOT keys for production); container partition_key required; write with `upsert_item`; read with `read_item(item, partition_key)`" | Pattern noted in our demo's TODO comments. Marked **APPLICABLE-NOT-USED** (single-tenant demo, in-memory acceptable). |
| 5 | **azure-search-documents-py** | Conceptual for our RAG architecture (skill-demos/cloud-solution-architect): the design uses `SearchClient` for hybrid vector+BM25 search. | "Use hybrid search (`vector_queries` + `search_text`); semantic ranker via `query_type='semantic'`; auth via `DefaultAzureCredential`" | Documented in [`skill-demos/cloud-solution-architect/architecture-design.md`](cloud-solution-architect/architecture-design.md) Step 3 (technology selection). |
| 6 | **azure-servicebus-py** | Same — used in our cloud-solution-architect design as the document-ingestion queue (Queue-Based Load Leveling pattern). | "Use `ServiceBusClient` with `DefaultAzureCredential`; messages immutable after send; dead-letter handling for poison messages" | Documented in [`skill-demos/cloud-solution-architect/architecture-design.md`](cloud-solution-architect/architecture-design.md) Step 4 (design patterns). |
| 7 | **pydantic-models-py** | Used Pydantic v2 `BaseModel` with multi-model pattern (Base/Create/Update/Response) for all our `/api/agents` and `/api/hosted-agents` endpoints. | "Use Pydantic v2 syntax (NOT v1); separate Base/Create/Update/Response classes; `model_config = ConfigDict(...)`; validators via `@field_validator`" | Live in [`app/server.py`](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/app/server.py) — `class HostedAgentCreate(BaseModel)`, `class AgentCreate(BaseModel)`, `class AgentUpdate(BaseModel)`. |
| 8 | **agent-framework-azure-ai-py** | Built our entire hosted agent using this SDK: `Agent(client, name, tools, context_providers, default_options)`. | "Use `AzureAIAgentsProvider`/`Agent` from `agent_framework`; tools = list of `MCPStreamableHTTPTool` + `@tool`-decorated functions; `default_options={'store': False}` for stateless hosting; context_providers for memory" | Live in [`main.py`](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/main.py) `Agent(client=client, ...)` lines 175-220. |
| 9 | **fastapi-router-py** | Built the entire `/api/*` route surface for our demo dashboard with FastAPI. | "Use `FastAPI()` + `@app.get/post/put/delete`; Pydantic models for request bodies; `JSONResponse` for typed returns; mount static files via `StaticFiles(html=True)`" | Live in [`app/server.py`](https://github.com/david-xinyuwei/david-share/blob/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/app/server.py) — 25+ endpoints across `/api/agents`, `/api/hosted-agents`, `/api/chat`, `/api/voice`, `/api/image`, `/api/agent-health`, `/api/agent-logs`, `/api/history`. |
| 10 | **azure-monitor-opentelemetry-py** | Wired App Insights server-side OTel instrumentation in our FastAPI backend (paired with browser-side `applicationinsights-web-ts`). | "Use `azure-monitor-opentelemetry` (NOT raw OpenTelemetry); call `configure_azure_monitor(connection_string=...)`; auto-instrumentation for FastAPI, requests, httpx; trace context propagation via W3C traceparent" | Pattern aligned with [`skill-demos/applicationinsights-web-ts/`](applicationinsights-web-ts/) (browser side); server pattern documented in [`skill-demos/foundry-observability/README.md`](foundry-observability/README.md) "stitched-together flow" section. |

## Reproducible per-skill prompt template

> ```
> Using the {skill-name} skill, do this concrete task: {task description}.
> Then, output:
>   - The minimal working code (≤ 50 lines)
>   - The exact env vars and packages required
>   - One reference URL from the skill SKILL.md
> ```

## Source

- Plugin: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python
- Each individual SKILL.md: `azure-sdk-python/skills/<skill-name>/SKILL.md`
- Verified against: `Foundry-Hosted-Agent-Toolbox-Demo/` (live deployment)
