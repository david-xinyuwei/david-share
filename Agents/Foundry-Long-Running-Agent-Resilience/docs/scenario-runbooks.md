# Scenario Proof Runbooks

These runbooks describe observable acceptance evidence. They are not deployment recipes and intentionally omit private packages, endpoints, identities and raw payloads.

## Research over Invocations

**Input shape:** one research topic that expands into 18 documented phases.

**Private execution sequence:** accept durable work → emit checkpoint before the controlled crash → lose the current connection → reconnect to the original logical work → observe recovery → receive phases 1–18 → terminal `done=completed` and normal run completion.

**Public pass fields:** checkpoint, injected failure, connection drop, recovery marker, phase count 18, completed state and terminal reason.

## Research over Responses

**Input shape:** one stored background response with 18 output items.

**Private execution sequence:** create stored background work → persist the first item → inject failure → reconnect to the same response → continue from the first uncheckpointed item → complete with indexes 0–17 and 18 total items.

The Python reconnect exposed a lifecycle reset marker. The .NET reconnect did not replay the same marker at its cursor, so the stronger cross-runtime invariant is same-response output continuity plus a completed final snapshot.

## LangGraph human approval

**Input shape:** a tool-using graph that parks before a sensitive action.

**Private execution sequence:** reach the approval interrupt → persist pending approval → replace the current process → submit one decision → resume the graph once → observe the post-approval confirmation and terminal result.

The proof is durable graph state and exactly-once decision handling. It does not prove a real airline, hotel, payment or reservation-system transaction.

## Durable workflow

**Input shape:** a three-stage translation workflow: English → French → Spanish → English.

**Private execution sequence:** produce and persist every stage output → tolerate temporary host replacement → reach a completed original response → verify the final round-trip output.

This pattern is not evaluated with the research failure/reconnect assertion set. Its proof is durable stage state and terminal workflow output.

## Active-turn steering

**Input shape:** a second, materially different turn submitted while the first turn is still active.

**Private execution sequence:** queue the second turn → cooperatively end the first turn → start the queued turn on the same conversation → require a completed answer relevant to the replacement input.

This pattern proves steering behavior, not crash recovery. A constant or unrelated second answer fails the scenario.

## Observer adjudication

The observer can fail after the workload has already completed. In one campaign path, a final read used an expired observer token; refreshing observer authentication and repeating only the read returned a completed snapshot. The workload was not rerun, and the authentication failure was not reclassified as a workload failure.

## Evidence publication

Raw events remain private. A public record contains:

- the exact scenario contract;
- an author-attested result;
- the number of retained private source artifacts;
- a commitment derived from their SHA-256 values;
- no private file names, endpoints, IDs, payload text or credentials.

The commitment supports later private-to-public drift checks. It does not allow a public reader to reconstruct or independently authenticate the private run.
