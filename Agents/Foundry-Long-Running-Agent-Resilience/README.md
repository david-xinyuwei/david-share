# Foundry Long-Running Agent Resilience

[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/foundry-long-running-agent-resilience-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/foundry-long-running-agent-resilience-ci.yml)
[![Evidence](https://img.shields.io/badge/sanitized_evidence-8%2F8_PASS-0F8B6D)](data/validation-matrix.json)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)

An evidence-first validation kit for long-running Microsoft Foundry Hosted Agents: checkpoint a real workload, inject failure, reconnect through the original logical work item, and require a valid terminal result.

> **Public boundary:** this repository publishes a sanitized attestation and reusable validation method. It **does not include private-preview source code**, private packages, raw hosted logs, service endpoints, resource identifiers, credentials, or deployment recipes. The result is **not a production certification** or an availability statement for every topology.

> **Author:** Xinyu Wei (魏新宇) - Microsoft AI and Apps GBB Senior System Engineer

[Chinese](README-CN.md) | English | [Hosted agents overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

---

## Executive Summary

The validated campaign covered **eight main documented scenarios** across Python and .NET, Responses and Invocations, graph human approval, a persisted workflow, and active-turn steering. All eight reached their workload-level pass criteria.

| Result | Public-safe evidence | Why it matters |
|---|---|---|
| 8/8 main scenarios passed | Eight independent files in `evidence/sanitized-runs/` plus a generated matrix | One aggregate number cannot hide a missing runtime or protocol. |
| Research workloads with 18 total phases completed despite injected failure | Python/.NET, Responses/Invocations attestations | A short smoke test cannot stand in for a long-running recovery path. |
| Human approval survived restart | Two graph HITL scenarios | Recovery preserved a pending decision boundary, not only generated text. |
| Workflow and steering reached terminal outcomes | Persisted stage outputs and a queued materially different follow-up | Durability and steering are tested as workload behavior. |
| Public artifacts are hash-locked | `evidence/manifest.json` | Evidence changes are visible and deterministic. |

The central lesson is simple:

> **Active deployment is a control-plane fact. Resilience is a workload-level claim that needs checkpoint, disruption, continuity, and terminal evidence.**

## What Is Real and What Is Withheld

| Layer | Published here | Boundary |
|---|---|---|
| Authenticated execution result | Sanitized per-scenario assertions derived from hosted runs | Real-run attestation, not a synthetic success fixture. |
| Validation code | Matrix validator, JSONL summarizer, manifest verifier, public scanner, tests | Fully executable with no Azure credential. |
| Parser fixtures | Two small synthetic JSONL streams under `tests/fixtures/` | Explicitly labeled `test-fixture`; never presented as live evidence. |
| Raw hosted evidence | Not published | Can contain endpoint, work identifiers, environment metadata, and generated payload text. |
| Original implementation | Not published | Private source and package details remain outside this public repository. |
| Deployment recipe | Not published | Use the official Foundry quickstart for public deployment guidance. |

## Evidence Hierarchy: Why Active Is Not Enough

An agent version can be active while the main scenario still fails after checkpointing, during reconnection, at approval resume, or during final snapshot retrieval. This kit separates six evidence levels:

1. Version active.
2. Work accepted.
3. Checkpoint observed.
4. Failure and connection drop observed.
5. Recovery marker or same-work continuity observed.
6. Full plan reaches terminal success.

Only Level 6 counts as a pass. See [Methodology](docs/methodology.md).

## Validation Architecture

![Evidence pipeline from authenticated run through checkpoint, failure, reconnect, sanitization, and hash-locked public attestation](images/evidence-pipeline.png)

The public boundary is intentionally one-way: raw evidence can produce a sanitized attestation, but the public artifact cannot reconstruct private service identity or deployment details.

## Scenario Coverage

![Eight validation scenarios grouped into research durability, graph approval, durable workflow, and steering proof patterns](images/scenario-coverage.png)

| Scenario ID | Runtime | Protocol | Main proof |
|---|---|---|---|
| `research-invocations-python` | Python | Invocations | 18 phases, checkpoint, failure, recovery event, `run_completion`. |
| `research-responses-python` | Python | Responses | 18 items, lifecycle reset, same-response resume, completed. |
| `graph-hitl-invocations-python` | Python | Invocations | Approval checkpoint survives failure and resumes to confirmation. |
| `graph-hitl-responses-python` | Python | Responses | Reconnect plus approval resume reaches a confirmed terminal result. |
| `durable-workflow-python` | Python | Responses | Persisted stage outputs survive temporary host unavailability. |
| `steering-python` | Python | Responses | A materially different follow-up queues and completes with a relevant answer. |
| `research-invocations-dotnet` | .NET | Invocations | 18 phases, checkpoint, failure, recovery event, `run_completion`. |
| `research-responses-dotnet` | .NET | Responses | 18 items continue on the same response after reconnect and complete. |

## Protocol-Specific Proof

### Invocations

Invocations owns its custom task and SSE contract. Strong evidence includes a workload checkpoint, a connection drop, an explicit recovery event, all documented phases, a terminal `done=completed`, and durable task termination by normal run completion.

### Responses

Responses uses the stored response lifecycle. Recovery can be proven by a lifecycle reset or by the observable invariant that the same response continues from the first uncheckpointed output index and reaches `completed`. The validator accepts both because SDK event replay differs at reconnect cursors.

### Graph Human Approval

The pass gate is not "an approval prompt appeared." The pending approval must remain durable across failure, the decision must resume exactly once, and the graph must execute the post-approval path to a terminal confirmation.

### Durable Workflow and Steering

A workflow pass requires persisted stage outputs and a terminal result. A steering pass requires a materially different follow-up input, queued delivery while another turn is active, termination of the old turn, and a relevant completed answer for the new input.

## Methodology

The method uses one falsifiable chain for every scenario:

```text
authenticated run
  -> workload checkpoint
  -> injected process failure
  -> connection drop / temporary unavailability
  -> reconnect with original logical work reference + cursor
  -> recovery marker or same-work output continuity
  -> full plan + terminal success
  -> sanitized public attestation + SHA-256 manifest
```

The full acceptance rules are in [docs/methodology.md](docs/methodology.md). The field schema and privacy rules are in [docs/evidence-contract.md](docs/evidence-contract.md).

## Evidence Contract

Every committed run declares runtime, protocol, proof pattern, source class, status, and pattern-specific assertions. The validator fails on:

- missing or duplicate scenario IDs,
- fewer or more than eight expected scenarios,
- missing phase, checkpoint, failure, recovery, approval, or completion evidence,
- a summary that does not match scenario rows,
- identity-bearing fields such as endpoint, resource, session, response, invocation, tenant, or subscription identifiers,
- manifest path traversal, missing files, byte changes, or SHA-256 changes.

The JSON Schema is [data/evidence-contract.schema.json](data/evidence-contract.schema.json); deterministic checks live in [src/lra_resilience/evidence.py](src/lra_resilience/evidence.py).

[scenario-manifest.json](scenario-manifest.json) classifies repository surfaces as `dynamic-runtime`, `architecture-explainer`, or `test-fixture`. A committed attestation can be a regression fixture for the validator while its `source_kind` still records that the assertion came from an authenticated run; synthetic parser fixtures remain isolated under `tests/fixtures/`.

## Quick Start

```bash
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Agents/Foundry-Long-Running-Agent-Resilience
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e .
lra-evidence validate
lra-evidence manifest
python scripts/runtime_differential.py
```

Expected output:

```text
PASS: validated 8 sanitized scenarios
PASS: verified 9 evidence artifacts
PASS: differential summaries changed with protocol-level input
```

No Azure credential is needed to validate committed public evidence.

## CLI

Validate the generated matrix:

```bash
lra-evidence validate --matrix data/validation-matrix.json
```

Verify all committed hashes:

```bash
lra-evidence manifest
```

Summarize your own JSONL stream without retaining identity fields:

```bash
lra-evidence summarize path/to/events.jsonl --output summary.json
```

The summarizer retains only event type, phase, output index, status, total, and sequence number. Unknown fields are discarded.

## Re-run with Your Own Events

1. Capture the complete stream privately; do not stop at a byte cap.
2. Keep raw evidence outside this repository.
3. Run `lra-evidence summarize` against the private JSONL file.
4. Review the public summary for business payloads or identity-bearing values.
5. Add a new contract only with matching tests and documentation.

This repository does not deploy or invoke an agent. Follow the [official Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent) for public deployment instructions.

## Running on Azure

This repository is an offline evidence validator, not an Azure deployment template. Validating the committed matrix requires no Azure credential and creates no cloud resource.

To generate evidence from your own Azure workload:

1. Deploy a Hosted Agent through the [official quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent).
2. Capture the complete authenticated event stream in a private location.
3. Run the documented checkpoint, failure, reconnect, and terminal-result sequence.
4. Use `lra-evidence summarize` to derive a protocol-only summary.
5. Review the summary before publication; never commit credentials, endpoints, IDs, business payloads, or raw logs.

Azure deployment and cost-bearing resource changes remain outside this repository's automation boundary.

## Failure Modes and Lessons

| Failure mode | Incorrect interpretation | Correct evidence response |
|---|---|---|
| Active version | "Resilience passed." | Run checkpoint through terminal completion. |
| Truncated stream | "Only captured phases ran." | Treat as incomplete evidence and query durable state. |
| Observer token expires at final GET | "The workload failed." | Refresh observer auth and repeat the read-only terminal query. |
| Runtime-specific reset event is absent | "Recovery did not occur." | Check same-work continuity, output indexes, cursor, and completion. |
| Approval decision is interpreted twice | "Approve means deny." | Identify the single owner of the approval contract. |
| Background lifecycle is omitted | "Stored recovery is broken." | Verify the request selected the required lifecycle. |
| Service onboarding is missing | "Enable an unrelated feature." | Separate service allowlisting from customer registration. |
| Shell quoting corrupts payload | "API rejected valid schema." | Use a structured or file-backed client and retain HTTP evidence. |

See [Failure Modes and Adjudication](docs/failure-modes.md) for the evidence rule behind each case.

## Repository Layout

```text
data/                         Generated matrix and public JSON Schema
docs/                         Methodology, evidence contract, and failure analysis (EN/CN)
evidence/sanitized-runs/      Eight public-safe real-run attestations
images/                       Generated architecture and coverage visuals
scripts/                      Build, validation, differential, and asset tools
src/lra_resilience/           Evidence, event-summary, manifest, and CLI library
tests/                        Contract, tamper, privacy, parser, and differential fixtures
tests/fixtures/               Synthetic JSONL parser inputs; never live-run evidence
scenario-manifest.json        Dynamic runtime / architecture / fixture classification
```

## Quality Gates

| Gate | Command | Failure behavior |
|---|---|---|
| Evidence contract | `python scripts/validate_evidence.py` | Missing proof or changed hash fails. |
| Runtime differential | `python scripts/runtime_differential.py` | Identical summaries for different streams fail. |
| Bilingual structure | `python scripts/validate_readmes.py` | Heading, table, code, image, link, or critical-claim drift fails. |
| Public boundary | `python scripts/validate_repo.py` | Credential values, IDs, private URLs, endpoints, or local paths fail. |
| Unit tests | `pytest -q` | Contract, parser, manifest, and tamper regressions fail. |
| Lint | `ruff check src tests scripts` | Static code findings fail. |
| Dependency audit | `pip-audit --local` | Known vulnerabilities in the clean installed environment fail. |
| Package | `python -m build --wheel` | Clean build failure blocks delivery. |

CI runs on Windows and Linux with Python 3.10-3.13.

## Public Boundary

This repository is a true public subset of a private validation campaign. It keeps the methodology, generic evidence contract, sanitized results, failure analysis, and executable checks. It withholds raw output, identifiers, private code, private packages, internal collaboration records, and environment-specific deployment details.

The `8/8` result means all eight main documented scenarios in the validation matrix passed. It does not mean every optional cancel/delete/deny branch, every region, every model, or every production topology was certified.

## Official Public Sources

| Source | Public fact used here | Verified |
|---|---|---|
| [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | Hosted agents support Responses and Invocations, stateful sessions, background work, Python/C#, and managed lifecycle. | 2026-07-23 |
| [Deploy your first hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent) | Public deployment and invocation workflow with `azd`, Python SDK, or VS Code. | 2026-07-23 |

The private implementation used for the original campaign is intentionally not linked or described.

## Related Repos

| Repo | Relationship |
|---|---|
| [Foundry-Agent-Lifecycle-Build-Deploy-Operate](../Foundry-Agent-Lifecycle-Build-Deploy-Operate/) | Broader Build, deploy, and operate lifecycle. |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | Hosted-agent tools, memory, skills, and operational validation. |
| [Foundry-Agent-ModelOps-Governance](../Foundry-Agent-ModelOps-Governance/) | Evidence-driven operational-plane boundary mapping. |

## Limitations

- Committed evidence is a sanitized attestation, not independently replayable raw service telemetry.
- The kit validates evidence semantics; it does not deploy an agent or certify service availability.
- Optional branches outside each main documented scenario are not included in the 8/8 count.
- Failure injection validates recovery behavior, not business-domain correctness or model quality.

## Next Steps

1. Apply the evidence hierarchy to another long-running workload without changing its business logic.
2. Add a new proof pattern only with an authenticated run, an exact assertion contract, fail-closed tests, and matching EN/CN documentation.
3. Keep raw evidence private and publish only the minimum protocol assertions needed for independent contract validation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New evidence patterns need tests, public-boundary review, bilingual documentation, and a deterministic manifest update.
