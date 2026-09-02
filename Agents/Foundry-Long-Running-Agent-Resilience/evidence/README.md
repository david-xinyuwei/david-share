# Evidence index

This directory contains public-safe evidence only. Raw authenticated screenshots, endpoints, response IDs, session IDs, process IDs, and unredacted Hosted Agent logs remain under the ignored `.repo-evidence/` intake tree.

The reader-facing [recovery timeline PNG](../images/lra-recovery-timeline.png) is derived from the exact local report and the live Foundry cross-check. Its [scalable SVG](../images/lra-recovery-timeline.svg) and [editable Excalidraw source](../images/lra-recovery-timeline.excalidraw) are committed beside it; the diagram summarizes evidence but does not replace the JSON or logs.

| Evidence | Classification | What it proves | Boundary |
|---|---|---|---|
| [`run-contract.json`](run-contract.json) | truth contract | Scenario-declared timeline milestones, state assertions, code hooks, README tokens, and matrix path | The generic gate interprets this data; it does not know LRA event names |
| [`rule-results.json`](rule-results.json) | executable rule result | One PASS/FAIL/N/A/NOT_VERIFIED record for each SOP-68 `RUN-001` through `RUN-015` rule, with assertions and evidence paths | Missing, duplicate, failed, unsupported, or ungrounded rules fail the native gate |
| [`scenario-matrix.json`](scenario-matrix.json) | truth contract | PASS / NOT VERIFIED status for every advertised mode | Each row keeps its runtime and evidence boundary |
| [`owned-hosted-agent-translation-local.json`](owned-hosted-agent-translation-local.json) | dynamic runtime | Real Translator S1 batch, exact process down/recovered/completed times, section 4 checkpoint, section 5 resume, all 12 results | Local AgentServer, not Foundry availability or translation quality |
| [`owned-hosted-agent-translation-local-events.jsonl`](owned-hosted-agent-translation-local-events.jsonl) and [`owned-hosted-agent-translation-local-trace.txt`](owned-hosted-agent-translation-local-trace.txt) | sanitized log / reader trace | Process A loss, Process B recovery, first resumed section, handler completion, original-response completion | Raw response/process identifiers are hashed |
| [`owned-hosted-agent-live-translation.json`](owned-hosted-agent-live-translation.json) | dynamic runtime | Foundry Version 7 recovery across two processes while completing 12 real S1 translations in 89.199 seconds | Exact prior-container down time and translation quality are not claimed |
| [`owned-hosted-agent-live-translation-events.jsonl`](owned-hosted-agent-live-translation-events.jsonl) | sanitized log | Recovery-container entry at section 5, remaining checkpoints, and completion | Does not contain the prior container's exit line |
| [`owned-hosted-agent-live-translation-trace.txt`](owned-hosted-agent-live-translation-trace.txt) | reader trace | Timeout, bounded 49.555-second successful-poll gap, Process B recovery, checkpoint continuity, handler completion, and terminal `completed` | Explicitly labels the exact prior-container down time as unavailable |
| [`owned-hosted-agent-live-translation-output.md`](owned-hosted-agent-live-translation-output.md) | completed business output | All 12 English inputs and 12 verbatim Chinese results from the recovered response | Not human post-edited and not a language-quality evaluation |
| [`owned-hosted-agent-local.json`](owned-hosted-agent-local.json) | dynamic runtime | Fast deterministic Python hard-process regression | Local AgentServer, not the primary long-task proof |
| [`owned-hosted-agent-local-events.jsonl`](owned-hosted-agent-local-events.jsonl) | sanitized log | Deterministic Python handler entry, checkpoints, injected exit, recovery, and completion | Raw response/process identifiers are hashed |
| [`owned-hosted-agent-live-recovery.json`](owned-hosted-agent-live-recovery.json) | dynamic runtime | Foundry Version 5 replacement timeout, same response, two process hashes, recovered entry, completed | The previous container log was not retained, so exact down time is not claimed |
| [`owned-hosted-agent-live-recovery-events.jsonl`](owned-hosted-agent-live-recovery-events.jsonl) | sanitized log | Recovery-container entry and completion on Foundry | Does not contain the prior container's exit line |
| [`owned-hosted-agent-dotnet.json`](owned-hosted-agent-dotnet.json) | dynamic runtime | Real .NET preview packages, CLR exit code 86, second-process recovery, same response, completed | Local AgentServer, not a live .NET deployment |
| [`owned-hosted-agent-dotnet-events.jsonl`](owned-hosted-agent-dotnet-events.jsonl) | sanitized log | .NET checkpoint, fault, recovery, and completion sequence | Raw process and response IDs are hashed |
| [`owned-hosted-agent-observer.json`](owned-hosted-agent-observer.json) | dynamic runtime | Observer A exited, Agent kept working, Observer B resumed the same response | Agent process stayed alive; this is not Agent recovery |
| [`owned-hosted-agent-observer-events.jsonl`](owned-hosted-agent-observer-events.jsonl) | sanitized log | Durable progress while no observer was attached | Local AgentServer |
| [`owned-hosted-agent-graceful-attempt.json`](owned-hosted-agent-graceful-attempt.json) | bounded attempt | Why Windows graceful-shutdown recovery remains NOT VERIFIED | It is not a passing recovery claim |
| [`owned-hosted-agent-live.json`](owned-hosted-agent-live.json) | dynamic runtime | Current safe Version 9 completed all 12 real S1 translations in one process | Fault injection disabled; not a recovery trial |
| [`owned-hosted-agent-status.json`](owned-hosted-agent-status.json) | CLI/API status | Current safe version, state, runtime, protocol, fault switch, and content hash | Endpoint and identities removed |
| [`owned-steering-live.json`](owned-steering-live.json) | dynamic runtime | Foundry Version 9 of the steering Agent: stream closed after 10 committed sections, recovered entry at section 11 on a second process, steered Traditional Chinese response started at section 1 on that process, both responses `completed`, 73.868 seconds | Client-observed only; the exact container-down time is not claimed, and the steer-then-crash order is not claimed |
| [`owned-steering-live-events.jsonl`](owned-steering-live-events.jsonl) and [`owned-steering-live-trace.txt`](owned-steering-live-trace.txt) | sanitized log / reader trace | Stream close, reconnect attempts, recovered entry, steer posted, replacement response, terminal states | Response and process identifiers are hashed |
| [`steering-order-boundary.json`](steering-order-boundary.json) | bounded attempt | Why the steer-then-crash order remains NOT VERIFIED with agentserver-core 2.0.0 and 2.1.0 | It is not a passing recovery claim |
| [`owned-approval-local.json`](owned-approval-local.json) | dynamic runtime | Local AgentServer review gate: 10-section sample, exit code 86 while awaiting review, Process B answered 2.004 seconds after the exit, approval landed on B, 30 sections, 52.411 seconds | Local AgentServer, not Foundry availability |
| [`owned-approval-local-events.jsonl`](owned-approval-local-events.jsonl) and [`owned-approval-local-trace.txt`](owned-approval-local-trace.txt) | sanitized log / reader trace | Exact Process A exit, Process B start, replacement observed, approval, remaining checkpoints, resolved | Session, task, invocation, and process identifiers are hashed |
| [`owned-approval-live.json`](owned-approval-live.json) | dynamic runtime | Foundry Version 4 of the approval Agent: the same review gate survived instance loss; a second process hash answered 36.121 seconds after the fault request, took the approval, and completed sections 11-30 in 75.249 seconds total | The exact instance-down time is not observable by the client |
| [`owned-approval-live-events.jsonl`](owned-approval-live-events.jsonl) and [`owned-approval-live-trace.txt`](owned-approval-live-trace.txt) | sanitized log / reader trace | Review gate, fault request, replacement observed, approval, remaining checkpoints, resolved | Identifiers are hashed |
| [`ui-evidence.json`](ui-evidence.json) | real product UI | Agent-captured visible signed-in window, source/public hashes, redactions, and proof boundaries | UI proves object/version/status/type, not behavior |
| [`runs/owned-agent-recovery-validation-20260826/run-manifest.json`](runs/owned-agent-recovery-validation-20260826/run-manifest.json) | test-run bundle | Commands, exits, logs, status, UI, and key-code hashes for this validation cycle | Raw authenticated sources remain ignored |
| [`public-sdk-contract.json`](public-sdk-contract.json) | dynamic runtime | Pinned public Python SDK symbols, types, decorators, and versions | Installed-package probe |
| [`resilience-sdk-usage.json`](resilience-sdk-usage.json) | dynamic runtime | Real `@task` registration through installed packages | Does not run the handler body |
| [`recovery-contract-demo.json`](recovery-contract-demo.json) and [`recovery-contract-events.jsonl`](recovery-contract-events.jsonl) | test fixture | Lease reclaim, generation fencing, checkpointing, and idempotency | Standard-library reference model, not Foundry internals |
| [`observation-validation.json`](observation-validation.json) | test fixture | Gap, duplicate, bare terminal, status-classification, and deadline rejection | Fixtures are not service responses |
| [`scenario-manifest.json`](scenario-manifest.json) | truth contract | Dynamic runtime / test fixture / explainer classification and non-claims | Prevents evidence-type confusion |
| [`manifest.json`](manifest.json) | integrity manifest | UTF-8/LF-normalized SHA-256 and byte count for every evidence file | Hashes public artifacts only |

