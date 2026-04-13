# NemoClaw on Azure: Deployment Guide and Technical Analysis

## Executive Summary

| Item | Finding |
|:---|:---|
| **What is NemoClaw** | NVIDIA open-source reference stack for running OpenClaw AI agents securely inside OpenShell sandboxes |
| **Azure Support** | No official Azure deployment path; manual installation on Azure Linux VMs works |
| **Maturity** | Alpha software (since March 2026). Not production-ready. APIs may change without notice |
| **Multi-User** | Single-user, single-sandbox design. No native multi-user or cross-VM management |
| **Azure OpenAI** | Not natively supported as inference provider. Requires a local proxy for header/path translation |
| **Inference Validated** | GPT-5.4 via Azure OpenAI APIM successfully tested through NemoClaw sandbox |
| **Key Value** | Security sandbox for autonomous AI agents (network/filesystem/process/inference isolation) |
| **Recommendation** | Suitable for evaluating agent security sandboxing. Not ready for enterprise multi-user production deployments |

> **Test Environment**: Azure Linux VM (Ubuntu 24.04, 4 vCPU, 8GB RAM, 1TB data disk), NemoClaw v0.0.14, OpenShell v0.0.26, OpenClaw v2026.3.11. Tested April 2026.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Supported Inference Providers](#supported-inference-providers)
- [Azure Deployment Guide](#azure-deployment-guide)
- [Azure OpenAI Integration](#azure-openai-integration)
- [Security Features](#security-features)
- [Multi-User Capabilities](#multi-user-capabilities)
- [Known Limitations](#known-limitations)
- [Reproducing the Results](#reproducing-the-results)

---

## Architecture Overview

NemoClaw is a three-layer stack:

```
┌─────────────────────────────────────────────┐
│  🦞 NemoClaw (Operations Layer)             │
│  CLI + Guided onboarding + Blueprint        │
│  State management + Security policies       │
├─────────────────────────────────────────────┤
│  🐚 OpenShell (Sandbox Runtime)             │
│  Gateway + Policy Engine + Inference proxy   │
│  Landlock + seccomp + Network namespace      │
├─────────────────────────────────────────────┤
│  🦞 OpenClaw (AI Agent)                     │
│  Autonomous assistant inside sandbox         │
│  Tool calling + Memory + Persistent state    │
└─────────────────────────────────────────────┘
```

**Inference Routing** — the agent never directly accesses the inference provider:

```
Agent (sandbox) ──► inference.local ──► OpenShell Gateway (host) ──► Inference Provider
                    (never direct)       (credential injection)       (API key on host only)
```

---

## Supported Inference Providers

| Provider | Status | Protocol | Models |
|:---|:---|:---|:---|
| NVIDIA Endpoints | Tested | OpenAI-compatible | Nemotron 3 Super 120B, MiniMax M2.5, GLM-5 |
| OpenAI | Tested | Native OpenAI | gpt-5.4, gpt-5.4-mini |
| Other OpenAI-compatible | Tested | Custom | Any `/v1/chat/completions` endpoint |
| Anthropic | Tested | Native Anthropic | claude-sonnet-4-6 |
| Google Gemini | Tested | OpenAI-compatible | gemini-2.5-pro/flash |
| Local Ollama | Caveated | Local Ollama API | Local models |
| Local vLLM | Experimental | Local OpenAI-compatible | Requires `NEMOCLAW_EXPERIMENTAL=1` |
| Local NVIDIA NIM | Experimental | Local OpenAI-compatible | Requires NIM-capable GPU |

**Azure OpenAI is not a built-in provider option.** It can be integrated via the "Other OpenAI-compatible endpoint" option with a local proxy (see [Azure OpenAI Integration](#azure-openai-integration)).

---

## Azure Deployment Guide

### Prerequisites

- Azure Linux VM (Ubuntu 24.04 recommended)
- Minimum: 4 vCPU, 8GB RAM, **40GB+ disk** (sandbox image is ~4GB compressed)
- Docker installed and running
- Node.js 22.16+ (installer handles this via nvm)

### Step 1: Install Docker

```bash
sudo apt-get update && sudo apt-get install -y docker.io
sudo systemctl enable --now docker
```

### Step 2: Install NemoClaw

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
```

The installer will:
1. Install/detect Node.js 22 via nvm
2. Clone and build NemoClaw from GitHub source
3. Install OpenShell CLI
4. Run the onboarding wizard

### Step 3: Onboard with Inference Provider

During the interactive onboarding wizard, select your inference provider. For Azure OpenAI, see the [next section](#azure-openai-integration).

For non-interactive setup:

```bash
NEMOCLAW_PROVIDER=custom \
NEMOCLAW_ENDPOINT_URL="http://localhost:9100/v1" \
NEMOCLAW_MODEL="gpt-5.4" \
COMPATIBLE_API_KEY="<your-key>" \
nemoclaw onboard --non-interactive
```

### Step 4: Connect to the Sandbox

```bash
nemoclaw my-assistant connect
```

### Step 5: Chat with the Agent

Inside the sandbox:

```bash
# Single message
openclaw agent --agent main -m "Hello, what can you do?" --session-id demo

# Interactive TUI
openclaw tui
```

---

## Azure OpenAI Integration

### The Challenge

NemoClaw's "Other OpenAI-compatible endpoint" provider sends requests using:
- `Authorization: Bearer <key>` header
- Standard OpenAI paths: `/v1/chat/completions`, `/v1/responses`

Azure OpenAI (including APIM proxy) requires:
- `api-key: <key>` header
- Azure-specific paths: `/openai/deployments/{model}/chat/completions?api-version=...`

### Solution: Local Proxy

Deploy a lightweight Node.js proxy on the host VM that translates between the two formats:

```
NemoClaw Sandbox
    ↓ inference.local
OpenShell Gateway
    ↓ http://127.0.0.1:9100/v1/chat/completions (Bearer token)
Local Proxy (aoai-proxy.js)
    ↓ https://your-aoai.openai.azure.com/openai/deployments/gpt-5.4/chat/completions (api-key)
Azure OpenAI
```

The proxy ([scripts/aoai-proxy.js](scripts/aoai-proxy.js)) handles:
1. **Header translation**: `Authorization: Bearer xxx` → `api-key: xxx`
2. **Path translation**: `/v1/chat/completions` → `/openai/deployments/{model}/chat/completions?api-version=...`
3. **Pass-through**: `/v1/responses`, `/v1/models` with proper Azure paths

### Proxy Setup

```bash
# Start the proxy on the host (not inside the sandbox)
node scripts/aoai-proxy.js &

# Verify it works
curl -s http://127.0.0.1:9100/v1/chat/completions \
  -H "Authorization: Bearer <your-apim-key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.4","messages":[{"role":"user","content":"hello"}],"max_completion_tokens":10}'
```

### Disk Space Considerations

NemoClaw requires significant disk space:

| Component | Size |
|:---|:---|
| Sandbox base image | ~3.8 GB |
| Built sandbox image | ~3.8 GB |
| OpenShell gateway (k3s) | ~850 MB |
| k3s extracted layers | ~2-3 GB |
| **Total minimum** | **~12-15 GB** |

If your OS disk is small (30GB), move Docker and k3s data to a data disk:

```bash
# Stop Docker
systemctl stop docker docker.socket

# Move to data disk
mkdir -p /data/docker
rsync -aP /var/lib/docker/ /data/docker/
rm -rf /var/lib/docker
ln -s /data/docker /var/lib/docker

# Restart
systemctl start docker
```

---

## Security Features

NemoClaw provides four layers of protection:

| Layer | Mechanism | Hot-reloadable |
|:---|:---|:---|
| **Network** | Deny-by-default egress. YAML policy. Operator approval for unlisted hosts | Yes |
| **Filesystem** | Landlock LSM. `/sandbox` read-only. Only specific paths writable | No (locked at creation) |
| **Process** | seccomp filters. ulimit 512 processes. No privilege escalation | No (locked at creation) |
| **Inference** | All calls routed through gateway. Credentials never enter sandbox | Yes |

Additional hardening:
- Build toolchains (gcc, g++, make) removed from runtime image
- Network probes (netcat) removed
- Agent home directory read-only
- Gateway config immutable

---

## Multi-User Capabilities

### What NemoClaw Supports

| Capability | Status |
|:---|:---|
| Single-user single-sandbox | ✅ Primary design |
| Channel messaging (Telegram/Discord/Slack) | ✅ Multiple users share one agent via bot |
| Per-user isolated sandboxes | ❌ Not supported natively |
| Cross-VM management | ❌ Not available |
| Central management dashboard | ❌ Not available |
| RBAC / user access control | ❌ Not available |
| Kubernetes multi-pod | 🧪 Experimental (requires privileged DinD pods) |

### For Multi-User Scenarios

The only native multi-user path is **channel messaging** — multiple users interact with the same agent through Telegram/Discord/Slack bots. All users share the same agent context with no isolation between them.

For per-user isolation, each user needs a separate NemoClaw instance (separate VM or separate K8s pod), which is costly and lacks centralized management.

---

## Known Limitations

| Limitation | Impact | Workaround |
|:---|:---|:---|
| Alpha software | APIs and behavior may change | Evaluation only, not production |
| No native Azure OpenAI support | Cannot directly connect to AOAI | Use local proxy (provided in this repo) |
| Web Dashboard remote auth bug | Device pairing fails over SSH tunnels | Use CLI (`openclaw agent`) or TUI (`openclaw tui`) |
| K8s requires privileged pods | Security concern for enterprise clusters | Use VM deployment instead |
| ~12-15GB disk requirement | Small OS disks run out of space | Use data disk, symlink Docker/k3s |
| No cross-instance communication | Sandboxes are fully isolated | Not addressable — by design |
| npm package name squatted | `npm install -g nemoclaw` installs a fake empty package | Use official installer script only |

---

## Reproducing the Results

### Environment Setup

```bash
# 1. Create an Azure Linux VM (Ubuntu 24.04, Standard_D4s_v3 or similar)
#    Ensure 40GB+ disk or attach a data disk

# 2. SSH into the VM
ssh -p 22 <user>@<vm-fqdn>

# 3. Install Docker
sudo apt-get update && sudo apt-get install -y docker.io
sudo systemctl enable --now docker

# 4. Install NemoClaw
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
source ~/.bashrc

# 5. Start the AOAI proxy (if using Azure OpenAI)
node scripts/aoai-proxy.js &

# 6. Run onboarding
nemoclaw onboard
# Select "Other OpenAI-compatible endpoint"
# Enter: http://127.0.0.1:9100 (if using AOAI proxy)
# Enter your API key
# Enter model name: gpt-5.4

# 7. Connect and test
nemoclaw my-assistant connect
openclaw agent --agent main -m "Hello!" --session-id test
```

### Expected Output

```
🦞 OpenClaw 2026.3.11 (29dc654)

Hello! I'm your AI assistant running inside a secure NemoClaw sandbox.
```

---

## References

- [NemoClaw GitHub](https://github.com/NVIDIA/NemoClaw) (19.1k stars, Apache 2.0)
- [NemoClaw Documentation](https://docs.nvidia.com/nemoclaw/latest/)
- [OpenShell GitHub](https://github.com/NVIDIA/OpenShell)
- [OpenClaw](https://openclaw.ai/)
- [NemoClaw Architecture](https://docs.nvidia.com/nemoclaw/latest/reference/architecture.html)
- [Inference Options](https://docs.nvidia.com/nemoclaw/latest/inference/inference-options.html)
- [Network Policies](https://docs.nvidia.com/nemoclaw/latest/reference/network-policies.html)

---

*Author: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer*
*Date: April 2026*
