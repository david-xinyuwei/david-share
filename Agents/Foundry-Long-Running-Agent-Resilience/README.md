# Recover a Microsoft Foundry Hosted Agent after process loss

[![Status](https://img.shields.io/badge/Foundry_capability-public_preview-B3541E)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
[![Scope](https://img.shields.io/badge/scope-repository_owned_agent-1363DF)](#one-complete-recovery-run)
[![Runtimes](https://img.shields.io/badge/runtimes-Python_3.13_%2B_.NET_8-0F8B6D)](#fault-matrix)
[![Protocol](https://img.shields.io/badge/protocol-Responses_%2B_Invocations-5F4BB6)](#put-the-same-hooks-in-your-agent)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

This repository contains a real Hosted Agent, caller, fault harness, and evidence. It answers one question: **when the Agent process disappears, how does the same stored response continue on a new process without losing checkpointed output?**

**Four interruptions on the demonstration portal, double speed, 2:52. This is the visual walkthrough; the committed evidence follows below.**

https://github.com/user-attachments/assets/d548d973-57d4-46e5-bfcd-b85142be9a6f

[Download the repository copy](https://github.com/david-xinyuwei/david-share/raw/refs/heads/master/Agents/Foundry-Long-Running-Agent-Resilience/media/lra-interruption-demo-2x.mp4?download=1)

> **Author:** Xinyu Wei (魏新宇)

[中文](README-CN.md) | English

[Four scenarios](#watch-it-happen-in-the-browser) · [One complete run](#one-complete-recovery-run) · [Fault matrix](#fault-matrix) · [Reproduce](#reproduce-it) · [Use in your Agent](#put-the-same-hooks-in-your-agent) · [Evidence](#evidence-and-boundaries) · [Official documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)

## Read this first

The mechanism is not "restart the old process." The caller creates one stored background response. Process A writes a checkpoint and exits. Process B starts with empty process memory, finds the same persisted response and input, enters the handler with `is_recovery=True`, restores the checkpointed response, and continues. The caller keeps polling the original response ID.

The repository is organized around four interruptions, shown in [the browser walkthrough](#watch-it-happen-in-the-browser): a safe baseline, hard process loss, caller disconnect, a human approval pending while the instance is lost, and a change of target language after recovery. Every scenario runs a real long task, not a sleep loop: the Agent calls Azure Translator S1 section by section and checkpoints each completed result. The recording is the visual walkthrough of those four scenarios; the sections below hold the committed, machine-checked evidence for each of them, and every measured duration in this README comes from those evidence files rather than from the recording.

The run documented next is that mechanism in detail: 12 English sections, Process A lost after section 4, Process B resuming at section 5, and the complete 12-section document with terminal status `completed`. Two runs prove different parts of that statement. The local AgentServer run provides the exact operating-system down timestamp. The Foundry Version 7 run proves replacement-compute recovery in the hosted product and took `89.199` seconds. The same hard-loss contract also passed against the repository-owned .NET handler. This is public-preview capability evidence, not an SLA or production-readiness claim.

The steering and approval Agents run a 30-section version of the same job under the last two interruptions; see [the same job under two more interruptions](#the-same-job-under-two-more-interruptions).

## One complete recovery run

### Where the Agent actually uses LRA

| Required hook | Actual repository code | What it changes |
|---|---|---|
| Import the AgentServer recovery APIs | [`main.py`](hosted-agent/src/lra-evidence-agent/main.py#L16-L24) | Uses the public task and Responses packages |
| Opt the server into crash recovery | [`ResponsesServerOptions(resilient_background=True)`](hosted-agent/src/lra-evidence-agent/main.py#L49-L52) | Stored background responses can be reinvoked after process loss |
| Enable startup recovery scanning | [`set_resilient_tasks_enabled(True)`](hosted-agent/src/lra-evidence-agent/main.py#L52) | A new process scans for recoverable work |
| Create stored background work | [`store=True`, `background=True`](hosted-agent/client.py#L197-L223) | The request and response identity outlive the original connection |
| Restore the durable snapshot | [`context.persisted_response`](hosted-agent/src/lra-evidence-agent/main.py#L170-L175) | A recovered handler starts from previously checkpointed output |
| Commit one durable boundary | [`yield stream.checkpoint()`](hosted-agent/src/lra-evidence-agent/main.py#L202-L228) | Output before that call survives process loss |
| Inject a real hard process exit | [`os._exit(86)`](hosted-agent/src/lra-evidence-agent/main.py#L240-L256) | Process A stops without normal cleanup |
| Keep observing the same work | [`state_file` and `validate_terminal_response`](hosted-agent/client.py#L339-L387) | A caller restart does not create replacement work |

There is no separate package named `LRA`. Python imports the resilient-task and Responses classes from `azure-ai-agentserver-*`:

```python
from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled
from azure.ai.agentserver.responses import (
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)

app = ResponsesAgentServerHost(
    options=ResponsesServerOptions(resilient_background=True)
)
set_resilient_tasks_enabled(True)

# Inside the response handler:
stream = (
    ResponseEventStream(
        response_id=context.response_id,
        response=context.persisted_response,
    )
    if context.is_recovery and context.persisted_response is not None
    else ResponseEventStream(response_id=context.response_id, request=request)
)
# Emit one complete, replay-safe unit of output, then:
yield stream.checkpoint()
```

.NET imports the corresponding NuGet namespaces and enables the same behavior:

```csharp
using Azure.AI.AgentServer.Core;
using Azure.AI.AgentServer.Responses;

var builder = AgentHost.CreateBuilder(args);
builder.AddResponses<LraEvidenceHandler>(
    options => options.ResilientBackground = true);

// Inside CreateAsync:
var stream = context.IsRecovery && context.PersistedResponse is not null
    ? new ResponseEventStream(context, context.PersistedResponse)
    : new ResponseEventStream(context, request);
yield return stream.Checkpoint();
```

The deployable Python package pins are in [`requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt); the .NET package pins are in [`LraEvidenceAgent.csproj`](dotnet-agent/LraEvidenceAgent.csproj).

### What the long task actually does

[`translation_workload.py`](hosted-agent/src/lra-evidence-agent/translation_workload.py) defines 12 public-safe English sections. For each section, [`main.py`](hosted-agent/src/lra-evidence-agent/main.py#L67) obtains a managed-identity token, calls the real Azure Translator S1 REST endpoint, emits the Chinese result, and only then executes `yield stream.checkpoint()`.

The fault request sets `crash_after_stage=3`, so Process A commits `translation_section_04` and calls `os._exit(86)`. Process B restores four output items from `persisted_response`; `_output_count` therefore returns `4`, and the loop starts with `translation_section_05` instead of translating sections 1-4 again. Acceptance rejects the run unless all 12 ordered section records, source hashes, non-empty translations, two process identities, `fresh + recovered`, and the original response's `completed` state are present.

The final hosted output is not merely a status flag: [`owned-hosted-agent-live-translation-output.md`](evidence/owned-hosted-agent-live-translation-output.md) contains all 12 English inputs and all 12 verbatim Translator results. It records completion and recovery, not a human language-quality evaluation.

![Exact Process A to Process B recovery timeline, including the actual request, fault injection, timestamps, checkpoint continuity, and completed state](images/lra-recovery-timeline.png)

The diagram uses the exact local timestamps below and includes the live Foundry boundary at the bottom. [Open the scalable SVG](images/lra-recovery-timeline.svg) or [edit the Excalidraw source](images/lra-recovery-timeline.excalidraw).

### Exactly when it went down, recovered, and completed

The table is from the real S1 run in [`owned-hosted-agent-translation-local.json`](evidence/owned-hosted-agent-translation-local.json). Times below are UTC+8; the JSON keeps ISO timestamps, the full acceptance result, and the sanitized event log.

| Event | UTC+8 | Elapsed | Process | What happened | Durable state after the event |
|---|---|---:|---|---|---|
| Process A started | 18:25:29.748 | 0.021 s | A | AgentServer started with recovery and Translator credentials | No request yet |
| Response created | 18:25:31.601 | 1.875 s | A | Caller sent one `store=true`, `background=true`, `translator_batch` request | Input and response identity persisted |
| Section 4 checkpoint | 18:25:44.638 | 14.911 s | A | Fourth real S1 result completed and `stream.checkpoint()` returned | Chinese results 1-4 persisted |
| Fault injected | 18:25:44.638 | 14.911 s | A | Handler logged the durable boundary and called `os._exit(86)` | Checkpoint survives; process memory is disposable |
| **Process down** | **18:25:45.176** | **15.452 s** | A | OS reported exit code `86` | No Agent process is running |
| Process B started | 18:25:45.190 | 15.466 s | B | New empty process opened the same AgentServer state | Original response remains addressable |
| **Recovery observed** | **18:25:46.591** | **16.864 s** | B | Handler entered `recovered` with the same response hash | Resume point is `translation_section_05` |
| First post-recovery checkpoint | 18:25:50.692 | 20.965 s | B | Fifth real S1 result committed | Process B is doing remaining business work |
| Handler completed | 18:26:11.112 | 41.385 s | B | Sections 5-12 completed; all 12 outputs are present | Response snapshot is complete |
| **Caller saw `completed`** | **18:26:11.276** | **41.556 s** | B | The original response reached its terminal state | Full-output acceptance passed |

Process A was actually down for **1.415 seconds before recovered entry**. Process B completed the handler **25.936 seconds after Process A went down**; the caller observed `completed` after 26.100 seconds. The response-ID SHA-256 remained `9acba831...b393d`; the report contains two different process-instance hashes.

The recovered task **really completed in Process B**. This machine-generated trace is rendered from the committed JSON report:

```text
RUN owned-agent-real-translation-primary
2026-08-26T10:25:29.748+00:00  PROCESS_A_START
2026-08-26T10:25:31.601+00:00  RESPONSE_CREATED       response_sha256=9acba83102c7a3b4da7da422d5083831235a3a6102a9d65c44679e24ff0b393d
2026-08-26T10:25:44.638+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_04
2026-08-26T10:25:44.638+00:00  FAULT_INJECTED         mode=hard_process_exit exit_code=86
2026-08-26T10:25:45.176+00:00  PROCESS_A_DOWN         exit_code=86
2026-08-26T10:25:45.190+00:00  PROCESS_B_START
2026-08-26T10:25:46.591+00:00  HANDLER_RECOVERED      mode=recovered resume_from=translation_section_05
2026-08-26T10:25:50.692+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_05
2026-08-26T10:26:11.112+00:00  HANDLER_COMPLETED
2026-08-26T10:26:11.276+00:00  RESPONSE_STATUS        status=completed
ASSERT same_response_reused=true
ASSERT process_memory_survived=false
ASSERT checkpointed_response_survived=true
ASSERT all_expected_checkpoints_completed_once=true
ASSERT process_instance_count=2
RESULT PASS
```

The source file is [`owned-hosted-agent-translation-local-trace.txt`](evidence/owned-hosted-agent-translation-local-trace.txt); the repository gate requires this README block to match it exactly.

### Hosted run: delay, recovery, and completion log

The real Foundry Version 7 run retained the recovery container log but not the previous container's exit line. Therefore **49.555 seconds is a bounded observation gap between successful polls, not an exact hang duration**. The log still shows the decisive chain: one timeout, Process B entering at section 5, the first recovered checkpoint, handler completion, and the original response reaching `completed`.

| Measurement | Value | Meaning |
|---|---:|---|
| Whole hosted run | 89.199 s | Request start through client-observed `completed` |
| Successful-poll gap around replacement | 49.555 s | Includes timeout, polling, scheduling, and replacement; not exact hang |
| Recovered entry → handler completed | 16.511 s | Process B completed sections 5-12 |
| Handler completed → client saw `completed` | 4.322 s | Final persistence and polling delay |

```text
RUN owned-agent-live-real-translation foundry_version=7
2026-08-26T10:16:04.612+00:00  REQUEST_STARTED        workload=translator_batch response_sha256=cfc1b7056cf1f2e8bb6fe4587405fc099d89c39b79b31fb90fc44f0be5519e09
2026-08-26T10:16:24.658+00:00  LAST_SUCCESSFUL_POLL   status=in_progress
2026-08-26T10:16:58.207+00:00  CONNECTION_TIMEOUT     detail=TimeoutError phase=replacement_window
2026-08-26T10:17:12.978+00:00  HANDLER_RECOVERED      process=B resume_from=translation_section_05
2026-08-26T10:17:14.213+00:00  POLL_AFTER_TIMEOUT     status=in_progress last_checkpoint=translation_section_04
2026-08-26T10:17:15.859+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_05
2026-08-26T10:17:29.489+00:00  HANDLER_COMPLETED      process=B
2026-08-26T10:17:33.811+00:00  RESPONSE_STATUS        status=completed process_instances=2
BOUNDARY exact_process_a_down_at=NOT_AVAILABLE reason=prior_container_log_not_retained
DURATION successful_poll_gap_seconds=49.555 meaning=timeout_plus_polling_plus_replacement_not_exact_hang
DURATION recovered_to_handler_completed_seconds=16.511
DURATION handler_completed_to_client_completed_seconds=4.322
DURATION total_run_seconds=89.199
ASSERT same_response_reused=true
ASSERT checkpoint_continuity=translation_section_04->translation_section_05
ASSERT all_12_translations_present=true
ASSERT entry_modes=fresh+recovered
ASSERT terminal_status=completed
RESULT PASS
```

The source file is [`owned-hosted-agent-live-translation-trace.txt`](evidence/owned-hosted-agent-live-translation-trace.txt). It is generated from the [client report](evidence/owned-hosted-agent-live-translation.json) plus the [sanitized recovery-container events](evidence/owned-hosted-agent-live-translation-events.jsonl), and the repository gate requires this block to match exactly.

### Why the task did not stop and the data did not disappear

| State | Where it lived | What happened at Process A loss |
|---|---|---|
| Python local variables, stack, socket, PID | Process A memory | **Lost**, intentionally |
| Work identity and original input | AgentServer file-backed task state | Survived and was reused by Process B |
| Chinese results for sections 1-4 | Persisted Responses checkpoint | Survived; Process B did not call S1 for them again |
| Remaining sections 5-12 | Derived from the persisted output count and named workload | Process B resumed at `translation_section_05` |
| Response ID and deadline | Caller state file | A new observer can poll the same response |
| Azure Translator calls | External read-only transformation | Completed results were checkpointed; a call after the last checkpoint may still be repeated and billed |
| Payments, bookings, emails, writes | Not used by this workload | **Not proven**; real applications still need idempotency and reconciliation |

This is at-least-once recovery. Work after the last successful checkpoint can run again. Checkpoint before an irreversible operation, and give that operation its own idempotency key.

<div align="center"><img src="images/official-lease-recovery-model.png" width="820" alt="Official Microsoft lease-based recovery model showing a later process reclaiming the same durable work record"></div>

<p align="center"><sub><i>"Lease-based recovery of a resilient work item"</i> from <a href="https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience">Microsoft Foundry documentation</a> © Microsoft, used unmodified under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. It is not covered by this repository's MIT license.</sub></p>

## The same job under two more interruptions

Process loss is one interruption. Two others happen to real long tasks: the requester changes their mind while the work is running, and the work has to wait for a human before it may continue. Two more repository-owned Agents put a 30-section version of the same Translator job under each of them. Their code, deploy scripts, and runners are in [`hosted-agent-steering/`](hosted-agent-steering/) and [`hosted-agent-approval/`](hosted-agent-approval/); the traces below come from Agents deployed from exactly those directories.

### Change of mind after recovery

The steering Agent ([`main.py`](hosted-agent-steering/src/resilient-steering/main.py)) enables `steerable_conversations=True` next to `resilient_background=True`. A steered turn is a new response posted to the same conversation while the first response is still running: the running handler sees `context.pending_input_count > 0`, finishes the section it is on, and emits `completed` with the sections it has; the new response enters with `context.is_steered_turn` and starts the new language at section 1, because a Traditional Chinese document cannot reuse Simplified Chinese sections.

The committed run stacks both interruptions: Process P1 commits `translation_section_10` and calls `os._exit(86)`; the gateway closes the client's stream; the replacement process P2 recovers the same response at `translation_section_11`; only then does the client post the change to Traditional Chinese, and P2 runs the steered response from section 1 to 30 while the original response completes with 14 sections.

```text
RUN owned-agent-live-steering foundry_version=9
2026-09-02T11:41:59.280+00:00  REQUEST_STARTED        response=A target=zh-Hans crash_after_stage=9
2026-09-02T11:42:04.863+00:00  RESPONSE_CREATED       response=A response_sha256=d74fda4d9b75404892324f8a5b52a80cf369a649bbc380b84c9ec1641d93283d
2026-09-02T11:42:04.863+00:00  HANDLER_ENTERED        response=A mode=fresh process=P1
2026-09-02T11:42:17.468+00:00  CHECKPOINT_COMMITTED   response=A checkpoint=translation_section_10 process=P1
2026-09-02T11:42:18.133+00:00  STREAM_CLOSED          response=A committed_sections=10 detail=no_terminal_event_process_gone
2026-09-02T11:42:43.437+00:00  HANDLER_RECOVERED      response=A mode=recovered process=P2 resume_from=translation_section_11
2026-09-02T11:42:43.439+00:00  CHECKPOINT_COMMITTED   response=A checkpoint=translation_section_11 process=P2
2026-09-02T11:42:45.215+00:00  STEER_POSTED           response=B from=zh-Hans to=zh-Hant same_conversation=true original_sections_so_far=14
2026-09-02T11:42:47.830+00:00  RESPONSE_CREATED       response=B response_sha256=89f83641ff214ade2cc9541bbab106594bc3cd34fd8180d5848abcb2d6d2a4d2
2026-09-02T11:42:47.830+00:00  HANDLER_ENTERED        response=B mode=steered process=P2
2026-09-02T11:42:48.791+00:00  CHECKPOINT_COMMITTED   response=B checkpoint=translation_section_01 process=P2 meaning=new_language_starts_at_section_1
2026-09-02T11:43:12.269+00:00  CHECKPOINT_COMMITTED   response=B checkpoint=translation_section_30 process=P2
2026-09-02T11:43:12.659+00:00  RESPONSE_STATUS        response=B status=completed sections=30
2026-09-02T11:43:13.148+00:00  RESPONSE_STATUS        response=A status=completed sections=14
BOUNDARY exact_process_p1_down_at=NOT_AVAILABLE reason=hosted_container_exit_not_observable_by_client observed=stream_close
DURATION stream_close_to_recovered_entry_seconds=25.304 meaning=observation_window_includes_replacement_scheduling_and_reconnect_polling
DURATION steer_posted_to_replacement_completed_seconds=27.444
DURATION total_run_seconds=73.868
ASSERT process_replaced=true
ASSERT checkpoint_continuity=translation_section_10->translation_section_11
ASSERT steered_on_replacement_process=true
ASSERT replacement_starts_at_section_1=true
ASSERT original_sections_kept=14 replacement_sections=30
ASSERT terminal_status=A:completed B:completed
RESULT PASS
```

The source file is [`owned-steering-live-trace.txt`](evidence/owned-steering-live-trace.txt), rendered from [`owned-steering-live.json`](evidence/owned-steering-live.json) by [`render_steering_trace.py`](scripts/render_steering_trace.py); [`run_steering_recovery.py`](hosted-agent-steering/run_steering_recovery.py) produced the report and applies the acceptance rules. The 25.304 seconds between the stream closing and the recovered entry include the reconnect attempts: a `GET` with `stream=true` on a response whose process is gone is rejected until the replacement has re-entered, so the runner polls the durable status in between. The opposite order, steer first and lose the process afterwards, is **NOT VERIFIED**: with `azure-ai-agentserver-core` 2.0.0 and 2.1.0 the replacement process rejected the persisted steered input and the response never left `in_progress`. [`steering-order-boundary.json`](evidence/steering-order-boundary.json) records the observed message.

### Human approval that survives instance loss

The approval Agent ([`main.py`](hosted-agent-approval/src/resilient-approval-gate/main.py)) uses the Invocations protocol and one `@multi_turn_task` chain per job. `start` translates a 10-section sample, commits each section with `await job.flush()`, sets the job phase to `awaiting_review`, and returns; nothing runs while the reviewer reads. `approve_review` re-enters the same chain, reads the committed sections and the phase back from the task store, and translates sections 11-30, again with one flush per section.

The committed local run loses the process while the sample is waiting: Process P1 exits with code 86 0.258 seconds after the fault request; Process P2 starts on the same task store, answers with a new process hash 2.004 seconds after the exit, still reports the sample as `awaiting_review`, takes the approval, and completes the remaining 20 sections. The Foundry run below does the same against Version 4 of the deployed Agent; there the client can only see that a different process answered 36.121 seconds after the fault request.

```text
RUN owned-agent-live-approval foundry_version=4
2026-09-02T11:40:43.595+00:00  REQUEST_STARTED        action=start target=zh-Hans sample_size=10
2026-09-02T11:40:51.774+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_01 batch=sample process=P1
2026-09-02T11:41:00.036+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_10 batch=sample process=P1
2026-09-02T11:41:00.037+00:00  REVIEW_GATE_REACHED    sample_sections=10 task_sha256=0a9c04dced7418f27de9e0b0d3ea05c78f21e9d0103bb194cca920e8d1e38a1b waiting_for=human_reviewer
2026-09-02T11:41:00.037+00:00  FAULT_INJECTED         mode=hard_process_exit exit_code=86 while=awaiting_review
2026-09-02T11:41:36.158+00:00  REPLACEMENT_OBSERVED   process=P2 sample_still=awaiting_review
2026-09-02T11:41:36.158+00:00  APPROVAL_SUBMITTED     decision=approve_review landed_on=P2
2026-09-02T11:41:38.580+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_11 batch=remaining process=P2
2026-09-02T11:41:58.844+00:00  CHECKPOINT_COMMITTED   checkpoint=translation_section_30 batch=remaining process=P2
2026-09-02T11:41:58.844+00:00  TASK_STATUS            status=resolved outcome=completed sections=30
BOUNDARY exact_instance_down_at=NOT_AVAILABLE reason=platform_replaced_the_instance observed=probe_answered_by_new_process
DURATION fault_request_to_replacement_observed_seconds=36.121 meaning=observation_window_not_exact_downtime
DURATION approval_to_completed_seconds=22.686
DURATION total_run_seconds=75.249
ASSERT same_task_identity=true
ASSERT process_replaced=true
ASSERT sample_result_hashes_unchanged=true
ASSERT sample_on_process_p1=true remaining_on_process_p2=true
ASSERT all_sections_present_once=true sections=30
RESULT PASS
```

The source file is [`owned-approval-live-trace.txt`](evidence/owned-approval-live-trace.txt); the local counterpart with the exact exit and restart times is [`owned-approval-local-trace.txt`](evidence/owned-approval-local-trace.txt). Both are generated by [`render_approval_trace.py`](scripts/render_approval_trace.py) from reports written by [`run_approval_recovery.py`](hosted-agent-approval/run_approval_recovery.py), and the gate regenerates and compares them. The approval Agent pins `azure-ai-agentserver-core` 2.0.0 because 2.1.0 removed the `TaskContext.metadata` namespaces this chain keeps its phase in; the steering Agent pins 2.1.0. Fault injection in both Agents is a test-only switch that stays off unless `LRE_ENABLE_FAULT_INJECTION=true` is exported before deploying.

## Watch it happen in the browser

The recording at the top of this README was made on 2026-09-03 on the Xingchen demonstration portal, the source of [`demo-portal/`](demo-portal/). In the recording, the baseline, process-loss, and disconnect scenarios ran a 30-section fault-injection build of the checkpoint Agent with the crash after section 10, while the approval and steering scenarios ran the same `lre-approval-gate` and `lre-steering-agent` as this repository. That portal does not persist machine-readable run records for these scenarios, so the durations shown on screen are one day's single observation for watching and are deliberately not repeated here as evidence.

The four interruptions, and what each one costs. A lost process restarts locally in seconds, while Foundry first has to notice the loss, schedule replacement compute, and start a new process, so the same interruption is visibly longer in the recording:

| # | Scenario | What is interrupted | How the platform continues | What to watch on screen | Committed evidence |
|---|---|---|---|---|---|
| ① | Baseline, nothing interrupted | nothing | durable background response, one checkpoint committed per section | 1 process finishes, no checkpoint missing, terminal completed | [control run](evidence/owned-hosted-agent-live.json) |
| ② | Process loss and recovery | the agent process | a replacement process reclaims the same durable work | A→B process hashes differ, response ID unchanged, no gap or duplicate | [1.415 s locally](evidence/owned-hosted-agent-translation-local.json) · [49.555 s window on Foundry](evidence/owned-hosted-agent-live-translation-trace.txt) |
| ③ | Caller disconnect and reattach | the caller connection | background execution is independent of the caller | still 1 process; progress continues while nobody is attached | [the agent never stopped](evidence/owned-hosted-agent-observer.json) |
| ④ | Instance lost while approval is pending | the instance holding the review | the multi-turn chain keeps phase and sample in the task store | sample hashes unchanged, approval lands on the new instance, remaining sections finish on B | [2.004 s locally](evidence/owned-approval-local-trace.txt) · [36.121 s window on Foundry](evidence/owned-approval-live-trace.txt) |
| ⑤ | Change of mind after recovery | the process and the objective | crash recovery and a steerable conversation stacked | A resumes from its checkpoint, B restarts at section 1 on that same new process, both complete | [25.304 s window on Foundry](evidence/owned-steering-live-trace.txt) |

[`demo-portal/`](demo-portal/) is a standalone extraction of the resilience stage from the larger Xingchen demonstration, not a copy of its unrelated chat, memory, toolbox, routing, or commerce stages. The FastAPI orchestrator in [`demo-portal/app.py`](demo-portal/app.py) drives only the three Agents in this repository. The bilingual UI in [`demo-portal/static/app.js`](demo-portal/static/app.js) exposes a safe baseline plus four interruptions: hard process loss, observer disconnect, a human approval pending during instance loss, and a target-language change after recovery.

The baseline, process-loss, and disconnect buttons target `lra-evidence-agent`, the existing 12-section Agent under [`hosted-agent/`](hosted-agent/). They do not assume 30 sections: the server and browser read `stage_count` from the Agent's checkpoint records. Steering and approval retain their 30-section workloads. [`test_demo_portal.py`](tests/test_demo_portal.py) exercises 12-section checkpoint recovery, a 6-section steering mock, an 8-section approval mock, and damaged-input cases so a fixed section count or an empty recovered lane cannot pass unnoticed.

After the three Agents have been deployed, start the Portal from the repository root:

```powershell
& $python -m pip install --no-input -r demo-portal\requirements.txt
$env:FOUNDRY_PROJECT_ENDPOINT = "<project-endpoint>"
$env:LRA_FAULT_AGENT_NAME = "lra-evidence-agent"
$env:LRA_STEERING_AGENT_NAME = "lre-steering-agent"
$env:LRA_APPROVAL_AGENT_NAME = "lre-approval-gate"
& $python -m uvicorn app:app --app-dir demo-portal --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. The baseline and observer-disconnect runs work against a safe deployment. The three process-loss stories require dedicated non-production Agent versions deployed with `LRE_ENABLE_FAULT_INJECTION=true`; every deploy script defaults that switch to `false`. Do not enable it on a customer-facing Agent. The page visualizes one run, while the JSON reports and logs under [`evidence/`](evidence/) remain the reproducible proof.

## What these four scenarios actually run

There is no language model in this path and therefore no reasoning-effort setting. Every `azure.yaml` here declares `deployments: []`, and no chat, responses-model, or reasoning call exists in any Agent. That is a deliberate choice: recovery is proven by comparing a SHA-256 hash per translated section across the old and the new process, and a sampled model would return different wording on replay, which would destroy the comparison. A deterministic translation service keeps the recovery claim falsifiable.

| Setting | Value as deployed |
|---|---|
| Model deployment | none; `deployments: []` in every `azure.yaml` |
| Reasoning effort | not applicable, because no reasoning model is in the path |
| Work performed | Azure AI Translator, Text Translation `v3.0`, fixed source language `en`, tier S1 |
| Translator auth | `DefaultAzureCredential` token for scope `https://cognitiveservices.azure.com/.default`, header `Ocp-Apim-Subscription-Region`, plus `Ocp-Apim-ResourceId` when the resource has no custom subdomain |
| Target languages offered | `zh-Hans`, `zh-Hant`, `ja`, `ko`, `fr`, `de`, `es` |
| Hosting | Foundry Hosted Agent, `python_3_13`, remote build, `microsoft.foundry` provider |
| Fault injection | environment-gated; the versions left deployed have it disabled |

| # | Agent | Protocol and server SDK | Container | Sections | Portal defaults |
|---|---|---|---|---|---|
| ① | `lra-evidence-agent` | responses `2.0.0`, core and responses `2.1.0b2` | 0.5 vCPU / 1 GiB | 12 | no injection, 300 ms per section |
| ② | `lra-evidence-agent` | responses `2.0.0`, core and responses `2.1.0b2` | 0.5 vCPU / 1 GiB | 12 | crash after stage 3, 300 ms per section |
| ③ | `lra-evidence-agent` | responses `2.0.0`, core and responses `2.1.0b2` | 0.5 vCPU / 1 GiB | 12 | detach after 3 sections for 8 s |
| ④ | `lre-approval-gate` | invocations `2.0.0`, core `2.0.0` and invocations `1.0.0b8` | 1 vCPU / 2 GiB | 30 | sample 10 sections, 300 ms per section |
| ⑤ | `lre-steering-agent` | responses `2.0.0`, core and responses `2.1.0` | 1 vCPU / 2 GiB | 30 | crash after stage 9, steer after 4 sections |

The recording departs from these defaults in one respect: scenarios ①, ②, and ③ ran a 30-section build with the crash after section 10.

The Portal gives every run an absolute 300 s deadline, a 180 s stream timeout, and a 10 s reconnect timeout retried once per second, so a reconnect attempt is never cancelled before the platform finishes its own handshake.

The orchestration behind these scenarios is covered by [`tests/test_demo_portal.py`](tests/test_demo_portal.py) without touching Azure. It asserts the loopback surface and the URL builder, then replays recorded event shapes through the same acceptance functions the live Portal uses: the 12-section contract passes while a gap, a duplicate, and a bare terminal event without a second process are all rejected; the steering path passes on a dynamic section count and fails closed when the resume leaves a gap or stays on the same process; the approval path passes two-phase review and fails closed when a sample hash changes between the phases. Run them with the acceptance step below.

## Fault matrix

| Scenario / mode | Trigger | Expected | Actual result | Status | Evidence |
|---|---|---|---|---|---|
| Real S1 batch, local Agent process loss | `os._exit(86)` after section 4 | Process B resumes at section 5 and finishes the same document | Recovered after 1.415 s; all 12 translations completed 25.936 s after down | **PASS** | [report](evidence/owned-hosted-agent-translation-local.json) · [events](evidence/owned-hosted-agent-translation-local-events.jsonl) |
| Real S1 batch, Foundry Hosted process loss | Guarded `os._exit(86)` on temporary fault-enabled Version 7 | Replacement compute resumes the same stored response | `89.199` s run; replacement timeout, `fresh + recovered`, two process hashes, all 12 results, `completed`; exact old-container down time remains bounded | **PASS** | [reader log](evidence/owned-hosted-agent-live-translation-trace.txt) · [report](evidence/owned-hosted-agent-live-translation.json) · [events](evidence/owned-hosted-agent-live-translation-events.jsonl) · [full output](evidence/owned-hosted-agent-live-translation-output.md) |
| Fast Python contract regression | `os._exit(86)` after a deterministic checkpoint | New process recovers the same response | Recovered after 1.435 s; completed 4.677 s after down | **PASS** | [report](evidence/owned-hosted-agent-local.json) · [events](evidence/owned-hosted-agent-local-events.jsonl) |
| Fast Foundry contract regression | Guarded `os._exit(86)` on temporary Version 5 | Replacement compute recovers the same stored response | Replacement timeout, `fresh + recovered`, two process hashes, and `completed` | **PASS** | [report](evidence/owned-hosted-agent-live-recovery.json) · [events](evidence/owned-hosted-agent-live-recovery-events.jsonl) |
| .NET Agent process loss | `Environment.Exit(86)` after a checkpoint | New CLR process recovers the same response | Recovered after 0.606 s; completed 3.917 s after down | **PASS** | [report](evidence/owned-hosted-agent-dotnet.json) · [events](evidence/owned-hosted-agent-dotnet-events.jsonl) |
| Caller / observer restart | Observer A exits after saving response ID and deadline | Agent continues; Observer B resumes the same response | Durable progress occurred while no observer was attached; Observer B saw `completed` | **PASS** | [report](evidence/owned-hosted-agent-observer.json) · [events](evidence/owned-hosted-agent-observer-events.jsonl) |
| Current safe Foundry deployment | Version 9, fault switch disabled | Normal real S1 batch remains callable after testing | 12 translations completed in one process in 22.862 s | **PASS** | [run](evidence/owned-hosted-agent-live.json) · [status](evidence/owned-hosted-agent-status.json) |
| Graceful host shutdown | Windows console shutdown signal | Host sets shutdown, defers work, later process recovers | Local Windows harness did not drive the complete host shutdown lifecycle | **NOT VERIFIED** | [attempt record](evidence/owned-hosted-agent-graceful-attempt.json) |
| Missing / duplicate output | Remove or duplicate completed output in fixtures | Acceptance fails closed | Gap, duplicate, and bare `done` cases were rejected | **PASS** | [validator evidence](evidence/observation-validation.json) |
| Change of target after recovery (steering Agent) | Guarded `os._exit(86)` after section 10 on Version 9, then a steered turn once P2 had recovered | P2 resumes the original response at section 11; the steered response starts at section 1 on P2; both complete | Recovered entry 25.304 s after the stream closed; steered response entered on P2 and completed 30 sections; original completed with 14; `73.868` s total | **PASS** | [reader log](evidence/owned-steering-live-trace.txt) · [report](evidence/owned-steering-live.json) · [events](evidence/owned-steering-live-events.jsonl) |
| Steer first, then process loss | Steered turn posted, then `os._exit(86)` | P2 recovers the original response and runs the steered turn | Replacement process failed the persisted steered input closed; response stayed `in_progress` (core 2.0.0 and 2.1.0) | **NOT VERIFIED** | [boundary record](evidence/steering-order-boundary.json) |
| Review gate, local process loss (approval Agent) | `os._exit(86)` while the 10-section sample is `awaiting_review` | New process keeps the task identity and sample hashes; approval lands on it; sections 11-30 complete | Exit 86 after 0.258 s; P2 answered 2.004 s later; approval on P2; 30 sections; `52.411` s total | **PASS** | [reader log](evidence/owned-approval-local-trace.txt) · [report](evidence/owned-approval-local.json) · [events](evidence/owned-approval-local-events.jsonl) |
| Review gate, Foundry instance loss | Guarded `os._exit(86)` on Version 4 while `awaiting_review` | Replacement instance keeps the gate and takes the approval | Second process hash answered 36.121 s after the fault request; approval on it; sections 11-30 done 22.686 s later; `75.249` s total | **PASS** | [reader log](evidence/owned-approval-live-trace.txt) · [report](evidence/owned-approval-live.json) · [events](evidence/owned-approval-live-events.jsonl) |

The matrix is data, not a promise. [`run-contract.json`](evidence/run-contract.json) declares the required milestones and state assertions; [`scenario-matrix.json`](evidence/scenario-matrix.json) declares the modes. The validator reads those files instead of hardcoding this demo's event names.

SOP-68 rules are executable, not self-attested: [`scripts\generate_rule_results.py`](scripts/generate_rule_results.py) computes `RUN-001` through `RUN-015`, writes [`rule-results.json`](evidence/rule-results.json), and the repository gate regenerates and compares that file byte-for-byte.

## Reproduce it

### Prerequisites

| Path | Required |
|---|---|
| Real translation recovery | Git, Python 3.13, packages from [`requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt), Azure CLI login, Translator S1, and `Cognitive Services User` on that resource |
| Fast Python recovery and observer restart | The same Python environment; Translator is not required |
| .NET recovery | .NET 8 SDK and restore access for the pinned preview packages in [`LraEvidenceAgent.csproj`](dotnet-agent/LraEvidenceAgent.csproj) |
| Live Foundry deployment | Non-production subscription, Foundry project, Azure CLI 2.80+, `azd` 1.27.1+, project-level `Foundry Project Manager`, and Agent managed-identity access to Translator |
| Steering and approval Agents | The same tooling plus the pins in [`hosted-agent-steering/.../requirements.txt`](hosted-agent-steering/src/resilient-steering/requirements.txt) and [`hosted-agent-approval/.../requirements.txt`](hosted-agent-approval/src/resilient-approval-gate/requirements.txt); the local approval run also needs `LRA_TRANSLATOR_RESOURCE_ID` |

On Windows PowerShell:

```powershell
git clone --depth 1 --filter=blob:none --sparse `
  https://github.com/david-xinyuwei/david-share.git lra-demo
git -C lra-demo sparse-checkout set `
  Agents/Foundry-Long-Running-Agent-Resilience
Set-Location lra-demo\Agents\Foundry-Long-Running-Agent-Resilience

python -m venv .venv
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m pip install --no-input `
  -r hosted-agent\src\lra-evidence-agent\requirements.txt

# 1. Real long task: 12 Azure Translator S1 calls.
az login
$env:LRA_TRANSLATOR_ENDPOINT = "https://<translator-name>.cognitiveservices.azure.com"
$env:LRA_TRANSLATOR_REGION = "<resource-region>"
& $python hosted-agent\run_local_recovery.py `
  --workload translator_batch `
  --crash-after-stage 3 `
  --stage-delay-ms 1000 `
  --report .demo-state\translation-recovery.json `
  --log-report .demo-state\translation-events.jsonl

# 2. Fast deterministic process-loss regression.
& $python hosted-agent\run_local_recovery.py `
  --report .demo-state\python-recovery.json `
  --log-report .demo-state\python-events.jsonl

# 3. Observer A exits -> Observer B resumes; Agent process stays alive.
& $python hosted-agent\run_observer_restart.py `
  --report .demo-state\observer-restart.json `
  --log-report .demo-state\observer-events.jsonl

# 4. Build and hard-exit the repository-owned .NET Agent.
dotnet build dotnet-agent\LraEvidenceAgent.csproj -c Release
$dotnetDir = (Resolve-Path dotnet-agent\bin\Release\net8.0).Path
$dotnetDll = Join-Path $dotnetDir LraEvidenceAgent.dll
& $python hosted-agent\run_local_recovery.py `
  --runtime-label ".NET 8.0" `
  --server-command dotnet $dotnetDll `
  --server-cwd $dotnetDir `
  --report .demo-state\dotnet-recovery.json `
  --log-report .demo-state\dotnet-events.jsonl

# 5. Review gate that survives local process loss (Translator variables from step 1).
& $python -m pip install --no-input `
  -r hosted-agent-approval\src\resilient-approval-gate\requirements.txt
$env:LRA_TRANSLATOR_RESOURCE_ID = "<translator-resource-id>"
& $python hosted-agent-approval\run_approval_recovery.py --local `
  --report .demo-state\approval-local.json `
  --log-report .demo-state\approval-local-events.jsonl

# 6. Repository acceptance.
& $python -m unittest discover -s tests -v
& $python scripts\validate_repo.py
```

Done-when each runner exits `0`; the translation report contains 12 non-empty results plus `recovery_proven: true`, `fresh + recovered`, two process hashes, and `completed`; the observer report shows two observer processes but one Agent process.

For Linux/macOS, use `.venv/bin/python` and `/` path separators. The runner accepts any server command, so the same contract is reused for Python and .NET instead of duplicating acceptance logic.

To deploy the safe Python Agent to Foundry:

```powershell
Set-Location hosted-agent
az login
azd auth login
azd ext install microsoft.foundry
azd env new <environment-name> `
  --subscription <subscription-id> `
  --location <supported-region> `
  --no-prompt
azd env set LRA_ENABLE_FAULT_INJECTION false
azd env set LRA_TRANSLATOR_ENDPOINT "https://<translator-name>.cognitiveservices.azure.com"
azd env set LRA_TRANSLATOR_REGION "<resource-region>"
azd provision
azd deploy
azd ai agent show lra-evidence-agent
```

Structured status and the Portal show repository-owned Version 9 as `active` / `Running`, `hosted` / `Hosted`, with fault injection disabled. A safe Version 9 real translation request completed all 12 sections in one process. By itself, that safe run is not live process-loss recovery evidence; the live proof is the temporary Version 7 row, after which Version 9 replaced it.

The steering and approval Agents deploy from their own directories with [`hosted-agent-steering/scripts/deploy.sh`](hosted-agent-steering/scripts/deploy.sh) and [`hosted-agent-approval/scripts/deploy.sh`](hosted-agent-approval/scripts/deploy.sh). Each script reads the subscription, location, project ID, project endpoint, and Translator resource ID from the environment, sets the `azd` environment, and runs `azd provision` and `azd deploy`. Then run `run_steering_recovery.py --endpoint "<responses endpoint with its API-version query>"` or `run_approval_recovery.py --endpoint "<invocations endpoint with its API-version query>"` with `--agent-version`; both authenticate with the Azure CLI login and exit non-zero unless every acceptance rule passes.

## Put the same hooks in your Agent

1. Pin the public AgentServer packages for your runtime.
2. Enable resilient background execution on the server.
3. Send `store=true` and `background=true`.
4. Persist `response.id`, your business work ID, and one absolute deadline before acknowledging success upstream.
5. After a complete, replay-safe unit of work, commit application state and then checkpoint the response.
6. On recovered entry, restore `persisted_response` or your application/framework checkpoint and skip already committed work.
7. Poll only the original response. Never create replacement work because a read timed out.
8. Make every external side effect idempotent or explicitly reconcilable.

Use an application database when progress is not fully represented by the response snapshot, or when approvals, tool state, large artifacts, payments, bookings, or writes must survive.

## Acceptance contract

A recovery claim passes only when all of these are true:

- Process A actually exits after a recorded checkpoint.
- Process B has a different process-instance hash and enters as `recovered`.
- Work ID, input hash, and response-ID hash are unchanged.
- The recovered run starts after the last durable checkpoint.
- Every expected checkpoint appears exactly once with no gap or duplicate.
- The original response reaches an explicit `completed` terminal state.
- External side effects are either absent, idempotent, or separately reconciled.

A `done` frame, a green Portal status, or a new successful request is not recovery proof.

## Evidence and boundaries

| Evidence | What it proves |
|---|---|
| [`run-contract.json`](evidence/run-contract.json) | Scenario-declared milestones and state assertions used by the generic gate |
| [`scenario-matrix.json`](evidence/scenario-matrix.json) | PASS / NOT VERIFIED status for each advertised mode |
| [Real local translation report](evidence/owned-hosted-agent-translation-local.json), [events](evidence/owned-hosted-agent-translation-local-events.jsonl), and [trace](evidence/owned-hosted-agent-translation-local-trace.txt) | Exact hard-loss time, section 4 boundary, section 5 resume, all 12 results, completion |
| [Live Version 7 reader log](evidence/owned-hosted-agent-live-translation-trace.txt), [report](evidence/owned-hosted-agent-live-translation.json), [events](evidence/owned-hosted-agent-live-translation-events.jsonl), and [full output](evidence/owned-hosted-agent-live-translation-output.md) | Visible timeout/recovery/completion chain and complete Translator result |
| [Fast Python report](evidence/owned-hosted-agent-local.json) and [events](evidence/owned-hosted-agent-local-events.jsonl) | Deterministic regression of the same recovery contract |
| [.NET report](evidence/owned-hosted-agent-dotnet.json) and [events](evidence/owned-hosted-agent-dotnet-events.jsonl) | The same contract executed by real .NET preview packages |
| [Observer report](evidence/owned-hosted-agent-observer.json) and [events](evidence/owned-hosted-agent-observer-events.jsonl) | Background work continued with no attached observer |
| [Version 9 safe run](evidence/owned-hosted-agent-live.json) and [status](evidence/owned-hosted-agent-status.json) | Current normal completion, runtime, protocol, status, fault switch, and content hash |
| [UI lineage](evidence/ui-evidence.json), [Version 9 list](images/product-ui/portal-owned-agent-list.png), and [Version 9 details](images/product-ui/portal-owned-agent-details.png) | Original/public image hashes, redactions, and deployment-object proof |
| [Run bundle](evidence/runs/owned-agent-recovery-validation-20260826/run-manifest.json) | Commands, exits, logs, status, UI, and key-code hashes |
| [Steering reader log](evidence/owned-steering-live-trace.txt), [report](evidence/owned-steering-live.json), and [events](evidence/owned-steering-live-events.jsonl) | Stream close, recovered entry at section 11, steered response from section 1 on the replacement process, both terminal states |
| [Steer-then-crash boundary](evidence/steering-order-boundary.json) | Why that order stays NOT VERIFIED with core 2.0.0 and 2.1.0 |
| [Approval local trace](evidence/owned-approval-local-trace.txt), [report](evidence/owned-approval-local.json), [events](evidence/owned-approval-local-events.jsonl), and the [Foundry trace](evidence/owned-approval-live-trace.txt), [report](evidence/owned-approval-live.json), [events](evidence/owned-approval-live-events.jsonl) | Review gate, exit code 86 while `awaiting_review`, replacement process, approval landing on it, sections 11-30 completing |

The linked Portal screenshots prove the deployed object, version, state, and type. They do not prove process recovery; JSON and logs provide that behavior evidence. Raw authenticated screenshots and identifiers are not committed.

This repository does not prove an SLA, repeated-trial reliability, load behavior, multi-region recovery, translation quality, or exactly-once external side effects. The steering and approval runs are single trials as well: they prove the recovery contract for a change of target after recovery and for a pending human approval, not the steer-then-crash order. Long-running-agent resilience is public preview and is not recommended for production workloads without workload-specific testing.

## Related work and license

- [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/)
- [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/)
- [Official long-running-agent resilience documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
- [Official API reference, including Python and .NET](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-reference)

Project-authored content is licensed under [MIT](LICENSE). The official Microsoft diagram is used under CC BY 4.0 and excluded from the MIT license; see [Third-party notices](THIRD-PARTY-NOTICES.md).
