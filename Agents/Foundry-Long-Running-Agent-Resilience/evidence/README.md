# Evidence index

This directory contains public-safe evidence only. Raw authenticated screenshots, endpoints, response IDs, session IDs, process IDs, and unredacted Hosted Agent logs remain under the ignored `.repo-evidence/` intake tree.

| Evidence | Classification | What it proves | Boundary |
|---|---|---|---|
| [`run-contract.json`](run-contract.json) | truth contract | Scenario-declared timeline milestones, state assertions, code hooks, README tokens, and matrix path | The generic gate interprets this data; it does not know LRA event names |
| [`scenario-matrix.json`](scenario-matrix.json) | truth contract | PASS / NOT VERIFIED status for every advertised mode | Each row keeps its runtime and evidence boundary |
| [`owned-hosted-agent-translation-local.json`](owned-hosted-agent-translation-local.json) | dynamic runtime | Real Translator S1 batch, exact process down/recovered/completed times, section 4 checkpoint, section 5 resume, all 12 results | Local AgentServer, not Foundry availability or translation quality |
| [`owned-hosted-agent-translation-local-events.jsonl`](owned-hosted-agent-translation-local-events.jsonl) and [`owned-hosted-agent-translation-local-trace.txt`](owned-hosted-agent-translation-local-trace.txt) | sanitized log / reader trace | Process A loss, Process B recovery, first resumed section, handler completion, original-response completion | Raw response/process identifiers are hashed |
| [`owned-hosted-agent-live-translation.json`](owned-hosted-agent-live-translation.json) | dynamic runtime | Foundry Version 7 recovery across two processes while completing 12 real S1 translations in 89.199 seconds | Exact prior-container down time and translation quality are not claimed |
| [`owned-hosted-agent-live-translation-events.jsonl`](owned-hosted-agent-live-translation-events.jsonl) | sanitized log | Recovery-container entry at section 5, remaining checkpoints, and completion | Does not contain the prior container's exit line |
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

python scripts\validate_repo.py
```

Timestamps and hashes change on a new run. The declared milestone order, state assertions, mode status, and acceptance contract must still pass.
