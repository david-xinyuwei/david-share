# Azure Agent Skills In Action

> A third-party engineering evaluation of Microsoft's Agent Skills ecosystem — covering architecture, real-world workflows, platform stickiness analysis, and hands-on verification across all skill categories.

This repository provides a comprehensive, independent assessment of two Microsoft repositories:

- **[microsoft/azure-skills](https://github.com/microsoft/azure-skills)** (v1.1.39) — The Azure Skills Plugin with 26 top-level skills, Azure MCP Server, and Foundry MCP.
- **[microsoft/skills](https://github.com/microsoft/skills)** — The Agent Skills monorepo with 174 skills across Python, .NET, TypeScript, Java, and Rust, plus plugins (deep-wiki, azure-skills), custom agents, prompts, and MCP configs.

The goal is not to repeat what the official README says, but to answer the questions a real engineering team would ask before adopting these skills at scale:

1. **What is the real architecture?** — Not just the marketing pitch, but how the pieces actually connect.
2. **Does the deployment workflow actually work?** — The `prepare → validate → deploy` pipeline claims to be a hard gate system. We trace through it.
3. **Where does platform stickiness happen?** — Which skills, once adopted, make it harder to leave Microsoft's ecosystem?
4. **What are the gaps?** — What is NOT covered (e.g., Office/Word automation, non-Azure clouds)?
5. **How should teams adopt this selectively?** — Not everything needs to be installed.

## Architecture Overview

The Azure Skills Plugin is not a prompt pack. It is a three-layer capability stack that turns a generic coding agent into an Azure-aware operator.

<div align="center"><img src="images/architecture-overview.png" width="720"/></div>

| Layer | Component | What It Does | Scale |
|:-----:|-----------|-------------|:-----:|
| **Brain** | 26 Azure Skills (31 SKILL.md files) | Decision trees, workflows, guardrails | 613 files |
| **Hands** | Azure MCP Server (`@azure/mcp@latest`) | 200+ structured tools across 40+ Azure services | Live Azure ops |
| **AI Specialist** | Foundry MCP (via Azure MCP `foundry` tool) | Model catalog, agent lifecycle, evaluations | Foundry-native |

**Key insight**: The "Foundry MCP" is not a separate MCP server in `.mcp.json`. It is exposed through the Azure MCP Server's `foundry` tool entry point. The `.mcp.json` across all plugin directories contains only one server:

```json
{
  "mcpServers": {
    "azure": {
      "command": "npx",
      "args": ["-y", "@azure/mcp@latest", "server", "start"]
    }
  }
}
```

Source: [.mcp.json](https://github.com/microsoft/azure-skills/blob/main/.mcp.json)

## Complete Skill Inventory

### Azure Skills Plugin (26 top-level skills)

Every skill in `microsoft/azure-skills` is listed below with its file count (a proxy for depth/complexity) and primary function.

| Category | Skill | Files | Function |
|----------|-------|:-----:|----------|
| **Build & Deploy** | `azure-prepare` | 164 | Analyze workspace, plan architecture, generate infra (Bicep/Terraform/AZD), write `deployment-plan.md` |
| | `azure-validate` | 17 | Pre-deployment validation: config, RBAC, managed identity, build verification |
| | `azure-deploy` | 41 | Execute deployment with error recovery (`azd up`, `terraform apply`, `az deployment`) |
| | `azure-upgrade` | 31 | Upgrade plans/tiers/SKUs, modernize Azure Java SDKs |
| | `azure-cloud-migrate` | 31 | Cross-cloud migration: AWS Lambda→Functions, Beanstalk→App Service, Fargate→Container Apps |
| **Platform & Infra** | `azure-compute` | 23 | VM recommendations, autoscale, connectivity troubleshooting |
| | `azure-kubernetes` | 11 | AKS cluster planning: Automatic vs Standard, networking, security |
| | `airunway-aks-setup` | 11 | AI Runway on AKS: GPU scheduling, model serving, inference setup |
| | `azure-storage` | 14 | Blob, File Share, Queue, Table, Data Lake; tier comparison and lifecycle |
| | `azure-messaging` | 1 | Event Hubs and Service Bus SDK troubleshooting |
| | `azure-kusto` | 1 | Azure Data Explorer / KQL queries |
| **Ops & Cost** | `azure-diagnostics` | 29 | Debug production issues: App Service, Container Apps, Functions, AKS, messaging |
| | `appinsights-instrumentation` | 13 | Add Application Insights telemetry to webapps |
| | `azure-cost` | 21 | Query costs, forecast spending, optimize waste, find orphaned resources |
| | `azure-quotas` | 3 | Check/manage quotas across Azure providers |
| | `azure-compliance` | 16 | Azure Quick Review (azqr), compliance scanning, resource graph audits |
| **Identity & RBAC** | `azure-rbac` | 1 | Find least-privilege RBAC roles, generate assignment CLI/Bicep |
| | `entra-app-registration` | 17 | Entra ID app registration, OAuth 2.0, MSAL integration |
| | `entra-agent-id` | 7 | Agent Identity Blueprints via Microsoft Graph for AI agent OAuth |
| **Resource & Architecture** | `azure-resource-lookup` | 2 | List/find Azure resources across subscriptions using Resource Graph |
| | `azure-resource-visualizer` | 4 | Generate Mermaid architecture diagrams from live Azure resource groups |
| | `azure-enterprise-infra-planner` | 35 | Design enterprise infra: landing zones, hub-spoke, multi-region DR, WAF alignment |
| **AI & Foundry** | `azure-ai` | 16 | Azure AI Search, Speech, OpenAI, Document Intelligence |
| | `azure-aigateway` | 9 | APIM as AI Gateway: semantic caching, token limits, content safety, load balancing |
| | `azure-hosted-copilot-sdk` | 6 | Build GitHub Copilot SDK apps on Azure |
| | `microsoft-foundry` | 89 | Foundry agent platform: model deploy, agent create/deploy/invoke/observe/trace/troubleshoot |

### microsoft/skills Monorepo (174 skills)

The broader `microsoft/skills` repo wraps `azure-skills` as a plugin and adds SDK-level skills organized by language:

| Language | Count | Key Categories |
|----------|:-----:|---------------|
| **Core** | 10 | Cloud Solution Architect, Copilot SDK, MCP Builder, Skill Creator, Frontend Design Review |
| **Foundry** | 11 | Router, Projects, Resources, Models, Hosted Agents, Toolboxes, Workflows, IQ Knowledge Bases, Memory, Observability, Governance |
| **Python** | 39 | Foundry AI (5), M365 (1), AI Services (8), Data & Storage (7), Messaging (4), Entra (2), Monitoring (4), Integration (5), Patterns (3) |
| **.NET** | 29 | Foundry AI (6), M365 (1), Data & Storage (6), Messaging (3), Entra (3), Compute & Integration (6), Monitoring (3) |
| **TypeScript** | 25 | Foundry AI (6), M365 (1), Data & Storage (5), Messaging (3), Entra & Integration (4), Monitoring & Frontend (5), Infrastructure (1) |
| **Java** | 26 | Foundry AI (7), Communication (5), Data & Storage (3), Messaging (3), Entra (3), Monitoring & Integration (5) |
| **Rust** | 7 | Entra (4), Data & Storage (2), Messaging (1) |

Source: [microsoft/skills README](https://github.com/microsoft/skills) — checked 2026-05-11.

## Deep Dive: The Deployment Workflow

The `azure-prepare → azure-validate → azure-deploy` pipeline is the most opinionated part of the skills ecosystem. It enforces a strict plan-first workflow with hard gates between phases.

<div align="center"><img src="images/deploy-workflow.png" width="720"/></div>

### How It Works

**Phase 1: azure-prepare** (164 files — the largest skill by far)

1. **Mandatory first action**: Write `.azure/deployment-plan.md` skeleton to disk before any code generation.
2. Analyze workspace → Gather requirements → Select recipe (AZD/Bicep/Terraform) → Plan architecture.
3. Generate infrastructure code, Dockerfiles, `azure.yaml`.
4. Present plan to user → Get approval → Set status to `Ready for Validation`.
5. **Hard rule**: `azure-prepare` must NOT run any deployment commands. It only generates artifacts.

**Phase 2: azure-validate** (17 files)

1. Read `deployment-plan.md` — if missing, STOP and invoke `azure-prepare`.
2. Run recipe-specific validation (e.g., `azd provision --preview`, `bicep build`, `terraform validate`).
3. Build verification — compile/build the project.
4. Static RBAC role verification — check Bicep/Terraform for correct role assignments.
5. Record proof in Section 7 of `deployment-plan.md`.
6. **Only azure-validate is authorized to set status to `Validated`**. azure-deploy is forbidden from doing this.

**Phase 3: azure-deploy** (41 files)

1. Check plan status = `Validated` AND Validation Proof section is populated.
2. Pre-deploy checklist (Container Apps + ACR RBAC health check).
3. Execute deployment with built-in error recovery.
4. Post-deploy: SQL managed identity + EF migrations.
5. Live RBAC verification.
6. Report endpoint URLs with `https://` scheme.

### What Makes This Design Strong

- **The plan file is the single source of truth**. All three skills read and write to `.azure/deployment-plan.md`. This prevents state drift between phases.
- **Validation proof is mandatory**. The validate skill must record what commands it ran and their results. Deploy checks this section is not empty.
- **Destructive actions require explicit user approval** via `ask_user` tool.
- **SQL Server**: NEVER generate `administratorLogin` or `administratorLoginPassword`. Always use Entra-only auth unconditionally.
- **Specialized routing**: If the user mentions copilot SDK, Azure Functions, APIM, or durable workflows, azure-prepare routes to the dedicated skill first.

### What to Watch Out For

- The 164-file `azure-prepare` skill is extremely comprehensive but also very prescriptive. Teams with existing deployment pipelines may find it conflicts with their workflows.
- The `@azure/mcp@latest` version is not pinned. For reproducibility in production, consider pinning to a specific version.
- The mandatory plan file approach adds overhead for simple one-off deployments. It is optimized for non-trivial, multi-service Azure deployments.

## Deep Dive: Foundry Agent Lifecycle

The `microsoft-foundry` skill (89 files) covers the complete AI agent development lifecycle:

| Phase | Sub-Skill | What It Does |
|-------|-----------|-------------|
| **Create** | `foundry-agent/create` | New agent app with Microsoft Agent Framework, LangGraph, or custom framework (Python/C#) |
| **Deploy** | `foundry-agent/deploy` | Containerize → ACR push → Create/update hosted agent deployment |
| **Invoke** | `foundry-agent/invoke` | Send messages to agents, single or multi-turn conversations |
| **Observe** | `foundry-agent/observe` | Batch evals, prompt optimization, regression detection, CI/CD monitoring |
| **Trace** | `foundry-agent/trace` | Query App Insights `customEvents`, correlate eval results to responses |
| **Troubleshoot** | `foundry-agent/troubleshoot` | View hosted agent logs, query telemetry, diagnose failures |
| **FAOS Optimize** | `foundry-agent/faos-optimize` | Convert existing code to FAOS optimization-ready version |
| **Eval Datasets** | `foundry-agent/eval-datasets` | Harvest production traces into evaluation datasets, version management |

The workspace standard requires a `.foundry/` directory:

```
<agent-root>/
  .foundry/
    agent-metadata.yaml
    agent-metadata.prod.yaml
    datasets/
    evaluators/
    results/
```

**Key design choice**: Foundry skills use Azure MCP's `foundry` tool as the primary entry point. SDK fallback (`azure-ai-projects`) is only used when MCP tools are unavailable.

### Foundry Skills: azure-skills vs microsoft/skills

The `microsoft-foundry` skill in `azure-skills` (89 files) is a monolithic orchestrator. The broader `microsoft/skills` repo restructured these into 11 focused, language-agnostic sub-skills:

| microsoft/skills Sub-Skill | Maps to azure-skills | New Capability |
|---------------------------|---------------------|----------------|
| `foundry-projects-resources` | `microsoft-foundry` project/create + resource/create | Dedicated project provisioning |
| `foundry-models` | `microsoft-foundry` models/deploy-model | Model discovery, PTU vs pay-as-you-go |
| `foundry-hosted-agents` | `microsoft-foundry` foundry-agent/deploy | Container-based agent management |
| `foundry-toolboxes` | New | MCP-compatible tool bundles (preview) |
| `foundry-iq-knowledge-bases` | New | Agentic retrieval pipeline (preview) |
| `foundry-workflows` | New | Multi-agent orchestration |
| `foundry-managed-skills` | New | SKILL.md as Foundry-side resource (preview) |
| `foundry-memory` | New | Long-term agent memory (preview) |
| `foundry-observability` | `microsoft-foundry` foundry-agent/observe + trace | OpenTelemetry traces in App Insights |
| `foundry-governance` | New | Fleet governance, RAI policies, tool catalog |

If you are building Foundry agents, the `microsoft/skills` Foundry sub-skills provide more granular control than the monolithic `microsoft-foundry` in `azure-skills`.

## Deep Dive: Cost Management

The `azure-cost` skill (21 files) is split into three sub-workflows:

| Sub-Workflow | Reference File | Purpose |
|-------------|---------------|---------|
| **Cost Query** | `cost-query/workflow.md` | Query historical costs via Cost Management REST API |
| **Cost Optimization** | `cost-optimization/workflow.md` | Find orphaned resources, rightsize VMs, Redis/AKS analysis |
| **Cost Forecast** | `cost-forecast/workflow.md` | Project future spending with forecast API |

**Enforced rules**:
- Always query actual costs first — never estimate or assume.
- Always present total bill alongside optimization recommendations.
- Use REST API (`az rest`) for cost queries, not `az costmanagement query`.
- Include `ClientType: GitHubCopilotForAzure` header on all Cost Management API requests.
- On 429 responses, wait for the longest `x-ms-ratelimit-microsoft.costmanagement-*-retry-after` header value.

## Deep Dive: Identity Layer

The identity-related skills create the deepest platform stickiness:

| Skill | Scope | Key Capability |
|-------|-------|---------------|
| `azure-rbac` | Role assignments | Find least-privilege roles, generate CLI/Bicep for assignment |
| `entra-app-registration` | App identity | OAuth 2.0 flows, MSAL, Microsoft Graph permissions, Bicep app registration |
| `entra-agent-id` | Agent identity | Agent Identity Blueprints via Graph API, OAuth token exchange (fmi_path, OBO, cross-tenant), AgentID sidecar |

Once an organization's identity model is built on Entra ID with Managed Identity + RBAC + Agent Identity, migrating to another cloud's identity system requires rebuilding the entire permission graph, not just changing SDK imports.

## Platform Stickiness Analysis

Not all stickiness is equal. Here is a four-layer model, from shallowest to deepest:

<div align="center"><img src="images/platform-stickiness.png" width="720"/></div>

| Layer | Stickiness | Migration Effort | What Gets Locked In |
|:-----:|:----------:|:----------------:|-------------------|
| **Dev Experience** | Low | Per-file SDK replacement | Azure SDK import patterns, auth patterns, error handling |
| **Infra & Deploy** | Medium | Rewrite IaC + deploy pipeline | Bicep/Terraform targeting Azure services, azure.yaml, Container Apps/Functions config |
| **AI Runtime** | High | Rebuild from scratch | Foundry agent runtime, eval pipelines, observability, toolboxes, memory |
| **Identity** | Very High | Rebuild org permission graph | Entra ID, RBAC assignments, Managed Identity, Agent Identity, Graph API permissions |

**The stickiness chain**: Azure SDK skills → azure-prepare/validate/deploy → Entra/RBAC → Monitor/App Insights → Foundry agent lifecycle → M365/Teams/Copilot Studio.

Once this full chain is in place, Microsoft becomes the **development, deployment, identity, AI, observability, governance, and collaboration platform** — not just a cloud resource provider.

## What Is NOT Covered

These skills focus on Azure cloud development and AI agent workflows. The following are explicitly out of scope:

| Category | Status | Notes |
|----------|:------:|-------|
| **Office/Word/Excel automation** | Not covered | No DOCX generation, editing, formatting, or Track Changes skills |
| **Non-Azure clouds** | Not covered | `azure-cloud-migrate` helps migrate TO Azure, not FROM Azure |
| **Mobile development** | Not covered | No iOS/Android/React Native skills |
| **Frontend frameworks** | Partially | `frontend-design-review` exists in Core skills, but no React/Vue/Angular SDK skills |
| **Database administration** | Partially | Cosmos DB and SQL are covered for deployment/RBAC, not for query optimization or schema design |
| **Networking deep-dive** | Partially | `azure-enterprise-infra-planner` covers VNets/NSGs/firewalls at architecture level, not packet-level troubleshooting |

The `m365-agents-py/dotnet/ts` skills in `microsoft/skills` are for building **agents on M365/Teams/Copilot Studio**, not for Office document manipulation.

The `azure-ai-translation-document-py` skill can translate Word/PDF/Excel files with format preservation, but this is a translation service, not a document automation tool.

## Installation and Verification

### Quick Install (APM — recommended)

```bash
apm install microsoft/azure-skills
```

### VS Code

Install the [Azure MCP Extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azure-mcp-server) — it automatically installs the companion skills extension.

### Copilot CLI

```bash
/plugin marketplace add microsoft/azure-skills
/plugin install azure@azure-skills
```

### Claude Code

```bash
/plugin install azure@claude-plugins-official
```

### Verification (three checks)

1. **Skills layer**: Ask "What Azure services would I need to deploy this project?" → expect structured Azure guidance.
2. **Azure MCP**: Ask "List my Azure resource groups." → expect real tool-backed response from your Azure account.
3. **Foundry MCP**: Ask "What AI models are available in Microsoft Foundry?" → expect Foundry-backed response.

### Prerequisites

- Azure account + subscription
- Node.js 18+ (`npx` required)
- Azure CLI (`az login`)
- Azure Developer CLI (`azd auth login`) for deployment workflows

## Best Practices for Selective Adoption

> **"Loading all skills causes context rot: diluted attention, wasted tokens, conflated patterns."**
> — microsoft/skills README

Not every team needs every skill. Here is a decision guide:

| If Your Team Needs... | Install These Skills | Skip These |
|----------------------|---------------------|-----------|
| Deploy apps to Azure | `azure-prepare`, `azure-validate`, `azure-deploy` | Foundry skills (unless building AI agents) |
| Build AI agents on Foundry | `microsoft-foundry` + Foundry sub-skills | `azure-cloud-migrate`, `azure-upgrade` |
| Manage costs and compliance | `azure-cost`, `azure-compliance`, `azure-quotas` | `azure-kubernetes`, `airunway-aks-setup` |
| Enterprise infrastructure | `azure-enterprise-infra-planner`, `azure-compute` | SDK-level skills (Python/Java/etc.) |
| Identity and security | `azure-rbac`, `entra-app-registration`, `entra-agent-id` | `azure-ai`, `azure-aigateway` |
| Troubleshoot production issues | `azure-diagnostics`, `appinsights-instrumentation` | `azure-hosted-copilot-sdk` |

## Reproducing This Analysis

### Clone the source repos

```bash
git clone --depth=1 https://github.com/microsoft/azure-skills.git /tmp/azure-skills
git clone --depth=1 https://github.com/microsoft/skills.git /tmp/skills
```

### Run the skill inventory

```bash
# Count all SKILL.md files
find /tmp/azure-skills/skills -name "SKILL.md" | wc -l
# → 31

# File count per skill (sorted by complexity)
for d in /tmp/azure-skills/skills/*/; do
  echo "$(find "$d" -type f | wc -l) $d"
done | sort -rn

# Total files
find /tmp/azure-skills/skills -type f | wc -l
# → 613
```

### Verify .mcp.json configuration

```bash
cat /tmp/azure-skills/.mcp.json
cat /tmp/azure-skills/.github/plugins/azure-skills/.mcp.json
# Both should show only one "azure" server using @azure/mcp@latest
```

### Regenerate diagrams

```bash
pip install Pillow
python images/generate_diagrams.py
```

## Project Information

| Field | Value |
|-------|-------|
| **Author** | Xinyu Wei (魏新宇) |
| **Date** | 2026-05-12 |
| **Source Repos** | [microsoft/azure-skills](https://github.com/microsoft/azure-skills) v1.1.39, [microsoft/skills](https://github.com/microsoft/skills) |
| **Data Checked** | 2026-05-11 |
| **License** | MIT |

## Related Repositories

Other repositories in [david-share/Agents](https://github.com/david-share/Agents) that demonstrate specific skills in action:

| Repository | Related Skills |
|-----------|----------------|
| [Azure-MCP-Solution](../Azure-MCP-Solution/) | Azure MCP Server setup and usage patterns |
| [Foundry-Hosted-Agent-Toolbox-Demo](../Foundry-Hosted-Agent-Toolbox-Demo/) | `microsoft-foundry` hosted agents + toolboxes |
| [AI-Foundry-Agent-VNET-Deployment](../AI-Foundry-Agent-VNET-Deployment/) | Foundry agent private network deployment |
| [Foundry-IQ](../Foundry-IQ/) | Foundry IQ knowledge bases |
| [Microsoft-Agent-Framework](../Microsoft-Agent-Framework/) | Microsoft Agent Framework patterns |
| [AOAI-APIM-Gateway-LoadBalancing](../AOAI-APIM-Gateway-LoadBalancing/) | `azure-aigateway` APIM AI Gateway scenarios |

*Running on Azure*