## Reproduce without overwriting committed evidence

From the repository root:

```powershell
New-Item -ItemType Directory -Force .demo-state | Out-Null

az login
$env:LRA_TRANSLATOR_ENDPOINT = "https://<translator-name>.cognitiveservices.azure.com"
$env:LRA_TRANSLATOR_REGION = "<resource-region>"
python hosted-agent\run_local_recovery.py `
  --workload translator_batch `
  --crash-after-stage 3 `
  --stage-delay-ms 1000 `
  --report .demo-state\translation-recovery.json `
  --log-report .demo-state\translation-events.jsonl

python hosted-agent\run_local_recovery.py `
  --report .demo-state\python-recovery.json `
  --log-report .demo-state\python-events.jsonl

python hosted-agent\run_observer_restart.py `
  --report .demo-state\observer-restart.json `
  --log-report .demo-state\observer-events.jsonl

dotnet build dotnet-agent\LraEvidenceAgent.csproj -c Release
$dotnetDir = (Resolve-Path dotnet-agent\bin\Release\net8.0).Path
$dotnetDll = Join-Path $dotnetDir LraEvidenceAgent.dll
python hosted-agent\run_local_recovery.py `
  --runtime-label ".NET 8.0" `
  --server-command dotnet $dotnetDll `
  --server-cwd $dotnetDir `
  --report .demo-state\dotnet-recovery.json `
  --log-report .demo-state\dotnet-events.jsonl

# Review gate that survives local process loss (needs the Translator variables above).
$env:LRA_TRANSLATOR_RESOURCE_ID = "<translator-resource-id>"
python hosted-agent-approval\run_approval_recovery.py --local `
  --report .demo-state\approval-local.json `
  --log-report .demo-state\approval-local-events.jsonl

# Against deployed Agents (see hosted-agent-steering\scripts\deploy.sh and hosted-agent-approval\scripts\deploy.sh).
python hosted-agent-steering\run_steering_recovery.py `
  --endpoint "<steering-agent-responses-endpoint-with-api-version-query>" `
  --agent-version <version> `
  --report .demo-state\steering-live.json `
  --log-report .demo-state\steering-live-events.jsonl
python hosted-agent-approval\run_approval_recovery.py `
  --endpoint "<approval-agent-invocations-endpoint-with-api-version-query>" `
  --agent-version <version> `
  --report .demo-state\approval-live.json `
  --log-report .demo-state\approval-live-events.jsonl

python scripts\validate_repo.py
```

Timestamps and hashes change on a new run. The declared milestone order, state assertions, mode status, and acceptance contract must still pass.
