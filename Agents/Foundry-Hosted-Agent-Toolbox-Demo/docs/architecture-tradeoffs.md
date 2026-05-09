# Architecture Trade-offs

Every architecture decision has a price. This document lists the explicit trade-offs in the hosted-agent-plus-toolbox shape so you can decide which ones you accept and which ones you do not.

Sources:

- Hosted Agents concept: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents
- Toolbox how-to: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox
- Foundry pricing: https://azure.microsoft.com/pricing/details/foundry-agent-service/

## The Three Forces

An agent system, like any distributed system, balances three forces:

- **Governance** — central control over auth, audit, approval, version, policy.
- **Latency** — wall-clock time from caller request to first useful token.
- **Flexibility** — how easily new tools, new agents, new frameworks plug in.

You can usually optimize two at a time. This architecture chooses **Governance + Flexibility** and pays in **Latency**.

| Architecture | Governance | Latency | Flexibility |
| --- | :---: | :---: | :---: |
| Direct model call from app | Low | Best | Low |
| App + in-process tools (function calling only) | Low | Good | Medium |
| App + private MCP server | Medium | Good | Medium |
| **Hosted Agent + Toolbox MCP (this repo)** | **High** | **Acceptable** | **High** |
| Hosted Agent + raw MCP servers (no toolbox) | Medium | Good | High |

If your scenario sits left of the bold row, you are paying for governance you do not need. If it sits right, you are paying for flexibility you do not need.

## Trade-off 1: Latency vs Governance

Each layer adds a hop:

| Hop | Cost | Why |
| --- | --- | --- |
| Caller → Hosted Agent endpoint | TLS + ingress routing | Required for stable endpoint and per-agent identity. |
| Hosted Agent container | Cold-start can be measurable on first request after idle | Per-session sandbox is provisioned on demand; warm requests skip this. |
| Hosted Agent → Foundry model | Model inference time (dominant) | Same as direct model call; no overhead added here. |
| Hosted Agent → Toolbox MCP | One MCP round-trip (`tools/list` cached, `tools/call` per use) | Required for governed tool execution. |
| Hosted Agent → Responses API web search | One HTTP round-trip plus Bing grounding | Required for current public web facts with citations. |

The model call dominates total latency for any non-trivial generation. The toolbox hop adds a small constant; the cold-start cost is the only measurable trade. Mitigations:

- Keep one warm session per active conversation (the Hosted Agents session model gives 15-minute idle timeout, then deprovision).
- Use the consumer endpoint (cached `default_version`) for steady-state traffic; reserve the version endpoint for canary tests.
- Avoid `prompts/list` round-trips on Foundry MCP — set `load_prompts=False` (Toolbox docs, troubleshooting table).
- Use streaming `tools/call` (the docs note non-streaming `tools/call` is unsupported and returns 500).

## Trade-off 2: Governance vs Flexibility

High governance pulls toward "everything goes through the catalog with approval gates"; high flexibility pulls toward "agents pick tools freely". The toolbox model resolves this with a per-tool `require_approval` flag (Toolbox docs, Step 4):

- `require_approval = "never"` — agent invokes the tool freely; suitable for read-only tools and code interpreter.
- `require_approval = "always"` — agent must surface the pending action to the user and wait for confirmation; suitable for write actions, money movement, irreversible changes.

The MCP endpoint **does not block** `tools/call` — enforcement is the agent runtime's responsibility. The toolbox surfaces `_meta.tool_configuration.require_approval` in `tools/list`; the agent reads it, compiles an approval map, and gates calls. This pushes the trade-off where it belongs: each tool owner decides the gate, the agent runtime enforces it consistently.

## Trade-off 3: Flexibility vs Operational Cost

Adding a hosted agent and a toolbox introduces operational surface:

| Surface | What it adds |
| --- | --- |
| Foundry project | Resource graph node, RBAC scope, regional placement. |
| Toolbox versions | Lifecycle to manage (create, test, promote, deprecate). |
| Hosted Agent versions | Container image lifecycle, ACR storage, idle session billing. |
| Connections | Each external service has a Foundry connection with credentials. |

Pricing (preview): managed hosting runtime is billed per CPU/memory consumed during active sessions; sessions deprovision after 15 minutes idle (Hosted Agents docs, Pricing). Compare against running your own ACA service plus a separate tool registry plus separate identity wiring — the operational cost trade tilts toward managed once you have more than a small number of agents or tools.

## Trade-off 4: Preview Stability vs Modern Capability

Both Hosted Agents and Toolbox are public preview. The trade is:

| You accept | You get |
| --- | --- |
| Preview SLA limits, possible breaking changes, region availability gaps | First-party managed surface for the agent + tool model, official sample, evolving feature set |

Mitigations encoded into this repo:

- All preview headers are explicit (`Foundry-Features: Toolboxes=V1Preview`).
- The dual web-search path (Toolbox MCP listing + direct Responses API runtime) absorbs the most visible preview gap.
- Region matrix and tool-by-region availability are linked from the toolbox docs; production rollout should pin to regions with all required tool types.

## Trade-off 5: Managed Identity vs Local Developer Velocity

The hosted agent runs as a Microsoft Entra ID created at deploy time. Locally, you typically use `AzureCliCredential` so multi-tenant developer machines pick the right subscription. The same code path runs in both environments via `DefaultAzureCredential`:

| Environment | Credential | Reason |
| --- | --- | --- |
| Local dev (multi-tenant box) | `AzureCliCredential` (`AZURE_AUTH_MODE=cli`) | Avoids `DefaultAzureCredential` picking the wrong tenant. |
| Hosted Agent | Default chain → agent's Entra ID | RBAC pre-wired by `azd deploy`; no key handling. |

Forcing the credential at startup keeps the local error surface obvious; defaulting in the hosted runtime keeps production secret-free.

## Decision Cheat Sheet

| Symptom | Likely wrong choice | Correct adjustment |
| --- | --- | --- |
| Cold-start latency unacceptable | Treating hosted agent as request-response only | Keep warm session per conversation; pre-warm during user idle |
| Tool name collisions across teams | One toolbox for everything | Multiple toolboxes per business domain; each team owns its toolbox |
| Frequent breaking tool changes | Promoting `default_version` aggressively | Stage with version endpoint, canary, then promote |
| Auth complexity creeping into agent code | Bypassing the toolbox for "simpler" direct calls | Move auth to a Foundry connection behind the toolbox |
| Approval requests confusing users | Mixing read-only and write tools without `require_approval` | Mark every write tool `require_approval=always`; let the agent show the dialog |

## Bottom Line

You pay one constant hop and a small management surface. You buy:

- A stable, identity-bearing agent endpoint that survives compute moves.
- A versioned, central tool catalog with explicit approval gating.
- The freedom to swap agent frameworks and add tools without redeploying clients.

If you do not need any of those three, you do not need this architecture.
