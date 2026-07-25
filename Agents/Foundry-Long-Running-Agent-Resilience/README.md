# Long-Running Agents on Microsoft Foundry: What Recovery Actually Looks Like

[![Scope](https://img.shields.io/badge/scope-8_measured_scenarios-1363DF)](#3-measured-effects)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_%2B_.NET-0F8B6D)](#3-measured-effects)
[![Protocols](https://img.shields.io/badge/protocols-Responses_%2B_Invocations-5F4BB6)](#22-two-protocols-two-different-proofs)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

An agent that runs for 20 minutes can lose its container. This page shows what that actually looked like across eight measured runs: how long recovery took, which signals proved the work survived, and which reflexes made things worse.

> **What this page is.** Measured behavior and recovery guidance from a private-preview evaluation.
> **What it is not.** It ships **no preview SDK source, no implementation code, no deployment recipe, no API schema, and no raw telemetry**, because the long-running capability was still in private preview. Numbers are observed values from that evaluation, not a service-level commitment or a claim about every region, model, and topology.

> **Author:** Xinyu Wei (魏新宇)

[中文](README-CN.md) | English | [Hosted agents overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

---

## Executive Summary

| Question | Measured answer |
|---|---|
| Does work survive a container crash? | Yes. One run continued through **phases 2-18** after the container died at phase 1. |
| How long was the recovery? | **56 seconds** from crash to the approval decision being accepted after restart. |
| Did the client lose events? | No. Sequence ran **1 to 12,248** with no gap and no replay. |
| Is a sequence number a safe continuity check? | **No.** One runtime restarted its stream counter after reattach. |
| Does an active deployment prove resilience? | No. It only proves the control plane accepted a version. |
| What should a client do on HTTP 424? | Keep polling the same response. The workflow completed after **29** consecutive 424 responses. |
| What should a client do on 403 at the final read? | Refresh observer auth and read again. The workload had already completed. |

**The one sentence worth keeping:** the platform kept the work alive, and the client's only job was to reattach to the same logical work and read the right signal.

---

## 1. Background: why long-running agents fail differently

A short chat call either returns or throws. A 20-minute agent run has a third outcome: **the process disappears while the work is still valid.**

Three things happen in that window:

1. The container can be restarted, redeployed, or evicted.
2. The client's stream ends without a terminal event.
3. The user may want to change their mind mid-run.

None of these are handled by retrying the request. Retrying starts a *new* run and abandons work that was still alive. That is the most expensive mistake in this space, and it is why the rest of this page focuses on **reattachment** rather than retry.

### Public platform behavior

Microsoft Foundry Hosted Agents run application code in Microsoft-managed, per-session isolated compute. The publicly documented behavior that matters here:

| Concept | What it means for recovery |
|---|---|
| Session | The compute and state boundary. Persisted `$HOME` and files survive idle periods. |
| Conversation | Durable message and tool-call history, used primarily by the Responses protocol. |
| Idle timeout | Compute is deprovisioned after inactivity and restored when the session resumes. |
| Agent identity | A dedicated Microsoft Entra identity used by agent code at runtime. |

Source: [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents).

These are platform properties. They do **not** prove that a specific workload resumes correctly, which is exactly what the measurements below are for.

---

## 2. Method: what was actually run

![Four responsibility layers: public Foundry hosting, the preview long-running capability, workload proof, and observer evidence](images/resilience-architecture.png)

### 2.1 The eight scenarios

![Eight scenarios grouped into four proof patterns](images/scenario-coverage.png)

| # | Runtime | Protocol | Pattern | Interruption used |
|---|---|---|---|---|
| 1 | Python | Invocations | Research durability | Container crash mid-run |
| 2 | Python | Responses | Research durability | Container crash mid-run |
| 3 | .NET | Invocations | Research durability | Container crash mid-run |
| 4 | .NET | Responses | Research durability | Container crash mid-run |
| 5 | Python | Invocations | Human approval | Crash while approval pending |
| 6 | Python | Responses | Human approval | Crash while approval pending |
| 7 | Python | Responses | Durable workflow | Host replacement |
| 8 | Python | Responses | Active-turn steering | Deliberate interruption, no failure |

### 2.2 Two protocols, two different proofs

| Concern | Responses | Invocations |
|---|---|---|
| Client contract | OpenAI-compatible responses behavior | Application-defined request and result schema |
| History | Platform-managed conversation | Application-managed session and task state |
| Long-running entry | Background stored response | Custom durable task |
| Recovery signal observed | Lifecycle replay, or continued output indexes | Explicit recovery event |
| Terminal signal observed | Response completion | Done event plus a task suspension reason |

The two protocols do not emit the same events. Any recovery check that hard-codes one protocol's event names will report false failures on the other.

### 2.3 Acceptance bar

A scenario counted as passing only when the **complete documented plan reached a terminal result** after the interruption. Partial recovery, a resumed stream that stalled, or a fresh run producing similar text did not count.

---

## 3. Measured effects

### 3.1 A crash mid-run: the work did not stop

![Measured recovery timeline showing 599 events before the crash and 11,649 after reattachment](images/recovery-timeline.png)

Python Invocations research run:

| Stage | Measured |
|---|---|
| Before crash | 599 events over 15 s, phase 1 reached, sequence 1-599 |
| Crash | Stream ends; the client observes a dropped connection |
| Reattach | Recovery event received; sequence resumes at **600** |
| After reattach | 11,649 events over 1,237 s, phases 2-18 |
| Terminal | Completed status, with the task suspended for run completion |
| Total | **1,301 s (21.7 min)**, sequence 1 to 12,248 |

The reattached stream carried **192 status events and 17 phase events**. The run had genuinely continued rather than restarted.

### 3.2 The same crash on a different protocol

Python Responses research run, 11,584 records total:

| Stage | Measured |
|---|---|
| Before crash | 577 events, 13 s, output index 0, 570 text deltas |
| Crash | The crash stream reported a failed response |
| Reattach | Lifecycle replay observed; sequence resumes at 578 |
| After reattach | 11,005 events, 1,140 s, output indexes 1-17, 10,918 text deltas |
| Terminal | Completion delivered on the reattached stream |
| Reconnect gap | **47 s** |

Output index 0 was produced before the crash and indexes 1-17 after it. **No index was repeated and none was skipped**, which is the strongest available evidence that this was the same logical response.

### 3.3 Crash while a human was thinking

This is the case people underestimate. The graph parked at an approval, so **nothing was executing at all**.

| Time (UTC) | Event |
|---|---|
| 12:22:54 | Run starts |
| 12:23:01 | Tools called for flight and hotel search |
| 12:23:07 | Approval requested for a 3-night Tokyo booking |
| 12:24:27 | Container crash injected |
| 12:25:23 | Approval decision sent after restart |
| 12:25:25 | Agent resumes with the **same flight and hotel selection** |
| 12:25:30 | Terminal result: confirmation `TRIP-182336` |

**56 seconds** from the crash to the approval decision being accepted after restart; the terminal confirmation followed 7 seconds later. The pending approval, the tool results, and the selected options all survived a process that no longer existed.

A second run of the same pattern on the Responses protocol reached its own terminal confirmation, `TRIP-749637`.

> These are deterministic sample tools. The confirmation numbers prove durable graph state and exactly-once decision handling, not a real airline or hotel booking.

### 3.4 Host replacement: 29 failures that were not failures

The durable workflow run received `HTTP 424 Failed Dependency` **29 consecutive times** while its host was being replaced. The client kept polling the same response instead of resubmitting, and the run completed with every stage intact.

Final persisted output, transcribed exactly:

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

A client that treated the first 424 as terminal would have discarded a run that was about to succeed. A client that gave up at the tenth would have done the same.

### 3.5 Steering: interrupting on purpose

Not every interruption is a failure. A second turn arrived while the first was still generating:

| Step | Observed |
|---|---|
| Turn 1 | Counting task, still running |
| Turn 2 sent mid-flight | New question, status `queued` |
| Turn 1 outcome | Terminated cooperatively as completed |
| Turn 2 outcome | 7 polls at `in_progress`, then `completed` |
| Answer | The replacement question was answered correctly |

The replacement input was queued rather than rejected, and the old turn wound down at a safe boundary instead of being killed mid-token.

---

## 4. What to trust when you reconnect

![Continuity evidence across four runs, where only output coverage held in all of them](images/continuity-evidence.png)

This is the most transferable finding on this page.

| Run | Before crash | After reattach | Continuity signal |
|---|---|---|---|
| Invocations / Python | seq 1-599 | seq 600-12,248 | Sequence continued |
| Responses / Python | output index 0 | output index 1-17 | Index continued |
| Invocations / .NET | seq 1-738 | seq 739-12,073 | Sequence continued |
| Responses / .NET | output index 0 | output index 1-17 | Index continued, **sequence restarted at 5** |

Three of four runs continued their sequence numbers. The fourth did not: the .NET Responses stream **restarted its counter after reattachment** while still delivering output indexes 1-17 on the same response.

**Practical rule:** validate continuity on *what the workload produced* (output indexes, phase numbers, durable state), not on *how the transport numbered its frames*. A monotonic sequence is also not a gap-free sequence, because `10, 12` is monotonic and still missing an event.

---

## 5. Failure and recovery playbook

![Four interruption types with the wrong reflex and the correct recovery for each](images/recovery-playbook.png)

### 5.1 Container crash mid-run

| Aspect | Detail |
|---|---|
| Symptom | The stream stops without a terminal event |
| Wrong reflex | Resubmit the job |
| Why it hurts | The original work is still alive, so you now have two runs and pay for both |
| Correct recovery | Reattach using the same logical work reference and the last known cursor |
| Confirmation | A recovery marker, or continued output indexes on the same work |
| Measured outcome | Phases 2-18 completed after reattachment |

### 5.2 Crash while waiting for a human

| Aspect | Detail |
|---|---|
| Symptom | Nothing is running and there is no stream to reconnect to |
| Wrong reflex | Rebuild the approval request from scratch |
| Why it hurts | You lose the tool results and the specific options the user was asked about |
| Correct recovery | Send the decision after the restart, letting the durable checkpoint wake the graph |
| Confirmation | The post-approval path executes and reaches a terminal confirmation |
| Measured outcome | The decision was accepted 56 s after the crash, with identical selections |

### 5.3 Host replacement returning HTTP 424

| Aspect | Detail |
|---|---|
| Symptom | Repeated `424 Failed Dependency` on the same response |
| Wrong reflex | Treat 424 as a terminal error |
| Why it hurts | The response is intact and only its host is being replaced |
| Correct recovery | Retry the same response with backoff |
| Confirmation | The response reports completion with all stages present |
| Measured outcome | Completed after 29 consecutive 424 responses |

### 5.4 Observer credential expired

| Aspect | Detail |
|---|---|
| Symptom | `403` on the final read of a long run |
| Wrong reflex | Rerun the workload |
| Why it hurts | The workload already finished, so you are rerunning to fix your own token |
| Correct recovery | Refresh observer authentication and repeat the read-only query |
| Confirmation | `200` with the completed terminal state |
| Measured outcome | A fresh-token read returned completion with 18 output items |

### 5.5 Truncated evidence

| Aspect | Detail |
|---|---|
| Symptom | The captured log or stream stops at a byte cap |
| Wrong reflex | Conclude that the workload stopped at the last captured event |
| Why it hurts | You misclassify a successful run as a failure |
| Correct recovery | Query durable state directly, or recapture the complete stream |
| Confirmation | Terminal state read from the service rather than inferred from the log tail |

---

## 6. Design guidance

Points that generalize beyond this preview:

1. **Checkpoint at a boundary you can name.** "Phase 7 of 18 complete" is recoverable, while "somewhere in the middle" is not.
2. **Give the work an identity that outlives the process.** Recovery means addressing a logical work item, not resuming a socket.
3. **Separate observer failures from workload failures.** Your token expiring is your problem, not the run's.
4. **Treat a 4xx from a hosting layer as transport state, not business truth.** Confirm against durable state before declaring failure.
5. **Make the terminal state explicit.** A stream that merely ends is not a result.
6. **Decide who owns an approval decision.** Applying it twice is worse than applying it late.
7. **Distinguish suspended work from active work.** A parked graph consumes nothing and may be evicted, which is expected rather than a fault.

---

## 7. Boundary and limitations

- Numbers are **observed values from one evaluation**, not benchmarks, guarantees, or SLAs.
- The long-running capability was in **private preview**, so its implementation, packages, APIs, and deployment recipes are not published here.
- Results cover **eight documented main scenarios**. Optional cancel, delete, and deny branches were not counted.
- Recovery behavior was validated. Business-domain correctness and model quality were not.
- Verify current capabilities against [official documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) before designing against anything described here.

## 8. Evidence basis

Every number on this page traces to captured artifacts from the evaluation:

| Claim | Source artifact type |
|---|---|
| Event counts, sequence ranges, elapsed times | Per-scenario captured event streams |
| Phase and output index coverage | Stream analysis over those captures |
| Approval timeline and confirmation | Client session logs |
| 424 retry behavior and stage output | Workflow client log |
| Steering queue and terminal answers | Steering client log |

Raw artifacts stay private because they contain endpoints, work identifiers, environment metadata, and generated payload text.

## Related work

| Repository | Relationship |
|---|---|
| [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/) | The broader build, deploy, and operate lifecycle |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | Hosted-agent tools, memory, and skills |
| [Foundry-Agent-ModelOps-Governance](../Foundry-Agent-ModelOps-Governance/) | Operational-plane boundary mapping |

## License

[MIT](LICENSE)
