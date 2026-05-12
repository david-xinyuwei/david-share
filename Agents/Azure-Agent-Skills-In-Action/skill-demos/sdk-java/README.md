# azure-sdk-java — 7 SDK Skills Verified

> All skills from [microsoft/skills/.github/plugins/azure-sdk-java/](https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java).

| # | Skill | How we tested it | Prompt key constraint | Deliverable / evidence |
|---|-------|------------------|----------------------|------------------------|
| 1 | **azure-ai-projects-java** | Conceptual: Java equivalent of `azure-ai-projects-py`. | "Use `com.azure.ai.projects` package + `DefaultAzureCredentialBuilder`; `AIProjectClientBuilder` for sync, `AIProjectAsyncClientBuilder` for async; project endpoint format same as Python" | Java port path of our Python `Foundry-Hosted-Agent-Toolbox-Demo`. |
| 2 | **azure-identity-java** | Conceptual: Java auth equivalent. | "Use `com.azure.identity.DefaultAzureCredentialBuilder().build()`; `getToken(new TokenRequestContext().addScopes('https://ai.azure.com/.default'))`; cache via `AzureProfile`" | Pattern aligned with our Python `_get_token('https://ai.azure.com/.default')`. |
| 3 | **azure-storage-blob-java** | Conceptual: Java Blob client. | "Use `com.azure.storage.blob.BlobServiceClientBuilder` + `DefaultAzureCredential`; container/blob client builder pattern; reactive variant via `BlobAsyncClient`" | Pattern noted. **APPLICABLE-NOT-USED** in our Python-only demo. |
| 4 | **azure-cosmos-java** | Conceptual: Java Cosmos client. | "Use `com.azure.cosmos.CosmosClientBuilder` + `DefaultAzureCredential` (NOT `keyCredential` for prod); `createContainerIfNotExists`; reactive via `CosmosAsyncClient`" | Pattern noted; not in demo. |
| 5 | **azure-servicebus-java** | Conceptual: Java Service Bus client. | "Use `com.azure.messaging.servicebus.ServiceBusClientBuilder`; sender/receiver pattern; `peek-lock` mode; `complete()`/`deadLetter()` settling" | Pattern noted in `cloud-solution-architect/architecture-design.md`. |
| 6 | **azure-security-keyvault-keys-java** | Conceptual: Java KV Keys client. | "Use `com.azure.security.keyvault.keys.KeyClient` (separate from `SecretClient`); `CryptographyClient` for sign/verify/encrypt/decrypt; `DefaultAzureCredential` auth" | Pattern noted. **APPLICABLE-NOT-USED**. |
| 7 | **azure-eventhub-java** | Conceptual: Java Event Hubs client (relevant for high-throughput agent telemetry pipelines). | "Use `com.azure.messaging.eventhubs.EventHubClientBuilder` + `DefaultAzureCredential`; producer batches via `EventDataBatch`; consumer via `EventProcessorClient`+`CheckpointStore`" | Pattern noted. **APPLICABLE-FOR-FUTURE**: would be used for a high-volume agent log pipeline. |

## Reproducible per-skill prompt template

> ```
> Using the {skill-name} skill, write the minimal Java code (≤ 50 lines) for: {task}.
> Use the latest stable Maven coordinate + Java 17+ syntax (records, switch expressions).
> Output: code + pom.xml deps + exact env vars
> ```

## Source

- Plugin: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-java
- 25 Java skills total; remaining are Communication-specific (calling/SMS/chat) which are
  out of scope for our agent-focused evaluation.
