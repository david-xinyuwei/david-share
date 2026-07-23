# Evidence Contract

## Public object model

Each committed scenario is an author-attested sanitized record with nine required fields:

| Field | Purpose |
|---|---|
| `id` | Stable public scenario identifier. |
| `runtime` | `python` or `dotnet`. |
| `protocol` | `responses` or `invocations`. |
| `pattern` | Research, graph HITL, durable workflow, or steering. |
| `status` | Must be `passed`; failures remain in private raw evidence and are discussed as lessons. |
| `source_kind` | Must be `author-attested-sanitized-run`. |
| `provenance` | Author-attestation type, campaign date, private source count, and a private-source commitment. |
| `assertions` | Pattern-specific observable invariants. |
| `scope` | Must remain limited to the documented main scenario. |

## Deliberately excluded fields

The contract rejects credentials, endpoints, subscription or tenant identifiers, resource IDs, private repository links, user identities, session IDs, response IDs, invocation IDs, VM names, and hostnames.

The event summarizer uses an allowlist instead of a denylist. It retains only protocol-level fields such as event type, phase, output index, status, total, and sequence number. Unknown fields are discarded.

Ordered phase/index observations and sequence diagnostics are retained in the summary. `monotonic` means nondecreasing order; it does not imply that there are no gaps. `gap_count`, `duplicate_count`, and `strictly_increasing` must be evaluated separately.

## Integrity

`evidence/manifest.json` stores relative path, byte count, and SHA-256 for every sanitized run and the generated matrix. `lra-evidence manifest` fails on missing files, byte changes, digest changes, duplicate paths, unexpected files, or path traversal.

The per-scenario `private_source_commitment_sha256` is derived from the SHA-256 values of retained private artifacts. It can detect private-source drift when the author rechecks those artifacts. It does not disclose the source files and does not provide public chain-of-custody proof of execution.

## Claim boundary

The matrix attests to eight main documented scenarios. It is not a claim that every optional branch, every model, every region, or every production topology was tested.

## Repository surface classification

[scenario-manifest.json](../scenario-manifest.json) separates four meanings:

- `dynamic-runtime`: output is computed from user-supplied JSONL and must vary with the stream.
- `architecture-explainer`: static documentation describes the method and is not an execution result.
- `sanitized-runtime-attestation`: an author-attested campaign result with a private-source commitment.
- `test-fixture`: a synthetic parser input under `tests/fixtures/`; it never counts as campaign evidence.
