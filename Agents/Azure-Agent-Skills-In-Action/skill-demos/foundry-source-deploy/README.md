# Skill Demo: Foundry Source Code Deploy

> Deploy a Hosted Agent from Python source code — no Docker, no ACR, no Dockerfile.

## What This Demonstrates

The standard Hosted Agent deployment path requires building a Docker image, pushing to ACR, and referencing the image in `container_configuration`. **Source Code Deploy** eliminates all of that:

| Step | Container Deploy | Source Code Deploy |
|------|:---:|:---:|
| Write agent code | ✅ | ✅ |
| Write Dockerfile | ✅ | ❌ skip |
| Build Docker image | ✅ | ❌ skip |
| Push to ACR | ✅ | ❌ skip |
| Upload zip + metadata | ❌ | ✅ |
| Cloud installs dependencies | ❌ | ✅ (remote_build) |

## Files

```
foundry-source-deploy/
├── deploy.sh              ← End-to-end deploy script (REST API)
├── agent-code/
│   ├── main.py            ← Agent code (agent_framework + 2 tools)
│   ├── requirements.txt   ← Dependencies (cloud-installed)
│   └── metadata.json      ← Agent definition (code_configuration)
└── README.md              ← This file
```

## Agent Code

`main.py` defines a minimal agent with two custom tools:

- `get_current_time()` — returns UTC time
- `calculate(expression)` — evaluates math expressions

Uses `agent_framework.AgentBase` + `ResponsesHostServer` (same framework as container-based agents).

## Deployment Evidence

Deployed to: `https://ai-account-zc3svc6qlpe3k.services.ai.azure.com/api/projects/ai-project-toolbox-demo-env`

```
Agent name:    hello-source-agent
Runtime:       python_3_13
Dep resolution: remote_build
Status:        creating → active (~2 min)
HTTP:          200 (Create)
content_hash:  e36d19ef673c3d0e614ad489980379d1c8dd93098d4c1ba3a946453a97b6f832
```

Key response fields:
- `definition.code_configuration.runtime`: `python_3_13`
- `definition.code_configuration.dependency_resolution`: `remote_build`
- `definition.code_configuration.content_hash`: SHA-256 of uploaded zip
- `instance_identity.principal_id`: auto-assigned Managed Identity
- `blueprint_reference.type`: `ManagedAgentIdentityBlueprint`

## How to Reproduce

```bash
# 1. Login to Azure
az login --use-device-code --tenant "<your-tenant>"
az account set --subscription "<your-subscription>"

# 2. Run deploy script
cd skill-demos/foundry-source-deploy
bash deploy.sh
```

The script will: build zip → create agent (multipart REST) → poll until active → invoke.

## Key Differences from Container Deploy

| Aspect | Container (`container_configuration`) | Source Code (`code_configuration`) |
|--------|:---:|:---:|
| Upload format | Docker image → ACR | `.zip` file → REST multipart |
| Dependencies | Dockerfile `pip install` | Cloud `remote_build` or local `bundled` |
| System packages | `apt-get install` in Dockerfile | ❌ Not available |
| Custom fonts/binaries | ✅ Full control | ❌ Python-only |
| Build time | Local Docker build + ACR push | Cloud build (~2 min) |
| Complexity | High (Docker + ACR + RBAC) | Low (zip + REST) |
| Best for | Complex agents with system deps | Pure Python agents |

## Source

- [Deploy a hosted agent from source code (preview)](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-code?tabs=bash) — Microsoft Learn, 2026-05-28
- [Deploy a hosted agent (container)](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent) — Container-based alternative
