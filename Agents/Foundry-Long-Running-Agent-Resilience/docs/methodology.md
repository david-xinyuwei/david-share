# Methodology

## Goal

The method answers one question: after a long-running hosted workload loses its current process or connection, can the same logical workload resume from persisted state and reach a valid terminal result?

## Recovery-pattern acceptance sequence

This sequence applies to Research durability and Graph human approval. Durable workflow and steering have different proof contracts below.

1. Start an authenticated hosted workload.
2. Observe a real checkpoint produced by workload code.
3. Inject a process failure while work is active.
4. Observe the client connection drop or temporary host unavailability.
5. Reconnect by using the original logical work reference and the latest cursor.
6. Observe a protocol recovery marker or same-work output continuity.
7. Require the full workload plan and a successful terminal state.
8. Save raw private evidence, then derive a public-safe attestation with identity-bearing fields removed.

## Why deployment status is insufficient

An active deployment proves that the control plane accepted and started an agent version. It does not prove that a workload created durable state, survived a failure, replayed a stream without a gap, resumed human approval, or reached completion.

## Evidence hierarchy

| Level | Evidence | What it proves |
|---|---|---|
| 1 | Deployment is active | The version can be provisioned. |
| 2 | Request accepted | The runtime accepted work. |
| 3 | Checkpoint observed | Workload state crossed a persistence boundary. |
| 4 | Failure and reconnect observed | The client and host experienced the intended disruption. |
| 5 | Recovery marker or same-work continuity | Persisted work resumed rather than starting a replacement task. |
| 6 | Full plan and terminal success | The recovered workload finished its documented main scenario. |

Only Level 6 is counted as a scenario pass in this repository.

## Pattern-specific acceptance

| Pattern | Required evidence |
|---|---|
| Research | Checkpoint before failure, connection loss, original logical work after reconnect, 18 phases/items, explicit terminal success |
| Graph HITL | Durable pending approval, process replacement, one resumed decision, post-approval confirmation and terminal success |
| Durable workflow | Persisted outputs from all required stages and a completed round-trip result |
| Steering | A materially different queued input, cooperative termination of the old turn, and a relevant completed answer for the new turn |

Workflow and steering passes do not imply that those two scenarios executed the Research crash/reconnect sequence.

## Runtime differences

Responses and Invocations expose different proof surfaces. Invocations can emit a dedicated `recovered` event and a terminal task reason. Responses can expose a lifecycle reset, or the stronger observable invariant that the same stored response continues from the first uncheckpointed output index and reaches `completed`.

The validator therefore accepts either a protocol recovery marker or same-response output continuity. It does not force one SDK's event sequence onto another runtime.

## Stream continuity diagnostics

The public event summarizer preserves ordered phase and output-index observations. It reports sequence monotonicity, strict increase, duplicate count, and gaps separately. A monotonic sequence can still contain gaps, so `monotonic=true` must never be interpreted as complete replay. Terminal completion also requires an explicit `completed` status.

## Provenance and integrity

Each public record is an author-attested sanitized result with a commitment derived from retained private source artifacts. The commitment supports a later private drift check. It does not let a public reader authenticate or replay the private execution.

The public manifest has a different purpose: it detects changes to the committed sanitized records and generated matrix. Contract validity, artifact integrity, and execution provenance are separate claims.
