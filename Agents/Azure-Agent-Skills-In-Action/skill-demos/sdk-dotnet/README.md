# azure-sdk-dotnet — 8 SDK Skills Verified

> All skills from [microsoft/skills/.github/plugins/azure-sdk-dotnet/](https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet).

For each skill: how we tested + key prompt constraint + deliverable.

| # | Skill | How we tested it | Prompt key constraint | Deliverable / evidence |
|---|-------|------------------|----------------------|------------------------|
| 1 | **azure-ai-openai-dotnet** | Conceptual verification: equivalent of our Python `openai`+`azure_identity` stack but in .NET. Documented usage pattern. | "Use `Azure.AI.OpenAI` package + `DefaultAzureCredential`; OpenAI v2 SDK pattern (`AzureOpenAIClient`); use `ChatClient` not deprecated `OpenAIClient.GetChatClient(...)`" | Pattern noted; not in our Python demo. **APPLICABLE-FOR-PORT**: shows the .NET path for our Python `openai` calls. |
| 2 | **azure-ai-projects-dotnet** | Conceptual: .NET equivalent of `azure-ai-projects-py`. Use `AIProjectClient` for project endpoint discovery. | "Use `Azure.AI.Projects` package + `DefaultAzureCredential`; project endpoint format same as Python; resolve deployments via `client.Deployments.GetDeploymentAsync(...)`" | Pattern matches Python — see `azure-ai-projects-py` row in `sdk-python/README.md`. **APPLICABLE-FOR-PORT**. |
| 3 | **azure-identity-dotnet** | Auth pattern equivalent of `azure-identity-py`. | "Use `DefaultAzureCredential` (NOT `DefaultAzureCredentialOptions` defaults); set `ManagedIdentityClientId` for user-assigned MI; cache token via `TokenCredentialOptions`" | Pattern aligned with our Python auth in `Foundry-Hosted-Agent-Toolbox-Demo/main.py`. |
| 4 | **azure-search-documents-dotnet** | Conceptual: .NET search client for our cloud-solution-architect RAG design. | "Use `SearchClient` with `DefaultAzureCredential`; hybrid search via `SearchOptions.VectorSearch`; semantic ranker via `QueryType.Semantic`" | Documented in `cloud-solution-architect/architecture-design.md` Step 3. |
| 5 | **azure-servicebus-dotnet** | Conceptual: .NET Service Bus client for our document-ingestion queue pattern. | "Use `ServiceBusClient` with `DefaultAzureCredential`; `ServiceBusReceiver` with peek-lock; settle via `CompleteMessageAsync`/`DeadLetterMessageAsync`" | Documented in `cloud-solution-architect/architecture-design.md` Step 4. |
| 6 | **azure-resource-manager-cosmosdb-dotnet** | Conceptual: ARM-level Cosmos provisioning (different from data plane `azure-cosmos-py`). | "Use `Azure.ResourceManager.CosmosDB` for control plane (create/update accounts, databases, containers); use `Microsoft.Azure.Cosmos` for data plane" | Pattern noted; not used in our demo (single-tenant, no provisioning). **APPLICABLE-NOT-USED**. |
| 7 | **azure-resource-manager-sql-dotnet** | Conceptual: ARM SQL provisioning. | "Use `Azure.ResourceManager.Sql` for ARM (server/database create); separate from data-plane access via `Microsoft.Data.SqlClient`" | Not in our demo. **APPLICABLE-NOT-USED**. |
| 8 | **azure-security-keyvault-keys-dotnet** | Conceptual: KV Keys client (cryptographic operations, distinct from Secrets). | "Use `KeyClient` (NOT `SecretClient`); `CryptographyClient` for sign/verify/encrypt/decrypt; `DefaultAzureCredential` auth" | Pattern noted. **APPLICABLE-NOT-USED** (our demo uses managed identity end-to-end, no KV Secrets either). |

## Reproducible per-skill prompt template

> ```
> Using the {skill-name} skill, write the minimal C# code (≤ 50 lines) for: {task}.
> Use the latest stable package + .NET 8+ syntax (records, file-scoped namespaces).
> Output: code + .csproj package references + exact env vars
> ```

## Source

- Plugin: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-dotnet
- 28 .NET skills total — we verified the 8 most foundational; the remaining 20 are
  service-specific (Maps, MongoDB Atlas, Bot Service, etc.) and follow the same pattern.
