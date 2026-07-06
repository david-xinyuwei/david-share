# AIPC Edge Agent Execution: Two Paths to Windows-Native Local Runtime

[![MAF](https://img.shields.io/badge/MAF-1.8-0078D4?logo=microsoft&logoColor=white)](https://github.com/microsoft/agent-framework) [![MXC](https://img.shields.io/badge/MXC_SDK-0.7-purple)](https://github.com/microsoft/mxc) [![Hyperlight](https://img.shields.io/badge/Hyperlight-Sandbox-blue)](https://github.com/hyperlight-dev/hyperlight) [![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AIPC needs local reasoning plus safe local execution. This repo evaluates two implementation paths from Build 2026 (BRK262 / KEY01): **Path A — MAF-based full agent loop**, and **Path B — MXC + runtime backend direct**. All test code, policy profiles, and evidence logs are included.

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

[中文版](README-CN.md) | English

---

## AIPC Two-Path Architecture (from Build 2026)

<div align="center">
  <img src="images/slide05-aipc-two-paths-overview.png" width="960" alt="AIPC demand and two implementation paths">
</div>

> Source: Build 2026 BRK262 + KEY01. Local small models can reason on device. Some AIPC tasks still need Windows-native local execution.

**Path A vs Path B — how to choose:**

| | Path A: MAF-based implementation | Path B: MXC + Runtime Backend Direct |
|---|---|---|
| **Scenario** | Complete hybrid cloud+local agent workflow | App only needs controlled Windows-native runtime, no full agent loop |
| **How it works** | Planning → call tools → generate action → observe → continue reasoning; MAF orchestration loop | MXC declares policy; ProcessContainer runs lighter tasks; Hyperlight isolates highest-risk generated code |
| **Representative demo** | CodeAct in Agent Framework; MAF + AIPC demo | MXC Policy demo; OpenClaw file-delete blocked |
| **Core traits** | ✓ Full reasoning-action loop ✓ Dynamic tool calls ✓ Multi-step long tasks | ✓ Lighter, no MAF dependency ✓ Declarative security boundary ✓ Hardware-level isolation (when needed) |
| **Best for** | ISV building complex agent experiences | Lightweight safe execution scenarios |

> **Decision rule**: Need an agent reasoning loop? → Path A (MAF). Only need safe local execution? → Path B (MXC direct). Hyperlight isolates highest-risk generated code in either path.

### How to choose (detailed)

| | Path A: MAF-based | Path B: MXC + runtime backend direct |
|---|---|---|
| **Use when** | Complete agent workflow: planning, tool calls, HITL, CodeAct, recovery, cloud/local routing | Controlled local execution for a Windows-native action — no full agent loop needed |
| **Main loop** | MAF carries reasoning-action loop; Hyperlight isolates generated code when needed | App/model chooses action; MXC declares policy; **ProcessContainer** is the default backend; Hyperlight only for highest-risk generated code |
| **Technologies** | Microsoft Agent Framework, Hyperlight CodeAct, Ollama/Foundry Local, OTel | MXC SDK 0.7, **ProcessContainer** (primary), Hyperlight (optional escalation), JSON policy profiles |
| **Evidence in this repo** | Framework comparison, MAF workflow/HITL, Sandbox API, host tools | MXC --probe, task-scoped policy, capability catalog, ProcessContainer behavior |

The two paths are **not mutually exclusive**. Production can use MAF for agent experience + MXC for policy-governed local actions.

---

## Path A: MAF-Based Full Agent Loop

MAF carries: plan → call tools → generate action → observe → continue → HITL → cloud/local routing → telemetry.

### Live Demo

MAF + Hyperlight host tools on Windows AIPC (screenshot, system info, CSV analysis, WHP isolation):

https://github.com/user-attachments/assets/c2554bf2-da92-4a32-8692-0c576d7af376

<div align="center">
  <img src="images/architecture.png" width="960" alt="Path A Architecture: MAF + Hyperlight call chain">
</div>

### Framework Comparison

| Dimension | LangChain | LangGraph | MAF |
|-----------|-----------|-----------|-----|
| Execution control | LLM decides | Developer graph | Both modes |
| State recovery | None | SQLite checkpoint | Workflow checkpoint |
| HITL | Manual | interrupt() | RequestInfoExecutor |
| Sandbox | None | None | agent-framework-hyperlight |
| Windows/.NET | No | No | Yes |
| Observability | LangSmith | LangSmith | Built-in OTel |
| Cloud hosting | No | No | Foundry Hosted Agents |

### Path A Test Results

| Script | Proves | Status |
|--------|--------|:------:|
| `scenarios/maf_travel_agent.py` | MAF + Ollama tool calling | ✅ |
| `scenarios/maf_workflow_travel.py` | MAF @workflow + HITL | ✅ |
| `scenarios/maf_workflow_demo.py` | MAF durable workflow + checkpoint | ✅ |
| `scenarios/langchain_travel_agent.py` | LangChain ReAct loop | ✅ |
| `scenarios/langgraph_travel_agent.py` | LangGraph StateGraph + SQLite | ✅ |
| `portal/sandbox_api.py` | Hyperlight Sandbox + 4 host tools | ✅ |
| `portal/server.py` | 4-tab comparison portal | ✅ |

### Path A Code: Hyperlight Sandbox + Host Tools

The AIPC Sandbox API registers 4 host tools with `HyperlightCodeActProvider`. The MAF Agent decides what code to write; Hyperlight executes it in a WHP-isolated micro-VM; `call_tool()` bridges back to host callbacks:

```python
# portal/sandbox_api.py — key excerpt
from agent_framework_hyperlight import HyperlightCodeActProvider

def read_csv(filename: str) -> str: ...      # host tool: read CSV from AIPC Desktop
def list_host_files(extension: str) -> str: ... # host tool: list files on AIPC
def host_system_info() -> str: ...              # host tool: hostname, OS, arch
def capture_screenshot() -> str: ...            # host tool: GDI CopyFromScreen

codeact = HyperlightCodeActProvider(
    tools=[read_csv, list_host_files, host_system_info, capture_screenshot],
)
agent = ChatCompletionAgent(
    name="AIPC-CodeAct",
    instructions="Use execute_code for EVERY request. Inside execute_code, call host tools via call_tool().",
    model_client=azure_client,
    code_act_provider=codeact,
)
result = await agent.run(task=user_query)
```

Sandbox code runs inside Hyperlight micro-VM (WASM backend, WHP isolation); `call_tool('read_csv', filename='sales_data.csv')` bridges out to the host process. The sandbox cannot access arbitrary host files — only the 4 registered tools are available.

### Path A Code: Standalone Hyperlight Sandbox

```python
# portal/sandbox_api.py — direct sandbox endpoint
from hyperlight_sandbox import Sandbox

async def sandbox_run(code: str):
    def _execute():
        sandbox = Sandbox(backend="wasm")
        result = sandbox.run_python(code)
        sandbox.close()
        return result
    return await asyncio.to_thread(_execute)  # keep Rust !Send on one thread
```

### CodeAct / Hyperlight Boundaries

- MAF does NOT call MXC today (MXC_MATCH_COUNT=0 in source, 2026-06-20)
- MAF CodeAct backend = Hyperlight (documented connector)
- Hyperlight does NOT manage host callbacks; host tools must be narrow

---

## Hyperlight-Unikraft Stateful Execution (Cross-Turn State Persistence)

Hyperlight supports **stateful multi-turn execution**: as long as the sandbox is not restored to snapshot after each turn, intermediate results (variables, imports, DataFrames) persist across turns within a session. This is critical for AIPC agent scenarios where a CodeAct agent needs to build on prior computation results — both Path A (MAF CodeAct) and Path B (MXC + Hyperlight backend) can benefit from this capability.

We reproduced the product team's [stateful demo](https://github.com/hyperlight-dev/hyperlight-unikraft/blob/proto/stateful-demo/host/src/bin/stateful_demo.rs) on our FY27 test environment. Key code from `stateful_demo.rs`:

```rust
// hyperlight-unikraft/host/src/bin/stateful_demo.rs — key excerpt
let mut rt = pyhl::Runtime::new(&home, &[], None, None, Some(0))?;

let turns = &[
    ("Turn 1: Create variables",
     "x = 42\ny = 'hello from turn 1'\nprint(f'  x = {x}, y = {y!r}')"),
    ("Turn 2: Access previous state + compute",
     "z = x * 2\nprint(f'  z = x * 2 = {z}')\nprint(f'  y from turn 1: {y!r}')"),
    ("Turn 3: Import library, build on prior state",
     "import pandas as pd\ndf = pd.DataFrame({'val': [x, z, x+z]})\nprint(df.to_string(index=False))"),
    ("Turn 4: Use everything from all prior turns",
     "total = df['val'].sum()\nprint(f'  x={x}, z={z}, df_sum={total}')"),
];

for (label, code) in turns {
    let t = rt.run_code_stateful(code)?;  // state persists between calls
}
```

**Actual output from our FY27 test** (Windows 10 Pro build 26200, WHP enabled):

```
Stateful multi-turn execution demo
==================================

[init] runtime created in 62ms

--- Turn 1: Create variables ---
  x = 42, y = 'hello from turn 1'
  [36ms (includes initial restore: 152ms)]

--- Turn 2: Access previous state + compute ---
  z = x * 2 = 84
  y from turn 1: 'hello from turn 1'
  [3ms]

--- Turn 3: Import library, build on prior state ---
 val
  42
  84
 126
  [182ms]

--- Turn 4: Use everything from all prior turns ---
  x=42, z=84, df_sum=252
  All state persisted across 4 turns!
  [11ms]

Session complete — sandbox torn down.
```

**What this proves**: `run_code_stateful()` keeps Python interpreter state alive across 4 turns. Turn 2 reads `x` from Turn 1; Turn 3 imports `pandas` and builds a DataFrame from prior variables; Turn 4 uses `df` from Turn 3. All within a single Hyperlight micro-VM session.

**Boundary**: This stateful execution model is not yet integrated with MXC mainline. Product team has started the integration at [`danbugs/mxc/tree/proto/hyperlight-stateful`](https://github.com/danbugs/mxc/tree/proto/hyperlight-stateful) — no fundamental technical blockers identified, but it is still a prototype branch.

> Source: [`hyperlight-dev/hyperlight-unikraft`](https://github.com/hyperlight-dev/hyperlight-unikraft) branch `proto/stateful-demo`, commit `ced2b301`
> Evidence: `mxc/evidence/fy27_hyperlight_unikraft_stateful_demo_20260629.log`

---

## Path B: MXC + Runtime Backend Direct

MXC is a policy-driven execution layer for controlled Windows-native execution without a full agent loop. The default backend is **ProcessContainer** (lighter, runs most tasks); Hyperlight is an optional escalation for highest-risk generated code only.

### Path B Demo

MXC policy-driven execution: task-scoped capability policy, ProcessContainer backend, Win32 capability catalog probe:

https://github.com/user-attachments/assets/581acf71-510b-489e-b3a4-af24e9977a35

<div align="center">
  <img src="images/slide15-mxc-definition.png" width="960" alt="MXC definition">
</div>

### MXC Demo Inventory

The Path B evidence is not a single toy script. It is a VS Code runnable test harness with policy files and logs checked into `mxc/`.

| Demo | Task | What it proves | Key evidence |
|------|------|----------------|--------------|
| Demo 1 | Probe host | MXC can launch a real Windows command through ProcessContainer/AppContainer fallback | `mxc/evidence/02_mxc_hello_world.log` |
| Demo 2 | No policy / full access | Baseline action can reach the network before policy is applied | `mxc/evidence/01_bare_baseline.log` |
| Demo 3 | Network denied | Same curl action gets `mxc_http:000`, exit 6 under network block | `mxc/evidence/03_network_block.log` |
| Demo 4 | Network approved | Same curl action gets `mxc_http:200`, exit 0 under allow policy | `mxc/evidence/04_network_allow.log` |
| Demo 4b | ProcessContainer policy probe | pip is blocked by filesystem policy setup, while Win32/UI policy can block/allow PowerShell init | `mxc/evidence/pip_policy_probe_summary.txt` |
| Demo 4c | Task-scoped policy | Text profile blocks UI capability; drawing profile allows it | `mxc/evidence/task_rbac_policy_probe_summary.txt` |
| Demo 4d | Capability catalog | Native Win32 API matrix across `Capability-Text-Lockdown`, `Capability-Gdi-Minimal-070`, `Capability-Broad-Ui` | `mxc/evidence/capability_catalog_summary.md` |
| Filesystem | Filesystem policy | `readwritePaths` permits only the declared directory; baseline/readonly/out-of-scope writes fail | `mxc/evidence/fs_policy_*.log` |

Primary runner: `mxc/scripts/Invoke-MXCDemo.ps1`. Policy profiles live in `mxc/policies/`; the native probe source is `mxc/examples/win32_capability_probe.c`.

### MXC 0.7 Probe

`wxc-exec.exe --probe` raw output from `@microsoft/mxc-sdk@0.7.0`:

```json
{
  "tier": "appcontainer-dacl",
  "needsDaclAugmentation": true,
  "warnings": [
    "BaseContainer API not present or not preferred ... falling back to AppContainer + DACL"
  ],
  "probes": {
    "baseContainerApiPresent": true,
    "bfscfgPresent": false,
    "bfsCompiledIn": false,
    "uiCapabilities": {
      "canBlockClipboardRead": true,
      "canBlockClipboardWrite": true,
      "canBlockInputInjection": true,
      "canBlockInputMethodChanges": true,
      "canBlockExternalUiObjects": true,
      "canBlockGlobalUiNamespace": true,
      "canBlockDesktopSwitching": true,
      "canBlockLogoffOrShutdown": true,
      "canBlockSystemParameterChanges": true,
      "canBlockDisplaySettingsChanges": true
    }
  }
}
```

> Full output: `mxc/evidence/mxc_sdk_0_7_probe_raw.txt`

### Task-Scoped Capability Policy

Two MXC 0.7 policy profiles demonstrate task-scoped capability boundaries:

**`processContainer.name = "Task-Text-Lockdown"`** — blocks all UI, clipboard, input, network:

```json
{
  "version": "0.7.0-alpha",
  "containment": "processcontainer",
  "processContainer": {
    "name": "Task-Text-Lockdown",
    "ui": { "isolation": "container", "desktopSystemControl": false, "systemSettings": "none", "ime": false }
  },
  "network": { "defaultPolicy": "block" },
  "ui": { "disable": true, "clipboard": "none", "injection": false }
}
```

**drawing-ui** — allows GDI, clipboard, input, system params:

```json
{
  "version": "0.7.0-alpha",
  "containment": "processcontainer",
  "processContainer": {
    "name": "Task-Drawing-UiAllowed",
    "ui": { "isolation": "desktop", "desktopSystemControl": true, "systemSettings": "all", "ime": true }
  },
  "network": { "defaultPolicy": "block" },
  "ui": { "disable": false, "clipboard": "all", "injection": true }
}
```

A native Win32 probe ([`mxc/examples/win32_capability_probe.c`](mxc/examples/win32_capability_probe.c)) tests 9 Win32 APIs under each profile:

| Profile | Capabilities | Exit | Verdict |
|---------|-------------|:----:|--------|
| Host (no MXC) | N/A | 0 | 7/9 PASS |
| `Task-Text-Lockdown` | No UI | -1073741502 | Process blocked |
| `drawing-ui` | GDI + sysParams + desktop | 0 | Process ran |

**Text task = locked down. Drawing task = GDI allowed.** This is the MXC vocabulary for Lenovo Qira task-scoped local execution.

> Policy files: `mxc/evidence/task-rbac-text-lockdown.json`, `mxc/evidence/task-rbac-drawing-ui.json`
> Probe logs: `mxc/evidence/task_rbac_*.log`

### Path B Code: Win32 Capability Probe (C)

The native probe tests individual Win32 API entrypoints to verify what MXC policy actually blocks:

```c
// mxc/examples/win32_capability_probe.c — key probes
static void probe_get_dc(void) {
    HDC dc = GetDC(NULL);
    report_bool("GDI_GetDC", dc != NULL, GetLastError());
    if (dc) ReleaseDC(NULL, dc);
}

static void probe_clipboard_open(void) {
    BOOL ok = OpenClipboard(NULL);
    report_bool("Clipboard_OpenClipboard", ok, GetLastError());
    if (ok) CloseClipboard();
}

static void probe_create_desktop(void) {
    HDESK desktop = CreateDesktopW(name, NULL, NULL, 0, GENERIC_ALL, NULL);
    report_bool("Desktop_CreateDesktop", desktop != NULL, GetLastError());
    if (desktop) CloseDesktop(desktop);
}
// ... 9 probes total: GDI, Clipboard, Desktop, Display, SystemParams,
//     Input, Registry, Camera DLL, WMI DLL
```

### Path B Code: Network Policy

MXC can block or allow external network access per-action. We tested with `curl https://api.github.com` under two policies:

```json
// mxc/policies/02-network-block.json
{
  "containment": "processcontainer",
  "process": { "commandLine": "curl -s https://api.github.com", "timeout": 15000 },
  "processContainer": { "name": "VSCode-Network-Block" },
  "network": { "defaultPolicy": "block" }
}

// mxc/policies/03-network-allow.json — adds:
  "processContainer": { "capabilities": ["internetClient"] },
  "network": { "defaultPolicy": "allow" }
```

| Policy | curl output | Exit code | Verdict |
|--------|-----------|:---------:|---------|
| `network-block` | `mxc_http:000` (connection failed) | 6 | ✅ Network blocked — same action, can't reach internet |
| `network-allow` | `mxc_http:200` (GitHub API responded) | 0 | ✅ Network allowed — same action, internet reachable |

Same executable, same URL, different policy → different outcome. This is the cleanest MXC network proof.

> Evidence: `mxc/evidence/03_network_block.log`, `mxc/evidence/04_network_allow.log`

### Filesystem Policy

MXC can scope which directories a contained process can read and write via `readwritePaths` and `readonlyPaths`. We tested 4 scenarios writing to `C:\temp\mxc-fs-test\`:

> **Note on pip install**: We also tried `pip install six==1.16.0` under network block/allow, but pip never reached the network layer — it failed earlier on a filesystem setup error (`bfscfg.exe` not available on current tier). This is a filesystem/BFS limitation, not a network result. Do not use pip results as network policy evidence; curl is the correct test.

**Test policies:**

```json
// fs-policy-02-readwrite-allowed.json — allow write to target directory
{
  "version": "0.7.0-alpha",
  "containment": "processcontainer",
  "process": {
    "commandLine": "cmd.exe /c echo MXC_FS_WRITE_ALLOWED > C:\\temp\\mxc-fs-test\\allowed.txt && type C:\\temp\\mxc-fs-test\\allowed.txt",
    "timeout": 15000
  },
  "processContainer": { "name": "FS-ReadWrite-Allowed" },
  "network": { "defaultPolicy": "block" },
  "filesystem": { "readwritePaths": ["C:\\temp\\mxc-fs-test"] }
}
```

**Actual results:**

| Test | Policy | Exit | Verdict |
|------|--------|:----:|---------|
| 01 baseline | No `filesystem` field | 1 | ❌ `Access is denied` — ProcessContainer default blocks write to `C:\temp` |
| 02 readwrite-allowed | `readwritePaths: ["C:\temp\mxc-fs-test"]` | **0** | ✅ **Write succeeded** — `allowed.txt` created with content `MXC_FS_WRITE_ALLOWED` |
| 03 readwrite-blocked | `readwritePaths` points to a different directory | 1 | ❌ Write blocked — target dir not in allow list |
| 04 readonly | `readonlyPaths: ["C:\temp\mxc-fs-test"]` only | 1 | ❌ `Access is denied` — read-only cannot write |

**Key finding**: `readwritePaths` works on the current `appcontainer-dacl` fallback tier for simple file write operations. This means MXC can enforce per-action filesystem scoping today — an agent action that should only write to `%APPDATA%\app-data` gets a policy that allows exactly that directory, and writes elsewhere are blocked.

> The earlier pip install test failed because pip needs complex filesystem redirection (BFS) for `--target` directory management, not simple file writes. Simple `readwritePaths` scoping works without BFS.

> Evidence: `mxc/evidence/fs-policy-*.json` (policies), `mxc/evidence/fs_policy_*.log` (execution logs)

### Capability Catalog (9 Win32 probes × 4 execution contexts)

Test setup:

| Item | Value |
|------|-------|
| MXC SDK | `@microsoft/mxc-sdk@0.7.0` (`wxc-exec.exe`) |
| Runtime backend | **ProcessContainer / AppContainer+DACL fallback**, not Hyperlight |
| MXC tier reported by `--probe` | `appcontainer-dacl` |
| OS / host | Stock Windows 11 test host, not Windows Insider BaseContainer tier |
| Test binary | Native C probe: `mxc/examples/win32_capability_probe.c` |
| Evidence | `mxc/evidence/capability_catalog_summary.md` and `mxc/evidence/capability_catalog_*.log` |

How to read this table:

The columns below are the real `processContainer.name` values from the JSON policies. The effective knobs are `processContainer.ui.*` and top-level `ui.*`.

| `processContainer.name` | Actual policy knobs used |
|--------------------------|--------------------------|
| `Capability-Text-Lockdown` | `ui.disable=true`, `ui.clipboard="none"`, `ui.injection=false`, `processContainer.ui.isolation="container"` |
| `Capability-Gdi-Minimal-070` | `ui.disable=false`, `ui.clipboard="none"`, `ui.injection=false`, `processContainer.ui.isolation="container"` |
| `Capability-Broad-Ui` | `ui.disable=false`, `ui.clipboard="all"`, `ui.injection=true`, `processContainer.ui.isolation="desktop"`, `desktopSystemControl=true`, `systemSettings="all"`, `ime=true` |

| Column | Plain-English meaning |
|--------|-----------------------|
| **No MXC (Host baseline)** | The same probe runs directly on Windows, without MXC. ✅ means the API works normally on the host. ❌ means the API already fails on this Windows environment, so MXC is not the cause. |
| **`Capability-Text-Lockdown`** | The strictest JSON policy in this test. `BLOCKED` means MXC stops the process before any Win32 API can run. |
| **`Capability-Gdi-Minimal-070`** | Minimal UI JSON policy for drawing/rendering-style actions. ✅ means this policy lets the API run. ❌ means the API still fails under this policy/tier. |
| **`Capability-Broad-Ui`** | Broader UI JSON policy. On the current `appcontainer-dacl` fallback tier, it behaves almost the same as `Capability-Gdi-Minimal-070`; it does not unlock clipboard/desktop/display/input/WMI in this test. |

Legend: ✅ = API call succeeded; ❌ = API call failed; `BLOCKED` = MXC blocked process startup before probes ran.

| Capability probe | No MXC<br/>(Host baseline) | `Capability-Text-Lockdown` | `Capability-Gdi-Minimal-070` | `Capability-Broad-Ui` |
|------------------|:-------------------------:|:-------------------:|:----------------:|:------------:|
| GDI_GetDC | ✅ | BLOCKED | ✅ | ✅ |
| Clipboard_OpenClipboard | ✅ | BLOCKED | ❌ | ❌ |
| Desktop_CreateDesktop | ✅ | BLOCKED | ❌ | ❌ |
| Display_ChangeDisplaySettings | ✅ | BLOCKED | ❌ | ❌ |
| SystemParametersInfo | ✅ | BLOCKED | ✅ | ✅ |
| Input_SendInput | ❌ | BLOCKED | ❌ | ❌ |
| Registry_HKCU_Read | ✅ | BLOCKED | ✅ | ✅ |
| CameraStack_Load_MF_DLL | ✅ | BLOCKED | ✅ | ✅ |
| WMI_Load_wbemuuid_DLL | ❌ | BLOCKED | ❌ | ❌ |

Customer-readable takeaway: MXC can choose different local capability envelopes per task. A text task can use `processContainer.name="Task-Text-Lockdown"` or another strict policy and not touch UI at all. A drawing/rendering task can use `processContainer.name="Capability-Gdi-Minimal-070"` to allow GDI and system-parameter access. Clipboard, desktop creation, display changes, input injection, and WMI remain unavailable in this current fallback tier.

Boundary: `CameraStack_Load_MF_DLL` only proves Media Foundation DLL loading, not camera capture permission. Host `Input_SendInput` and `WMI_Load_wbemuuid_DLL` already fail without MXC, so those failures are not MXC-specific.

### Path B Boundaries

- Current tier: `appcontainer-dacl` (fallback)
- MXC = early preview, not production security boundary
- Camera/fan/Android not proven

---

## Running on Azure

| Resource | SKU | Purpose |
|----------|-----|---------|
| Portal VM | Linux D4s_v5, East Asia | FastAPI + nginx |
| AIPC VM | Windows 11, NPU | Hyperlight + Ollama + MAF |
| Azure OpenAI | gpt-5.4 via APIM | Cloud LLM |

## Project Structure

```
├── images/                     # Slides + architecture
├── scenarios/                  # Path A: framework scripts
├── portal/                     # Path A: demo portal + sandbox API
├── aipc/                       # Path A: Windows service config
├── mxc/                        # Path B: MXC test code + evidence
│   ├── scripts/Invoke-MXCDemo.ps1
│   ├── examples/win32_capability_probe.c
│   ├── policies/ (13 JSON profiles)
│   └── evidence/ (30+ logs)
├── .env.example / requirements.txt
└── README.md / README-CN.md
```

## Setup

### Path A

```bash
pip install -r requirements.txt && cp .env.example .env
python portal/server.py       # Portal :8506
python portal/sandbox_api.py  # AIPC :8507
```

### Path B

```powershell
npm install @microsoft/mxc-sdk@0.7.0
.\node_modules\.bin\wxc-exec.exe --probe
powershell -File mxc\scripts\Invoke-MXCDemo.ps1
```

## Tech Stack

| Component | Version |
|-----------|---------|
| Microsoft Agent Framework | 1.8+ |
| MXC SDK | 0.7.0 |
| Hyperlight | 0.3+ |
| LangChain / LangGraph | 0.3+ / 0.4+ |
| Python / FastAPI | 3.12 / 0.115+ |

## Related Repos

- [Hyperlight & MXC Sandbox Landscape](../Hyperlight-MXC-Sandbox-Landscape/)
- [Microsoft Agent Framework Demos](../Microsoft-Agent-Framework/)
