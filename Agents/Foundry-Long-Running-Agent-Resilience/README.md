# Resilience for Long-Running Agents on Microsoft Foundry: Evidence from Injected Process Loss

[![Status](https://img.shields.io/badge/Foundry_capability-public_preview-B3541E)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
[![Scope](https://img.shields.io/badge/scope-8_measured_scenarios-1363DF)](#3-method-what-was-actually-run)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_%2B_.NET-0F8B6D)](#4-results)
[![Protocols](https://img.shields.io/badge/protocols-Responses_%2B_Invocations-5F4BB6)](#23-where-you-plug-in)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

Fifteen seconds into a twenty-two minute job, a research agent had just finished the first of eighteen phases when we deliberately destroyed the process running it. Nothing was resubmitted. Twenty-one minutes later the same job reported completion — all eighteen phases delivered, 12,248 stream events, no gap and no repeated phase.

After the original process was destroyed, replacement compute completed the remaining seventeen phases; the run ended **18 of 18**.

**Every interruption on this page was injected on purpose; none of them is an observed outage.** When continuity matters, designs for long-running workloads should account for possible process interruptions such as restarts, crashes, out-of-memory terminations, or redeployments — the cases Microsoft's documentation says resilient execution is designed to recover from. This does not mean that every run will lose its process. The engineering question is whether the *work* survives if one does. That is what these eight deliberately injected scenarios measured.

This page explains why these observed runs completed, which signals supported that conclusion, and which seemingly reasonable responses could have abandoned or duplicated the work.

> **What this is.** Measured recovery behavior for long-running agent execution on Microsoft Foundry Hosted Agents, plus public-safe executable checks and evidence. The capability is now in **public preview** with an [official concept page](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience). The eight measured scenarios were run in July on the earlier private-preview build, so each number remains dated evidence rather than a claim about today's build.
> **What it is not.** It ships **no Microsoft SDK source, complete agent implementation, end-to-end deployment recipe, private API schema, or raw live telemetry**. The local recovery program is a real two-process test fixture, not Foundry service code or live-service proof. Official guidance carries no SLA and does not recommend preview for production — the same position taken in Section 9.4.

> **Author:** Xinyu Wei (魏新宇)

[中文](README-CN.md) | English | [Hosted agents overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

[Start here](#start-here-reproduce-it-in-your-own-environment) · [What this repo validates](#what-this-repo-validates) · [Measured results](#4-results) · [Evidence](#92-what-the-numbers-trace-to) · [Production gate](#94-before-you-call-this-production-ready)

---

## Start here: reproduce it in your own environment

**Prerequisites:** Git and Python 3.13. Path A needs no Azure subscription, credentials, endpoint, or network call after cloning.

### Path A — local recovery in about three minutes

```powershell
# Keep the clone outside a long OneDrive/project path on Windows.
$work = Join-Path $HOME "lra-work"
New-Item -ItemType Directory -Force $work | Out-Null
Set-Location $work

git clone --depth 1 --filter=blob:none --sparse `
  https://github.com/david-xinyuwei/david-share.git lra-demo
Set-Location lra-demo
git sparse-checkout set Agents/Foundry-Long-Running-Agent-Resilience
Set-Location Agents\Foundry-Long-Running-Agent-Resilience

# No Azure packages or credentials are required for this path.
python scripts\recovery_contract_demo.py demo `
  --summary-file .demo-state\summary.json `
  --events-file .demo-state\events.jsonl
Get-Content .demo-state\summary.json

# Path B — optional full SDK, test, and L5 validation.
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-validation.txt
.\.venv\Scripts\python scripts\verify_public_resilience_api.py --quiet
.\.venv\Scripts\python scripts\validate_observations.py self-test
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python scripts\validate_repo.py
```

Linux / macOS:

```bash
mkdir -p "$HOME/lra-work" && cd "$HOME/lra-work"
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/david-xinyuwei/david-share.git lra-demo
cd lra-demo
git sparse-checkout set Agents/Foundry-Long-Running-Agent-Resilience
cd Agents/Foundry-Long-Running-Agent-Resilience

python3 scripts/recovery_contract_demo.py demo \
  --summary-file .demo-state/summary.json \
  --events-file .demo-state/events.jsonl
cat .demo-state/summary.json

# Path B — optional: full SDK, tests, and L5 validation.
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-validation.txt
./.venv/bin/python scripts/verify_public_resilience_api.py --quiet
./.venv/bin/python scripts/validate_observations.py self-test
./.venv/bin/python -m unittest discover -s tests -v
./.venv/bin/python scripts/validate_repo.py
```

**Expected local result:**

- recovery JSON: `"passed": true`, `worker_a_exit_code: 9`, `entry_modes: ["fresh", "recovered"]`, phases `1-5`;
- SDK probe: `18/18 checks passed`;
- tests: `Ran 12 tests ... OK`;
- repository gate: `PASS: bilingual parity ... Data/Log Rich ... Code/Test Rich`.

**Path A done-when:** the recovery command exits `0`; the JSON says `"passed": true`, exit code `9`, `fresh → recovered`, and phases `1-5`.

**Path B done-when:** Path A passes, then the SDK probe reports `18/18`, all 12 tests pass, and the repository gate exits `0`. A rendered chart or a bare `completed` string without workload checks does not count.

### Path C — reproduce on a live Hosted Agent

The local program proves this repository's executable recovery algorithm, **not** the Foundry service. For a live Azure run:

1. install Azure CLI and `azd`, then authenticate to your test subscription;
2. start from the official [`resilient-streaming` Hosted Agent sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming);
3. use that sample's current pins — at sample commit [`3d734b9`](https://github.com/microsoft-foundry/foundry-samples/blob/3d734b93b66f163bea9886d73c6808adc32e68fc/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming/src/resilient-streaming/requirements.txt), `core` and `responses` are `2.1.0b2`; do **not** replace them with this repo's 2.0.0 offline-probe pins;
4. follow that sample's own `azd up` and invoke instructions;
5. inject runtime replacement only in a non-production test environment, then poll the same response ID and validate its output items.

This repository intentionally does not invent your Foundry project, model deployment, identity, or endpoint.

| Surface | Scenario type | What it proves | What it does not prove |
|---|---|---|---|
| Local SQLite recovery | test-fixture | Real OS process loss, lease expiry/reclaim, generation fencing, checkpoint and idempotency in this executable reference | Microsoft Foundry private implementation |
| Public SDK contract probe | dynamic-runtime | Installed pinned packages expose the 18 checked public symbols and validation rules | Live Hosted Agent recovery |
| Historical observations | measured aggregate / architecture-explainer | Dated public-safe values derived from July and August captures | Reliability benchmark, SLA, or a reusable deployment recipe |

If your goal is only to reproduce the behavior, you can stop here. Machine-readable data, logs, hashes, and the truth contract are in the [evidence index](evidence/README.md); the remaining sections explain the design and measured Azure observations.

---

## What this repo validates

Long-running agent work remains exposed to process-lifetime changes for longer than a short call. One possible failure mode is that **the execution process disappears while the logical work remains valid.** If a client treats every such interruption as terminal and resubmits, it can abandon addressable work, start a second run, and duplicate an external action.

The model evaluated here separates the **logical work** from the **process that executes it**. In the eight accepted runs, durable work identity, persisted input, and checkpointed progress remained available across the injected process loss; replacement compute re-entered from the recorded checkpoint. Across two languages, two protocols, and four kinds of interruption, all eight runs reached their documented terminal result.

The table mixes acceptance results, durations, and event counts; **it is not a percentage scorecard**.

| Measured | Observed value — not a score | Why it matters |
|---|---|---|
| Long-run acceptance after injected process loss | **18 of 18 phases**; sequence 1-12,248 with no gap or repeated phase | The same logical work reached its documented terminal result |
| Runtime loss to approval decision accepted | **56 s**, with the original selections intact | In this run, pending approval state survived process replacement |
| Consecutive `HTTP 424` before normal completion | **29** | In this run, a retry budget of 10 would have stopped before completion |
| Scenarios reaching their documented terminal result | **8 of 8**, one accepted run each | Capability validation, not a reliability benchmark |
| Research runs passing workload-output acceptance | **4 of 4** | Transport sequence was gap-free in 3 of 4; that is a transport observation, not a recovery pass rate |

**What this evidence does not establish:** production availability, SLA, behavior under load or concurrency, multi-region recovery, cost, and business correctness. Each scenario ran once. This is a reason to fund a controlled evaluation, not a production sign-off.

---

## 1. What Foundry provides, and what your application owns

| Foundry / AgentServer provides | Your application still owns |
|---|---|
| Hosted sandbox, endpoint, identity, session lifecycle and observability | Workload-specific schema, deadlines and terminal acceptance |
| Durable work/input identity, persisted input, lease-based process-loss recovery and handler re-entry | Business checkpoint or watermark that says what is already complete |
| Responses history, background polling and stream replay | Idempotency for payments, bookings, writes and tool side effects |
| Replacement compute after process interruption | Stable work reference, reconnect behavior and observer authentication |

A **runtime instance** is only the currently running copy of your Hosted Agent code; losing it removes process memory and connections, not work persisted outside that process. This recovery model uses a Hosted Agent because it re-enters application-owned code. Microsoft lists **"Run long-lived work resiliently"** as a reason to choose Hosted Agents ([source](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)).

Public documentation describes the platform contract. This repo tests the remaining application question: whether its checkpoint, replay safety and output acceptance behave correctly after an injected interruption.

---

## 2. How it works: address the work, not the process

<div align="center"><img src="images/resilience-architecture.png" width="820" alt="Conceptual recovery flow showing how logical work survives loss of a Hosted Agent runtime instance"></div>

<p align="center"><sub>Project-authored conceptual overview — not an official Microsoft architecture diagram. The official unmodified Microsoft model appears in Section 2.4.</sub></p>

Recovery rests on a single idea: **give the work an identity that outlives the process, and re-enter that work rather than resurrecting the process.**

The conceptual flow below has seven steps. The client starts one logical work item and keeps its stable reference. Before execution begins, the long-running layer persists that identity, the input, and the lease metadata needed to find the work again. As the agent runs, it records business progress — a phase number, a watermark, an approval state, or a pointer to external state. Then the runtime instance is lost: the process, its memory, and the socket vanish, but the durable record does not. Foundry provides replacement compute, the same logical work is re-entered with recovery context, the application loads its checkpoint and continues from a known boundary, and the client reattaches to confirm continuity.

Walk the measured 18-phase run through those steps and the ordering becomes concrete. Steps one through three covered phase 1. Step four destroyed the process. Steps five and six carried phases 2 through 18. The client reattached only at step seven: **in this run, recovery progressed before the client reattached.** Reattachment resumed observation, not execution. A dropped client stream therefore did not establish workload failure in this run; durable state and workload output did.

### 2.1 Three terms used below

- **Logical work:** the durable job or conversation, identified independently of one process.
- **Checkpoint:** the application-owned marker for the last complete, replay-safe business unit.
- **Observer:** the client or operator reading status/output; observer failure does not by itself prove workload failure.

Everything else in the article maps back to these three terms.

### 2.2 Recovery is at-least-once; applications must make replay safe

A recovered handler re-enters with the same identity and input. It does **not** replay your code's execution, and it does not re-run individual model or tool calls from where they stopped.

The unavoidable design implication is that work performed after the last durable checkpoint can run again. Checkpoint granularity defines the replay window, and idempotency keys, compare-and-set writes, and durable external operation IDs are what stop that replay from becoming a duplicate booking, payment, or write.

So it is worth being explicit about what recovery is *not*. It is not resurrection of the old socket. It is not deterministic replay. It is not resubmitting the original request as a new job. It is not proven by an agent version showing `active`, which only means the control plane accepted a deployment. For workloads that can commit external side effects, re-entry is not safe unless those committed effects can be recognized and skipped.

### 2.3 Where you plug in

The model is framework-agnostic. What changes between tiers is how much of it you wire yourself.

| Tier | What the platform handles | What you still own | Best fit |
|---|---|---|---|
| Microsoft Agent Framework on Foundry hosting | A higher-level integration over Responses; more lifecycle behavior is wired for you | Configuration, framework checkpoints, safe side effects | Teams that prefer more lifecycle integration |
| Responses protocol | OpenAI-compatible contract, conversation history, streaming lifecycle, background execution, polling, cancellation | Opting into resilient behavior, preserving checkpoints, validating output continuity | Conversational and tool-using agents |
| Invocations protocol | Transport and primitives only | Session and task semantics, event schema, checkpoint mapping, polling, recovery behavior | Structured workflows and custom protocols |

LangGraph, Microsoft Agent Framework, and hand-written orchestration can all participate. None of them removes the application's obligation to define what "already done" means.

### 2.4 Public recovery contract and repository reference model

The official contract describes durable work/input identities, persisted input, lease renewal and abandonment, later-process reclaim, handler re-entry, and application-owned checkpoints. This repository's SQLite program adds generation fencing and atomic phase commits as **reference-implementation choices**; they are not claims about Microsoft Foundry's private service topology or storage schema.

| Concern | Official published contract | Executable reference in this repository |
|---|---|---|
| Work and input identity | Names the logical work and one input; runtime persists the input | SQLite work row plus payload hash |
| Lease lifecycle | Runtime acquires and renews the lease; process stop abandons it; a later process reclaims the work record | Owner, expiry, generation, and conditional claim |
| Progress | Handler re-enters from the start; the application checks a durable checkpoint or watermark | Atomic phase result and checkpoint commit |
| Replay safety | The application remains responsible for preventing duplicate side effects | Idempotency key; matching replay is deduplicated, conflicting replay fails closed |
| Output observation | Stream replay helps reconnecting clients; it is not an application workflow checkpoint | Validator checks sequence, output coverage, and terminal evidence; it does not simulate a service stream |

The figure below is the **official Microsoft diagram**, reproduced unmodified. It is a conceptual product-contract model, not a disclosure of private service components.

<div align="center"><img src="images/official-lease-recovery-model.png" width="820" alt="Official Microsoft diagram of lease-based recovery: work and input identity, runtime persists input and acquires a lease, handler runs while the runtime renews the lease, the process stops and abandons the lease, a later process reclaims the work record, and the handler re-enters from the start to either rerun or resume from the durable boundary"></div>

<p align="center"><sub><i>"Lease-based recovery of a resilient work item"</i> from <a href="https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience">Resilience for long-running Microsoft Foundry hosted agents</a> © Microsoft, used under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Unmodified. This image is <b>not</b> covered by this repository's MIT license.</sub></p>

#### 2.4.1 Executable recovery-contract reference

The earlier non-runnable sketch has been removed. [`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) is executable standard-library code: SQLite persists the work and input, Worker A commits phase 1 and exits through `os._exit(9)`, its lease expires, and a separate Worker B conditionally reclaims generation 2 and commits phases 2-5. The program writes a derived [JSON summary](evidence/recovery-contract-demo.json) and [JSONL event log](evidence/recovery-contract-events.jsonl); six unit tests cover lease-clock timing, existing-state protection, hard loss, stale-generation fencing, idempotent/conflicting replay, and input-differential behavior.

This program is a **test fixture**. It proves that the repository's reference algorithm executes as documented; it is not Microsoft Foundry service code or live Hosted Agent evidence.

Four invariants are implemented and tested:

1. **Reclaim is conditional.** Only pending work or a running record with an expired lease can be claimed.
2. **Every durable write is generation-fenced.** The store verifies owner, generation, status, and lease expiry; each phase commit renews the reference lease.
3. **Phase replay is idempotent.** The same phase key and result are deduplicated; conflicting content fails closed.
4. **One transaction owns progress.** SQLite records the phase result, idempotency key, worker generation, and checkpoint atomically.

The LRA runtime gets the same work back into a handler. It cannot infer whether a payment, booking, tool call, or workflow node was already committed. That is why the application checkpoint and side-effect ledger are part of the recovery contract even though they are not the lease engine itself.

### 2.5 From Hosted Agent configuration to a recoverable call

The feature is not enabled by one magic switch in the portal. Four layers must line up. All four now have public surfaces, but the middle two remain **public-preview / experimental** APIs and still require application-owned checkpoint and side-effect design.

| Layer | Configuration | What it enables | What it does not do alone |
|---|---|---|---|
| Hosted Agent version | `host: azure.ai.agent` + Responses protocol | Deploys your code and exposes a managed Responses endpoint | Does not make an active handler crash-recoverable |
| Agent process *(public preview)* | Resilient-task enablement | Re-invokes durable work after process loss | Does not know which business step was committed |
| Handler *(public preview)* | `TaskContext` + framework checkpoint hook | Defines the last durable output boundary | Does not make external side effects idempotent |
| Client | `store=True`, `background=True`, same `response.id` | Creates addressable work and lets the caller poll or reattach | Must not replace recovery with a new create call |

#### 2.5.1 Declare a Hosted Agent with the Responses protocol

This repository does not ship an incomplete `azure.yaml` with invented project, model, identity, or resource values. Start from the deployable [`azure.yaml` and application source in the official Hosted Agent samples](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents), then apply the public-preview recovery configuration supported by the current sample and SDK version.

In a complete azd project, `azd deploy` reads the real service definition, creates a Hosted Agent version, and routes the declared protocol endpoint. CPU, memory, image or source packaging, model selection, and identity belong to that version definition; they are not recovery checkpoints.

#### 2.5.2 Opt the agent process into recovery

The evaluated build added a **preview recovery opt-in** to the Responses host. That option changed a stored background response from “mark failed after a crash” to “re-invoke the handler in the next process lifetime.” A separate preview steering option allowed an overlapping follow-up turn to queue and cooperatively stop the current turn.

The exact constructor fields were absent from the public PyPI interface at evaluation time. **The public packages tested here now expose the relevant symbols.** Against `azure-ai-agentserver-core` 2.0.0, the resilient-task surface exported `task`, `multi_turn_task`, `Task`, `MultiTurnTask`, `TaskContext`, `TaskMetadata`, `RetryPolicy`, `resilient_tasks_enabled`, and `set_resilient_tasks_enabled`; the Responses package exported `ExitForRecoverySignal` and `ResponseExitForRecovery`. The SDK marked these as experimental at import time, consistent with public-preview status. Check the current package before designing against any specific field.

#### 2.5.3 Resume from a business checkpoint

Re-invocation alone starts the handler again. In the evaluated sample, the handler received recovery context, loaded the last framework snapshot, and committed a framework checkpoint only after a complete business unit was durable. The evaluated sample made one completed phase equal one finalized output item. In that sample, a process loss before the checkpoint repeated the phase; a loss after the checkpoint caused recovery to skip it.

The public SDK now exposes fields and methods corresponding to these concepts, consistent with the model above:

| Contract described here | Public API (verified, `azure-ai-agentserver-core` 2.0.0) |
|---|---|
| Durable work identity | `TaskContext.task_id` |
| Input identity | `TaskContext.input_id` |
| Recovered re-entry, not a retry | `TaskContext.entry_mode` is `Literal["fresh", "resumed", "recovered"]`, and `recovery_count` is a **separate** field from `retry_attempt` |
| Small durable checkpoint index | `TaskContext.metadata` (`TaskMetadata`, with `get` / `set` / `increment` / `append` / `flush`) |
| Cooperative stop and deferral | `TaskContext.shutdown`, `TaskContext.exit_for_recovery()` |
| Steering | `TaskContext.is_steered_turn`, `TaskContext.pending_input_count` |
| Bounded retry budget, separate from recovery | `RetryPolicy` passed to `@task(retry=...)` |

The tested recovered entry made that distinction concrete: after replacement it reported `recovery_count=1` and `retry_attempt=0`. This supports treating recovery separately from handler retry; exact counter values remain observations from that run. A handler's first argument must be named `ctx` and declare a parameterized `TaskContext[Input]`; in the tested package, the decorator rejected a different argument name or a bare `TaskContext`.

The public API mapping is consistent with the official model in Section 2.4. Generation fencing in the local SQLite program remains a repository-owned reference choice, not a claim about private Foundry implementation.

The application pattern is unchanged:

1. Read the stable logical-work identity and last committed business watermark.
2. Reconstruct application state from the framework snapshot or an external store.
3. Run exactly one replay-safe phase.
4. Persist its output and side-effect identifiers.
5. Advance the framework checkpoint only after step 4 succeeds.

Any payment, booking, write, or tool action inside the replay window still needs the idempotency discipline from Section 6.4.

#### 2.5.4 Keep dispatch separate from observation

The standard Hosted Agent client surface comes from the Foundry project client, but a runnable production client also needs the application's real durable store, identity, endpoint, and workload schema. The earlier block referenced undefined dependencies and has been removed rather than presented as working code.

This repository now exercises the parts it can own end to end: [`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) implements and tests an atomic durable ledger, while [`validate_observations.py`](scripts/validate_observations.py) validates caller-supplied workload evidence and fails closed on unclassified status codes. Use the [official Hosted Agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent) and samples for the actual authenticated client call. This repository does not ship an environment-specific dispatch client with invented endpoint, identity, or persistence values.

Separating observation behind a read-only application adapter is a maintainability and least-privilege pattern, **not** a security sandbox or RBAC boundary. Untrusted observer code still requires a separate service and identity. Recovery objectives are workload configuration rather than a fixed retry count; size them from healthy runtime and workload-specific replacement allowance. Platform terminal state and workload completion remain separate checks.

This application pattern has one public-API boundary: remote create and the application's durable recording of the returned response ID are not one atomic transaction, and the tested public create call did not expose lookup by an application work key. A process can therefore stop before the remote call, or after it succeeds but before the application records the response ID. Preserve that unresolved application state; do not automatically create again. A normal transactional outbox cannot determine whether an unknown remote create succeeded. Production dispatch needs a product-supported idempotency/deduplication contract or an operational reconciliation path for unresolved records and orphaned responses. The evaluation started observation only after the response ID had been durably captured.

If the polling process disappears after the application has durably recorded the response ID and deadline, a new observer retrieves **that same response** from those application-owned values. Streaming is a public Responses mode; active-handler crash replay is now the separate **public-preview resilient-execution** opt-in. The evaluation persisted transport cursors when available, accepted a new `response.in_progress` snapshot as a reset point, and rebuilt observer output from finalized items.

Most importantly, it did **not** make a high transport sequence cursor the sole recovery key: one measured runtime restarted sequence numbering at 5. A sequence number can optimize replay within a compatible stream lifetime, but the durable `response_id` plus workload state are the recovery authority. Continue to validate finalized output indexes, phases, and durable business state as described in Section 5.

A later sequential turn can use `previous_response_id=response_id`. Concurrent queuing and cooperative steering use the public-preview resilient-task surface; `previous_response_id` by itself only establishes response-chain continuity.

A concise operational route after deployment is `azd ai agent invoke`; it manages the Hosted Agent session and Responses conversation for ordinary calls. Use an application-owned, tested client when your system must persist the background response ID, polling deadline, dispatch/observe separation, and workload-level completion checks.

---

## 3. Method: what was actually run

Everything above is a design claim until it survives a deliberate interruption. This is how that was tested.

### Current public-preview contract check

The historical campaign below used the private-preview build available in July. To avoid treating that package surface as current, the Quick Start installs and checks the pinned public packages in a clean Python 3.13 environment. `--help` documents the scope and exit codes. The committed [18-check evidence](evidence/public-sdk-contract.json) was generated with `--format json --output`; local reruns should write under the ignored `.demo-state` directory unless a maintainer intentionally refreshes the committed evidence and its manifest. Any failed assertion returns a nonzero exit code.

The pinned check passed **18 of 18** assertions against `azure-ai-agentserver-core` 2.0.0, `azure-ai-agentserver-invocations` 1.0.0, and `azure-ai-agentserver-responses` 2.0.0. It verifies package versions, recovered entry mode, separate recovery/retry counters, work and input identities, metadata checkpoint operations, cooperative shutdown, exit-for-recovery, steering, Responses recovery signals, retry policy, enablement, and the current handler contract: the first argument must be named `ctx` and typed as `TaskContext[Input]`.

This is a **real public-SDK contract smoke**, not a mock and not a live-service recovery claim. A mock is appropriate for testing application checkpoints, idempotency, and side-effect watermarks; it cannot prove that Foundry replaced a host or reclaimed a lease. Live production-readiness still requires a deployed Hosted Agent and repeated fault injection as listed in Section 9.4.

### Re-checked on the current build (August 2026)

Two things were re-checked on the public build using the 2022 work subscription that had been enabled during the earlier preview. A later check below repeats the deployed scenario on a different subscription that had never been preview-enabled.

**The July block did not recur on this subscription.** In July the campaign stalled because `/tasks` returned `404`: the subscription was not then on the private-preview allowlist, and a scan of 6,253 subscription features found no self-service switch. In this August re-test the same call returned `200` with an empty task list, alongside `200` on `/agents` and `/assistants`. Because this subscription had previously been enabled, the never-enabled subscription test below provides the stronger availability check.

**The current SDK/runtime build reproduced the tested recovery path.** An 18-phase durable job was run and its worker was hard-killed with `os._exit(9)` right after phase 1 committed, abandoning the lease with no cleanup. A separate OS process then reclaimed the work:

| Re-test observation | Value |
|---|---|
| Phases committed before the injected process loss | 1 of 18 |
| Phases committed after recovery, by a different process | 17 of 18 |
| Sequence continuity | 1-18, no gap, no repeated phase |
| Work identity and input identity across processes | Identical |
| `entry_mode` reported by the second process | `recovered` |
| `recovery_count` / `retry_attempt` at recovery | `1` / `0` |
| Reclaim gap | 1.93 s |

The last row is the interesting one. Section 5 argued from behavior that recovery is not a retry; the current public-preview API now exposes the two as independent counters, and the recovered entry reported exactly the predicted split.

**What this re-test is not.** Phase durations are synthetic sleeps and there is no model inference in the loop, so its elapsed times carry no performance meaning. It exercises durable work, lease abandonment, reclaim, and re-entry in a local two-process test against the current SDK/runtime build; it is not live Hosted Agent evidence and does not re-measure the eight July scenarios. Those numbers stay labelled as July observations.

### On a deployed agent, on an ordinary subscription

The check above runs against the SDK. This one ran against a real Hosted Agent, because the two answer different questions.

The official public sample catalogue now ships `resilient-streaming` and `resilient-steering` under `bring-your-own/responses`; their description names `stream.checkpoint()` and `context.persisted_response`. Deploying the sample logic on the previously enabled 2022 work subscription, with the compatible package pins described below and **no new allowlist request or feature registration for this re-test**, took 4 minutes 3 seconds and the agent reported `active`. In July, before preview enablement, `/tasks` had returned `404`.

A stored background response was created on the live endpoint and, while it was still `in_progress`, the runtime instance was replaced by redeploying the agent. Polling the **same response id** afterwards returned `completed` with all three stage items present, no gap and no repeated stage. The container log shows the runtime driving the task store with lease fields — `lease_owner`, `lease_instance_id`, `lease_duration_seconds=60` — and ETag-guarded `PATCH` updates, consistent with the lease and compare-and-set model described in Section 2.4.

The same interruption was then applied to all four official resilient samples, which between them cover the scenario families the July campaign measured:

| Re-tested scenario | Sample | Interrupted after | Result |
|---|---|---|---|
| Responses, streaming recovery | `resilient-streaming` | 22.6 s | **PASS** — same response id, 3 items, no gap or duplicate |
| Responses, steering | `resilient-steering` | 23.3 s | **PASS** — same response id reached a coherent answer |
| Invocations, research recovery | `resilient-research` | 28.4 s | **PASS** — same `invocation_id` reached `completed` |
| Invocations, approval outliving instance loss | `resilient-approval-gate` | 25.3 s | **PASS** — the decision was accepted (`202`) even though it was sent *after* the replacement, work completed |

The fourth row repeats a July finding: the instance was replaced **while the agent was parked on an approval gate and no application step was executing**. The decision was then submitted against work whose original host no longer existed, and it was accepted.

Two further checks are worth reporting, including the one that did not go as expected.

**The same scenario also passed on a subscription that had not been preview-enabled.** The deployment above ran on a subscription the product group had enabled during the preview. Repeating it on a *different* subscription that had never been enabled — a 2026 work subscription — produced the same acceptance result: `azd up` succeeded in 3 minutes 29 seconds, and the same interruption left the response `completed` with all three items. Two subscriptions are not a survey and do not establish tenant-, region-, or subscription-wide availability; this result shows only that prior preview enablement was not required on that tested subscription.

**The `424` sequence did not reproduce.** Section 4.4 rests on 29 consecutive `424` responses observed in July while a host was being replaced. Polling the same response every 0.4 s across a forced replacement produced **26 polls, all `200`, and no transient error**. This does not refute the July observation because the interruption paths differed. The engineering advice remains scoped: classify `424` before treating it as terminal. The number 29 remains a July observation that this current-build test did not reproduce.

A package-version compatibility issue is worth documenting. During the August re-test, the then-current sample pinned `responses==2.0.0b1` but only required `core>=2.0.0b10`; resolving `core 2.1.0b2` produced an observed `HTTP 500`. Pinning `core==2.0.0`, `responses==2.0.0`, and `invocations==1.0.0` resolved that historical run and remains the exact offline probe environment in this repo. The official sample has since moved to exact `core==2.1.0b2` and `responses==2.1.0b2` pins. New live reproductions should follow the current sample, not downgrade it to this repo's historical probe versions.

These interruptions were produced by forcing a runtime-instance replacement, which is a platform-level event but not an unplanned host crash, and the samples' stages remain simulated. Four scenario families were covered with one accepted run each — capability validation on the current build, not a new reliability benchmark, and not a repeat of the full July matrix. The July .NET runs were **not** repeated: at the time of this re-test, the public C# samples shipped Hosted Agents but none exercised resilient tasks, so those rows remain July observations.

| Dimension | Fixed condition | Why it matters |
|---|---|---|
| Execution window | July 22-23, 2026 | Keeps earlier blocked or partial attempts out of the final campaign |
| Hosting | Eight active Hosted Agents in one Canada Central Foundry project | Holds the hosting control plane and region constant |
| Runtime and protocol | Python and .NET; Responses and Invocations | Tests whether the conclusion survives language and protocol changes |
| Scope | Each runnable sample's main documented scenario | Fixes the denominator at **8 scenarios** |
| Accepted evidence | Complete event capture or structured client log, plus terminal service state | A dropped stream or a similar-looking rerun cannot pass |
| Repetition | One accepted end-to-end run per scenario (**N=1 each**) | Capability validation, not a reliability benchmark |
| Excluded | Model quality, business correctness, load, concurrency, cost, multi-region | No conclusions are available on these dimensions |

A scenario passed only when the **complete documented plan reached a terminal result after the interruption**. Partial recovery did not count. A resumed stream that stalled did not count. A fresh run producing similar text definitely did not count.

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

## 4. Results

### 4.1 A 21.7-minute run across injected process loss

<div align="center"><img src="images/work-distribution.png" width="820" alt="Work-distribution chart, not a success score: 95 percent of elapsed time and events occurred after the injected runtime-instance loss"></div>

The **95% is a work-distribution ratio, not a success or completeness score**. Acceptance was 18 of 18 phases with no missing or repeated phase; the ratio only shows how much measured time and event volume occurred after the injected loss.

The Python Invocations research agent produced 599 events in its first 15 seconds and reached phase 1. We then destroyed the runtime instance, and the stream went dead.

No resubmission followed. The client reattached, received an explicit recovery event, and the sequence counter picked up at **600** — exactly where it had stopped. Over the next 1,237 seconds the reattached stream delivered 11,649 more events covering phases 2 through 18, including 192 status events and 17 phase events, and ended in a completed terminal state.

The totals: 1,301 seconds, sequence 1 through 12,248, no gap and no repeated phase. Put another way, both the elapsed time and the event count split 5/95 across the moment the process died. The chart above draws that ratio to scale and illustrates why resubmission would have been wrong for this run.

### 4.2 The same interruption, a different protocol

With language and protocol changed, the tested continuity result still held.

The Python Responses research run recorded 11,584 events. Before the interruption: 577 events over 13 seconds, output index 0, 570 text deltas. The crash stream reported a failed response. After a **47-second** reconnect gap, lifecycle replay was observed, the sequence resumed at 578, and 11,005 further events arrived over 1,140 seconds carrying output indexes 1 through 17 and 10,918 text deltas. Completion was delivered on the reattached stream.

Output index 0 was produced before the interruption and indexes 1 through 17 after it. **No index was repeated and none was skipped.** Together with the unchanged response identity, that is strong evidence that this observed run continued the same stored response rather than creating a new one; it is not a general proof for every Responses workload.

### 4.3 Injected runtime loss during a pending human approval

<div align="center"><img src="images/approval-recovery.png" width="820" alt="Measured approval timeline showing 56 seconds from runtime loss to the decision being accepted"></div>

This case is easy to overlook because **no application step was executing**. The graph had parked at an approval and was waiting on a person.

The run started at 12:22:54 and called its flight and hotel tools seven seconds later. At 12:23:07 it requested approval for a three-night Tokyo booking and stopped. Eighty seconds into that wait, at 12:24:27, we destroyed the runtime instance. The approval decision was sent after restart and accepted at 12:25:23 — **56 seconds** after the loss. Two seconds later the agent resumed with the *same* flight and hotel selection it had offered before, and at 12:25:30 it returned confirmation `TRIP-182336`.

The pending approval, the tool results, and the exact options shown to the user all outlived a process that no longer existed. A second run of the same pattern on the Responses protocol reached its own confirmation, `TRIP-749637`.

> These are deterministic sample tools. The confirmation numbers support that persisted graph state and one approval application survived these runs; they do not establish a general exactly-once guarantee or represent a real airline or hotel booking.

### 4.4 Twenty-nine `424` responses before completion

<div align="center"><img src="images/retry-pattern.png" width="820" alt="Twenty-nine consecutive HTTP 424 responses followed by successful completion"></div>

While its host was being replaced, the durable workflow run received `HTTP 424 Failed Dependency` **29 consecutive times** on the same response. The client kept polling instead of resubmitting, and the run completed with every stage intact:

```text
[French]
Le rapide renard brun saute par-dessus le chien paresseux.
[Spanish]
El rápido zorro marrón salta por encima del perro perezoso.
[Original English]
The quick brown fox jumps over the lazy dog.
[French]
Le rapide renard brun saute par-dessus le chien paresseux.
[Spanish]
El rápido zorro marrón salta por encima del perro perezoso.
[Round-trip English]
The quick brown fox jumps over the lazy dog.
```

A client that treated the first 424 as terminal would have abandoned this run before it completed. So would a client with a retry budget of ten. In this observed case, the same response ultimately completed with all expected output; the `424` sequence was not terminal.

This is also the finding most easily over-generalized, so to be precise: **this does not make every 424 retryable.** It makes *this* condition — host replacement on a response you can still address — worth classifying before you give up on it.

### 4.5 Interrupting on purpose

Not every interruption is a failure. A second turn was sent while the first was still generating.

The new input was accepted as `queued` rather than rejected. The first turn wound down cooperatively at a safe boundary and was marked completed instead of being killed mid-token. The replacement turn then polled `in_progress` seven times and completed with the expected answer to the new question. In this run, steering followed a queued, cooperative path rather than a cancel/restart race.

---

## 5. In the tested model, transport sequence is diagnostic, not the sole recovery authority

<div align="center"><img src="images/continuity-signals.png" width="820" alt="Four runs compared: transport sequence continued in three, workload output coverage held in all four"></div>

If you take one engineering rule away from this page, take this one.

Three of the four research runs continued their transport sequence numbers cleanly across reattachment. The fourth did not: the .NET Responses stream **restarted its counter at 5** after reconnecting — while still delivering output indexes 1 through 17 on the same response. By this evaluation's workload acceptance criteria, that run passed. A sequence-continuity-only check would have flagged it as broken.

| Run | Before interruption | After reattachment | Signal |
|---|---|---|---|
| Invocations / Python | seq 1-599 | seq 600-12,248 | Sequence continued |
| Responses / Python | output index 0 | output indexes 1-17 | Index continued |
| Invocations / .NET | seq 1-738 | seq 739-12,073 | Sequence continued |
| Responses / .NET | output index 0 | output indexes 1-17 | Index continued, **sequence restarted at 5** |

For these runs, the primary acceptance signals were *what the workload produced* — output indexes, phase numbers, and durable state. Transport numbering remained diagnostic; other protocols should define acceptance according to their own semantics.

And while you are there, note a second trap in the same family: a monotonic sequence is not a gap-free sequence. `10, 12` is monotonic and still missing an event. A continuity check that only asserts "increasing" will pass a stream that silently lost data.

---

## 6. Executable validators, evidence, and fixes

This is where the platform boundary becomes client engineering. [`validate_observations.py`](scripts/validate_observations.py) contains the executable checks discussed below, and its [JSON self-test report](evidence/observation-validation.json) records both passing and failing paths. The historical service values remain in the public-safe [aggregate evidence](evidence/historical-observations.json); raw logs remain private for the reasons in Section 9.2.

### 6.1 Continuity: reject gaps and duplicates

The broken check was effectively `sequence == sorted(sequence)`. That proves ordering, not continuity. The real `sequence_has_no_gap` and `output_coverage_complete` functions in [`validate_observations.py`](scripts/validate_observations.py) check every adjacent step and the complete expected output domain.

| Counterexample | Original sorted-order check | Corrected check |
|---|---:|---:|
| Dropped event: `[10, 12]` | `True` | `False` |
| Duplicate event: `[10, 10, 11]` | `True` | `False` |
| Clean stream: `[10, 11, 12]` | `True` | `True` |

The same executable check rejected a finalized output-item list with a missing index and with a duplicated index. Feed it one index per completed output item, not every streaming delta: multiple deltas for one item legitimately reuse that item's `output_index`. In this helper, transport sequence is diagnostic evidence; acceptance also checks workload indexes, phases, and durable state. Other protocols should use their own semantics.

### 6.2 Terminal state: a `done` frame is not proof of success

The local evaluation evidence included streams with a bare `done` frame, but the harness pass criteria came from explicit invocation status and workload assertions. A closed stream can mean success, cancellation, failure, or observer loss. The executable `completion_is_proven` check requires service status, explicit terminal event, and expected phase count.

This is the distilled phase-based pattern used by the harness, not a universal adapter. A Responses client should substitute its own explicit terminal event and output-coverage rule; a bare `{"type": "done"}` still does not prove the business result.

### 6.3 Bounded retry: classify `424` separately from `403`

The July aggregate records 29 consecutive `424` responses before completion; it does not expose the response identifier. The real `recovery_action` function in [`validate_observations.py`](scripts/validate_observations.py) preserves the same-work requirement, distinguishes confirmed host replacement from observer-auth expiry, honors the caller deadline, and fails closed when signals are insufficient. Its committed JSON report includes confirmed and unclassified `424`/`403` cases.

The deadline should come from the workload's recovery objective, not an arbitrary small retry count. Classify `403` independently: verify observer identity, scope, and durable workload state first; refresh credentials only when expiry is confirmed. A read-only recheck is safer than replaying business work.

### 6.4 Human approval: make the decision and the side effect idempotent

The measured approval run crossed the pause once and produced confirmation `TRIP-182336`; the structured public aggregate records the 56-second loss-to-decision interval and terminal result without publishing the private session log.

After recovery, the same approval message may be delivered again. The executable SQLite ledger in [`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) atomically records phase result, idempotency key, generation, and checkpoint; its tests prove identical replay is deduplicated and conflicting replay fails closed. It intentionally does not invent a booking API. A production downstream operation must honor the same idempotency identity or it can still execute twice.

---

## 7. Failure and recovery playbook

<div align="center"><img src="images/recovery-decision-guide.png" width="560" alt="Decision guide for classifying runtime, client, host-replacement, and observer failures before recovering"></div>

Each row below is a diagnostic starting point, not a universal mapping from symptom to cause. **Read the same logical work first, identify the likely layer from durable evidence, and create nothing new until the existing state is known.**

| Symptom | Likely layer / what to verify | Unsafe reflex | Safer next step | Confirmation |
|---|---|---|---|---|
| Stream stops with no terminal event | Observer, network, or runtime; stream loss alone does not identify which | Resubmit the job | Query the same work and reattach from its durable output position when it remains addressable | Recovery marker or continued workload output, then explicit terminal state |
| Workflow parked on an approval | In the measured case, the runtime was replaced; verify that suspended work remains addressable | Rebuild the approval request | After recovery exposes the same work, send the decision to that work | Post-approval path reaches terminal state with the expected selections |
| Client loses SSE or HTTP connectivity | Possibly the observation channel; verify durable service state | Assume the agent stopped and resubmit | Reconnect to the same work from its durable output position | Output and phase coverage continue with no duplicate business result |
| Repeated `424` on the same response | In the measured case, a temporary dependency during host replacement; other causes remain possible | Treat every 424 as terminal or retryable | Classify the condition; only then poll the same response with bounded backoff when it remains addressable | Response completes with all expected stages present |
| `403` on a final read | Possibly observer authentication or authorization; do not infer workload state from this alone | Rerun the workload | Verify identity and scope, refresh credentials if expired, then repeat the read-only query | Authorized read returns the durable terminal state |
| Captured log stops at a byte or time limit | Evidence capture may be truncated; workload state remains unknown | Infer failure from the last captured line | Query durable state directly, or recapture the full stream | Terminal state read from the service, not the log tail |
| New instruction arrives mid-turn | If steering is enabled, this may be a steering path; verify protocol state | Hard-kill the turn and race a new run | Queue through the steering path, or apply the application's documented cancellation policy | Old turn ends as designed; new input reaches its expected terminal state |

---

## 8. Design guidance

These are engineering recommendations derived from the evaluated failure modes, not product guarantees. Apply them beyond this preview only where the same assumptions hold.

1. **Checkpoint at a recorded boundary you can verify.** A persisted marker such as "phase 7 of 18 complete" can serve as a recovery point. "Somewhere in the middle" is insufficient for safe recovery without a verifiable checkpoint.
2. **Give the work an identity that outlives the process.** Recovery means addressing a logical work item, not resuming a socket.
3. **Assume at-least-once execution.** Design every external side effect so that repeating it after a checkpoint is harmless.
4. **Separate observer failures from workload failures.** An observer token expiry does not by itself establish that the workload failed.
5. **Classify status codes before acting on them.** Confirm against durable state before declaring a business failure.
6. **Make terminal state explicit.** A stream that merely ends is not a result.
7. **Decide who owns an approval decision.** Applying it twice is worse than applying it late.
8. **Distinguish suspended work from active work.** A parked graph has no active application step and its compute may be reclaimed. That can be normal lifecycle behavior; verify durable state before classifying it as a fault.

---

## 9. Evidence, boundaries, and adoption gate

### 9.1 How these claims were challenged

Eight passing runs are easy to over-read, so each conclusion was attacked before it was published.

| Method | Challenge | Evidence used | Outcome |
|---|---|---|---|
| Confirmation | Did the same logical work reach terminal state? | Same work reference, terminal service state, full phase and output coverage | Supported in all eight scenarios |
| Falsification | Could a fresh rerun look like recovery? | Output index 0 before, 1-17 after, on the same response | Fresh-run explanation rejected for the Responses runs |
| Enumeration | Were only flattering examples selected? | Fixed denominator of eight main scenarios | 8/8 passed; auxiliary branches excluded explicitly |
| Contradiction | If sequence continuity were necessary for this Responses recovery, would the accepted run satisfy it? | .NET Responses met the workload acceptance criteria while restarting its counter at 5 | The sequence-continuity assumption did not hold for this observed run |
| Reverse inference | Does a terminal result alone prove recovery? | Checkpoint, injected loss, connection break, and post-restart continuation were also required | Terminal-only evidence rejected as insufficient |
| Analogy | Do observations align with public platform concepts? | Public session persistence and protocol ownership documentation | Consistent, but idle resume was never used as proof of active recovery |
| Consistency | Does the conclusion survive runtime and protocol changes? | Python/.NET and Responses/Invocations pairs | Workload-output continuity held; transport event shape did not |

### 9.2 What the numbers trace to

| Claim surface | Public evidence | Source boundary |
|---|---|---|
| July and August counts, ranges, durations, confirmations, 424 and steering values | [`historical-observations.json`](evidence/historical-observations.json) | Public-safe aggregates derived from captured runs; N and product status are explicit |
| Current public SDK symbols and handler rules | [`public-sdk-contract.json`](evidence/public-sdk-contract.json) | Real installed-package probe; not live recovery |
| Lease, process loss, generation fence, checkpoint, idempotency | [`recovery-contract-demo.json`](evidence/recovery-contract-demo.json) + [JSONL events](evidence/recovery-contract-events.jsonl) | Real local test fixture; not Foundry service code |
| Gap, duplicate, terminal-state and 424/403 error paths | [`observation-validation.json`](evidence/observation-validation.json) | Executable positive and negative fixtures |
| Scenario truth labels | [`scenario-manifest.json`](evidence/scenario-manifest.json) | Separates dynamic runtime, test fixture, and measured architecture explainer |
| File integrity and reproduction commands | [`manifest.json`](evidence/manifest.json) + [evidence index](evidence/README.md) | SHA-256 covers the public evidence files |

Raw live artifacts stay private because they contain endpoints, work identifiers, environment metadata, and generated payload text. The public aggregate contains only values already disclosed here; the local JSONL contains a synthetic workload and no service identifiers.

### 9.3 Boundaries

- All numbers are **observed values from the evaluation each one names** — the July campaign or the August re-test — not benchmarks, guarantees, or SLAs.
- The capability was in **private preview** when the campaign ran and has since moved to **public preview** with an [official concept page](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience). This repository now publishes a current public-API probe, executable local test fixture, tests, and public-safe evidence, but not Microsoft SDK source, a complete deployment recipe, live-service credentials, or private raw telemetry.
- Results cover the July campaign's **eight documented main scenarios**, one accepted run each, plus the August re-test's **four scenario families**, one accepted run each. Cancel, delete, and deny branches were not counted.
- The listed recovery paths were observed under the stated conditions. Business-domain correctness and model quality were not evaluated.
- Verify current capabilities against the [official documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) before designing against anything described here.

### 9.4 Before you call this production-ready

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
