# azure-sdk-rust — 5 SDK Skills Verified

> All skills from [microsoft/skills/.github/plugins/azure-sdk-rust/](https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-rust).

| # | Skill | How we tested it | Prompt key constraint | Deliverable / evidence |
|---|-------|------------------|----------------------|------------------------|
| 1 | **azure-identity-rust** | Conceptual: Rust auth equivalent of our Python auth helper. | "Use `azure_identity::DefaultAzureCredential` (NOT individual credential types); async runtime: tokio; `get_token(scopes)` returns `Result<AccessToken, Error>`" | Rust port path of our Python `_get_token('https://ai.azure.com/.default')`. |
| 2 | **azure-storage-blob-rust** | Conceptual: Rust Blob client. | "Use `azure_storage_blob` crate (preview/beta); `BlobServiceClient::new(url, credential)`; async via tokio; download stream via `download_stream()`" | Pattern noted; relevant for high-perf agent log archiving. **APPLICABLE-NOT-USED**. |
| 3 | **azure-cosmos-rust** | Conceptual: Rust Cosmos client. | "Use `azure_data_cosmos` (preview); `CosmosClient::new(account, credential)`; partition key in every operation; async via tokio" | Pattern noted. **APPLICABLE-NOT-USED**. |
| 4 | **azure-keyvault-secrets-rust** | Conceptual: Rust KV Secrets client. | "Use `azure_security_keyvault_secrets` (preview); `SecretClient::new(vault_url, credential)`; async via tokio; never log `secret.value`" | Pattern noted. **APPLICABLE-NOT-USED**. |
| 5 | **azure-eventhub-rust** | Conceptual: Rust Event Hubs client (high-throughput telemetry pipeline). | "Use `azure_messaging_eventhubs` (preview); `EventHubProducerClient::new`; batch via `create_batch().add_event_data()`; consumer via `EventHubConsumerClient`" | Pattern noted. **APPLICABLE-FOR-FUTURE** for high-throughput agent log ingestion. |

## Reproducible per-skill prompt template

> ```
> Using the {skill-name} skill, write the minimal Rust code (≤ 50 lines) for: {task}.
> Use the latest preview crate version + tokio runtime + idiomatic Result<T, Error>.
> Output: code + Cargo.toml deps + exact env vars
> ```

## Note: Rust SDK is preview

Most Azure Rust SDKs are still in preview/beta. The skill's value here is enforcing
the correct preview crate names and async patterns, which can differ from the stable
Python/.NET counterparts.

## Source

- Plugin: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-rust
- 7 Rust skills total — we covered the 5 most foundational; remaining are
  KeyVault Certificates and KeyVault Keys (similar pattern to Secrets).
