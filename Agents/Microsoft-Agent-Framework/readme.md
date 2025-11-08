# Microsoft Agent Framework Workflow Demos

> Dual workflow showcase combining a human-in-the-loop pipeline and a MagenticBuilder orchestration demo with shared DevUI tooling.

## Overview
- Demonstrates two production-style agent workflows built on Microsoft Agent Framework.
- Includes a staged document authoring pipeline with human approvals and a dynamic agent routing experience.
- Ships with DevUI launchers so runs can be inspected visually and from the terminal.
- Depends on Azure OpenAI Chat Completions for model execution (defaults to the `gpt-5-chat` deployment).

## Solution Scenarios
| Workflow | Primary Goal | Interaction Model | Demo Video |
| --- | --- | --- | --- |
| `hitl_*` | Multi-stage document creation with formal human approval gates | Users review and approve output at each stage from the terminal while DevUI renders the workflow graph | [Watch HITL Demo](https://github.com/user-attachments/assets/371de179-192b-411b-b388-e67c4a4563ab) |
| `magentic_*` | Intelligent agent routing across weather, calculator, and travel personas | MagenticBuilder selects the appropriate agent automatically; DevUI surfaces orchestration state | [Watch Magentic Demo](https://github.com/user-attachments/assets/a3ab7aae-1594-4198-a462-d782a1195ab6) |

## Architecture Overview
- Workflow code uses Microsoft Agent Framework primitives (`WorkflowBuilder`, `MagenticBuilder`, executors, and agents).
- DevUI launchers (`*_devui.py`, `*_start.py`) host Uvicorn to render the workflow graph in the browser and optionally open an interactive terminal mode.
- Azure OpenAI Chat Completions provides the model backing; credentials are loaded via `.env`.
- The architecture supports local execution only; no cloud deployment assets are provided yet.

## Agent Framework Workload APIs
The Agent Framework source (see `python/packages/core/agent_framework/_workflows/`) ships six workload builder APIs. The table below calls out where each builder lives, whether it produces a **static** graph (all paths are fixed before execution) or a **dynamic** graph (the orchestrator decides the next hop at runtime), and notes which of the demos in this folder exercise it.

| Builder API (module) | Intended scenario | Graph behavior | Demo usage |
| --- | --- | --- | --- |
| `WorkflowBuilder` (`_workflow_builder.py`) | Low-level graph authoring with manual edge wiring | **Static** | `hitl_agent.py` builds its multi-stage approval flow with this builder |
| `SequentialBuilder` (`_sequential.py`) | Straight-line pipelines with optional shared state adapters | **Static** | Not used in these demos |
| `ConcurrentBuilder` (`_concurrent.py`) | Fan-out/fan-in orchestration across multiple agents | **Static** | Not used in these demos |
| `GroupChatBuilder` (`_group_chat.py`) | Manager-directed round-robin or selector-driven group chats | **Dynamic** | Not used in these demos |
| `HandoffBuilder` (`_handoff.py`) | Coordinator routes requests to specialists via handoff tool calls | **Dynamic** | Not used in these demos |
| `MagenticBuilder` (`_magentic.py`) | Magentic manager plans and selects participants adaptively | **Dynamic** | `magentic_agent.py` constructs its demo workflow with this builder |

**Key takeaways**
- The **HITL demo** relies on `WorkflowBuilder`, so all executors and edges are declared ahead of time (static graph).
- The **Magentic demo** uses `MagenticBuilder`, where the Magentic manager evaluates the plan and chooses participant executors as the run progresses (dynamic graph).
- Extend the samples with the remaining builders to cover additional patterns such as concurrent fan-out, sequential helper pipelines, or handoff-style routing.

### Demo Highlights

| Demo | Builder API | Pain point addressed | Why it works well |
| --- | --- | --- | --- |
| Human-in-the-Loop (HITL) | `WorkflowBuilder` (static) | Teams need deterministic multi-stage document production with mandatory approvals at each gate. | Full graph is predeclared, so every stage, approval edge, and rework loop is explicit and observable. Easy to reason about compliance and rehearse sign-off scenarios. |
| Magentic Planner | `MagenticBuilder` (dynamic) | Users ask open-ended questions that require routing to the best specialist (weather, math, travel) without hardcoding flow. | Magentic manager plans and selects participants adaptively, mixing tool calls and plan reviews. Enables flexible orchestration without redesigning the graph for every new skill. |

```
┌─────────────┐      ┌────────────────────┐      ┌──────────────┐
│ Start Script│ ───▶ │ Workflow Orchestrator │ ─▶ │ Azure OpenAI │
└─────────────┘      └────────────────────┘      └──────────────┘
        │                        │                         │
        │                        └──▶ DevUI events ───────▶│
        └──▶ Terminal I/O ◀──────┘                         │
```

## Repository Layout
- `hitl_agent.py` – Human-in-the-loop workflow definition with four stages.
- `hitl_devui.py` – DevUI host for the HITL pipeline.
- `hitl_start.py` – Combined launcher that starts DevUI and the terminal workflow together.
- `magentic_agent.py` – MagenticBuilder agents and manager configuration.
- `magentic_devui.py` – DevUI host for the Magentic workflow.
- `magentic_start.py` – Launcher that boots the Magentic workflow and DevUI.
- `.env.example` – Template for Azure OpenAI credentials.

## Prerequisites
- Azure subscription with access to [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/overview) and permission to deploy chat models.
- Python 3.10 or later (scripts verified on 3.12).
- `pip` access to install runtime dependencies (no requirements file is pinned).
- Ability to open TCP port 8080 locally for DevUI.

## Provisioning and Configuration
1. Create an Azure OpenAI resource in the desired region. Deploy a chat-capable model; the scripts default to the `gpt-5-chat` deployment name (override via `AZURE_OPENAI_DEPLOYMENT_NAME`).
2. Record the endpoint URL, API key, deployment name, and API version.
3. Copy `.env.example` to `.env` and set:
   ```env
   AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com"
   AZURE_OPENAI_API_KEY="<key>"
   AZURE_OPENAI_DEPLOYMENT_NAME="<deployment>"
   AZURE_OPENAI_API_VERSION="2024-08-01-preview"
   ```
   The checked-in `.env` uses `gpt-5-chat`; adjust if your deployment name differs.
4. The project does not yet ship with Infrastructure-as-Code or `azd` automation. If cloud deployment is required, plan to author Bicep or Terraform modules that provision Azure OpenAI, optional storage, and monitoring resources.

## Local Quickstart
1. Set up a virtual environment (recommended):
   ```pwsh
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```pwsh
   pip install agent-framework agent-framework-devui --pre
   pip install python-dotenv
   ```
3. Start the human-in-the-loop demo:
   ```pwsh
   python hitl_start.py
   ```
   - DevUI opens at `http://localhost:8080`.
   - The terminal prompts for document topics and approval decisions (`y`, `n`, or feedback text).
4. Start the Magentic workflow:
   ```pwsh
   python magentic_start.py
   ```
   - DevUI opens at `http://localhost:8080`.
   - Interact via the terminal; the orchestrator routes to Weather, Calculator, or Travel agents automatically.


## Identity and Access
- Running locally requires only the Azure OpenAI API key stored in `.env`.
- In production scenarios prefer managed identities or Azure Key Vault for secret storage.
- Azure roles: Operators need `Cognitive Services OpenAI User` or `Cognitive Services Contributor` to manage deployments and fetch keys.

## Limitations and Known Issues
- No automated provisioning (`azd`, Bicep, Terraform) is included. Infrastructure deployment must be scripted separately.
- DevUI expects port 8080; adjust launchers manually if the port is occupied.
- The Magentic workflow currently exposes only three sample agents; extending the registry requires code changes and testing.
- Release automation, CI/CD, and evaluation harnesses are not provided.


## Resources
- [Microsoft Agent Framework repository](https://github.com/microsoft/agent-framework)
- [Agent Framework DevUI package](https://pypi.org/project/agent-framework-devui/)
- [Azure OpenAI Service documentation](https://learn.microsoft.com/azure/ai-services/openai/)
