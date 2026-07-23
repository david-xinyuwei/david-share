# Evidence Contract

## Public object model

Each committed scenario is a sanitized attestation with seven required fields:

| Field | Purpose |
|---|---|
| `id` | Stable public scenario identifier. |
| `runtime` | `python` or `dotnet`. |
| `protocol` | `responses` or `invocations`. |
| `pattern` | Research, graph HITL, durable workflow, or steering. |
| `status` | Must be `passed`; failures remain in private raw evidence and are discussed as lessons. |
| `source_kind` | Must be `sanitized-authenticated-run`. |
| `assertions` | Pattern-specific observable invariants. |

## Deliberately excluded fields

The contract rejects credentials, endpoints, subscription or tenant identifiers, resource IDs, private repository links, user identities, session IDs, response IDs, invocation IDs, VM names, and hostnames.

The event summarizer uses an allowlist instead of a denylist. It retains only protocol-level fields such as event type, phase, output index, status, total, and sequence number. Unknown fields are discarded.

## Integrity

`evidence/manifest.json` stores relative path, byte count, and SHA-256 for every sanitized run and the generated matrix. `lra-evidence manifest` fails on missing files, byte changes, digest changes, duplicate paths, unexpected files, or path traversal.

## Claim boundary

The matrix attests to eight main documented scenarios. It is not a claim that every optional branch, every model, every region, or every production topology was tested.

## Repository surface classification

[scenario-manifest.json](../scenario-manifest.json) separates three meanings:

- `dynamic-runtime`: output is computed from user-supplied JSONL and must vary with the stream.
- `architecture-explainer`: static documentation describes the method and is not an execution result.
- `test-fixture`: a committed regression input for deterministic validation. Sanitized real-run attestations remain identified by `source_kind=sanitized-authenticated-run`; synthetic parser fixtures stay under `tests/fixtures/`.
