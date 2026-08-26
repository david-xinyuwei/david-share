# Long-Running Agent Resilience: Customer Start Here

This is the shortest complete path for adding process-loss recovery to a Microsoft Foundry Hosted Agent. It covers the server, progress strategy, Azure deployment, optional external state, caller behavior, and recovery test.

[Chinese](CUSTOMER-START-HERE-CN.md) | **English** | [Full technical evidence](README.md)

## Supported path

`this repository's Hosted Agent -> stored background response -> stage checkpoint -> injected process loss -> same response ID completes`

The runnable path is now owned by this repository:

| File | What it does |
|---|---|
| [`hosted-agent/azure.yaml`](hosted-agent/azure.yaml) | Deploys `lra-evidence-agent` as a Python 3.13 Hosted Agent over Responses `2.0.0` |
| [`hosted-agent/src/lra-evidence-agent/main.py`](hosted-agent/src/lra-evidence-agent/main.py) | Complete executable handler: five deterministic stages, one checkpoint per stage, and one guarded hard process exit |
| [`hosted-agent/client.py`](hosted-agent/client.py) | Creates stored background work, saves the response ID, polls that same ID, and rejects gaps, duplicates, one-process "recovery," or an incomplete terminal state |
| [`hosted-agent/run_local_recovery.py`](hosted-agent/run_local_recovery.py) | Starts process A, verifies exit code 86, starts process B against the same state root, and validates completion |

The agent explicitly uses `ResponsesServerOptions(resilient_background=True)`, `set_resilient_tasks_enabled(True)`, `context.persisted_response`, `stream.checkpoint()`, and `context.exit_for_recovery()`.

The Microsoft [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) sample at `b9b2cdd` remains the pinned public API reference, not the executable product path. Its `2.1.0b2` package pins must not be replaced with this repository's historical `2.0.0` offline-probe pins.

### Choose the progress strategy

| Strategy | External progress store? | Use when |
|---|---|---|
| Safe rerun | No | The entire handler is cheap and safe to repeat |
| Responses checkpoint | No separate database for completed response output | Progress is the staged output in one response |
| Application/framework checkpoint | Yes | Business state, approvals, large artifacts, writes, payments, bookings, or tool state must survive |

Foundry persists the work identity, input, lease, and stored response events. It does not automatically checkpoint arbitrary business state.

### Prerequisites

| Requirement | Configuration |
|---|---|
| Azure | Non-production subscription; this deterministic agent needs a Foundry project but no model deployment |
| Permissions | `Foundry Project Manager` at project scope; creating a project also requires `Owner` at resource-group scope |
| Tools | Python 3.13, Azure CLI 2.80+, Azure Developer CLI (`azd`) 1.27.1+, Git |
| Sign-in | `az login`, `azd ext install microsoft.foundry`, `azd auth login` |
| Packages | [`hosted-agent/src/lra-evidence-agent/requirements.txt`](hosted-agent/src/lra-evidence-agent/requirements.txt) pins core and Responses to `2.1.0b2` |

### Prove recovery locally first

From the repository root:

```powershell
python -m venv .venv-owned-agent
$python = (Resolve-Path .\.venv-owned-agent\Scripts\python.exe).Path
& $python -m pip install -r hosted-agent\src\lra-evidence-agent\requirements.txt
& $python hosted-agent\run_local_recovery.py --python $python
```

Pass only when process A exits with code `86`, process B reports `recovered`, and stages `0-4` complete once on the same response. The committed [local evidence](evidence/owned-hosted-agent-local.json) records that result without publishing the raw response or process IDs.

### Deploy and run the live fault test

Use an isolated non-production project because the test intentionally terminates its own process:

```powershell
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
```

The measured repository run used version `1`: after an initial `in_progress`, one read timeout, and replacement compute, the same response completed all five stages across two process instances in **57.884 seconds**. The public-safe [live evidence](evidence/owned-hosted-agent-live.json) stores hashes instead of endpoint, response, process, tenant, or subscription identifiers.

When the fault test is not in use, run `azd env set LRA_ENABLE_FAULT_INJECTION false` and `azd deploy`. Normal requests cannot trigger a hard exit when that setting is false.

### Configure external state only when needed

Create one durable record per logical job:

| Field | Purpose |
|---|---|
| `work_id` | Stable application job ID and primary key |
| `response_id` or `input_id` | Maps the job to Foundry work |
| `completed_phase` | Last phase whose output was committed |
| `state_ref` | JSON state or pointer to a large artifact |
| `idempotency_key` | Stable key sent to downstream operations |
| `status` | `running`, `completed`, `failed`, or `needs_reconciliation` |
| `version` / ETag | Rejects a stale process after takeover |
| `updated_at` | Audit and timeout decisions |

1. Set non-secret values with `azd env set CHECKPOINT_ENDPOINT <resource-endpoint>` and `azd env set CHECKPOINT_DATABASE <database-name>`.
2. Map those names under the agent service's `environmentVariables` in `azure.yaml`.
3. Authenticate through the identity method supported by the selected SDK, commonly `DefaultAzureCredential`; never embed a connection string.
4. After deployment, confirm the active version with `azd ai agent show`, open the Hosted Agent's **Identity** in Foundry, and grant least privilege on the target resource—for example, `Storage Blob Data Contributor` on one Blob scope or the appropriate data-plane role on one Cosmos DB database/container.
5. Use a transaction or ETag condition to commit the stage result and `completed_phase` together.
6. Derive the downstream idempotency key from `work_id + phase`. If the target has no idempotency or lookup API, mark an uncertain result `needs_reconciliation` instead of guessing.
7. Keep `TaskContext.metadata` small: phase, idempotency key, or state pointer. Do not store conversation history, model output, tool results, or large artifacts there.

For executable storage logic, use [`recovery_contract_demo.py`](scripts/recovery_contract_demo.py). Its SQLite implementation includes lease/generation fencing, atomic phase-result plus checkpoint commit, idempotency, and conflicting-replay rejection.

### Configure the caller

| Action | Required behavior |
|---|---|
| Create | Send `store=true` and `background=true`; `stream=true` is optional |
| Persist | Save `response.id`, your `work_id`, and a deadline before acknowledging success to your caller |
| Reconnect | Use `GET /responses/{response_id}` or `GET /responses/{response_id}?stream=true` |
| Finish | Require an explicit terminal state and complete expected output |
| Unknown create result | Do not create another response automatically; remote create and local ID persistence are not atomic, so deduplicate or reconcile |

### Accept the recovery

On Linux, WSL2, or a container, start the pinned sample with `SIMULATE_CRASH_AFTER_STAGE=0 azd ai agent run`, create a stored background response, restart with the same `AGENTSERVER_STATE_ROOT`, and query the same response ID.

Pass only when every expected stage appears once and the response reaches an explicit terminal state. With application-owned storage, repeat the fault once before and once after every phase commit: an uncommitted phase must rerun safely, a committed phase must be skipped, and no side effect may be duplicated.

The capability is in public preview and has no production SLA. See the [full evidence, failure boundaries, and measured runs](README.md) before making a production-readiness claim.
