# Architecture and Responsibility Boundaries

## Four layers

The validated system is easier to understand when four responsibility layers are separated. The first layer is a current public Microsoft Foundry capability; the second records private-preview campaign observations without publishing its implementation.

| Layer | Owner | Publicly verifiable responsibility | Evidence used here |
|---|---|---|---|
| Foundry hosting | Microsoft Foundry | Hosted container lifecycle, dedicated agent identity and endpoint, session/conversation state, protocol routing | Current Microsoft Learn documentation |
| Long-running capability | Preview service + workload integration | Durable task state, reconnectable event delivery, recovery entry and steering pressure observed in the campaign | Author-attested sanitized campaign results |
| Workload | Agent application | Checkpoint meaning, approval ownership, stage outputs, safe cancellation boundaries and business completion | Pattern-specific assertions |
| Observer | Validation client | Failure injection, reconnect cursor, final read, sanitization and publication boundary | Public validator and private-source commitments |

The public repository validates the last two columns. It does not contain the private-preview implementation of the long-running capability.

## Public Foundry concepts

Hosted Agents run application code in Microsoft-managed, session-isolated compute. Public documentation distinguishes:

- **Session**: the compute/state boundary, including persisted `$HOME` and files.
- **Conversation**: the durable message/tool history used primarily by the Responses protocol.
- **Responses**: OpenAI-compatible conversations, platform-managed streaming and optional background execution.
- **Invocations**: arbitrary request/response contracts where the application owns session semantics, event schema and task tracking.
- **Agent identity**: the dedicated Microsoft Entra identity used by agent code at runtime.
- **Project managed identity**: the project-level identity used for platform infrastructure operations.

These public concepts do not, by themselves, prove that an application resumes correctly after a process failure. That proof remains workload-specific.

## Active work and suspended work

Long-running does not always mean that computation is continuously active.

| Work shape | What persists | What wakes it | Pass criterion |
|---|---|---|---|
| Active research | Phase watermark and task/output state | Recovery of pending work | Remaining phases continue and terminal completion is reached |
| Suspended human approval | Graph checkpoint and pending approval | A later approval request | Decision is applied once and the post-approval path completes |
| Durable workflow | Per-stage outputs | Background workflow recovery | Required stage outputs and final round-trip result exist |
| Steering | Conversation state and queued replacement input | A materially different new turn | Old turn ends cooperatively; queued turn completes with a relevant answer |

A suspended approval can survive for a long time without a process running. The durable checkpoint—not process uptime—is the continuity mechanism.

## Protocol ownership

| Concern | Responses | Invocations |
|---|---|---|
| Client contract | OpenAI-compatible `/responses` behavior | Application-defined request and result schema |
| History | Platform-managed conversation history | Application-managed session/task state |
| Long-running entry | Background stored response | Custom durable task contract |
| Stream proof | Same response, output indexes, terminal response status | Application event sequence, recovery marker, terminal task status |
| Reconnect risk | Cursor or lifecycle event differs across SDKs | Application must define replay and terminal semantics |

The campaign therefore uses protocol-specific evidence. It never requires one SDK's event name to appear in another protocol.

## Operational boundary observed in the campaign

During the private-preview campaign, deployed agent versions could be active while durable task operations remained unavailable because the target environment had not yet received service-side preview onboarding. Product-team enablement corrected that condition; no unrelated customer-side resource-provider feature was the remedy.

This is a scoped campaign observation, not a public self-service registration instruction. When a durable task path is unavailable, separate four questions before changing infrastructure:

1. Is the agent version active?
2. Does the protocol endpoint reach the application?
3. Is the durable task/storage capability enabled for the target environment?
4. Is observer authentication valid for the final read?

## Trust model

Three claims must remain separate:

1. **Contract validity**: the public assertions satisfy the exact schema and Python validator.
2. **Artifact integrity**: the manifest detects changes to committed public artifacts.
3. **Execution provenance**: the author attests that the assertions were derived from private authenticated runs; per-scenario commitments can be rechecked against retained private artifacts, but public readers cannot independently replay those private runs.

A SHA-256 manifest proves the second claim, not the third.

## Public sources

- [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Deploy your first hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)
