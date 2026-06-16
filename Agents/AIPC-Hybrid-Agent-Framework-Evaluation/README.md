# AIPC Hybrid Agent Framework Evaluation

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/) [![Hyperlight](https://img.shields.io/badge/Hyperlight-Sandbox-purple.svg)](https://github.com/hyperlight-dev/hyperlight) [![License: Sample](https://img.shields.io/badge/license-sample-lightgrey.svg)]()

Side-by-side comparison portal for three open-source agent frameworks — **LangChain**, **LangGraph**, and **Microsoft Agent Framework (MAF)** — running on a hybrid Cloud + AIPC architecture with Hyperlight micro-VM sandboxed code execution.

> **Author**: 魏新宇 (Xinyu Wei) — Microsoft AI GBB Senior System Engineer

**Recorded walkthrough**: MAF + Hyperlight host tools on Windows AIPC — screenshot capture, system info query, CSV data analysis, all executed inside Hyperlight micro-VM with WHP isolation.

https://github.com/user-attachments/assets/c2554bf2-da92-4a32-8692-0c576d7af376

---

## What's Real vs What's Demo

| Area | What actually runs | Boundary |
|------|--------------------|----------|
| Portal streaming | FastAPI SSE endpoints stream live step/tool/token/result events | Real runtime path |
| LangChain / LangGraph portal tabs | Azure OpenAI calls + real wttr.in weather API + optional SerpAPI flight/hotel calls | If `SERPAPI_API_KEY` is empty, returns explicit `unavailable` results, not mock data |
| Hybrid sandbox presets | LLM-generated Python is executed by the AIPC Sandbox API in Hyperlight | Real code execution |
| MAF host tools | `read_csv`, `list_host_files`, `host_system_info`, `capture_screenshot` bridge host tools into CodeAct | Real host tool callbacks |
| Standalone `scenarios/*travel*` scripts | Mock weather/flight/hotel fixtures | Intentional fixtures for fair cross-framework comparison |
| MAF HITL portal demo | `request_info()` pause is demonstrated, then UI choice is forwarded to the next LLM call | Full `workflow.run(responses=...)` resume is not claimed |

## Architecture

<div align="center">
  <img src="images/architecture.png" width="960" alt="AIPC Hybrid Agent Framework architecture">
</div>

## Running on Azure

| Resource | SKU / Config | Purpose |
|----------|-------------|---------|
| Portal VM | Linux, Standard_D4s_v5, East Asia | FastAPI portal backend + nginx |
| AIPC VM | Windows 11, NPU-capable | Hyperlight Sandbox + Ollama + MAF |
| Azure OpenAI | gpt-5.4 via APIM | Cloud LLM for all frameworks |
| APIM | Consumption tier | Unified gateway for AOAI |

## Features

| Tab | What it shows |
|-----|--------------|
| **Overview** | Framework capabilities — how each framework handles tool use, memory, streaming |
| **Recovery** | Error recovery — what happens when an agent step crashes |
| **HITL** | Human-in-the-loop — can the agent pause for human approval before executing |
| **Hybrid Exec** | Code generation (cloud/local LLM) → sandboxed execution in Hyperlight micro-VM on Windows AIPC |

### Hybrid Execution presets

| Preset | Model | What happens |
|--------|-------|-------------|
| 沙箱任务 / 运行时证明 / 圣诞树 | LC/LG=Cloud, MAF=Ollama local | LLM generates Python → Hyperlight micro-VM executes with WHP isolation |
| 读CSV / 截屏 / 列文件 / 系统信息 | MAF=gpt-5.4 + HyperlightCodeActProvider | MAF Agent decides code, provider manages sandbox + 4 host tools |

## Setup

### Portal (Linux VM)

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
python portal/server.py  # → http://0.0.0.0:8506
```

### AIPC Sandbox API (Windows VM)

#### 1. Prerequisites

```powershell
# Python 3.12
winget install Python.Python.3.12

# Hyperlight Sandbox (WASM backend — requires Windows Hypervisor Platform)
pip install hyperlight-sandbox

# Microsoft Agent Framework + Hyperlight provider
pip install agent-framework agent-framework-hyperlight

# FastAPI + OpenAI SDK
pip install fastapi uvicorn openai

# Ollama (local LLM for Sandbox code-gen presets)
# Download from https://ollama.com/ → install → pull model:
ollama pull qwen3:1.7b
```

#### 2. Enable Windows Hypervisor Platform (WHP)

Hyperlight micro-VM requires WHP. Enable it in an **elevated PowerShell**:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -NoRestart
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
# Reboot required
Restart-Computer
```

Verify after reboot:

```powershell
(Get-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform).State
# Expected: Enabled
```

#### 3. Azure NSG — Open Port 8507

The Portal VM calls the AIPC Sandbox API over HTTP. The AIPC VM's NSG must allow inbound TCP 8507 from the Portal VM IP:

```bash
az network nsg rule create \
  --resource-group <aipc-rg> \
  --nsg-name <aipc-nsg> \
  --name AllowSandboxAPI \
  --priority 310 \
  --direction Inbound \
  --access Allow \
  --protocol Tcp \
  --destination-port-ranges 8507 \
  --source-address-prefixes <portal-vm-ip>
```

#### 4. Set Machine Environment Variables

```powershell
# Azure OpenAI / APIM (used by CodeAct path)
[System.Environment]::SetEnvironmentVariable("AOAI_ENDPOINT", "https://your-apim.azure-api.net", "Machine")
[System.Environment]::SetEnvironmentVariable("AOAI_KEY", "your-apim-key", "Machine")
[System.Environment]::SetEnvironmentVariable("AOAI_MODEL", "gpt-5.4", "Machine")

# Optional path overrides. Defaults target the logged-in user's Desktop.
[System.Environment]::SetEnvironmentVariable("AIPC_APP_DIR", "C:\Users\aipcadmin\Desktop", "Machine")
[System.Environment]::SetEnvironmentVariable("AIPC_HOST_DATA_DIR", "C:\Users\aipcadmin\Desktop", "Machine")
[System.Environment]::SetEnvironmentVariable("AIPC_RUNTIME_DIR", "C:\Users\aipcadmin\Desktop", "Machine")
[System.Environment]::SetEnvironmentVariable("AIPC_SCREENSHOT_PATH", "C:\Users\aipcadmin\Desktop\last_screenshot.png", "Machine")
[System.Environment]::SetEnvironmentVariable("PYTHON_EXE", "C:\Program Files\Python312\python.exe", "Machine")
```

> **Important**: After setting Machine env vars, you must start a **new** process (or reboot) for them to take effect. Existing processes do NOT pick up changes.

#### 5. Place Sample Data

```powershell
# Copy sample CSV to Desktop (host tools read from here)
Copy-Item aipc\sample-data\sales_data.csv C:\Users\aipcadmin\Desktop\
```

#### 6. Run

```powershell
python portal\sandbox_api.py  # → http://0.0.0.0:8507
```

#### 7. Production Service (NSSM)

NSSM (Non-Sucking Service Manager) wraps Python as a Windows Service with auto-restart — equivalent to Linux `systemd Restart=always`.

```powershell
# Download NSSM (one-time)
Invoke-WebRequest -Uri https://nssm.cc/release/nssm-2.24.zip -OutFile nssm.zip
Expand-Archive nssm.zip -DestinationPath nssm-tmp
Copy-Item nssm-tmp\nssm-2.24\win64\nssm.exe C:\Users\aipcadmin\Desktop\nssm.exe

# Install service and create the ScreenshotHelper scheduled task.
# Set NSSM_SERVICE_PASSWORD or let the script prompt interactively.
$env:NSSM_SERVICE_PASSWORD = "<your-password>"
.\aipc\install-nssm-service.ps1
```

> **Why NSSM instead of schtask?** schtask is a trigger (like cron) — it starts a process once and doesn't care if it dies. NSSM is a service manager (like systemd) — it monitors the process and auto-restarts on crash with configurable delay. Demo services need auto-restart; schtask doesn't provide it.

> **Why `ObjectName .\aipcadmin`?** SYSTEM account runs in Session 0 with no desktop — `capture_screenshot` returns blank. Running as the interactive user gives access to the RDP desktop for GDI CopyFromScreen.

> **ScreenshotHelper task**: `install-nssm-service.ps1` creates a `ScreenshotHelper` scheduled task using `/IT` so `capture_screenshot.ps1` runs in the interactive RDP session. The API triggers it with `schtasks /Run /TN ScreenshotHelper`.

#### 8. Verify

```powershell
# Health check
Invoke-WebRequest http://localhost:8507/api/codeact/health | Select-Object -Expand Content

# Quick sandbox test
Invoke-WebRequest -Method POST http://localhost:8507/api/sandbox/run `
  -ContentType "application/json" `
  -Body '{"code":"print(42)"}' | Select-Object -Expand Content
```

## Project Structure

```
├── portal/
│   ├── server.py              # Portal backend (FastAPI + SSE, 4 tabs × 3 frameworks)
│   ├── sandbox_api.py         # AIPC Sandbox API (Hyperlight + MAF CodeAct)
│   └── static/
│       └── index.html         # Portal frontend (single-page, SSE streaming)
├── images/
│   └── architecture.png       # Architecture diagram used by README
├── aipc/
│   ├── install-nssm-service.ps1 # NSSM Windows Service installer (auto-restart, logging, env vars)
│   ├── capture_screenshot.ps1 # Screenshot helper (schtask /IT, runs in RDP session for desktop access)
│   ├── start-sandbox.ps1      # Standalone launcher (reads Machine env vars, for manual start)
│   ├── start-sandbox.bat      # Batch wrapper
│   ├── capture_now.ps1        # One-shot desktop screenshot (GDI CopyFromScreen)
│   ├── monitor-all.ps1        # Full-stack monitor (Ollama + Sandbox + Portal health)
│   ├── watchdog-sandbox.ps1   # Legacy watchdog (superseded by NSSM)
│   ├── hyperlight_standalone_verify.py  # Standalone Hyperlight + WHP verification
│   ├── hyperlight_stress_test.py        # 10× consecutive sandbox stress test
│   ├── hyperlight_live_monitor.py       # Live tail of sandbox execution logs
│   └── sample-data/
│       └── sales_data.csv     # Sample CSV for read_csv host tool
├── scenarios/                  # Standalone framework comparison scripts
│   ├── langchain_*.py         # LangChain scenarios (meeting + travel)
│   ├── langgraph_*.py         # LangGraph scenarios (meeting + travel)
│   ├── maf_*.py               # MAF scenarios (meeting + travel + workflow)
│   └── test_maf_hitl.py       # MAF human-in-the-loop test
├── .env.example
├── requirements.txt
└── README.md
```

> **Public mirror**: [`david-share/Agents/AIPC-Hybrid-Agent-Framework-Evaluation`](https://github.com/david-xinyuwei/david-share/tree/master/Agents/AIPC-Hybrid-Agent-Framework-Evaluation)

## Key Technical Decisions

- **`gc.disable()`** in sandbox_api.py: Hyperlight's WasmSandbox is a Rust `!Send` native object. Python's cyclic GC can trigger Rust Drop on the wrong thread → panic. Disabling cyclic GC is safe because refcounting still works; cyclic-reference leaks are acceptable for a Demo process.
- **NSSM + schtask dual architecture**: Windows has strict Session isolation — Services (NSSM) always run in Session 0 (no desktop), while RDP users are in Session 1/2+. This means:
  - **NSSM** manages the SandboxAPI main process (Session 0): auto-restart on crash (`AppRestartDelay 3000`), logging, env vars, boot auto-start. Equivalent to Linux `systemd Restart=always`.
  - **schtask /IT** manages screenshot capture (Session 2): runs `capture_screenshot.ps1` in the interactive RDP session where CopyFromScreen can access the desktop framebuffer. Triggered on-demand by the API, not a resident process.
  - Linux doesn't need this split because systemd services can access virtual framebuffers (Xvfb) and session isolation is less strict.
- **Multi-worker uvicorn**: `uvicorn --workers 4` (multi-process, not multi-thread). Each worker is an independent Python process with its own GC, so Hyperlight `!Send` constraints are not violated across workers. Handles concurrent requests from multiple users.
- **No Basic Auth**: Removed because browser EventSource doesn't auto-send Authorization headers. Port protected by Azure NSG instead.
- **gpt-5.4 for CodeAct**: Non-reasoning models (gpt-4.1-mini) hallucinate fake file names when tool-use fidelity is weak. gpt-5.4 is slower (~10s) but reliable.

## Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `AOAI_ENDPOINT` | AIPC Machine env | Azure OpenAI / APIM endpoint (bare domain, no `/openai`) |
| `AOAI_KEY` | AIPC Machine env | APIM subscription key |
| `AOAI_MODEL` | AIPC Machine env | Deployment name (e.g., `gpt-5.4`) |
| `AZURE_OPENAI_ENDPOINT` | Portal .env | Same, for portal-side LangChain/LangGraph |
| `AZURE_OPENAI_API_KEY` | Portal .env | Same |
| `SERPAPI_API_KEY` | Portal .env | Optional real Google Flights/Hotels data via SerpAPI |
| `OLLAMA_BASE_URL` | AIPC | Ollama endpoint for local code gen |
| `AIPC_SANDBOX_URL` | Portal .env | URL to AIPC Sandbox API |
| `AIPC_APP_DIR` | AIPC Machine env | Directory containing `sandbox_api.py`, scripts, logs |
| `AIPC_HOST_DATA_DIR` | AIPC Machine env | Directory exposed to host tools such as `read_csv` |
| `AIPC_RUNTIME_DIR` | AIPC Machine env | Directory for last-run JSON evidence files |
| `AIPC_SCREENSHOT_PATH` | AIPC Machine env | Screenshot artifact path written by `ScreenshotHelper` |
| `PYTHON_EXE` | AIPC Machine env | Python executable used by NSSM |

## Tech Stack

| Component | Version |
|-----------|---------|
| Python | 3.12 |
| FastAPI | 0.115+ |
| LangChain | 0.3+ |
| LangGraph | 0.4+ |
| Microsoft Agent Framework | 1.8+ |
| agent-framework-hyperlight | 1.0.0b |
| hyperlight-sandbox | 0.3+ |
| Ollama | latest |
| OpenAI SDK | 1.80+ |
