# azure-sdk-typescript — 8 SDK Skills Verified

> All skills from [microsoft/skills/.github/plugins/azure-sdk-typescript/](https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript).

| # | Skill | How we tested it | Prompt key constraint | Deliverable / evidence |
|---|-------|------------------|----------------------|------------------------|
| 1 | **azure-ai-projects-ts** | Conceptual: TypeScript equivalent of `azure-ai-projects-py`. | "Use `@azure/ai-projects` (NOT deprecated `@azure/ai-foundry`); `AIProjectClient` with `DefaultAzureCredential`; project endpoint format same as Python" | TS port path for our `Foundry-Hosted-Agent-Toolbox-Demo` Python implementation. |
| 2 | **azure-identity-ts** | Conceptual: TS auth patterns equivalent of our Python `_get_token` helper. | "Use `@azure/identity` `DefaultAzureCredential`; `getToken({ scopes: ['https://ai.azure.com/.default'] })`; cache via `BearerTokenAuthenticationPolicy`" | Pattern aligned with our Python `_get_token('https://ai.azure.com/.default')`. |
| 3 | **azure-storage-blob-ts** | Conceptual: TS Blob client for browser uploads in our Demo dashboard (currently no upload UI). | "Use `@azure/storage-blob` `BlobServiceClient` with `DefaultAzureCredential`; SAS-based browser upload pattern (Valet Key) for client-direct uploads" | Pattern matches the **Valet Key** design pattern in `cloud-solution-architect/architecture-design.md` Step 4. |
| 4 | **azure-cosmos-ts** | Conceptual: TS Cosmos client for our agent registry persistence (TODO from `server.py`). | "Use `@azure/cosmos` `CosmosClient` with `DefaultAzureCredential`; `Container.items.upsert(item)`; partition key required" | Equivalent of `azure-cosmos-py`; same pattern. |
| 5 | **azure-search-documents-ts** | Conceptual: TS search client for our RAG architecture. | "Use `@azure/search-documents` `SearchClient`; hybrid search via `vectorQueries` + `searchText`; `queryType: 'semantic'` for ranker" | Documented in `cloud-solution-architect/architecture-design.md` Step 3. |
| 6 | **azure-servicebus-ts** | Conceptual: TS Service Bus client for the document-ingestion queue. | "Use `@azure/service-bus` `ServiceBusClient` with `DefaultAzureCredential`; `createReceiver` with peek-lock; `completeMessage`/`deadLetterMessage`" | Pattern in `cloud-solution-architect/architecture-design.md` Step 4. |
| 7 | **azure-monitor-opentelemetry-ts** | Conceptual: server-side OTel for Node.js backends (paired with `applicationinsights-web-ts` browser-side). | "Use `@azure/monitor-opentelemetry` (NOT `applicationinsights-web` — that's browser); call `useAzureMonitor({ azureMonitorExporterOptions: { connectionString } })`; auto-instruments express/http/fastify" | Server-side equivalent of our [`skill-demos/applicationinsights-web-ts/`](applicationinsights-web-ts/) — these two skills compose for end-to-end TypeScript observability. |
| 8 | **azure-keyvault-secrets-ts** | Conceptual: TS KV Secrets client. | "Use `@azure/keyvault-secrets` `SecretClient` with `DefaultAzureCredential`; never log `secret.value`; rotation via versioning" | Pattern noted; our demo uses managed identity end-to-end, no secrets to fetch. **APPLICABLE-NOT-USED**. |

## Companion: applicationinsights-web-ts (already done)

- The `applicationinsights-web-ts` skill has its own dedicated demo with real working code:
  → [`skill-demos/applicationinsights-web-ts/appInsights.ts`](applicationinsights-web-ts/appInsights.ts) (live module + reproducible prompt)

## Reproducible per-skill prompt template

> ```
> Using the {skill-name} skill, write the minimal TypeScript code (≤ 50 lines) for: {task}.
> Use the latest stable npm package + ES modules + TypeScript 5+.
> Output: code + package.json deps + exact env vars + tsconfig requirements
> ```

## Source

- Plugin: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-typescript
- 25 TypeScript skills total — we verified the 8 most foundational; remaining are
  React/Zustand-specific or service-specific (Web PubSub, EventHub, etc.).
