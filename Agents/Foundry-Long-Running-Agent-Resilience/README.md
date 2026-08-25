# Resilience for Long-Running Agents on Microsoft Foundry: Evidence from Injected Process Loss

[![Status](https://img.shields.io/badge/Foundry_capability-public_preview-B3541E)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
[![Scope](https://img.shields.io/badge/scope-8_measured_scenarios-1363DF)](#evaluation-what-was-actually-run)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_%2B_.NET-0F8B6D)](#measured-results)
[![Protocols](https://img.shields.io/badge/protocols-Responses_%2B_Invocations-5F4BB6)](#three-integration-options)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

This repository asks one question: **if the process running a long task disappears, can the same task continue from saved progress instead of starting over?** It includes eight fault-injection results, a public-SDK check, a local two-process demo, tests, and reviewable evidence.

The capability is in **public preview**. Every interruption was deliberate, not an outage. Results apply only to the stated July and August 2026 conditions; they are not an SLA or production-readiness claim.

> **Author:** Xinyu Wei (魏新宇)

[中文](README-CN.md) | English

[Use this in your own agent](#use-this-in-your-own-agent) · [Measured scenarios](#evaluation-what-was-actually-run) · [Recovery model](#deep-dive-how-recovery-works) · [Quick start](#quick-start) · [Evidence](#evidence-and-boundaries) · [Official product documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)

---

## Use this in your own agent

Pick your goal first:

| Your goal | Where to go | Azure subscription needed? |
|---|---|---|
| Watch a process die and the same task continue, on my own machine | [Run the local recovery experiment](#run-the-local-recovery-experiment) — one command, about a minute | No |
| Put recovery into my own Hosted Agent code | The six steps in this section | Only when you deploy |
| Reproduce the measured Foundry behavior | [Reproduce on a live Hosted Agent](#reproduce-on-a-live-hosted-agent) | Yes, a non-production test subscription |

There is no package named `Resilience`. The task API lives in `azure-ai-agentserver-core`, under `azure.ai.agentserver.core.tasks`; Responses recovery signals live in `azure-ai-agentserver-responses`. Install the versions the current official sample pins:

`pip install azure-ai-agentserver-core==2.1.0b2 azure-ai-agentserver-responses==2.1.0b2`

Then turn your long-running work into a task handler. The block below is copied verbatim from [`examples/resilience_handler.py`](examples/resilience_handler.py), and the repository gate compares the two so they cannot drift. Your own work replaces the return body; the rest is what makes recovery possible:

```python
from typing import Any, TypedDict

from azure.ai.agentserver.core.tasks import RetryPolicy, TaskContext, task


class WorkInput(TypedDict):
    payload: str


@task(name="resilience-api-usage", timeout=None, retry=RetryPolicy())
async def resilience_api_usage(ctx: TaskContext[WorkInput]) -> dict[str, Any]:
    if ctx.shutdown.is_set():
        return await ctx.exit_for_recovery()

    completed = int(ctx.metadata.get("completed_phases", 0) or 0)
    return {
        "task_id": ctx.task_id,
        "input_id": ctx.input_id,
        "entry_mode": ctx.entry_mode,
        "recovery_count": ctx.recovery_count,
        "retry_attempt": ctx.retry_attempt,
        "completed_phases": completed,
        "payload_length": len(ctx.input["payload"]),
    }
```

**That snippet alone is not enough.** Pasting it into a project does not give you recovery; three things are still missing:

| What else you need | Who provides it | What happens without it |
|---|---|---|
| Resilient-task enablement on the Hosted Agent (public preview) | Platform-side configuration; your code can check the current state with `resilient_tasks_enabled()` | After process loss the call simply fails instead of being re-entered in a new process |
| Your own progress store that can confirm the write | **You provide it** — Foundry does not store your business progress. This repository's local demo uses SQLite, and the official Microsoft sample also uses a separate progress store | After re-entry nothing knows which phase was committed, so the work restarts from the beginning |
| A client that persists the same response / invocation ID and deadline | Your caller code | After a disconnect you can only create a new task, and the original result is unreachable |

`ctx.metadata` holds a small amount of progress marking, not your business data. In core 2.0.0, the version this repository inspected offline, `flush()` returning is not a confirmed write ([why](#the-repository-is-executable-not-just-a-write-up)). For what each layer is responsible for, see [Four layers required for recovery](#four-layers-required-for-recovery).

To add resilience to your code:

1. **Start from an official Hosted Agent sample** and keep its package pins, so deployment, identity, and endpoint are real rather than invented.
2. **Declare the handler** with a typed input and `@task`, as above; use `@multi_turn_task` when the work spans turns.
3. **Read where you are.** `ctx.entry_mode` says whether this is a fresh start or a recovered re-entry, `ctx.task_id` and `ctx.input_id` identify the same work across processes, and `recovery_count` / `retry_attempt` keep process loss separate from retry.
4. **Save business progress after every completed phase** in a store that can confirm the write, and skip phases already recorded. Do not treat `ctx.metadata.flush()` as a confirmed write — see [the pinned-SDK limitation](#the-repository-is-executable-not-just-a-write-up).
5. **Make payments, bookings, writes, and tool calls idempotent**, because [work after the last saved phase can run a second time](#recovery-can-repeat-work-after-the-last-checkpoint).
6. **In the client, persist the response or invocation ID and the deadline**, then reconnect to that same ID instead of creating a new task.

Verify it the way this repository does: kill the process mid-run, and accept the run only when the workload output is complete and the task reports an explicit terminal state.

---

## What Foundry provides, and what your application owns

| Foundry / AgentServer provides | Your application still owns |
|---|---|
| Hosted sandbox, endpoint, identity, session lifecycle and observability | Workload-specific schema, deadlines and terminal acceptance |
| Durable work/input identity, persisted input, lease-based process-loss recovery and handler re-entry | Business checkpoint or watermark that says what is already complete |
| Responses history, background polling and stream replay | Idempotency for payments, bookings, writes and tool side effects |
| Replacement compute after process interruption | Stable work reference, reconnect behavior and observer authentication |

A **runtime instance** is only the currently running copy of your Hosted Agent code; losing it removes process memory and connections, not work persisted outside that process. Microsoft lists **"Run long-lived work resiliently"** as a reason to choose Hosted Agents ([source](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)).

The public documentation defines the platform contract. This repository tests the application side: checkpointing, replay safety, reconnect behavior, and output acceptance after an injected interruption.

**What this resilience changes**

This is not active-active redundancy with two agents doing the same work at once. It is **task-level recovery**: the platform can re-enter the same stored work on replacement compute, while the application resumes from a durable business checkpoint.

| Without task-level recovery | With task-level recovery |
|---|---|
| Process loss removes in-memory state; the client may create a second task | Replacement compute re-enters the same task ID and input |
| A disconnected client cannot tell whether work stopped | The client persists the response/invocation ID and reads the same work again |
| Work waiting for approval may be mistaken for abandoned work | The saved task and approval state remain addressable |
| Repeating a payment, booking, write, or tool call can duplicate the action | The application uses checkpoints and idempotency to recognize completed actions |

The evidence below shows that this capability worked in the tested scenarios. It is not a reliability percentage or SLA; production confidence still requires repeated fault injection against your workload.

## What this repo validates

The measured 18-phase workload came from a **Microsoft private-preview `resilient-research` sample used in July 2026**; it was not invented by this repository. It was a generic deep-research briefing task: the caller supplied a topic, while the measured topic and generated text remain private. The sample processed that topic through 18 fixed phases:

- phases 1-4 framed the research questions, background literature, key researchers, and history;
- phases 5-9 reviewed recent work, debates, evidence quality, related fields, and open problems;
- phases 10-15 covered applications and adoption, funding, ethics, alternatives, risks, and outlook;
- phases 16-18 synthesized the briefing, recommendations, and next steps.

Each phase made one streaming model call and saved the completed-phase count before moving on. The [current public `resilient-research` sample](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/invocations/resilient-research) demonstrates the same workload family, but its configurable plan and defaults have evolved. **The number 18 is a property of the July sample run, not a current product requirement.**

It is also not the only public resilience example. The current official catalog includes [`resilient-approval-gate`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/invocations/resilient-approval-gate) for Invocations and [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) plus [`resilient-steering`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-steering) for Responses.

A research job had 18 planned phases and an expected runtime of about 22 minutes. Fifteen seconds into the run, phase 1 finished, and we terminated Process A. We did not submit a new job. Process B found the same task record, loaded the saved phase-1 progress, and completed phases 2-18. All **18 planned phases completed**. The run recorded 12,248 events with sequence numbers from 1 through 12,248; no sequence number was missing or repeated.

The test is simple: after process loss, can the **same work item** continue and produce complete output? These are observations, not product scores.

| Measured | Observed value — not a score | Why it matters |
|---|---|---|
| Long-run acceptance after injected process loss | All **18 planned phases completed**; 12,248 events had consecutive sequence numbers 1-12,248, with no missing or repeated number | Processes A and B completed the same task record |
| Runtime loss to approval decision accepted | **56 s**, with the original selections intact | In this run, pending approval state survived process replacement |
| Consecutive `HTTP 424` before normal completion | **29** | In this run, a retry budget of 10 would have stopped before completion |
| Scenarios reaching their documented terminal result | **8 of 8**, one accepted run each | Capability validation, not a reliability benchmark |
| Research runs passing workload-output acceptance | **4 of 4** | Transport sequence was gap-free in 3 of 4; that is a transport observation, not a recovery pass rate |

The evidence does **not** establish production availability, SLA, load or concurrency behavior, multi-region recovery, cost, or business correctness. The repo also ships no Microsoft SDK source, complete agent, private API, raw live telemetry, or generic deployment recipe.

### Recovery model at a glance

The figure below is the **official Microsoft diagram**, reproduced unmodified. It shows the published lease-based recovery contract; it is not a disclosure of private service components.

<div align="center"><img src="images/official-lease-recovery-model.png" width="820" alt="Official Microsoft diagram of lease-based recovery: work and input identity, runtime persists input and acquires a lease, handler runs while the runtime renews the lease, the process stops and abandons the lease, a later process reclaims the work record, and the handler re-enters from the start to either rerun or resume from the durable boundary"></div>

<p align="center"><sub><i>"Lease-based recovery of a resilient work item"</i> from <a href="https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience">Resilience for long-running Microsoft Foundry hosted agents</a> © Microsoft, used under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Unmodified. This image is <b>not</b> covered by this repository's MIT license.</sub></p>

### The repository is executable, not just a write-up

| Path | Contract |
|---|---|
| [`examples/resilience_handler.py`](examples/resilience_handler.py) | The actual typed `@task` handler that imports and reads the public recovery context |
| [`examples/resilience_sdk_usage.py`](examples/resilience_sdk_usage.py) | Loads that handler through the real decorator and emits dynamic JSON evidence; `--check` runs without an Azure endpoint |
| [`scripts/recovery_contract_demo.py`](scripts/recovery_contract_demo.py) | Standard-library SQLite recovery reference with two real OS processes, hard process loss, lease reclaim, generation fencing, checkpointing and idempotency |
| [`scripts/verify_public_resilience_api.py`](scripts/verify_public_resilience_api.py) | Checks 18 public symbols and handler rules against the pinned installed SDK packages |
| [`scripts/validate_observations.py`](scripts/validate_observations.py) | Rejects sequence gaps, duplicate/missing output, insufficient terminal proof, and unclassified `424` / `403` conditions |
| [`scripts/validate_repo.py`](scripts/validate_repo.py) | Fail-closed bilingual, evidence-integrity, Data/Log Rich and Code/Test Rich repository gate |
| [`tests/`](tests/) | Twelve tests covering positive, negative, timing, replay, input-integrity and validator refusal paths |
| [`evidence/`](evidence/) | Structured summaries, JSONL events, truth labels, normalized SHA-256 hashes and reproduction index |

Each file below uses the public SDK, or deliberately does not:

| Code | Direct SDK use |
|---|---|
| [`examples/resilience_handler.py`](examples/resilience_handler.py) | Imports `RetryPolicy`, `TaskContext`, and `task`; registers `@task(name="resilience-api-usage")`; reads task/input identities, `ctx.metadata`, entry mode, and recovery/retry counters; exits through `ctx.exit_for_recovery()` on shutdown |
| [`examples/resilience_sdk_usage.py`](examples/resilience_sdk_usage.py) | Imports the handler, runs the real decorator registration, and writes `resilience-sdk-usage.json` |
| [`scripts/verify_public_resilience_api.py`](scripts/verify_public_resilience_api.py) | Imports the same task types plus `TaskMetadata` and Responses recovery signals, then validates the installed package contract |
| [`scripts/recovery_contract_demo.py`](scripts/recovery_contract_demo.py) | Deliberately imports **no Azure SDK**; it tests the recovery algorithm locally with SQLite and two OS processes |
| [Official deployed `resilient-research` handler](https://github.com/microsoft-foundry/foundry-samples/blob/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/invocations/resilient-research/src/resilient-research/agent.py#L246-L285) | Uses `@multi_turn_task`, `TaskContext`, `ctx.metadata`, and the streaming registry inside a complete Microsoft sample |

`--check` proves that the installed package imports and that the real decorator registers the typed handler. It does **not** execute the handler body or prove live recovery; the body runs only inside a Hosted Agent runtime.

**Pinned SDK limitation:** in core 2.0.0, returning from `await ctx.metadata.flush()` is not a durable-write acknowledgement because storage callback failures are logged rather than propagated to the handler. The example therefore reads metadata but does not present `flush()` as a confirmed checkpoint. Production code needs a persistence path that can confirm the write or an operational reconciliation path; the current official sample also uses a separate checkpoint store for in-flight text.

---

## Deep dive: how recovery works

Recovery requires the **task ID, input, and completed progress to be stored outside the process that is currently executing the task**. If that process exits, a replacement process can find the same task record, load the latest saved progress, and continue the unfinished phases.

The flow has three steps:

1. Before execution, the platform stores the task ID and input.
2. After each completed business phase, the application stores the latest completed phase outside the executing process.
3. If that process exits, a replacement process loads the same task record and continues with the next unfinished phase.

Client reconnection only resumes reading status and output; it does not start recovery. In the measured run, Process B had already resumed before the client reconnected.

### Three concepts used below

- **Task record:** a durable record stored outside the executing process. It keeps the same task ID when a replacement process takes over.
- **Checkpoint:** the latest business phase that the application has confirmed complete and stored.
- **Observer:** a client or operator process that reads status and output. If it disconnects, the task can continue running.

### Recovery can repeat work after the last checkpoint

Recovery calls the handler from its entry point. It does not resume a line of code, model call, tool call, or old connection. Work completed after the latest stored checkpoint may therefore run again.

The application must recognize payments, bookings, writes, and tool actions that already completed. Recovery does not create a new task, and an `active` agent version proves deployment—not recovery.

### Three integration options

The three tiers differ mainly in how much lifecycle code you own.

| Tier | What the platform handles | What you still own | Best fit |
|---|---|---|---|
| Microsoft Agent Framework on Foundry hosting | A higher-level integration over Responses; more lifecycle behavior is wired for you | Configuration, framework checkpoints, safe side effects | Teams that prefer more lifecycle integration |
| Responses protocol | OpenAI-compatible contract, conversation history, streaming lifecycle, background execution, polling, cancellation | Opting into resilient behavior, preserving checkpoints, validating output continuity | Conversational and tool-using agents |
| Invocations protocol | Transport and primitives only | Session and task semantics, event schema, checkpoint mapping, polling, recovery behavior | Structured workflows and custom protocols |

Every tier still requires the application to define what "already done" means.

### Official recovery contract and local example

The official contract covers saved work and input, lease expiry, later-process reclaim, handler re-entry, and application checkpoints. The SQLite demo adds version fencing and atomic phase commits as **local design choices**, not claims about Foundry internals.

| Concern | Official published contract | Executable reference in this repository |
|---|---|---|
| Task and input identity | Names one task record and one input; runtime persists the input | SQLite task row plus payload hash |
| Lease lifecycle | Runtime acquires and renews the lease; process stop abandons it; a later process reclaims the work record | Owner, expiry, generation, and conditional claim |
| Progress | Handler re-enters from the start; the application checks a durable checkpoint or watermark | Atomic phase result and checkpoint commit |
| Replay safety | The application remains responsible for preventing duplicate side effects | Idempotency key; matching replay is deduplicated, conflicting replay fails closed |
| Output observation | Stream replay helps reconnecting clients; it is not an application workflow checkpoint | Validator checks sequence, output coverage, and terminal evidence; it does not simulate a service stream |

#### Executable local recovery demo

[`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) uses only the Python standard library. Worker A commits phase 1 and exits through `os._exit(9)`; after lease expiry, Worker B reclaims the same work and completes phases 2-5. It writes a [JSON result](evidence/recovery-contract-demo.json) and [JSONL event log](evidence/recovery-contract-events.jsonl).

Tests enforce four rules: reclaim only pending or expired work; block stale writers; deduplicate identical replay and reject conflicting replay; save phase output and checkpoint in one transaction.

This is a **local test fixture**, not Foundry service code or live-service evidence.

### Four layers required for recovery

Four layers must line up; the process and handler layers remain **public-preview / experimental** APIs.

| Layer | Configuration | What it enables | What it does not do alone |
|---|---|---|---|
| Hosted Agent version | `host: azure.ai.agent` + Responses protocol | Deploys your code and exposes a managed Responses endpoint | Does not make an active handler crash-recoverable |
| Agent process *(public preview)* | Resilient-task enablement | Re-invokes durable work after process loss | Does not know which business step was committed |
| Handler *(public preview)* | `TaskContext` + framework checkpoint hook | Defines the last durable output boundary | Does not make external side effects idempotent |
| Client | `store=True`, `background=True`, same `response.id` | Creates addressable work and lets the caller poll or reattach | Must not replace recovery with a new create call |

#### Start from the official Responses samples

Start from the deployable [`azure.yaml` and source in the official samples](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents), not an incomplete file with invented project, model, or identity values. `azd deploy` handles deployment; it does not save business progress.

#### Enable process recovery

With preview recovery enabled, a stored background response is re-entered in a new process instead of being marked failed after process loss. The public packages expose the relevant interfaces but still mark them experimental; see the [SDK report](evidence/public-sdk-contract.json) for the complete symbol list.

#### Continue from saved business progress

After re-entry, the application reads its last checkpoint. A phase may repeat if the process died before that checkpoint; a saved phase should be skipped.

| Application need | Public API (`azure-ai-agentserver-core` 2.0.0) |
|---|---|
| Identify the work and input | `TaskContext.task_id`, `TaskContext.input_id` |
| Know whether entry is fresh or recovered | `TaskContext.entry_mode` |
| Count recovery separately from retry | `recovery_count`, `retry_attempt` |
| Store a small progress marker | `TaskContext.metadata` |

The observed recovered entry reported `recovery_count=1` and `retry_attempt=0`.

The application pattern is: read identity and progress, rebuild state, run one replay-safe phase, persist its output and external-operation IDs, then advance the checkpoint. Payments, bookings, writes, and tools still require [idempotency](#prevent-duplicate-approvals-and-side-effects).

#### Separate task creation from status observation

This repo tests local progress storage and result validation. Use the [official quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent) for authenticated calls; the repo does not invent your endpoint, identity, store, or workload schema.

| Concern | Application rule |
|---|---|
| Create crash window | Remote create and local persistence of the response ID are not atomic; the tested API also had no lookup by application work key. Preserve an unknown result instead of creating again. Production needs deduplication or reconciliation. |
| Observer restart | Persist `response_id` and deadline, then retrieve the **same response** from a new observer. |
| Recovery authority | Use `response_id` plus workload state, not a high transport cursor. One measured stream restarted at sequence 5. |
| Later turns | `previous_response_id` links sequential turns; concurrent queuing and steering require the resilient-task surface. |
| Read boundary | A read-only adapter is **not** a security sandbox or RBAC boundary. Untrusted observers need a separate service and identity; platform and workload completion remain separate checks. |

Use `azd ai agent invoke` for ordinary calls. Use a tested application client when you must persist IDs and deadlines, restart polling, or enforce workload completion.

---

## Evaluation: what was actually run

Everything above is a design claim until it survives a deliberate interruption. This is how that was tested.

### Current public-preview contract check

Because the July campaign used a private-preview build, the Quick Start also checks pinned public packages in a clean Python 3.13 environment. All **18 of 18** checks passed against `core` 2.0.0, `invocations` 1.0.0, and `responses` 2.0.0; the exact assertions and versions are in the [JSON report](evidence/public-sdk-contract.json).

This proves the installed public API surface—not live recovery. Any failed assertion returns a nonzero exit code.

### Re-checked on the current build (August 2026)

On the current public build, `/tasks`, `/agents`, and `/assistants` returned `200` on a previously enabled subscription. A local 18-phase job then hard-killed Worker A after phase 1; Worker B reclaimed the same work:

| Re-test observation | Value |
|---|---|
| Phases committed before the injected process loss | 1 of 18 |
| Phases committed after recovery, by a different process | 17 of 18 |
| Sequence continuity | 1-18, no gap, no repeated phase |
| Work identity and input identity across processes | Identical |
| `entry_mode` reported by the second process | `recovered` |
| `recovery_count` / `retry_attempt` at recovery | `1` / `0` |
| Reclaim gap | 1.93 s |

The independent `recovery_count=1` and `retry_attempt=0` values confirm that recovery is not handler retry. Phase timing is synthetic and includes no model inference, so the 1.93 seconds is not a performance result. This is still a local two-process test, not live Hosted Agent evidence.

### On a deployed agent, on an ordinary subscription

The next check deployed the official resilient samples and replaced the runtime while work was still running. No new allowlist request or feature registration was made.

| Re-tested scenario | Sample | Interrupted after | Result |
|---|---|---|---|
| Responses, streaming recovery | `resilient-streaming` | 22.6 s | **PASS** — same response id, 3 items, no gap or duplicate |
| Responses, steering | `resilient-steering` | 23.3 s | **PASS** — same response id reached a coherent answer |
| Invocations, research recovery | `resilient-research` | 28.4 s | **PASS** — same `invocation_id` reached `completed` |
| Invocations, approval during runtime replacement | `resilient-approval-gate` | 25.3 s | **PASS** — the decision was accepted (`202`) after replacement, and the task completed |

Three details matter:

- The streaming scenario also passed on a subscription that had never been preview-enabled (`azd up`: 3 minutes 29 seconds). This is one subscription, not proof of universal availability.
- The July `424` pattern did **not** repeat: 26 polls were all `200`. The two interruption paths differed, so both observations remain scoped to their runs.
- New live runs should follow the official sample's exact `core==2.1.0b2` and `responses==2.1.0b2` pins. This repo's 2.0.0 pins reproduce only its historical offline probe.

These were forced runtime replacements, not unplanned crashes. Each of the four current sample families ran once; the July .NET rows were not repeated.

The July campaign ran July 22-23 in one Canada Central project across Python/.NET and Responses/Invocations. Each main scenario ran once (**N=1**). A pass required the same work to reach its documented terminal result with complete event or client evidence; partial recovery, a stalled reconnect, or a similar fresh run did not count.

| # | Runtime / protocol | Scenario and interruption | Required terminal proof | Result |
|---|---|---|---|---|
| 1 | Python / Invocations | Research; runtime-instance loss | Recovery marker, phases 1-18, completed task | **PASS** |
| 2 | Python / Responses | Research; runtime-instance loss | Same response, output indexes 0-17, 18 items | **PASS** |
| 3 | .NET / Invocations | Research; runtime-instance loss | Recovery marker, phases 1-18, completed task | **PASS** |
| 4 | .NET / Responses | Research; runtime-instance loss | Same response, output indexes 0-17, 18 items | **PASS** |
| 5 | Python / Invocations | Approval; runtime loss while suspended | Decision applied after restart, confirmation `TRIP-182336` | **PASS** |
| 6 | Python / Responses | Approval; runtime loss while suspended | Recovery lifecycle, confirmation `TRIP-749637` | **PASS** |
| 7 | Python / Responses | Durable workflow; host replacement | Complete French, Spanish, and round-trip output | **PASS** |
| 8 | Python / Responses | Steering; deliberate interruption | Turn 2 queued, turn 1 ended safely, turn 2 completed | **PASS** |

Optional cancel, delete, and deny branches were outside this matrix and remain unverified here.

---

## Measured results

### A 21.7-minute run across injected process loss

The Python Invocations run reached phase 1 and event 599 in 15 seconds; we then killed its process. Nothing was resubmitted. After reattachment, event 600 arrived on the same work item and phases 2-18 completed.

The run ended after 1,301 seconds. All **18 planned phases completed**. It recorded 12,248 events with consecutive sequence numbers 1-12,248; no number was missing or repeated. Roughly 95% of elapsed time and events came after process loss; that is a work-distribution ratio, not a success score.

### The same interruption, a different protocol

The Python Responses run produced output index 0 before interruption. After a **47-second** reconnect gap, the same response produced indexes 1-17 and completed.

Across 11,584 events, no output index was missing or repeated. This supports continuation of that stored response; it is not a guarantee for every Responses workload.

### Injected runtime loss during a pending human approval

<div align="center"><img src="images/approval-recovery.png" width="820" alt="Measured approval timeline showing 56 seconds from runtime loss to the decision being accepted"></div>

The workflow was waiting for a person; no application step was running. We replaced the runtime at 12:24:27. The decision was accepted **56 seconds** later, and the agent resumed with the same options, returning `TRIP-182336`. A Responses run of the same pattern returned `TRIP-749637`.

> These are deterministic sample tools. The confirmation numbers support that persisted graph state and one approval application survived these runs; they do not establish a general exactly-once guarantee or represent a real airline or hotel booking.

### Twenty-nine `424` responses before completion

During host replacement, the same response returned `HTTP 424 Failed Dependency` **29 times**, then completed with the expected French, Spanish, and round-trip output. A fixed retry budget of ten would have abandoned it too early.

This does **not** make every `424` retryable. It means a still-addressable response under confirmed host replacement should be classified before it is abandoned.

### Interrupting on purpose

A second turn sent during generation was accepted as `queued`. The first turn stopped after its latest completed step had been saved; after seven `in_progress` polls, the second completed with the expected answer. This was cooperative steering, not a cancel/restart race.

---

## Judge recovery by workload output, not transport sequence

Three research runs continued their transport sequence after reattachment. One .NET Responses run **restarted at 5** but still delivered complete output indexes 1-17 on the same response.

| Run | Before interruption | After reattachment | Signal |
|---|---|---|---|
| Invocations / Python | seq 1-599 | seq 600-12,248 | Sequence continued |
| Responses / Python | output index 0 | output indexes 1-17 | Index continued |
| Invocations / .NET | seq 1-738 | seq 739-12,073 | Sequence continued |
| Responses / .NET | output index 0 | output indexes 1-17 | Index continued, **sequence restarted at 5** |

Check output indexes, phases, and durable state. Transport numbering is diagnostic only; and monotonic is not gap-free—`10, 12` still misses 11.

---

## Executable checks and client rules

[`validate_observations.py`](scripts/validate_observations.py) implements the rules below; its [JSON report](evidence/observation-validation.json) records both passing and failing cases.

### Reject gaps and duplicates

`sequence == sorted(sequence)` proves order, not continuity. The corrected check compares adjacent values and the full expected output range.

| Counterexample | Original sorted-order check | Corrected check |
|---|---:|---:|
| Dropped event: `[10, 12]` | `True` | `False` |
| Duplicate event: `[10, 10, 11]` | `True` | `False` |
| Clean stream: `[10, 11, 12]` | `True` | `True` |

The same rule rejects missing or repeated output indexes. Feed it completed items, not every streaming delta, because deltas for one item legitimately share an index.

### A `done` frame is not proof of success

A closed stream can mean success, cancellation, failure, or observer loss. `completion_is_proven` requires service status, an explicit terminal event, and the expected phase count; `{"type": "done"}` alone is insufficient.

### Classify `424` separately from `403`

Continue bounded polling on `424` only when the same work remains addressable and host replacement is confirmed; otherwise fail closed. For `403`, verify read identity and scope, and refresh only after confirmed expiry. The workload deadline—not an arbitrary retry count—sets the stop point.

### Prevent duplicate approvals and side effects

The same approval may arrive again after recovery. The SQLite ledger skips identical replay and rejects conflicting content. Real payment, booking, and write APIs must honor the same idempotency identity or they may still execute twice.

---

## Quick start

**Prerequisites:** Git and Python 3.13. The local experiment and tests require no Azure subscription, credentials, endpoint, or service call. On Windows, clone under a short path such as `$HOME\lra-work` rather than a long OneDrive or project path. The experiment commands below use no shell-specific continuation or activation syntax, so they run in PowerShell, Bash, or zsh; use `python3` instead of `python` only if that is how your platform exposes Python 3.13.

### Run the local recovery experiment

```console
git clone --depth 1 --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git lra-demo
git -C lra-demo sparse-checkout set Agents/Foundry-Long-Running-Agent-Resilience
cd lra-demo/Agents/Foundry-Long-Running-Agent-Resilience

python scripts/recovery_contract_demo.py demo --summary-file .demo-state/summary.json --events-file .demo-state/events.jsonl
```

Done-when is exit code `0` and a summary containing `"passed": true`, `worker_a_exit_code: 9`, `entry_modes: ["fresh", "recovered"]`, and phases `1-5`. Worker A exits through a real `os._exit(9)`; Worker B is a different operating-system process.

### Tests and repository gate

Windows PowerShell:

```powershell
python -m venv .venv
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m pip install --no-input -r requirements-validation.txt
& $python examples\resilience_sdk_usage.py --check
& $python scripts\verify_public_resilience_api.py --quiet
& $python scripts\validate_observations.py self-test
& $python -m unittest discover -s tests -v
& $python scripts\validate_repo.py
```

Linux / macOS:

```bash
python3 -m venv .venv
PYTHON=.venv/bin/python
"$PYTHON" -m pip install --no-input -r requirements-validation.txt
"$PYTHON" examples/resilience_sdk_usage.py --check
"$PYTHON" scripts/verify_public_resilience_api.py --quiet
"$PYTHON" scripts/validate_observations.py self-test
"$PYTHON" -m unittest discover -s tests -v
"$PYTHON" scripts/validate_repo.py
```

Done-when is `PASS: imported azure.ai.agentserver.core.tasks`, `18/18 checks passed`, `Ran 12 tests ... OK`, and `PASS: bilingual parity ... Data/Log Rich ... Code/Test Rich`. These checks validate the pinned public SDK surface and this repository; they do not call a live Hosted Agent.

### Reproduce on a live Hosted Agent

The local commands prove this repository's executable recovery algorithm, **not** the Foundry service. A live service run starts from Microsoft's deployable sample rather than an incomplete project invented here:

1. install Azure CLI and `azd`, then authenticate to a non-production test subscription;
2. clone the official [`resilient-streaming` Hosted Agent sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming);
3. follow that sample's own deployment and invoke instructions; at the sample revision verified for this article, [`3d734b9`](https://github.com/microsoft-foundry/foundry-samples/blob/3d734b93b66f163bea9886d73c6808adc32e68fc/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming/src/resilient-streaming/requirements.txt), `core` and `responses` are both `2.1.0b2` — do **not** replace them with this repository's historical 2.0.0 offline-probe pins;
4. while a stored background response remains `in_progress`, inject runtime-instance replacement;
5. poll the same response ID and validate every expected output item before accepting completion.

This repository intentionally does not invent your Foundry project, model deployment, identity, or endpoint. Live done-when is recovery of the same work identity plus complete workload output and explicit terminal state—not a portal chart or a bare `completed` string.

---

## Failure and recovery playbook

<div align="center"><img src="images/recovery-decision-guide.png" width="560" alt="Decision guide for classifying runtime, client, host-replacement, and observer failures before recovering"></div>

Each row below is a diagnostic starting point, not a universal mapping from symptom to cause. **Read the same task record first, identify the likely layer from durable evidence, and create nothing new until the existing state is known.**

| Symptom | Check first | Do not | Safer action |
|---|---|---|---|
| Stream stops without a terminal event | Read the same work item; the failure may be client, network, or runtime | Resubmit | Reattach if the work remains addressable; require complete output and explicit terminal state |
| Workflow waits for approval | Verify that the suspended work still exists | Rebuild the approval | Send the decision to the recovered work and verify the expected path |
| Repeated `424` | Confirm host replacement and that the same response remains addressable | Treat every `424` as terminal or retryable | Poll that response with bounded backoff |
| `403` on a read | Verify reader identity and scope | Rerun the work | Refresh only after confirmed expiry, then repeat the read |
| Captured log stops | Query durable service state | Infer failure from the last line | Recapture or read the terminal state directly |
| New instruction arrives mid-turn | Check whether steering is enabled | Hard-kill and race a new run | Queue through steering or use the documented cancellation policy |

---

## Design guidance

These are engineering recommendations, not product guarantees:

1. **Save progress at a verifiable boundary.** "Phase 7 of 18 complete" is useful; "somewhere in the middle" is not.
2. **Store the task ID and completed progress outside the executing process.** A replacement process must be able to find the same task record and continue from the latest checkpoint.
3. **Assume at-least-once execution.** Repeating payments, approvals, writes, and tools must be harmless.
4. **Separate reader failure from work failure, and require an explicit terminal result.**
5. **Classify status codes against durable state before acting.**
6. **Distinguish suspended from active work.** Waiting for approval may release compute without losing the task.

---

## Evidence and boundaries

### How these claims were challenged

| Method | Evidence | Outcome |
|---|---|---|
| Same work or fresh rerun? | Same response held output 0 before loss and 1-17 after | Fresh-rerun explanation rejected |
| Cherry-picked examples? | Denominator fixed at eight main scenarios | 8/8 passed; excluded branches are listed |
| Is sequence continuity required? | One accepted .NET run restarted at 5 | Workload output, not sequence alone, is authoritative |
| Is terminal state enough? | Also required checkpoint, injected loss, disconnect, and continuation | Terminal-only evidence rejected |

### What the numbers trace to

| Claim surface | Public evidence | Source boundary |
|---|---|---|
| July and August counts, ranges, durations, confirmations, 424 and steering values | [`historical-observations.json`](evidence/historical-observations.json) | Public-safe aggregates derived from captured runs; N and product status are explicit |
| Current public SDK symbols and handler rules | [`public-sdk-contract.json`](evidence/public-sdk-contract.json) | Real installed-package probe; not live recovery |
| Direct SDK import and `@task` registration | [`resilience-sdk-usage.json`](evidence/resilience-sdk-usage.json) | Generated by the example's own `--check`; not handler execution or live recovery |
| Lease, process loss, generation fence, checkpoint, idempotency | [`recovery-contract-demo.json`](evidence/recovery-contract-demo.json) + [JSONL events](evidence/recovery-contract-events.jsonl) | Real local test fixture; not Foundry service code |
| Gap, duplicate, terminal-state and 424/403 error paths | [`observation-validation.json`](evidence/observation-validation.json) | Executable positive and negative fixtures |
| Scenario truth labels | [`scenario-manifest.json`](evidence/scenario-manifest.json) | Separates dynamic runtime, test fixture, and measured architecture explainer |
| File integrity and reproduction commands | [`manifest.json`](evidence/manifest.json) + [evidence index](evidence/README.md) | SHA-256 covers the public evidence files |

Raw live artifacts remain private because they contain endpoints, work IDs, environment metadata, and generated text. Public evidence contains only the disclosed values; local JSONL uses synthetic data.

### Boundaries

- Every number is an observation from the named July or August run—not a benchmark, guarantee, or SLA.
- July covered eight main scenarios once each; August covered four current sample families once each. Cancel, delete, and deny were not tested.
- The capability moved from private preview to public preview. Check the [current official documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) before designing against it.

### Before you call this production-ready

For a specific workload, require all of the following:

- repeated failure-injection trials with an explicit recovery-time objective and failure budget;
- idempotency tests for every external write, approval, payment, booking, or tool side effect;
- load and concurrency tests that include overlapping turns and replacement compute;
- timeout, cancellation, retention, deletion, and dead-letter policy;
- monitoring that separates runtime, workload, observer, and authentication failures;
- revalidation against current product documentation for your target region, runtime, and protocol.

---

## Related work

| Repository | Relationship |
|---|---|
| [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/) | The broader build, deploy, and operate lifecycle |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | Hosted-agent tools, memory, and skills |
| [Foundry-Agent-ModelOps-Governance](../Foundry-Agent-ModelOps-Governance/) | Operational-plane boundary mapping |

## License

Project-authored content is licensed under [MIT](LICENSE). The official Microsoft diagram is used under CC BY 4.0 and is excluded from the MIT license; see [Third-party notices](THIRD-PARTY-NOTICES.md).
