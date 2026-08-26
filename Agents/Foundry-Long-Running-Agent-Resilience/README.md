# Resilience for Long-Running Agents on Microsoft Foundry: Evidence from Injected Process Loss

[![Status](https://img.shields.io/badge/Foundry_capability-public_preview-B3541E)](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)
[![Scope](https://img.shields.io/badge/scope-repository_owned_agent-1363DF)](#repository-owned-hosted-agent-result)
[![Runtime](https://img.shields.io/badge/runtime-Python_3.13-0F8B6D)](#measured-results)
[![Protocol](https://img.shields.io/badge/protocol-Responses-5F4BB6)](#three-integration-options)
[![License](https://img.shields.io/badge/license-MIT-D98E04)](LICENSE)

This repository asks one question: **if the process running a long task disappears, can the same task continue from saved progress instead of starting over?** It includes a repository-owned deployable Hosted Agent and client, a current Version 4 deployment check, a local two-process recovery test, SDK contract checks, tests, and reviewable evidence.

The capability is in **public preview**. Every interruption was deliberate, not an outage. Results apply only to this non-production implementation and test environment; they are not an SLA or production-readiness claim.

> **Author:** Xinyu Wei (魏新宇)

[中文](README-CN.md) | English

[Reproduce](#reproduce-with-this-repository) · [Measured results](#measured-results) · [Recovery model](#deep-dive-how-recovery-works) · [Evidence](#evidence-and-boundaries) · [Official documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience)


## Start here

Do not read the whole repository first. Choose the path that matches your goal:

| What you want to do | Go here |
|---|---|
| Add recovery to your Hosted Agent | [Reproduce with this repository](#reproduce-with-this-repository) — packages, server settings, deployment, state, identity, caller and fault test |
| Watch two local processes recover one task | [Run local and live checks](#run-local-validate-then-deploy) — the first two paths need no Azure subscription |
| Inspect the measured claim | [Measured results](#measured-results), then [evidence and boundaries](#evidence-and-boundaries) |

The shortest accurate answer is: enable resilient stored background work on the server and request; choose safe rerun, a Responses snapshot, or application-owned state; then keep the same response/work ID in the caller. An external database is required only when meaningful progress lives outside the stored response or a side effect must be reconciled.

**Done-when:** after injected process loss, the same work identity reaches an explicit terminal state with complete expected output, and committed side effects are not duplicated.

## Reproduce with this repository

The complete customer path is here in the main README. The runnable Agent, caller and evidence are owned by this repository:

| File | What it does |
|---|---|
| [`hosted-agent/azure.yaml`](hosted-agent/azure.yaml) | Deploys `lra-evidence-agent` as a Python 3.13 Hosted Agent over Responses `2.0.0` |
| [`hosted-agent/src/lra-evidence-agent/main.py`](hosted-agent/src/lra-evidence-agent/main.py) | Complete executable handler with deterministic named checkpoints and one guarded hard process exit |
| [`hosted-agent/client.py`](hosted-agent/client.py) | Creates stored background work, saves and reuses the response ID, and rejects gaps, duplicates, expired observation, one-process "recovery," or an incomplete terminal state |
| [`hosted-agent/run_local_recovery.py`](hosted-agent/run_local_recovery.py) | Starts process A, verifies exit code `86`, starts process B against the same state root, and validates completion |

The Agent uses `ResponsesServerOptions(resilient_background=True)`, `set_resilient_tasks_enabled(True)`, `context.persisted_response`, `stream.checkpoint()` and `context.exit_for_recovery()`.

The Microsoft [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) sample at `b9b2cdd` remains the public API reference, not the executable product path. Its `2.1.0b2` deployment pins must not be replaced with the separate `2.0.0` compatibility-probe pins.

### Choose where progress lives

| Strategy | External progress store? | Use when |
|---|---|---|
| Safe rerun | No | The entire handler is inexpensive and safe to repeat |
| Responses checkpoint | No separate database for completed response output | Progress is the staged output in one response |
| Application/framework checkpoint | Yes | Business state, approvals, large artifacts, writes, payments, bookings or tool state must survive |

Foundry persists work identity, input, leases and stored response events. It does not automatically preserve arbitrary business state or make side effects idempotent.

### Prerequisites

| Requirement | Configuration |
|---|---|
| Local | Git and Python 3.13 |
| Azure | A non-production subscription and Foundry project; this deterministic Agent needs no model deployment |
| Permissions | `Foundry Project Manager` at project scope; creating a project also requires `Owner` at resource-group scope |
| Tools | Azure CLI 2.80+, Azure Developer CLI (`azd`) 1.27.1+, and `azd ext install microsoft.foundry` |
| Sign-in | `az login` and `azd auth login` |
| Packages | [`hosted-agent/src/lra-evidence-agent/requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt) pins core and Responses to `2.1.0b2` |

Use a short clone path on Windows, such as `$HOME\lra-work`.

### Run local, validate, then deploy

The fastest no-Azure check is a standard-library recovery contract:

```console
git clone --depth 1 --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git lra-demo
git -C lra-demo sparse-checkout set Agents/Foundry-Long-Running-Agent-Resilience
cd lra-demo/Agents/Foundry-Long-Running-Agent-Resilience

python scripts/recovery_contract_demo.py demo --summary-file .demo-state/summary.json --events-file .demo-state/events.jsonl
```

Done-when is exit code `0` and a summary containing `"passed": true`, `worker_a_exit_code: 9`, `entry_modes: ["fresh", "recovered"]`, and phases `1-5`.

On Windows PowerShell, run the repository-owned Agent locally, run every gate in a separate SDK environment, then deploy the same source to an isolated non-production project:

```powershell
# Repository-owned Agent: process A exits 86; process B completes the same response.
python -m venv .venv-owned-agent
$ownedPython = (Resolve-Path .\.venv-owned-agent\Scripts\python.exe).Path
& $ownedPython -m pip install --no-input -r hosted-agent\src\lra-evidence-agent\requirements.txt
& $ownedPython hosted-agent\run_local_recovery.py --python $ownedPython

# SDK contract probe and all repository gates use their own pinned environment.
python -m venv .venv-validation
$validationPython = (Resolve-Path .\.venv-validation\Scripts\python.exe).Path
& $validationPython -m pip install --no-input -r requirements-validation.txt
& $validationPython examples\resilience_sdk_usage.py --check
& $validationPython scripts\verify_public_resilience_api.py --quiet
& $validationPython scripts\validate_observations.py self-test
& $validationPython -m unittest discover -s tests -v
& $validationPython scripts\validate_repo.py

# Live fault test. Use a dedicated non-production environment.
Set-Location .\hosted-agent
azd env new <environment-name> `
  --subscription <subscription-id> `
  --location <supported-region> `
  --no-prompt
azd env set LRA_ENABLE_FAULT_INJECTION true
azd env set LRA_STAGE_DELAY_MS 500
azd provision
azd deploy

$agent = azd ai agent show lra-evidence-agent --output json |
  ConvertFrom-Json
python .\client.py `
  --endpoint $agent.agent_endpoints.responses `
  --auth azure-cli `
  --agent-version $agent.version `
  --deployed-content-sha256 $agent.definition.code_configuration.content_hash `
  --work-id owned-agent-live-001 `
  --payload "public-safe live recovery workload" `
  --crash-after-stage 1 `
  --deadline-seconds 360

# Return the deployment to a safe state after collecting evidence.
azd env set LRA_ENABLE_FAULT_INJECTION false
azd deploy
Set-Location ..
```

Linux, macOS and WSL can run the no-Azure checks with:

```bash
python3 -m venv .venv-owned-agent
OWNED_PYTHON=.venv-owned-agent/bin/python
"$OWNED_PYTHON" -m pip install --no-input -r hosted-agent/src/lra-evidence-agent/requirements.txt
"$OWNED_PYTHON" hosted-agent/run_local_recovery.py --python "$OWNED_PYTHON"

python3 -m venv .venv-validation
VALIDATION_PYTHON=.venv-validation/bin/python
"$VALIDATION_PYTHON" -m pip install --no-input -r requirements-validation.txt
"$VALIDATION_PYTHON" examples/resilience_sdk_usage.py --check
"$VALIDATION_PYTHON" scripts/verify_public_resilience_api.py --quiet
"$VALIDATION_PYTHON" scripts/validate_observations.py self-test
"$VALIDATION_PYTHON" -m unittest discover -s tests -v
"$VALIDATION_PYTHON" scripts/validate_repo.py
```

Done-when is `PASS: imported azure.ai.agentserver.core.tasks`, all SDK contract checks pass, `Ran 22 tests ... OK`, and `PASS: bilingual parity ... Data/Log Rich ... Code/Test Rich`.

### Configure external state only when needed

For application/framework checkpoints, create one durable record per logical job:

| Field | Purpose |
|---|---|
| `work_id` | Stable application job ID and primary key |
| `response_id` or `input_id` | Maps the job to Foundry work |
| `completed_phase` | Last phase whose output was committed |
| `state_ref` | JSON state or pointer to a large artifact |
| `idempotency_key` | Stable key sent to downstream operations |
| `status` | `running`, `completed`, `failed` or `needs_reconciliation` |
| `version` / ETag | Rejects a stale process after takeover |
| `updated_at` | Audit and timeout decisions |

Set non-secret resource names with `azd env set CHECKPOINT_ENDPOINT <resource-endpoint>` and `azd env set CHECKPOINT_DATABASE <database-name>`, then map them under `environmentVariables` in `azure.yaml`. Authenticate through the identity method supported by the selected SDK, commonly `DefaultAzureCredential`; never embed a connection string. After deployment, run `azd ai agent show`, open the Hosted Agent's **Identity** in Foundry, and grant least privilege—such as `Storage Blob Data Contributor`—on only the required Blob, Cosmos DB or SQL scope.

Use a transaction or ETag condition to commit the stage result and `completed_phase` together. Derive downstream idempotency keys from `work_id + phase`; when the target supports neither idempotency nor result lookup, record `needs_reconciliation` instead of guessing. Keep `TaskContext.metadata` small: phase, idempotency key or an external-state pointer.

### Caller and acceptance contract

| Action | Required behavior |
|---|---|
| Create | Send `store=true` and `background=true`; `stream=true` is optional |
| Persist | Save `response.id`, `work_id` and one absolute deadline before acknowledging success upstream |
| Reconnect | Read only `GET /responses/{response_id}` or `GET /responses/{response_id}?stream=true`; never create replacement work |
| Recover | Treat bounded timeout, `404`, `424`, `429` and replacement `5xx` as transient only for that known response ID |
| Finish | Require an explicit terminal state, every named checkpoint exactly once, one payload hash, and complete expected output |
| Unknown create result | Do not create another response automatically; remote create and local ID persistence are not atomic, so deduplicate or reconcile |

Local done-when is process A exit code `86`, process B entry mode `recovered`, two process instances, and every expected checkpoint exactly once. Live done-when is Version 4, `fault_injection_requested: false`, a completed checkpoint contract, and status `completed`. Public evidence stores hashes rather than endpoint, response, process, tenant or subscription identifiers.

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

### Repository-owned Hosted Agent result

This repository now owns the complete test path rather than asking the reader to trust an external sample:

| Surface | Repository implementation | What the run proved |
|---|---|---|
| Current deployment | [`hosted-agent/azure.yaml`](hosted-agent/azure.yaml), pinned [`requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt), and [`owned-hosted-agent-live.json`](evidence/owned-hosted-agent-live.json) | Repository-owned Version `4` is active and completes the full checkpoint contract with fault injection disabled |
| Runtime | [`main.py`](hosted-agent/src/lra-evidence-agent/main.py) | Each named checkpoint is persisted; recovery seeds from `context.persisted_response`; hard exit is guarded by the non-production fault switch |
| Local recovery | [`run_local_recovery.py`](hosted-agent/run_local_recovery.py) and [`owned-hosted-agent-local.json`](evidence/owned-hosted-agent-local.json) | Process A exits with code `86`; Process B reuses the same stored response; `fresh` and `recovered` entries and two process hashes prove takeover |
| Caller | [`client.py`](hosted-agent/client.py) | Saves the original response ID, polls only that ID, enforces one deadline, and rejects missing/duplicate checkpoints or incomplete terminal output |

<div align="center"><img src="images/product-ui/portal-owned-agent-list.png" width="820" alt="Sanitized Microsoft Foundry Portal Agent list showing lra-evidence-agent version 4 as Running and Hosted"></div>

<div align="center"><img src="images/product-ui/portal-owned-agent-details.png" width="820" alt="Sanitized Microsoft Foundry Portal details for lra-evidence-agent version 4 showing hosted kind and Playground"></div>

*Real Microsoft Foundry Portal views of this repository's Agent. The project name is replaced with `non-production project`; no tenant, subscription, endpoint, response or identity value is shown. The screenshots prove Version `4` is `Running` and `Hosted`. The Version 4 structured run proves normal completion with no fault requested; the local two-process report proves injected recovery for the same repository implementation. Source lineage, redactions, hashes and proof boundaries are in [`ui-evidence.json`](evidence/ui-evidence.json).*

The Version 4 poll sequence moved from `in_progress` to `completed` on the same stored response. Raw identifiers are not published; the evidence contains hashes. The official [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) sample remains an API reference only; it is not required to reproduce this repository's result.

### Recovery model at a glance

The figure below is the **official Microsoft diagram**, reproduced unmodified. It shows the published lease-based recovery contract; it is not a disclosure of private service components.

<div align="center"><img src="images/official-lease-recovery-model.png" width="820" alt="Official Microsoft diagram of lease-based recovery: work and input identity, runtime persists input and acquires a lease, handler runs while the runtime renews the lease, the process stops and abandons the lease, a later process reclaims the work record, and the handler re-enters from the start to either rerun or resume from the durable boundary"></div>

<p align="center"><sub><i>"Lease-based recovery of a resilient work item"</i> from <a href="https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/long-running-agent-resilience">Resilience for long-running Microsoft Foundry hosted agents</a> © Microsoft, used under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Unmodified. This image is <b>not</b> covered by this repository's MIT license.</sub></p>

### The repository is executable, not just a write-up

| Path | Contract |
|---|---|
| [`hosted-agent/`](hosted-agent/) | Repository-owned deployable Hosted Agent, recovery client, local two-process runner and exact package pins |
| [`examples/resilient_responses_agent.py`](examples/resilient_responses_agent.py) | Complete Responses recovery wiring: server opt-in, persisted-response restore, per-stage checkpoint and shutdown handoff |
| [`examples/resilience_handler.py`](examples/resilience_handler.py) | The actual typed `@task` handler that imports and reads the public recovery context |
| [`examples/resilience_sdk_usage.py`](examples/resilience_sdk_usage.py) | Loads that handler through the real decorator and emits dynamic JSON evidence; `--check` runs without an Azure endpoint |
| [`scripts/recovery_contract_demo.py`](scripts/recovery_contract_demo.py) | Standard-library SQLite recovery reference with two real OS processes, hard process loss, lease reclaim, generation fencing, checkpointing and idempotency |
| [`scripts/verify_public_resilience_api.py`](scripts/verify_public_resilience_api.py) | Checks the required public symbols and handler rules against the pinned installed SDK packages |
| [`scripts/validate_observations.py`](scripts/validate_observations.py) | Rejects sequence gaps, duplicate/missing output, insufficient terminal proof, and unclassified `424` / `403` conditions |
| [`scripts/validate_repo.py`](scripts/validate_repo.py) | Fail-closed bilingual, evidence-integrity, Data/Log Rich and Code/Test Rich repository gate |
| [`tests/`](tests/) | Twenty-two tests covering recovery contracts, authentication, persisted deadlines, positive/negative paths, timing, replay, input integrity and validator refusal |
| [`evidence/`](evidence/) | Structured summaries, JSONL events, truth labels, normalized SHA-256 hashes and reproduction index |

Each file below uses the public SDK, or deliberately does not:

| Code | Direct SDK use |
|---|---|
| [`examples/resilient_responses_agent.py`](examples/resilient_responses_agent.py) | Uses `ResponsesServerOptions(resilient_background=True)`, `set_resilient_tasks_enabled(True)`, `context.persisted_response`, `stream.checkpoint()` and `context.exit_for_recovery()` |
| [`examples/resilience_handler.py`](examples/resilience_handler.py) | Imports `RetryPolicy`, `TaskContext`, and `task`; registers `@task(name="resilience-api-usage")`; reads task/input identities, `ctx.metadata`, entry mode, and recovery/retry counters; exits through `ctx.exit_for_recovery()` on shutdown |
| [`examples/resilience_sdk_usage.py`](examples/resilience_sdk_usage.py) | Imports the handler, runs the real decorator registration, and writes `resilience-sdk-usage.json` |
| [`scripts/verify_public_resilience_api.py`](scripts/verify_public_resilience_api.py) | Imports the same task types plus `TaskMetadata` and Responses recovery signals, then validates the installed package contract |
| [`scripts/recovery_contract_demo.py`](scripts/recovery_contract_demo.py) | Deliberately imports **no Azure SDK**; it tests the recovery algorithm locally with SQLite and two OS processes |
`--check` proves that the installed package imports and that the real decorator registers the typed handler. It does **not** execute the handler body or prove live recovery; the body runs only inside a Hosted Agent runtime.

**Pinned SDK limitation:** in core 2.0.0, returning from `await ctx.metadata.flush()` is not a durable-write acknowledgement because storage callback failures are logged rather than propagated to the handler. The lower-level `@task` example therefore reads metadata but does not present `flush()` as a confirmed checkpoint. The current Responses sample instead calls `stream.checkpoint()` to persist response snapshots; business state still needs a checkpointer that can confirm the write or a reconciliation path.


## Measured results

| Scenario | Interruption and recovery | Measured result | Boundary |
|---|---|---|---|
| Current Version 4 deployment | No fault requested | Same stored response reached `completed`; every expected checkpoint was present exactly once; the report records Version `4` and the deployed content hash | Proves current deployment and normal completion, not live process-loss recovery |
| Repository-owned local recovery | Process A hard-exited; Process B started against the same AgentServer state | Exit code `86`, unchanged response-ID hash, `fresh + recovered`, two process-instance hashes, and a complete checkpoint-contract hash | Real local AgentServer recovery; not a Foundry service availability result |
| Public SDK contract | Clean pinned environment | Every required import, runtime type, member, decorator rule, and package version passed | Installed-package contract only; not live recovery |

These are scoped capability checks, not an SLA or reliability percentage.

## Deep dive: how recovery works

Recovery requires the **task ID, input, and completed progress to be stored outside the process that is currently executing the task**. Completed progress can be a framework-managed response snapshot or application-owned state. If the process exits, a replacement process finds the same work and resumes from that durable boundary.

The flow has three steps:

1. Before execution, the platform stores the task ID and input.
2. After each completed checkpoint, the handler saves the response snapshot or commits application state outside the process.
3. If that process exits, a replacement process loads the same task record and continues with the next unfinished checkpoint.

Client reconnection only resumes reading status and output; it does not start recovery.

### Three concepts used below

- **Task record:** a durable record stored outside the executing process. It keeps the same task ID when a replacement process takes over.
- **Checkpoint:** the latest business boundary that the application has confirmed complete and stored.
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
| Output observation | Stream replay reconnects clients; an explicit Responses `stream.checkpoint()` also persists a completed response snapshot | Validator checks sequence, output coverage, and terminal evidence; it does not simulate a service stream |

**Executable local recovery demo.**

[`recovery_contract_demo.py`](scripts/recovery_contract_demo.py) uses only the Python standard library. Worker A commits phase 1 and exits through `os._exit(9)`; after lease expiry, Worker B reclaims the same work and completes phases 2-5. It writes a [JSON result](evidence/recovery-contract-demo.json) and [JSONL event log](evidence/recovery-contract-events.jsonl).

Tests enforce four rules: reclaim only pending or expired work; block stale writers; deduplicate identical replay and reject conflicting replay; save phase output and checkpoint in one transaction.

This is a **local test fixture**, not Foundry service code or live-service evidence.

### Four layers required for recovery

Four layers must line up; the process and handler layers remain **public-preview / experimental** APIs.

| Layer | Configuration | What it enables | What it does not do alone |
|---|---|---|---|
| Hosted Agent version | `host: azure.ai.agent` + Responses protocol | Deploys your code and exposes a managed Responses endpoint | Does not make an active handler crash-recoverable |
| Agent process *(public preview)* | `ResponsesServerOptions(resilient_background=True)` + `set_resilient_tasks_enabled(True)` | Re-invokes stored background work after process loss | Does not choose the application's durable boundary |
| Handler *(public preview)* | `context.persisted_response` + `stream.checkpoint()`, or an application/framework checkpoint | Restores completed output or business state | Does not make external side effects idempotent |
| Client | `store=True`, `background=True`, same `response.id` | Creates addressable work and lets the caller poll or reattach | Must not replace recovery with a new create call |

**Official sample.**

Use the pinned deployable [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) sample as the public API reference, not as the runnable product path. Complete prerequisites, commands and storage choices are in [Reproduce with this repository](#reproduce-with-this-repository).

**Process recovery.**

Set `ResponsesServerOptions(resilient_background=True)`; the official sample also calls `set_resilient_tasks_enabled(True)` to make its opt-in explicit. Then send `store=True` and `background=True`. A foreground response or a background response without storage is not crash-reinvoked. The interfaces remain experimental; see the [SDK report](evidence/public-sdk-contract.json) for the lower-level symbol list.

**Saved progress.**

After re-entry, the handler reads its Responses snapshot, framework checkpoint or application record. A phase may repeat if the process died before that boundary; a committed phase must be skipped.

| Application need | Public API (`azure-ai-agentserver-core` 2.0.0) |
|---|---|
| Identify the work and input | `TaskContext.task_id`, `TaskContext.input_id` |
| Know whether entry is fresh or recovered | `TaskContext.entry_mode` |
| Count recovery separately from retry | `recovery_count`, `retry_attempt` |
| Store a small progress marker | `TaskContext.metadata` |

The observed recovered entry reported `recovery_count=1` and `retry_attempt=0`.

The pattern is: read identity and progress, rebuild state, run one replay-safe phase, persist its output and external-operation IDs, then advance the checkpoint. Payments, bookings, writes, and tools still require [idempotency](#prevent-duplicate-approvals-and-side-effects).

**Creation and observation.**

This repo tests local progress storage and result validation. Use the [official quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent) for authenticated calls; the repo does not invent your endpoint, identity, store, or workload schema.

| Concern | Application rule |
|---|---|
| Create crash window | Remote create and local persistence of the response ID are not atomic; the tested API also had no lookup by application work key. Preserve an unknown result instead of creating again. Production needs deduplication or reconciliation. |
| Observer restart | Persist `response_id` and deadline, then retrieve the **same response** from a new observer. |
| Recovery authority | Use `response_id` plus workload state, not a transport cursor. |
| Later turns | `previous_response_id` links sequential turns; concurrent queuing and steering require the resilient-task surface. |
| Read boundary | A read-only adapter is **not** a security sandbox or RBAC boundary. Untrusted observers need a separate service and identity; platform and workload completion remain separate checks. |

Use `azd ai agent invoke` for ordinary calls. Use a tested application client when you must persist IDs and deadlines, restart polling, or enforce workload completion.


## Evaluation: what was actually run

This repository separates the current live deployment check from the injected-recovery check so neither is overstated.

### Current public-preview contract check

The reproduction section checks pinned public packages in a clean Python 3.13 environment. Every required check passed against `core` 2.0.0, `invocations` 1.0.0, and `responses` 2.0.0; the exact assertions and versions are in the [JSON report](evidence/public-sdk-contract.json).

This proves the installed public API surface—not live recovery. Any failed assertion returns a nonzero exit code.

### Current Version 4 deployment

The repository-owned `lra-evidence-agent` Version `4` was queried directly on Foundry:

| Check | Result |
|---|---|
| Portal object | Version `4`, `Running`, `Hosted` |
| Safe request | `fault_injection_requested: false` |
| Terminal result | `completed` with the full owned checkpoint contract |
| Source identity | Deployment content hash recorded in the structured report |

This live run proves the current safe deployment works. It deliberately does **not** claim live process-loss recovery.

### Local injected recovery

The same repository implementation was then run through the local AgentServer recovery path. Process A committed durable progress and hard-exited with code `86`; Process B opened the same state root and response, entered as `recovered`, and completed every expected checkpoint exactly once. This proves the application recovery contract locally, not Foundry availability or an SLA.


## Acceptance rules

Acceptance is tied to the checkpoint contract in the repository-owned Agent, not to a headline stage count. The client requires the exact named checkpoint sequence, unique checkpoint-result hashes, one payload hash, the same work identity, and an explicit terminal state. Public evidence commits a hash of that contract rather than turning its size into a product claim.

[`validate_observations.py`](scripts/validate_observations.py) implements the remaining rules below; its [JSON report](evidence/observation-validation.json) records both passing and failing cases.

### Reject gaps and duplicates

`sequence == sorted(sequence)` proves order, not continuity. The corrected check compares adjacent values and the full expected output range.

| Counterexample | Original sorted-order check | Corrected check |
|---|---:|---:|
| Dropped event: `[10, 12]` | `True` | `False` |
| Duplicate event: `[10, 10, 11]` | `True` | `False` |
| Clean stream: `[10, 11, 12]` | `True` | `True` |

The same rule rejects missing or repeated output indexes. Feed it completed items, not every streaming delta, because deltas for one item legitimately share an index.

### A `done` frame is not proof of success

A closed stream can mean success, cancellation, failure, or observer loss. `completion_is_proven` requires service status, an explicit terminal event, and the complete checkpoint contract; `{"type": "done"}` alone is insufficient.

### Classify `424` separately from `403`

Continue bounded polling on `424` only when the same work remains addressable and host replacement is confirmed; otherwise fail closed. For `403`, verify read identity and scope, and refresh only after confirmed expiry. The workload deadline—not an arbitrary retry count—sets the stop point.

### Prevent duplicate approvals and side effects

The same approval may arrive again after recovery. The SQLite ledger skips identical replay and rejects conflicting content. Real payment, booking, and write APIs must honor the same idempotency identity or they may still execute twice.


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


## Design guidance

These are engineering recommendations, not product guarantees:

1. **Save progress at a verifiable boundary.** A named committed checkpoint is useful; "somewhere in the middle" is not.
2. **Store the task ID and completed progress outside the executing process.** A replacement process must be able to find the same task record and continue from the latest checkpoint.
3. **Assume at-least-once execution.** Repeating payments, approvals, writes, and tools must be harmless.
4. **Separate reader failure from work failure, and require an explicit terminal result.**
5. **Classify status codes against durable state before acting.**
6. **Distinguish suspended from active work.** Waiting for approval may release compute without losing the task.


## Evidence and boundaries

### How these claims were challenged

| Method | Evidence | Outcome |
|---|---|---|
| Is the current deployment real? | Version 4 Portal views plus a structured run carrying the deployment content hash | Object-existence and normal-completion claims accepted |
| Does Version 4 UI prove recovery? | UI evidence explicitly says it does not | Live-recovery overclaim rejected |
| Same local work or fresh rerun? | One response-ID hash, `fresh + recovered`, and two process hashes | Fresh-rerun explanation rejected |
| Is terminal state enough? | The validator also requires the exact checkpoint contract, payload identity, and process evidence | Terminal-only evidence rejected |

### What the numbers trace to

| Claim surface | Public evidence | Source boundary |
|---|---|---|
| Current public SDK symbols and handler rules | [`public-sdk-contract.json`](evidence/public-sdk-contract.json) | Real installed-package probe; not live recovery |
| Direct SDK import and `@task` registration | [`resilience-sdk-usage.json`](evidence/resilience-sdk-usage.json) | Generated by the example's own `--check`; not handler execution or live recovery |
| Lease, process loss, generation fence, checkpoint, idempotency | [`recovery-contract-demo.json`](evidence/recovery-contract-demo.json) + [JSONL events](evidence/recovery-contract-events.jsonl) | Real local test fixture; not Foundry service code |
| Gap, duplicate, terminal-state and 424/403 error paths | [`observation-validation.json`](evidence/observation-validation.json) | Executable positive and negative fixtures |
| Repository-owned deployment and recovery contract | [`run-manifest.json`](evidence/runs/owned-agent-version4-validation-20260826/run-manifest.json) links [`owned-hosted-agent-live.json`](evidence/owned-hosted-agent-live.json), [`owned-hosted-agent-local.json`](evidence/owned-hosted-agent-local.json), status, UI, commands, exits, logs, and key-code hashes | Version 4 live completion plus local injected recovery; each claim keeps its own boundary |
| Scenario truth labels | [`scenario-manifest.json`](evidence/scenario-manifest.json) | Separates live deployment, local recovery, test fixtures, and non-claims |
| File integrity and reproduction commands | [`manifest.json`](evidence/manifest.json) + [evidence index](evidence/README.md) | SHA-256 covers the public evidence files |

Raw live artifacts remain private because they contain endpoints, work IDs, environment metadata, and payload text. Public evidence contains hashes and scoped results; local JSONL uses synthetic data.

### Boundaries

- The current live evidence is one safe Version 4 run; it is not a benchmark, guarantee, SLA, or live recovery trial.
- Injected recovery is proven by the local two-process AgentServer run, not by the Portal screenshots.
- The capability is in public preview. Check the [current official documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) before designing against it.
- This repository contains no Microsoft SDK source or private service implementation. It pins public packages and publishes only its own application code and public-safe evidence.

### Before you call this production-ready

For a specific workload, require all of the following:

- repeated failure-injection trials with an explicit recovery-time objective and failure budget;
- idempotency tests for every external write, approval, payment, booking, or tool side effect;
- load and concurrency tests that include overlapping turns and replacement compute;
- timeout, cancellation, retention, deletion, and dead-letter policy;
- monitoring that separates runtime, workload, observer, and authentication failures;
- revalidation against current product documentation for your target region, runtime, and protocol.


## Related work

| Repository | Relationship |
|---|---|
| [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/) | The broader build, deploy, and operate lifecycle |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | Hosted-agent tools, memory, and skills |
| [Foundry-Agent-ModelOps-Governance](../Foundry-Agent-ModelOps-Governance/) | Operational-plane boundary mapping |

## License

Project-authored content is licensed under [MIT](LICENSE). The official Microsoft diagram is used under CC BY 4.0 and is excluded from the MIT license; see [Third-party notices](THIRD-PARTY-NOTICES.md).
