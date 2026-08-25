# Long-Running Agent Resilience: Customer Start Here

This is the shortest complete path for adding process-loss recovery to a Microsoft Foundry Hosted Agent. It covers the server, progress strategy, Azure deployment, optional external state, caller behavior, and recovery test.

[Chinese](CUSTOMER-START-HERE-CN.md) | **English** | [Full technical evidence](README.md)

## Supported path

`stored background response -> resilient Hosted Agent -> stage checkpoint -> same response ID after process loss`

Use Microsoft's deployable [`resilient-streaming`](https://github.com/microsoft-foundry/foundry-samples/tree/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming) sample at commit `b9b2cdd`. Do not begin with an invented partial `azure.yaml`.

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
| Azure | Non-production subscription, Foundry project, and model deployment |
| Permissions | `Foundry Project Manager` at project scope; creating a project also requires `Owner` at resource-group scope |
| Tools | Python 3.13, Azure CLI 2.80+, Azure Developer CLI (`azd`) 1.27.1+, Git |
| Sign-in | `az login`, `azd ext install microsoft.foundry`, `azd auth login` |
| Packages | `pip install azure-ai-agentserver-core==2.1.0b2 azure-ai-agentserver-responses==2.1.0b2` |

The pinned sample's [`azure.yaml`](https://github.com/microsoft-foundry/foundry-samples/blob/b9b2cdd67efee6287e4b263f83ed45f18fe892be/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming/azure.yaml) already defines `host: azure.ai.agent`, Responses protocol `2.0.0`, Python `3.13`, and the project/model dependency.

### Configure the agent

Use the complete executable handler in [`examples/resilient_responses_agent.py`](examples/resilient_responses_agent.py). Replace only `run_stage()` with one completed unit of your work.

| Location | Required setting | Purpose |
|---|---|---|
| Server | `ResponsesServerOptions(resilient_background=True)` | Makes stored background responses eligible for recovery |
| Explicit opt-in | `set_resilient_tasks_enabled(True)` | Records the sample's resilient-task intent |
| Recovery entry | `context.is_recovery` + `context.persisted_response` | Restores the last response snapshot |
| Durable boundary | `yield stream.checkpoint()` after a complete stage | Commits completed output before the next stage |
| Shutdown | `await context.exit_for_recovery()` | Leaves unfinished work for a later process |

One completed output item maps to one stage in this example. If the stage changes an external system, also use application storage and idempotency.

### Run and deploy

1. Run `git clone https://github.com/microsoft-foundry/foundry-samples.git`.
2. Pin it with `git -C foundry-samples checkout b9b2cdd67efee6287e4b263f83ed45f18fe892be`.
3. Enter `foundry-samples/samples/python/hosted-agents/bring-your-own/responses/resilient-streaming`.
4. Start locally with `azd ai agent run`; the endpoint is `http://localhost:8088`.
5. Create work with `store=true` and `background=true`; save the returned `response.id`.
6. Run `azd provision`, then `azd deploy`.
7. Invoke with `azd ai agent invoke '{"input":"test recovery","store":true,"background":true}'`.
8. Inspect logs with `azd ai agent monitor --follow`.

The sample simulates three stages and needs no model credential locally. For a real model call, replace `_stage_tokens` or `run_stage()` and use the hosted container's injected `FOUNDRY_PROJECT_ENDPOINT`; do not commit credentials.

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
