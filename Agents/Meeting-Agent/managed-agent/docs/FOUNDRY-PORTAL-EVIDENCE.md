# Foundry Portal Evidence

[Chinese](FOUNDRY-PORTAL-EVIDENCE-CN.md) | **English** | [Managed implementation](MANAGED-IMPLEMENTATION.md) | [Product home](../../README.md)

This page explains what the Microsoft Foundry portal shows for a separate West US 2 private-preview validation deployment of the Managed Meeting Agent. The screenshots were captured on 2026-07-28 and sanitized before being added to the repository: project, Agent, endpoint, subscription, tenant, account, and browser-profile identifiers are removed.

These images complement the local browser workspace shown on the product home. They prove that the cloud Agent, Toolbox, versioned Skills, and built-in Hand/Sandbox path were visible and executable in Foundry. They do not claim a production SLA or replace versioned API exports as the authority for exact configuration.

## 1. Agent resource and managed harness

The Agents list records three product facts without exposing the resource name: the Agent was **Running**, its type was **prompt**, and its harness was **GitHub Copilot**.

<div align="center">
<img src="../images/foundry-portal/agent-list.png" width="960" alt="Sanitized Foundry Agents list showing Running prompt Agent with GitHub Copilot harness">
</div>

The Playground then shows the selected model and Agent instructions. The Toolbox endpoint and resource names are intentionally masked. This view demonstrates the Portal authoring surface; the live Agent API export remains authoritative for immutable version fields.

<div align="center">
<img src="../images/foundry-portal/agent-playground.png" width="800" alt="Sanitized Foundry Playground showing model and Agent instructions">
</div>

## 2. Toolbox as the governed MCP surface

The Toolbox view exposes Web Search and the meeting-output Skills. A Toolbox is a versioned Foundry resource whose MCP endpoint presents tools and Skill resources to the Agent. Toolbox is not the Hand Sandbox.

<div align="center">
<img src="../images/foundry-portal/toolbox-skills.png" width="800" alt="Sanitized Foundry Toolbox showing Web Search and meeting Skills">
</div>

The screenshot is a Portal observation, not a complete inventory contract. Exact membership is version-scoped and should be verified through the Toolbox API or MCP `resources/list`. The repository source defines three meeting-output responsibilities:

| Skill | Responsibility | Renderer boundary |
|---|---|---|
| `meeting-package` | Summary, topics, decisions, actions, and open questions | Does not own mind-map or slide rendering |
| `mind-map-story` | Evidence-grounded semantic tree | Does not choose coordinates, colors, or file formats |
| `presentation-story` | Strict six-section `DeckPlan` | Does not create PPTX shapes or files |

## 3. Versioned Skill source in the Portal

The Portal can display the immutable `SKILL.md` content resolved by a Toolbox version.

### Meeting analysis

<div align="center">
<img src="../images/foundry-portal/skill-meeting-package-version-drift.png" width="800" alt="Foundry Portal view of an earlier meeting-package Skill version">
</div>

This capture is useful because it also exposes version drift: the displayed older cloud Skill description still mentions a concise mind map, while the latest repository source moves semantic-tree ownership to `mind-map-story`. Do not treat a Portal screenshot as proof that cloud and source are identical. Reconcile and republish the Toolbox, then verify the exact Skill body or hash through the versioned API.

### Mind-map semantics

<div align="center">
<img src="../images/foundry-portal/skill-mind-map-story.png" width="800" alt="Foundry Portal view of the mind-map-story Skill">
</div>

`mind-map-story` owns evidence selection, hierarchy, branch boundaries, and concise labels. The local deterministic renderer owns Mermaid syntax, SVG/PNG generation, geometry, wrapping, and colors.

### Six-slide narrative

<div align="center">
<img src="../images/foundry-portal/skill-presentation-story.png" width="800" alt="Foundry Portal view of the presentation-story Skill">
</div>

`presentation-story` creates the strict six-section `DeckPlan`. The local renderer and packaged template remain responsible for editable PPTX generation.

## 4. Built-in Hand/Sandbox observation

The Managed Agent definition does not contain a customer-configured Sandbox Tool, CPU, memory, image, or runtime field. Selecting the managed GHCP harness makes built-in Hand execution tools available at runtime. Sandbox compute starts on demand when the model calls execution or file tools such as Bash, shell, code execution, or file operations.

The Portal run below asked the Agent to inspect its filesystem and capacity. That session reported a 19 GB root filesystem, two visible CPU cores, and 4 GB memory.

<div align="center">
<img src="../images/foundry-portal/hand-sandbox-capacity.png" width="960" alt="Foundry Portal Hand Sandbox filesystem CPU and memory observation">
</div>

A separate fail-closed probe corroborated Linux x86_64, two visible processors, approximately 4.07 GiB total memory, Debian 12, Python 3.13.14, and `/workspace` as the working directory. See [the sanitized observation](../evidence/managed-live-westus2/sandbox-runtime-observation.json).

These numbers are a single-session observation. They are not an immutable Agent-version guarantee, Sandbox profile, quota, or SLA. The current Portal and Agent definition do not expose a versioned Sandbox profile, image digest, runtime package inventory, cgroup limits, or Sandbox session lifecycle. Workloads that require a guaranteed CPU/memory shape or a customer-controlled Python/.NET image should use a Hosted Agent or directly managed ACA Sandbox.

## What the screenshots prove—and what they do not

| Claim | Status | Evidence boundary |
|---|---|---|
| A prompt Agent ran on the managed GitHub Copilot harness | Proven | Agents list and live Agent API |
| Toolbox exposed versioned tools and Skills | Proven | Toolbox view plus API/MCP validation |
| Meeting, mind-map, and presentation responsibilities were separated | Proven in current source; Portal versions must be reconciled | Skill views plus repository contracts |
| Built-in Hand executed filesystem and capacity commands | Proven for the observed session | Portal output plus independent fail-closed probe |
| Every future Sandbox has two CPUs and 4 GB memory | **Not proven** | No versioned Sandbox runtime contract is exposed |
| The Hand Sandbox is a customer-configured Toolbox Tool | **False** | Live Agent definition contains only the Toolbox MCP connection |

The product gap is visible: the Portal proves that Hand execution occurred, but it does not provide a customer-auditable runtime profile for CPU, memory, OS image, language versions, lifecycle, persistence, or drift. That limitation must remain explicit in any production-readiness discussion.
