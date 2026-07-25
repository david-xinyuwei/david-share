# Long-Running Agents on Microsoft Foundry: What Happens After the Process Dies

[![Scope](https://img.shields.io/badge/scope-8_measured_scenarios-1363DF)](#3-method-what-was-actually-run)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_%2B_.NET-0F8B6D)](#4-results)
[![Protocols](https://img.shields.io/badge/protocols-Responses_%2B_Invocations-5F4BB6)](#23-where-you-plug-in)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

Fifteen seconds into a twenty-two minute job, a research agent had just finished the first of eighteen phases when the process running it was destroyed. Nothing was resubmitted. Twenty-one minutes later the same job reported completion — all eighteen phases delivered, 12,248 stream events, no gap and no repeated phase.

Ninety-five percent of that work was performed by a process that no longer existed.

This page explains why that worked, which signals proved it, and which perfectly reasonable instincts would have destroyed it.

> **What this is.** Measured behavior from a private-preview evaluation of long-running agent execution on Microsoft Foundry Hosted Agents.
> **What it is not.** It ships **no preview SDK source, no implementation code, no deployment recipe, no API schema, and no raw telemetry**, because the capability was in private preview at the time. Every number is an observation from that evaluation, not a service-level commitment.

> **Author:** Xinyu Wei (魏新宇)

[中文](README-CN.md) | English | [Hosted agents overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

---

## Executive Summary

Long-running agents fail in a way that short calls do not: **the process disappears while the work is still valid.** A client that treats this as an error and resubmits abandons live work, pays for two runs, and risks committing the same external action twice.

The capability under evaluation separates the **logical work** from the **process that executes it**. The work carries a durable identity, its input and progress outlive the process, and replacement compute re-enters from the last checkpoint. Across eight scenarios — two languages, two protocols, four kinds of interruption — every run reached its documented terminal result after being interrupted.

| Measured | Value | Why it matters |
|---|---|---|
| Work performed after the process was destroyed | **95%** of 1,301 s and 95% of 12,248 events | A destroyed process does not imply lost work |
| Runtime loss to approval decision accepted | **56 s**, with the original selections intact | A pending human decision can outlive the process holding it |
| Consecutive `HTTP 424` before normal completion | **29** | A retry budget of 10 would have discarded a healthy run |
| Scenarios reaching their documented terminal result | **8 of 8**, one accepted run each | Capability validation, not a reliability benchmark |
| Runs where transport sequence numbering proved continuity | **3 of 4** | One runtime restarted its counter; workload output held in all four |

**What this evidence does not establish:** production availability, SLA, behavior under load or concurrency, multi-region recovery, cost, and business correctness. Each scenario ran once. This is a reason to fund a controlled evaluation, not a production sign-off.

---

## 1. Background: the third outcome

A short agent call has two outcomes — it returns, or it throws. A twenty-minute agent run has a third: the process disappears while the work is still valid.

Three things can happen inside that window. The runtime instance can stop, whether from a crash, a redeploy, host replacement, or a lifecycle action. The client's stream can end without ever delivering a terminal event. And the user can change their mind halfway through.

None of these are solved by retrying the request. A retry starts a *new* run and walks away from work that is still alive. You now have two runs, you pay for both, and any external action the first one already committed may happen a second time. That reflex is the most expensive mistake in this space, which is why everything below is about **reattaching to existing work** rather than resubmitting it.

### What "runtime instance" means here

A Hosted Agent is your own agent code, packaged as a container image. Foundry runs that code inside a per-session, VM-isolated sandbox and manages its lifecycle for you. Throughout this page, **runtime instance** means the currently running copy of that code.

It is not a Docker container you operate. Losing it removes the process, its memory, and its open connections. It does not delete the agent definition, the session, or any work that was recorded outside the process — and that distinction is the whole point.

### What the platform already gives you

The public platform provides the hosting baseline: per-session isolation, a persisted `$HOME` and `/files` that survive idle deprovisioning, durable conversation history, a dedicated Microsoft Entra identity, and managed lifecycle and observability ([source](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)).

What that documentation does not tell you is whether *your* workload resumes correctly when active work is interrupted. Idle-state restoration and active-work recovery are different claims. The evaluation deliberately targeted the second one.

| Layer | Public documentation (July 21, 2026) | What was measured | Boundary |
|---|---|---|---|
| Session state | `$HOME` and `/files` are restored when idle compute resumes | Active work continued after injected runtime loss | Idle restoration is consistent with, but does not prove, active-work recovery |
| Responses | Conversation history, streaming lifecycle, and background polling are platform-managed | The same response delivered output indexes 0-17 across recovery | Proves this response, not an SLA for every workload |
| Invocations | The application owns payload, session semantics, task tracking, and polling | Explicit recovery events and phases 1-18 were observed | The application still owns correct checkpoint and side-effect semantics |

---

## 2. How it works: address the work, not the process

<div align="center"><img src="images/resilience-architecture.png" width="820" alt="Six-step model showing how logical work survives loss of a Hosted Agent runtime instance"></div>

Recovery rests on a single idea: **give the work an identity that outlives the process, and re-enter that work rather than resurrecting the process.**

In practice it runs in seven steps. The client starts one logical work item and keeps its stable reference. Before execution begins, the long-running layer persists that identity, the input, and the lease metadata needed to find the work again. As the agent runs, it records business progress — a phase number, a watermark, an approval state, or a pointer to external state. Then the runtime instance is lost: the process, its memory, and the socket vanish, but the durable record does not. Foundry provides replacement compute, the same logical work is re-entered with recovery context, the application loads its checkpoint and continues from a known boundary, and the client reattaches to confirm continuity.

Walk the measured 18-phase run through those steps and the ordering becomes concrete. Steps one through three covered phase 1. Step four destroyed the process. Steps five and six carried phases 2 through 18. The client reattached at step seven — but note *when*: **the workload recovered whether or not anyone was watching.** Reattachment resumes observation, not execution. That single fact is what makes a dropped client stream a non-event instead of an incident.

### 2.1 Four responsibilities that must stay separate

Keeping these apart is most of the design work, because it determines what you are allowed to conclude when something breaks.

| Layer | Owns | Must remain valid | Does not prove |
|---|---|---|---|
| Foundry Hosted Agent platform | Runtime sandbox, endpoint, identity, session and conversation state, lifecycle | The ability to provision replacement compute and address the same session | That application progress was checkpointed correctly |
| Long-running execution layer | Stable work identity, persisted input, recovery entry, task and stream state | The logical work record across process loss | That external business actions are safe to repeat |
| Agent framework or application | Meaningful checkpoints, workflow phase, approval state, terminal result | Enough business progress to resume safely | That the client will reconnect correctly |
| Client or operator | Stable work reference, reconnect cursor, bounded polling, auth refresh | The ability to observe the same work after a disconnect | That a transport error means the workload failed |

The practical rule: **runtime state, workload state, and observer state are three different failure domains.** A failure in one must never be promoted automatically into a failure of the others. Section 6 is essentially this rule turned into a lookup table.

### 2.2 Recovery is at-least-once, and that is your problem to handle

A recovered handler re-enters with the same identity and input. It does **not** replay your code's execution, and it does not re-run individual model or tool calls from where they stopped.

The consequence is unavoidable: work performed after the last durable checkpoint can run again. Checkpoint granularity defines the replay window, and idempotency keys, compare-and-set writes, and durable external operation IDs are what stop that replay from becoming a duplicate booking, payment, or write.

So it is worth being explicit about what recovery is *not*. It is not resurrection of the old socket. It is not deterministic replay. It is not resubmitting the original request as a new job. It is not proven by an agent version showing `active`, which only means the control plane accepted a deployment. And it is not safe at all unless committed side effects can be recognized and skipped on re-entry.

### 2.3 Where you plug in

The model is framework-agnostic. What changes between tiers is how much of it you wire yourself.

| Tier | What the platform handles | What you still own | Best fit |
|---|---|---|---|
| Microsoft Agent Framework on Foundry hosting | The highest-level integration over Responses; most lifecycle behavior is wired for you | Configuration, framework checkpoints, safe side effects | Teams that want the least recovery plumbing |
| Responses protocol | OpenAI-compatible contract, conversation history, streaming lifecycle, background execution, polling, cancellation | Opting into resilient behavior, preserving checkpoints, validating output continuity | Conversational and tool-using agents |
| Invocations protocol | Transport and primitives only | Session and task semantics, event schema, checkpoint mapping, polling, recovery behavior | Structured workflows and custom protocols |

LangGraph, Microsoft Agent Framework, and hand-written orchestration can all participate. None of them removes the application's obligation to define what "already done" means.

---

## 3. Method: what was actually run

Everything above is a design claim until it survives a deliberate interruption. This is how that was tested.

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

### 4.1 A 21.7-minute run that outlived its process

<div align="center"><img src="images/work-distribution.png" width="820" alt="Proportional chart showing 95 percent of elapsed time and events occurred after the runtime instance was destroyed"></div>

The Python Invocations research agent produced 599 events in its first 15 seconds and reached phase 1. Then the runtime instance was destroyed and the stream went dead.

No resubmission followed. The client reattached, received an explicit recovery event, and the sequence counter picked up at **600** — exactly where it had stopped. Over the next 1,237 seconds the reattached stream delivered 11,649 more events covering phases 2 through 18, including 192 status events and 17 phase events, and ended in a completed terminal state.

The totals: 1,301 seconds, sequence 1 through 12,248, no gap and no repeated phase. Put another way, both the elapsed time and the event count split 5/95 across the moment the process died. The chart above is that ratio drawn to scale, and it is the single clearest argument against resubmitting.

### 4.2 The same interruption, a different protocol

Language and protocol changed; the conclusion did not.

The Python Responses research run recorded 11,584 events. Before the interruption: 577 events over 13 seconds, output index 0, 570 text deltas. The crash stream reported a failed response. After a **47-second** reconnect gap, lifecycle replay was observed, the sequence resumed at 578, and 11,005 further events arrived over 1,140 seconds carrying output indexes 1 through 17 and 10,918 text deltas. Completion was delivered on the reattached stream.

Output index 0 was produced before the interruption and indexes 1 through 17 after it. **No index was repeated and none was skipped.** For a Responses workload that is the strongest evidence available that this was the same logical response rather than a convincing new one — and it is exactly the check a resubmitted run would fail.

### 4.3 A runtime instance died while a human was thinking

<div align="center"><img src="images/approval-recovery.png" width="820" alt="Measured approval timeline showing 56 seconds from runtime loss to the decision being accepted"></div>

This is the case teams underestimate, because when it happens **nothing is executing at all**. The graph had parked at an approval and was waiting on a person.

The run started at 12:22:54 and called its flight and hotel tools seven seconds later. At 12:23:07 it requested approval for a three-night Tokyo booking and stopped. Eighty seconds into that wait, at 12:24:27, the runtime instance was destroyed. The approval decision was sent after restart and accepted at 12:25:23 — **56 seconds** after the loss. Two seconds later the agent resumed with the *same* flight and hotel selection it had offered before, and at 12:25:30 it returned confirmation `TRIP-182336`.

The pending approval, the tool results, and the exact options shown to the user all outlived a process that no longer existed. A second run of the same pattern on the Responses protocol reached its own confirmation, `TRIP-749637`.

> These are deterministic sample tools. The confirmation numbers prove durable graph state and exactly-once decision handling — not a real airline or hotel booking.

### 4.4 Twenty-nine failures that were not failures

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

A client that treated the first 424 as terminal would have thrown away a run that was about to succeed. So would a client with a sensible-looking retry budget of ten. The response was intact the entire time; only its host was being replaced.

This is also the finding most easily over-generalized, so to be precise: **this does not make every 424 retryable.** It makes *this* condition — host replacement on a response you can still address — worth classifying before you give up on it.

### 4.5 Interrupting on purpose

Not every interruption is a failure. A second turn was sent while the first was still generating.

The new input was accepted as `queued` rather than rejected. The first turn wound down cooperatively at a safe boundary and was marked completed instead of being killed mid-token. The replacement turn then polled `in_progress` seven times and completed with a correct answer to the new question. Steering, in other words, is a first-class path rather than a race between cancel and restart.

---

## 5. The finding that transfers: don't trust the sequence number

<div align="center"><img src="images/continuity-signals.png" width="820" alt="Four runs compared: transport sequence continued in three, workload output coverage held in all four"></div>

If you take one engineering rule away from this page, take this one.

Three of the four research runs continued their transport sequence numbers cleanly across reattachment. The fourth did not: the .NET Responses stream **restarted its counter at 5** after reconnecting — while still delivering output indexes 1 through 17 on the same response. By any workload measure that run recovered perfectly. By a sequence-continuity check it would have been flagged as broken.

| Run | Before interruption | After reattachment | Signal |
|---|---|---|---|
| Invocations / Python | seq 1-599 | seq 600-12,248 | Sequence continued |
| Responses / Python | output index 0 | output indexes 1-17 | Index continued |
| Invocations / .NET | seq 1-738 | seq 739-12,073 | Sequence continued |
| Responses / .NET | output index 0 | output indexes 1-17 | Index continued, **sequence restarted at 5** |

So validate continuity on *what the workload produced* — output indexes, phase numbers, durable state — not on *how the transport numbered its frames*.

And while you are there, note a second trap in the same family: a monotonic sequence is not a gap-free sequence. `10, 12` is monotonic and still missing an event. A continuity check that only asserts "increasing" will pass a stream that silently lost data.

---

## 6. Failure and recovery playbook

<div align="center"><img src="images/recovery-decision-guide.png" width="560" alt="Decision guide for classifying runtime, client, host-replacement, and observer failures before recovering"></div>

Every row below follows the same discipline: **read the same logical work first, decide which layer actually failed, and create nothing new until the existing state is known.**

| Symptom | What actually failed | Wrong reflex | Correct recovery | Confirmation |
|---|---|---|---|---|
| Stream stops with no terminal event | One execution process, not necessarily the work | Resubmit the job | Let the platform re-enter, then reattach with the same work reference and last durable position | Recovery marker or continued workload output, then explicit terminal state |
| Workflow parked on an approval, nothing running | The runtime instance; the suspended workflow is intact | Rebuild the approval request | Send the decision to the same logical work after restart | Post-approval path reaches terminal state with identical selections |
| Client loses SSE or HTTP connectivity | The observation channel only | Assume the agent stopped and resubmit | Reconnect to the same work from its durable output position | Output and phase coverage continue with no duplicate business result |
| Repeated `424` on the same response | Nothing yet — the host is being replaced | Treat the first 424 as terminal | After classifying this condition, poll the same response with bounded backoff | Response completes with all expected stages present |
| `403` on a final read | Your authorization, not the workload | Rerun the workload | Refresh observer auth and repeat the read-only query | `200` with completed terminal state |
| Captured log stops at a byte or time limit | Evidence capture | Infer failure from the last captured line | Query durable state directly, or recapture the full stream | Terminal state read from the service, not the log tail |
| New instruction arrives mid-turn | Nothing — this is a steering path | Hard-kill the turn and race a new run | Queue the input and let the current turn stop at a safe boundary | Old turn ends cooperatively; new input reaches a terminal answer |

---

## 7. Design guidance

These generalize well beyond the preview that produced them.

1. **Checkpoint at a boundary you can name.** "Phase 7 of 18 complete" is recoverable. "Somewhere in the middle" is not.
2. **Give the work an identity that outlives the process.** Recovery means addressing a logical work item, not resuming a socket.
3. **Assume at-least-once execution.** Design every external side effect so that repeating it after a checkpoint is harmless.
4. **Separate observer failures from workload failures.** Your token expiring is your problem, not the run's.
5. **Classify status codes before acting on them.** Confirm against durable state before declaring a business failure.
6. **Make terminal state explicit.** A stream that merely ends is not a result.
7. **Decide who owns an approval decision.** Applying it twice is worse than applying it late.
8. **Distinguish suspended work from active work.** A parked graph has no active execution and its compute may be reclaimed. That is expected behavior, not a fault.

---

## 8. Evidence, boundaries, and adoption gate

### 8.1 How these claims were challenged

Eight passing runs are easy to over-read, so each conclusion was attacked before it was published.

| Method | Challenge | Evidence used | Outcome |
|---|---|---|---|
| Confirmation | Did the same logical work reach terminal state? | Same work reference, terminal service state, full phase and output coverage | Supported in all eight scenarios |
| Falsification | Could a fresh rerun look like recovery? | Output index 0 before, 1-17 after, on the same response | Fresh-run explanation rejected for the Responses runs |
| Enumeration | Were only flattering examples selected? | Fixed denominator of eight main scenarios | 8/8 passed; auxiliary branches excluded explicitly |
| Contradiction | If sequence continuity were necessary, would every valid recovery satisfy it? | .NET Responses recovered while restarting its counter at 5 | Universal sequence rule disproved |
| Reverse inference | Does a terminal result alone prove recovery? | Checkpoint, injected loss, connection break, and post-restart continuation were also required | Terminal-only evidence rejected as insufficient |
| Analogy | Do observations align with public platform concepts? | Public session persistence and protocol ownership documentation | Consistent, but idle resume was never used as proof of active recovery |
| Consistency | Does the conclusion survive runtime and protocol changes? | Python/.NET and Responses/Invocations pairs | Workload-output continuity held; transport event shape did not |

### 8.2 What the numbers trace to

| Claim | Source artifact |
|---|---|
| Event counts, sequence ranges, elapsed times | Per-scenario captured event streams |
| Phase and output index coverage | Stream analysis over those captures |
| Approval timeline and confirmation numbers | Client session logs |
| 424 retry behavior and stage output | Workflow client log |
| Steering queue behavior and terminal answers | Steering client log |

Raw artifacts stay private because they contain endpoints, work identifiers, environment metadata, and generated payload text. Every chart on this page is rendered from the aggregate values above and contains no identifiers.

### 8.3 Boundaries

- Numbers are **observed values from one evaluation**, not benchmarks, guarantees, or SLAs.
- The capability was in **private preview**, so its implementation, packages, APIs, and deployment recipes are not published here.
- Results cover **eight documented main scenarios**, each run once. Cancel, delete, and deny branches were not counted.
- Recovery behavior was validated. Business-domain correctness and model quality were not.
- Verify current capabilities against the [official documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) before designing against anything described here.

### 8.4 Before you call this production-ready

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

[MIT](LICENSE)
