# Meeting Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-107C10.svg)](LICENSE)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/meeting-agent-ci.yml/badge.svg?branch=master)](https://github.com/david-xinyuwei/david-share/actions/workflows/meeting-agent-ci.yml)
[![Human Send Required](https://img.shields.io/badge/email-human%20send%20required-D83B01.svg)](#human-controlled-outlook-handoff)

One Meeting Agent product, implemented two ways: classic application-owned prompt orchestration and a Microsoft Foundry Agent whose model loop and versioned Skill are managed by the platform. Both paths produce the same structured notes, mind map, editable PowerPoint, and unsent New Outlook draft.

> Author: Xinyu Wei

[Chinese](README-CN.md) | **English** | [Source](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Meeting-Agent)

## Demo Video

https://github.com/user-attachments/assets/023f22f0-31f2-4039-85f0-e22712770ff2

[Download the repository copy](https://github.com/david-xinyuwei/david-share/raw/refs/heads/master/Agents/Meeting-Agent/media/meeting-agent-demo-1.6x.mp4?download=1)

*The full video remains `2392x1500` at `1.6x` speed and preserves all 3,860 frames; measured quality is SSIM `0.99966` and PSNR `56.17 dB`. [View the validation evidence](evidence/meeting-agent-demo-video.json).*

## Start Here: Why Two Implementations?

The original implementation proved the workflow, but the application owns almost the entire AI runtime: it constructs the system prompt, loads `SKILL.md`, selects the model, calls Azure OpenAI directly, parses the response, and carries the API key. The Managed implementation keeps the deterministic meeting and artifact code while moving the model loop, Agent identity, instructions, and Skill lifecycle into Microsoft Foundry.

This is the question the repository answers with one concrete application:

> Can a Foundry-managed Agent remove application-owned orchestration and key handling without making the Meeting Agent less capable?

| Dimension | Classic direct Responses implementation | Foundry prompt agent with managed GHCP harness |
|---|---|---|
| Implementation | Repository root | `managed-agent/` source inside this same product repository |
| Agent definition | None; the application is the orchestrator | [`agent.yaml`](managed-agent/agent.yaml) defines the Foundry Agent resource |
| Instructions | Python builds the system message | [`instructions.md`](managed-agent/instructions.md) is deployed with the Agent |
| Skill | Python reads local `SKILL.md` and injects it into every request | Toolbox references independent [`meeting-package`](managed-agent/skills/meeting-package/SKILL.md) and [`presentation-story`](managed-agent/skills/presentation-story/SKILL.md) behavior assets; current v6 live evidence covers only the former |
| Model loop owner | Local application code | Foundry-managed GHCP harness |
| Invocation | Direct Azure OpenAI Responses client | Application references Agent name + immutable version; the endpoint is transport, not the Agent itself |
| Authentication | API key in the local backend process | Entra ID for Responses and Agentic identity for Toolbox; no model API key in the customer path |
| Artifact/UI contract | JSON, Mermaid, SVG, PNG, editable PPTX, EML, browser UI, New Outlook draft | The same user contract; six shared modules remain byte-identical, while Models and Hosted Pipeline intentionally add DeckPlan support |
| PowerPoint responsibility | Local Skill provides content guidance; local template/renderer creates the deck | `presentation-story` owns writing guidance; strict `DeckPlan`, external Deck/Style YAML, and the PPTX template drive deterministic rendering |
| Customer code ownership | Owns model request construction and orchestration | Owns event validation, artifacts, and Outlook handoff; Foundry owns the model loop |
| Operational change | Prompt, Skill loading, model call, key handling, and parsing are one application release | Agent instructions and Skill are versioned platform assets; app code keeps a smaller deterministic responsibility |

The classic path is **prompt-style local orchestration**, not a deployed Foundry Prompt Agent. The comparison therefore isolates the practical ownership transfer introduced by the Managed Agent path without overstating the earlier implementation.

Microsoft Learn defines Foundry Agent Service as a managed platform for building, deploying, and scaling AI agents, with Prompt agents as declarative agents that Foundry runs and Hosted agents as customer code that Foundry hosts. This repository's Managed path is a **Prompt agent**; the local UI and Python artifact backend are its deterministic client application, not a Hosted Agent. See the [official-product mapping](managed-agent/docs/MANAGED-IMPLEMENTATION.md#microsoft-official-definition-and-this-implementation).

### What the Managed Agent is in this codebase

The Managed Agent is not a second UI and not merely an AI endpoint. It is the deployed Foundry Agent selected by `agent_reference.name` and `agent_reference.version`. Its behavior is assembled from four concrete assets:

1. [`agent.yaml`](managed-agent/agent.yaml): Agent kind, public name, description, and model.
2. [`instructions.md`](managed-agent/instructions.md): stable evidence and safety policy owned by the Agent.
3. [`meeting-package`](managed-agent/skills/meeting-package/SKILL.md) and [`presentation-story`](managed-agent/skills/presentation-story/SKILL.md): separate meeting-analysis and six-slide writing methods exposed through Toolbox MCP.
4. [`ManagedAgentAnalyzer`](managed-agent/src/meeting_agent/analyzers.py): a thin Entra-authenticated adapter that supplies meeting evidence, requires one exact Agent version, and validates the returned `MeetingAnalysis` contract.

The local application still owns what should remain deterministic: event validation, ordering and idempotency, file generation, path safety, the browser workspace, and the human-controlled Outlook handoff.

Current source fully separates the presentation domain: `presentation-story` owns the six-slide writing method, `DeckPlan` is the strict exchange contract, Deck/Style YAML owns mapping and visual tokens, and the PPTX template owns geometry. The deployed v6 evidence predates this split; a new Skill/Toolbox/Agent version still requires live validation.

### What this repository must prove

| Claim | Repository proof |
|---|---|
| No feature regression | Executable event, session, artifact, UI, and Outlook contracts plus a Parity Manifest with six equal modules and two documented DeckPlan differences |
| Output changes with the meeting | Two materially different meeting inputs must produce different analysis and artifact hashes |
| Managed deployment is real | The checked-in Agent, instructions, and Skill must deploy as a new immutable Foundry Agent version and report `active` |
| Managed invocation is real | The deployed version must return its own Agent reference and strict `MeetingAnalysis` JSON over Entra authentication |
| The benefit is concrete | The application no longer carries a model API key or injects the full Skill as a system message; Foundry owns those lifecycle concerns |
| Safety is preserved | No send API or Send-button automation; Outlook stops at an editable unsent draft |

Implementation details and parity evidence are linked from this root page; `managed-agent/` is a source directory, not a separate product or repository.

### Measured result: public-source Managed Agent v6 with GPT-5.4

The repository source was redeployed with the same GPT-5.4 model family used by the Classic path. The Preview extension's generated skills-only Toolbox was reconciled to the official Toolbox Search contract, and the Agent uses a dedicated `AgenticIdentityToken` connection. The checked-in deployment gate keeps private azd values under ignored `.azure`, restores the public placeholder YAML, and idempotently records the active runtime in `.azure/managed-runtime.json`.

| Verification | Measured result |
|---|---|
| Public-source deployment | `managed-meeting-agent` version `6`, `status=active`, `harness=ghcp`, model `gpt-5.4` version `2026-03-05` |
| Toolbox and identity | Toolbox v2 exposes `meeting-package` plus Toolbox Search; Agent-specific identity has project-scoped `Foundry User` |
| Agent identity | Non-stream and stream responses passed strict Agent Reference validation for name `managed-meeting-agent`, version `6` |
| Real streaming | Nonempty model deltas and two distinct hashed response IDs are recorded in the sanitized evidence |
| Cross-input behavior | Planning and operations meetings produced different titles, analysis hashes, mind maps, PPTX hashes, and EML hashes |
| Artifact contract | Both runs produced nonblank 1280x720 PNGs, editable six-slide PPTX files, and `X-Unsent: 1` EML drafts with zero recipients and two attachments |
| Browser workflow | Live GPT-5.4 Playwright desktop/mobile `2/2` with native Windows ARM64 Node and Edge; zero console errors |
| Shared deterministic behavior | Six core modules remain byte-for-byte identical; Models and Hosted Pipeline have explicit baseline/current hashes and DeckPlan reasons |

This proves functional parity at the contract and workflow level. It does **not** claim that the two orchestration paths produce identical prose or that Preview behavior is a permanent production SLA.

[Managed implementation details](managed-agent/docs/MANAGED-IMPLEMENTATION.md) · [Feature parity](managed-agent/FEATURE-PARITY.md) · [GPT-5.4 evidence](managed-agent/evidence/managed-live-gpt54/runtime-validation.json)

## Executive Summary

The customer path is a local browser workspace, not a Python command line. A transcript, structured meeting JSON, or visual adapter becomes strict meeting events; a local Python backend calls GPT-5.4 with Responses API structured output and medium reasoning, generates traceable artifacts, and lets the Windows UI open an EML draft in New Outlook for human review.

Generation uses a finite NDJSON response stream. The UI displays real `response.output_text.delta` content first, then unlocks the structured analysis, Mermaid map, PowerPoint, and EML only when each corresponding backend stage has actually completed. No timer, typewriter simulation, fixed progress percentage, or synthetic stream event is used.

| Outcome | Delivered behavior | Verification |
|---|---|---|
| Browser experience | Transcript TXT, normalized ASR JSONL, or Meeting JSON input; card-layout mind-map preview; rich-text copy; matching PNG and Mermaid source downloads | Playwright desktop/mobile E2E |
| Local runtime | Loopback Python artifact backend with strict Pydantic validation | `tests/test_hosted_api.py` |
| Meeting analysis | GPT-5.4 Responses API, structured output, reasoning `medium`, `store=False` | `tests/test_azure_analyzer.py`, runtime HTTP log |
| Session artifacts | JSON, SVG, PNG, editable PPTX, HTML/plain EML under managed `$HOME` | `tests/test_hosted_pipeline.py` |
| Outlook handoff | `X-Unsent: 1` draft opened through `olk.exe` | `evidence/outlook-draft-probe.json` |
| Send safety | No SMTP, Graph `sendMail`, Outlook `.Send`, or UI Send activation across Python/Node/UI/scripts | `scripts/audit_no_send.py` |

## What Is Real vs What Is Adapter-Owned

| Capability | What this repository does | Evidence | Boundary |
|---|---|---|---|
| Browser UI | Calls the local artifact backend through a loopback BFF and renders real returned artifacts | Browser E2E and Node tests | It is local in this release; it is not a public cloud website |
| AOAI runtime | Calls `https://<resource>.openai.azure.com/openai/v1/responses` with API key authentication | Key-auth Responses API 200 log and SDK contract tests | The resource must have `disableLocalAuth=false` |
| Event intake | Validates, orders, deduplicates, and hashes normalized ASR JSONL events | Unit tests and two sample streams | Capture transport is supplied by an adapter |
| Transcript processing | Uses only `transcript.final` in generated artifacts | `tests/test_session.py` | Embedded Speech returns an in-memory recognition result; an adapter maps it to JSONL |
| Visual context | Accepts a visual summary and optional `image_uri` | Event schema tests | Screen capture and image interpretation belong to the visual adapter |
| GPT-5.4 analysis | Loads the meeting-package skill, uses Pydantic structured output, medium reasoning, and `store=False` | SDK contract and live AOAI response | It never falls back to a local fixture |
| Committed sample fixtures | Static artifacts for renderer, EML, and evidence-contract regression tests | Hash validation and unit tests | They are not an AI-quality substitute, executable analyzer, or production fallback |
| Artifact generation | Creates real, parseable PNG/SVG/JSON/PPTX/EML files | SHA-256 manifest and artifact tests | Layout is intentionally compact and customizable |
| New Outlook | Opens an editable EML draft with real attachments | Sanitized Windows probe | Windows and New Outlook are required for the UI button or `--open-outlook` |
| Message transmission | Does not transmit mail | Static audit in every CI job | The user reviews and clicks Send manually |

The committed sample artifacts are static `test-fixture` evidence for deterministic renderer and draft-contract regression tests; no fixture is addressable from the customer path. Live validation uses the local Windows UI and full GPT-5.4 Responses API: the structured meeting JSON produces grounded analysis, one card-layout mind map shared by the page, PNG download, and inline Outlook draft, a renderer-neutral Mermaid source, a six-slide editable PPTX, and an EML with two attachments. This is functional evidence, not production certification or a model-quality benchmark. The sanitized Outlook probe validates the Windows draft handoff only.

[Live runtime differential evidence](evidence/aoai-runtime-differential.json) records two materially different real Responses API inputs. Their source, title, analysis, card PNG, PPTX, and EML hashes all differ; response IDs are verified locally and redacted from the public record.

## Architecture

![Meeting Agent architecture](images/meeting-agent-architecture.svg)

*Full-size vector architecture: Windows browser workspace, loopback BFF, local Python artifact backend, GPT-5.4 Responses API, local session files, and human-controlled New Outlook handoff. [Open the SVG directly](images/meeting-agent-architecture.svg).*

### Browser workspace

![Meeting Agent browser workspace](images/meeting-agent-ui.png)

*Sanitized 1440 px Playwright capture from the live local AOAI path. Tenant, subscription, resource, endpoint, token, and session identifiers are not rendered or published.*

### Processing invariants

1. `event_id` is idempotent. Reusing it with different content fails closed.
2. Events sort by `sequence`, then `timestamp`, then `event_id`.
3. Partial ASR hypotheses never enter summaries or attachments.
4. Every input stream and output artifact receives a SHA-256 digest.
5. Azure event content is treated as untrusted data, not as model instructions.
6. The EML must contain `X-Unsent: 1` and at least one real attachment.
7. The codebase contains no automatic mail-transmission capability.
8. Azure analysis normalizes each event to one line and rejects input above 200,000 characters.
9. Local invocation requests reject unknown fields and more than 5,000 events.
10. Runtime artifacts stay under the ignored local session directory; the BFF rejects path traversal.
11. Browser code never receives an Azure access token; only the loopback BFF acquires one.

## Event Contract

Each line is one JSON object. Unknown fields are rejected.

| Field | Type | Constraint | Purpose |
|---|---|---|---|
| `event_id` | string | 1 to 128 characters | Idempotency key |
| `session_id` | string | 1 to 128 characters | Meeting boundary |
| `sequence` | integer | `>= 0` | Provider ordering |
| `timestamp` | RFC 3339 datetime | Time zone required | Deterministic tie-breaking |
| `kind` | enum | See event kinds below | Event behavior |
| `text` | string or null | Up to 20,000 characters | Transcript or visual summary |
| `image_uri` | string or null | Up to 2,048 characters; no `data:` URI or line break | Adapter-owned image reference |
| `metadata` | object | Default `{}` | Provider-specific non-secret metadata |

| `kind` | Required payload | Pipeline behavior |
|---|---|---|
| `transcript.partial` | Non-empty `text` | Accepted for observability, excluded from artifacts |
| `transcript.final` | Non-empty `text` | Included in analysis |
| `visual.frame` | `text` or `image_uri` | Adds adapter-supplied visual context |
| `meeting.end` | None | Marks the upstream meeting boundary |

Example:

```json
{"event_id":"event-004","session_id":"product-planning","sequence":4,"timestamp":"2026-01-15T09:00:08Z","kind":"transcript.final","text":"Mina will follow up with security and prepare the pilot checklist.","metadata":{"source":"local-asr"}}
```

See [examples/product-planning.jsonl](examples/product-planning.jsonl) and [examples/operations-review.jsonl](examples/operations-review.jsonl) for complete streams.

## Evidence Showcase

The two committed runs differ in source content, analysis output, mind map, presentation, and EML hashes. CI recalculates every digest from disk and checks each source stream against its evidence manifest.

| Run | Events | Source SHA-256 | Analysis SHA-256 | Result |
|---|---:|---|---|---|
| `product-planning` | 6 | `413799e9783ac40a5a4e225a553bef94f33fd4c5990607add57e50547f91486b` | `988d06fa2c29be218c8945ddb23734ce07752e5e5428b5e80506194f30fd4864` | Distinct planning summary |
| `operations-review` | 6 | `88d71ad49cd875e2eb958c884e1ce2eb76a208576047df923decda79e7e109fb` | `22e4e3c9a679d3d3e3a7fbca64a16166ef4e4e546c5d2d35f2413cea9675dd13` | Distinct incident summary |

### Product planning sample

![Product planning mind map](evidence/sample-runs/product-planning/mind-map.png)

### Operations review sample

![Operations review mind map](evidence/sample-runs/operations-review/mind-map.png)

Each run contains:

| File | Purpose |
|---|---|
| `meeting-analysis.json` | Full structured analysis |
| `mind-map.json` | Renderer-neutral graph |
| `mind-map.svg` | Scalable six-card rendering |
| `mind-map.png` | Six-card bitmap shared by the page, download, PPTX, and email |
| `meeting-summary.pptx` | Editable six-slide template-based presentation |
| `meeting-follow-up.eml` | Unsent MIME draft with the inline card map plus PNG and PPTX attachments |
| `evidence.json` | Source and artifact size/hash manifest |

## Quick Start

### Prerequisites

- Windows 11 with New Outlook, Python 3.12, and Node.js 22 or newer
- An existing Azure OpenAI endpoint, deployment name, and API key
- The Azure OpenAI resource must allow local authentication (`disableLocalAuth=false`)

The local demo uses the GA AOAI Responses API. Confirm model availability, quota, identity policy, and data residency before treating it as a production deployment standard.

### AIPC customer end-to-end runbook (Key authentication)

This is the supported AIPC path for the complete browser → Azure OpenAI → artifacts → New Outlook workflow. It does not require Azure account sign-in or Azure command-line tools. Run every command in native Windows PowerShell, not WSL.

1. Obtain the source and enter the project directory. If you received the customer ZIP, extract it and open the extracted `Meeting-Agent` folder:

```powershell
Expand-Archive .\Meeting-Agent-Customer-Package-*.zip -DestinationPath .\Meeting-Agent-Delivery
Set-Location .\Meeting-Agent-Delivery\Meeting-Agent
```

For GitHub delivery, clone the repository instead:

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
Set-Location .\david-share\Agents\Meeting-Agent
```

2. Get the Azure OpenAI connection values from the Azure portal:

- Open the target **Azure OpenAI** or **Azure AI Services** resource.
- Go to **Resource Management > Keys and Endpoint**.
- Copy the **Endpoint** and either **KEY 1** or **KEY 2**.
- Confirm the deployment name under **Model deployments**; this runbook uses `gpt-5.4`.

3. Start the application with the existing Azure OpenAI resource. Replace only the endpoint and deployment placeholders; do not put the API key in the command:

```powershell
.\scripts\start-ui-key.ps1 `
  -Endpoint "https://<your-resource>.openai.azure.com/" `
  -Deployment "gpt-5.4"
```

The launcher asks for the API key using hidden input. Paste the key and press Enter; it is never displayed or written to a file. The launcher validates Windows, Node.js, Python, and New Outlook, installs locked dependencies, starts the Python backend on `18089`, and opens the loopback UI on `http://127.0.0.1:4173`.

PowerShell displays this prompt after the command starts:

```text
Azure OpenAI API key:
```

Paste **KEY 1** or **KEY 2** at that prompt and press Enter. No characters appear while pasting because the input is hidden. There is intentionally no `-ApiKey` command-line parameter, so the key does not enter PowerShell history.

4. Open `http://127.0.0.1:4173`, choose **Meeting JSON**, upload `examples/meeting-record-stargate.json`, optionally enter draft recipients, and select **Generate meeting package**.

5. Accept the run only when all of these are true:

- The header shows **Azure OpenAI Responses API** and `gpt-5.4 · reasoning medium · key auth`.
- All six real generation stages complete; model text appears before analysis and artifacts.
- The page shows the six-card mind map; **Save PNG** downloads that same image.
- The PowerPoint opens as an editable six-slide deck.
- The EML opens as an unsent New Outlook draft with the same inline card map, PNG/PPTX attachments, and manual Send only.

Press `Ctrl+C` in the launcher terminal to stop the UI and backend. Use the same `start-ui-key.ps1` command for later sessions. The key is passed only to the Python backend process, removed before the Node BFF starts, and is never written to `.env`, command-line arguments, logs, browser responses, generated artifacts, Git, or the customer ZIP. If Azure returns `403 AuthenticationTypeDisabled`, the resource administrator must enable local authentication in accordance with organizational policy.

### Deterministic test fixtures

```bash
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Agents/Meeting-Agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pytest \
  tests/test_artifacts.py \
  tests/test_hosted_pipeline.py \
  tests/test_draft.py
```

After installation, `meeting-agent` and `python -m meeting_agent.cli` are equivalent.

### Windows test commands

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest `
  tests\test_artifacts.py `
  tests\test_hosted_pipeline.py `
  tests\test_draft.py
```

### Example Output

Validation output:

```json
{"session_id":"product-planning","event_count":6,"content_sha256":"413799e9783ac40a5a4e225a553bef94f33fd4c5990607add57e50547f91486b"}
```

Evidence excerpt:

```json
{
  "analyzer": "test-fixture",
  "source": {
    "session_id": "product-planning",
    "event_count": 6,
    "content_sha256": "413799e9783ac40a5a4e225a553bef94f33fd4c5990607add57e50547f91486b"
  },
  "eml": {
    "x_unsent": "1",
    "recipient_count": 0,
    "attachment_count": 2
  },
  "automatic_send": false,
  "next_state": "DRAFT_READY_MANUAL_SEND_REQUIRED"
}
```

## GPT-5.4 Key-Authenticated Responses Analyzer

The local Azure OpenAI analyzer is the primary runtime:

- `InvocationAgentServerHost` exposes the strict local JSON contract through `/invocations`.
- `AzureOpenAIAnalyzer` calls the AOAI `/openai/v1/responses` endpoint with API key authentication.
- GPT-5.4 uses the packaged meeting skill, Pydantic structured output, reasoning `medium`, and `store=False`.
- The Windows launcher reads the key through a hidden prompt and passes it only to the Python backend process.
- Generated files are written below the ignored local runtime session, not a public directory.

The standalone CLI remains available for adapter development and recovery. Its Azure path follows the current Responses v1 pattern:

- `OpenAI(base_url="https://<resource>.openai.azure.com/openai/v1/")`
- `AZURE_OPENAI_API_KEY` supplied only in process memory
- Pydantic `MeetingAnalysis` passed to `responses.parse`
- `store=False` on the response request
- Event text normalized to one line per event, with a 200,000-character fail-closed limit

The repository pins `openai==2.32.0`. Start from [.env.example](.env.example), then keep the real key out of source control and use the hidden-input launcher.

Configure the resource and deployment without committing credentials:

```bash
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT="<deployment-name>"
export AZURE_OPENAI_API_KEY="<api-key>"
python -m meeting_agent.cli build \
  --events examples/product-planning.jsonl \
  --output-dir artifacts/azure-product-planning
```

This CLI example is for ephemeral developer shells only. The customer launcher is safer because it reads the key with hidden input. Never place API keys, tenant-specific endpoints, or customer data in this repository.

Official references:

- [Azure OpenAI Responses API](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/responses)
- [Structured Outputs parsing helpers](https://github.com/openai/openai-python/blob/main/helpers.md)

## Human-Controlled Outlook Handoff

On Windows, the customer path is the **Open Outlook draft** button in the browser workspace. The loopback BFF reads the EML from the current local session, writes it atomically to a local temporary directory, and starts `olk.exe` with that file. The BFF exposes no send endpoint.

Start the complete local application with:

```powershell
.\scripts\start-ui-key.ps1 `
  -Endpoint "https://<your-resource>.openai.azure.com/" `
  -Deployment "gpt-5.4"
```

Run this command in Windows PowerShell, not WSL. The launcher verifies Node.js, Python, the HTTPS endpoint, and `olk.exe` before enabling the Outlook button.

The standalone CLI remains Azure-only. CI verifies EML drafting through static test fixtures rather than exposing an alternative local analyzer. The supported UI path writes or downloads the EML first, validates its contract, and launches `olk.exe <absolute-eml-path>`. The compose window remains editable. The repository never clicks Send and never calls a send API.

![Sanitized New Outlook draft probe](images/outlook-draft-handoff-sanitized.png)

*Sanitized documentation derivative of the real New Outlook probe. The account identifier is redacted, the former internal working title is normalized to the public project name, recipient fields remain empty, and the private original is not published.*

The sanitized Windows probe records:

| Check | Observed value |
|---|---:|
| `X-Unsent` | `1` |
| Recipient count | `0` |
| Attachment count | `2` |
| New Outlook window delta | `+1` |
| Automatic send | `false` |

See [evidence/outlook-draft-probe.json](evidence/outlook-draft-probe.json). The record identifies the private probe artifacts and the published sanitized screenshot independently; private files and user-specific window data remain unpublished.

## CLI Reference

```text
meeting-agent validate-events --events <meeting.jsonl>

meeting-agent build \
  --events <meeting.jsonl> \
  --output-dir <directory> \
  [--recipient <address>] \
  [--open-outlook]
```

`--recipient` can pre-address the draft but does not send it. The committed evidence intentionally uses zero recipients.
Specify `--recipient` more than once to pre-address multiple reviewers. Each value must be one valid address. A build holds an exclusive `.meeting-agent.lock` for its output directory; concurrent builds must use different output directories or wait for the active build to finish. The input JSONL must be immutable and complete before `build` starts.

## Evidence Format

Each build writes `evidence.json` with:

| Key | Meaning |
|---|---|
| `schema_version` | Evidence contract version |
| `analyzer` | `azure` for executable CLI builds; `test-fixture` for committed static regression assets |
| `source` | Session ID, event count, and canonical source SHA-256 |
| `artifacts` | Relative filename, byte count, and SHA-256 for every output |
| `eml` | `X-Unsent`, recipient count, attachment count/names, subject, and SHA-256 |
| `automatic_send` | Always `false` in this repository |
| `next_state` | `DRAFT_READY_MANUAL_SEND_REQUIRED` |

Use `scripts/validate_sample_runs.py` to verify the committed examples. For a new run, compare each file with its entry in `artifacts` and confirm the EML safety fields before opening the draft.

## Testing and Quality Gates

```bash
python scripts/audit_no_send.py
python scripts/audit_public_content.py
python scripts/validate_evidence.py
python scripts/validate_sample_runs.py
python scripts/validate_readmes.py
python scripts/pre_delivery_check.py
ruff check src tests scripts main.py
pytest
pip-audit -r requirements.txt --progress-spinner off
python -m build --wheel
python -m pip check
cd ui
npm ci --no-audit --no-fund
npm test
npm run build
npm run test:e2e
npm audit --omit=dev --audit-level=high
```

CI runs the Python gates on Ubuntu and Windows with Python 3.11, 3.12, and 3.13. A separate Ubuntu/Node 22 job runs the UI/BFF tests, TypeScript build, Vite production build, and production dependency audit.

| Test area | Coverage |
|---|---|
| Schema | Every `MeetingEvent` field, all four kinds, unknown fields, invalid payloads |
| Session | Ordering, idempotent duplicates, conflicting IDs, final-only transcript selection |
| Hosted protocol | Invocations request validation, explicit test-fixture injection gate, OpenAPI, error responses, and session paths |
| Azure contract | v1 base URL, key requirement, structured output type, `store=False`, prompt boundary |
| Authenticity | Two materially different inputs must produce different analysis and source hashes |
| Artifacts | Nonblank `1280x720` PNG, valid SVG/JSON, parseable PPTX package |
| Draft | `X-Unsent`, recipients, attachments, MIME parsing, normalized subject |
| UI/BFF | Input conversion, loopback-only routing, traversal rejection, responsive browser E2E, and real downloads |
| Safety | Static failure gate for automatic transmission APIs and Send activation |
| Evidence | Source hashes, file sizes, artifact hashes, EML state, cross-run distinction |

## Security and Privacy

- Input is meeting content. Apply organizational data classification and retention policy before calling any cloud analyzer.
- The Azure request sets `store=False`; Azure service and deployment policies still apply.
- The browser talks only to the loopback BFF; the Azure OpenAI API key is never inherited by the BFF or returned to browser JavaScript.
- Local runtime session files are stored under an ignored directory and are not public download URLs.
- Event metadata must not contain secrets, access tokens, or unnecessary personal data.
- `.env`, `password.txt`, token files, runtime output, and local artifacts are ignored by Git.
- Endpoint and deployment values come from environment variables.
- The public evidence is synthetic or sanitized and contains no customer endpoint, tenant, subscription, email address, or private path.
- `SECURITY.md` defines responsible vulnerability reporting.

## Schema Versioning

`schema_version` currently versions `evidence.json`, with version `1` introduced in package version `0.1.0`. Additive evidence fields may be introduced without incrementing it; removing a field, changing its meaning, or changing an enum value requires a new schema version and migration notes. No automatic migration tool is currently provided. The strict `MeetingEvent` input model rejects unknown fields, so adapter owners should pin a compatible package version and update deliberately.

## Extending the Pipeline

Implement adapters outside the core package and emit the documented JSONL contract. For Microsoft Embedded Speech, map each SDK recognition result (`text`, offset, duration, speaker ID, confidence, and final/partial state when available) into one event; the SDK does not create a TXT file by default. This keeps capture libraries, device protocols, and vendor SDKs out of the analysis and artifact layers.

To add an analyzer, implement:

```python
class Analyzer(Protocol):
    def analyze(self, session: MeetingSession) -> MeetingAnalysis:
        ...
```

Return the existing `MeetingAnalysis` schema so every downstream generator and safety check remains unchanged.

Custom analyzers are currently wired programmatically rather than through the built-in CLI choices:

```python
from pathlib import Path

from meeting_agent.artifacts import generate_artifacts
from meeting_agent.session import load_jsonl

session = load_jsonl(Path("meeting.jsonl"))
analysis = CustomAnalyzer().analyze(session)
generate_artifacts(analysis, Path("artifacts/custom"))
```

## Project Structure

```text
main.py                                    Local strict invocation backend entry point
src/meeting_agent/skills/                  Runtime meeting-package prompt skill
src/meeting_agent/templates/               Editable six-slide PPTX template
src/meeting_agent/                         Core schemas, local handler, session logic, analyzers, artifacts, EML handoff, CLI
ui/                                        React workspace and key-isolated loopback BFF
examples/                                  JSONL streams plus a structured meeting-record JSON
images/                                    Full-size architecture and sanitized Outlook evidence
tests/                                     Schema, Hosted protocol, cross-input, artifact, draft, and CLI tests
scripts/                                   Key launcher plus no-send and evidence validation gates
evidence/                                  Sanitized Outlook probe and committed sample-run manifests/artifacts
../../.github/workflows/meeting-agent-ci.yml  Monorepo-scoped cross-platform CI
```

## Limitations

- This repository does not capture microphone audio or screen pixels.
- Visual frames are textual summaries or references supplied by an external adapter.
- Deterministic test fixtures are isolated under `tests/` and are not a production fallback.
- Model quality is not benchmarked by the committed deterministic samples.
- The browser UI is a loopback companion, not an internet-facing multi-user web service.
- The existing Azure OpenAI resource must allow key authentication (`disableLocalAuth=false`).
- SHA-256 manifests attest to one run. PPTX ZIP metadata and MIME boundaries may change binary hashes across rebuilds without changing the structured analysis.
- New Outlook launch is Windows-only and depends on `olk.exe` being available.
- Generated summaries and action items require human review before external use.
- The code creates a draft only; delivery, mailbox policy, signatures, and Send remain with Outlook and the user.

## Troubleshooting

| Symptom | Check |
|---|---|
| `at least one transcript.final event is required` | Emit a final transcript segment before building |
| `AZURE_OPENAI_ENDPOINT ... required` | Start through `start-ui-key.ps1` and provide the HTTPS endpoint and deployment |
| Azure `401` | Re-enter the current Azure OpenAI API key through the hidden prompt |
| Azure `403 AuthenticationTypeDisabled` | Ask the resource administrator to set `disableLocalAuth=false` |
| Azure `404` | Verify the deployment name and Responses API availability |
| `olk.exe` not found | Install New Outlook and verify it can be launched from the same Windows session |
| Outlook button is disabled | Run the loopback UI on Windows; non-Windows hosts can still download the EML |
| Draft opens without expected data | Inspect `evidence.json`, then run `validate_sample_runs.py` for committed samples |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Changes that add automatic message transmission or weaken evidence validation will fail CI.

## License

Licensed under the [MIT License](LICENSE).