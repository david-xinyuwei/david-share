# Foundry Long-Running Agent Resilience

[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/foundry-long-running-agent-resilience-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/foundry-long-running-agent-resilience-ci.yml)
[![Evidence](https://img.shields.io/badge/author_attested_campaign-8%2F8_PASS-0F8B6D)](data/validation-matrix.json)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)

A public knowledge and evidence-validation kit for long-running Microsoft Foundry Hosted Agents. It explains the architecture and proof patterns behind an eight-scenario private campaign, then provides executable checks for the sanitized public attestations.

> **Trust and public boundary:** `8/8` is an **author-attested campaign result**, not independently replayable public telemetry. The exact Schema and Python validator prove contract validity; SHA-256 proves committed-artifact integrity; neither alone proves that a private run occurred. This repository **does not include private-preview source code**, private packages, raw hosted logs, service endpoints, resource identifiers, credentials, or deployment recipes. The result is **not a production certification** or an availability statement for every topology.

> **Author:** Xinyu Wei (魏新宇) - Microsoft AI and Apps GBB Senior System Engineer

[Chinese](README-CN.md) | English | [Hosted agents overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents) | [Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)

---

## Executive Summary

The private campaign covered **eight main documented scenarios** across Python and .NET, Responses and Invocations, graph human approval, a persisted workflow, and active-turn steering. All eight reached their pattern-specific workload pass criteria; this public repo validates the sanitized author attestations and their private-source commitments.

| Result | Public-safe evidence | Why it matters |
|---|---|---|
| 8/8 main scenarios passed in the author-attested campaign | Eight independent files in `evidence/sanitized-runs/` plus a generated matrix | One aggregate number cannot hide a missing runtime or protocol; provenance still depends on the stated trust model. |
| Research workloads with 18 total phases completed despite injected failure | Python/.NET, Responses/Invocations attestations | A short smoke test cannot stand in for a long-running recovery path. |
| Human approval survived restart | Two graph HITL scenarios | Recovery preserved a pending decision boundary, not only generated text. |
| Workflow and steering reached terminal outcomes | Persisted stage outputs and a queued materially different follow-up | Durability and steering are tested as workload behavior. |
| Public artifacts are hash-locked | `evidence/manifest.json` | Changes to committed public artifacts are visible; the manifest is not proof of private execution. |

The central lesson is simple:

> **Active deployment is a control-plane fact. Resilience is a workload-level claim that needs checkpoint, disruption, continuity, and terminal evidence.**

## What Is Real and What Is Withheld

| Layer | Published here | Boundary |
|---|---|---|
| Private campaign result | Author-attested per-scenario assertions derived from authenticated hosted runs | A sanitized claim with private-source commitments; public readers cannot replay the withheld run. |
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

For recovery patterns, only Level 6 counts as a pass. Workflow and steering use their own pattern-specific terminal criteria. See [Methodology](docs/methodology.md).

## Validation Architecture

![Evidence pipeline from authenticated run through checkpoint, failure, reconnect, sanitization, and hash-locked public attestation](images/evidence-pipeline.png)

The public boundary is intentionally one-way: raw evidence can produce a sanitized attestation, but the public artifact cannot reconstruct private service identity or deployment details.

## System Architecture and Responsibility Boundaries

![Four layers separating public Foundry hosting, the observed long-running capability, workload proof, and observer evidence](images/resilience-architecture.png)

The essential design decision is to separate what the platform publicly guarantees from what a workload must prove:

| Layer | Public or observed responsibility | Evidence boundary |
|---|---|---|
| Foundry hosting | Session/conversation state, agent identity, dedicated protocol endpoints, managed lifecycle | Current Microsoft Learn documentation |
| Long-running capability | Durable task state, recovery entry, reconnectable events, steering pressure observed in the private campaign | Author-attested sanitized observations; implementation withheld |
| Workload | Checkpoint meaning, approval ownership, stage outputs, safe cancellation, terminal business result | Pattern-specific assertions |
| Observer | Failure injection, reconnect cursor, final read, sanitization and publication | Public tools plus private-source commitments |

Long-running work has two different shapes. **Active work** resumes pending computation after recovery; **suspended work** parks at a durable human-approval checkpoint and wakes only when a later request arrives. Process uptime is not the durability mechanism in either case.

See [Architecture and Responsibility Boundaries](docs/architecture.md) for the full Responses/Invocations, session/conversation, identity and trust-model mapping.

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

Research durability and graph-approval recovery use this falsifiable chain:

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

Durable workflow and steering are not forced into that chain:

| Proof pattern | Required observable outcome |
|---|---|
| Research | Checkpoint before failure, same logical work after reconnect, all 18 phases/items, explicit terminal success |
| Graph HITL | Pending approval persists across process replacement, decision resumes once, post-approval path completes |
| Durable workflow | Every required stage output persists and the original background response reaches its round-trip terminal result |
| Steering | A materially different follow-up queues while active, the old turn ends cooperatively, and the queued turn completes with a relevant answer |

The full acceptance rules are in [Methodology](docs/methodology.md); per-pattern timelines are in [Scenario Proof Runbooks](docs/scenario-runbooks.md); field and privacy rules are in [Evidence Contract](docs/evidence-contract.md).

## Evidence Contract

Every committed record declares runtime, protocol, proof pattern, source class, author-attested provenance, status, and pattern-specific assertions. The validator fails on:

- missing or duplicate scenario IDs,
- fewer or more than eight expected scenarios,
- missing phase, checkpoint, failure, recovery, approval, or completion evidence,
- a summary that does not match scenario rows,
- a missing or malformed private-source commitment,
- identity-bearing fields such as endpoint, resource, session, response, invocation, tenant, or subscription identifiers,
- manifest path traversal, missing files, byte changes, or SHA-256 changes.

The generated exact JSON Schema is [data/evidence-contract.schema.json](data/evidence-contract.schema.json); its authoritative generator and deterministic checks live in [src/lra_resilience/evidence.py](src/lra_resilience/evidence.py).

[scenario-manifest.json](scenario-manifest.json) distinguishes `sanitized-runtime-attestation`, `dynamic-runtime`, `architecture-explainer`, and `test-fixture`. Synthetic parser fixtures remain isolated under `tests/fixtures/` and never count toward the campaign.

## Quick Start

```bash
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Agents/Foundry-Long-Running-Agent-Resilience
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e .
lra-evidence validate
lra-evidence manifest
python scripts/protocol_summary_differential.py
```

Expected output:

```text
PASS: validated 8 sanitized scenarios
PASS: verified 9 evidence artifacts
PASS: synthetic protocol fixtures produced different public summaries
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

The summarizer retains only event type, phase, output index, status, total, and sequence number. It reports ordered phase/index observations plus sequence monotonicity, duplicates, and gaps; unknown fields are discarded. A terminal event counts as complete only when it carries an explicit `completed` status.

## Re-run with Your Own Events

1. Capture the complete stream privately; do not stop at a byte cap.
2. Keep raw evidence outside this repository.
3. Run `lra-evidence summarize` against the private JSONL file.
4. Review the public summary for business payloads or identity-bearing values.
5. Add a new contract only with matching tests and documentation.

This repository does not deploy or invoke an agent. Follow the [official Hosted agent quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent) for current public deployment instructions. The offline validator supports Python 3.10–3.13; current Hosted deployment prerequisites are governed by the linked quickstart and may be newer.

## Running on Azure

This repository is an offline evidence validator, not an Azure deployment template. Validating the committed matrix requires no Azure credential and creates no cloud resource.

To generate evidence from your own Azure workload:

1. Deploy a Hosted Agent through the [official quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent).
2. Capture the complete authenticated event stream in a private location.
3. Run the proof sequence for the selected pattern; workflow and steering do not reuse the Research assertion chain.
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
| Durable task/storage preview onboarding is missing | "Enable an unrelated feature." | Separate service-side allowlisting from customer registration; an active Agent version does not prove this data path is enabled. |
| Shell quoting corrupts payload | "API rejected valid schema." | Use a structured or file-backed client and retain HTTP evidence. |

See [Failure Modes and Adjudication](docs/failure-modes.md) for the evidence rule behind each case.

## Repository Layout

```text
data/                         Generated matrix and exact public JSON Schema
docs/                         Architecture, runbooks, methodology, contract, and failure analysis (EN/CN)
evidence/sanitized-runs/      Eight public-safe author-attested campaign records
images/                       Generated bilingual architecture, evidence, and coverage visuals
scripts/                      Build, validation, parser-differential, package, and asset tools
src/lra_resilience/           Evidence, event-summary, manifest, and CLI library
tests/                        Contract, tamper, privacy, parser, and differential fixtures
tests/fixtures/               Synthetic JSONL parser inputs; never live-run evidence
scenario-manifest.json        Dynamic runtime / architecture / fixture classification
```

## Quality Gates

| Gate | Command | Failure behavior |
|---|---|---|
| Evidence contract | `python scripts/validate_evidence.py` | Missing proof or changed hash fails. |
| Protocol-summary differential | `python scripts/protocol_summary_differential.py` | Different synthetic parser fixtures producing identical summaries fail; this is not a Hosted runtime test. |
| Bilingual deterministic gate | `python scripts/validate_readmes.py` | Heading, table, code, localized image, numeric claim, link, or critical-boundary drift fails. |
| Deterministic public scanner | `python scripts/validate_repo.py` | Known credential values, IDs, private URLs, endpoints, local paths, missing assets, or malformed images fail. This complements—not replaces—manual export review. |
| Unit tests | `pytest -q` | Contract, parser, manifest, and tamper regressions fail. |
| Lint | `ruff check src tests scripts` | Static code findings fail. |
| Dependency audit | `pip-audit --local` | Known vulnerabilities in the clean installed environment fail. |
| Package | `python -m build --wheel` | Clean build failure blocks delivery. |
| Installed CLI smoke | `python scripts/package_smoke.py` | The installed CLI must work outside the checkout with explicit evidence paths. |

CI runs on Windows and Linux with Python 3.10-3.13.

## Public Boundary

This repository is a true public subset of a private validation campaign. It keeps the methodology, generic evidence contract, sanitized results, failure analysis, and executable checks. It withholds raw output, identifiers, private code, private packages, internal collaboration records, and environment-specific deployment details.

The `8/8` result means the author attests that all eight main documented campaign scenarios passed and that the public records satisfy the exact contract. It does not mean the private runs are independently replayable from public artifacts, or that every optional cancel/delete/deny branch, region, model, or production topology was certified.

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
- Per-scenario private-source commitments support later private verification but do not create a public cryptographic chain of custody to execution.
- The kit validates evidence semantics; it does not deploy an agent or certify service availability.
- Optional branches outside each main documented scenario are not included in the 8/8 count.
- Failure injection validates recovery behavior, not business-domain correctness or model quality.

## Next Steps

1. Apply the evidence hierarchy to another long-running workload without changing its business logic.
2. Add a new proof pattern only with an authenticated run, an exact assertion contract, fail-closed tests, and matching EN/CN documentation.
3. Keep raw evidence private and publish only the minimum protocol assertions needed for independent contract validation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New evidence patterns need tests, public-boundary review, bilingual documentation, and a deterministic manifest update.

## License

This project is licensed under the [MIT License](LICENSE).
