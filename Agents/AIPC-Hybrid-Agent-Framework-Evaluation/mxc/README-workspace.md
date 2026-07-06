# MXC VS Code Workspace Demo

This folder is a recording-friendly MXC demo workspace. Open **this folder** in VS Code, then run the predefined tasks from **Terminal -> Run Task...**.

The goal is to show a real local project directory with code, policy files, and repeatable evidence:

- Bare Windows command can access network and write files.
- MXC launches commands inside a Windows processcontainer/AppContainer fallback.
- MXC network policy can block and allow outbound access.
- MXC ProcessContainer policy can block Win32/UI-dependent actions by default and allow them when UI access is explicitly enabled.
- Filesystem policy is included as a concrete policy probe; on this host it shows the current limitation (`bfscfg.exe` missing), which explains why the full Build shield demo needs newer Windows filesystem-policy components.

## How To Run

### Recommended Sales Recording Mode

Run the tasks in this exact order from **Terminal -> Run Task...**:

| Task | What the audience sees |
|------|------------------------|
| `MXC Demo 1: Probe host` | MXC is present and can launch a real Windows command inside processcontainer. |
| `MXC Demo 2: No policy (full access)` | A local agent action reaches `http://www.microsoft.com` (`HTTP 200`). |
| `MXC Demo 3: Block policy (network denied)` | The exact same action ID is blocked under MXC policy (`HTTP 000`). |
| `MXC Demo 4: Allow policy (network approved)` | The exact same action ID succeeds again after policy approval (`HTTP 200`). |
| `MXC Demo 4b: ProcessContainer policy probe` | A pip install attempt records the current host limitation; a Win32/UI PowerShell action is blocked under default UI lockdown and succeeds when UI is explicitly enabled. |
| `MXC Demo 4c: Task-scoped RBAC probe` | Simulates two task profiles: a text task blocks Win32/UI capability, while a drawing task allows the same UI-dependent action. |
| `MXC Demo 4d: Capability catalog probe` | Runs native Win32 probes across `text-lockdown`, `gdi-minimal`, and `broad-ui` profiles to show which concrete capabilities are affected. |
| `MXC Demo 5: Coding assistant (Hyperlight)` | The runner sends the visible problem prompt to SOP-5 APIM GPT-5.4, writes the returned Python into a temporary artifact, and runs that artifact in Hyperlight; processcontainer fails and leaks host identity metadata. |
| `MXC Demo 6: Hyperlight network policy` | Hyperlight network behavior follows the current policy (`allow` or `block`). |
| `MXC Demo 7: Hyperlight lifecycle (long run)` | A long Hyperlight action stays visible in Windows as `wxc-exec.exe`, then the demo manually cleans it up. |

For one-click rehearsal, run `MXC Demo: Run all (1-7)`. For recording, use `MXC Demo: Run all paused (1-7)`.

When you run `MXC Demo 5: Coding assistant (Hyperlight)`, the integrated terminal prompts for the coding request. You can press Enter to use the default prompt, or type your own prompt. The exact prompt is printed as `Problem prompt sent to model` before the APIM call.

Demo 2/3/4 show `action id -> <same hash>` so the audience can see this is the same action under different policies, not three different commands.

Demo 4b is the current ProcessContainer policy proof for the Lenovo Qira question. It records two things:

1. A `pip install --target ... six==1.16.0` attempt is inconclusive on this host because filesystem policy setup fails before pip can run (`bfscfg.exe` is missing for the required filesystem grant). Do not use this as proof that pip is blocked by network policy.
2. A Win32/UI-sensitive action proves policy enforcement: the same `powershell.exe -NoProfile -Command "Write-Output MXC_PS_OK"` action fails under default UI lockdown with `STATUS_DLL_INIT_FAILED (0xC0000142)` / Win32k blocked, and succeeds when the MXC policy sets `ui.disable=false`.

Demo 4c is the task-scoped policy version of that proof. It treats `text` and `drawing` as two task profiles selected by an upper-layer RBAC/ABAC decision:

- `text` profile: UI/Win32k is locked down, so the UI-dependent PowerShell action is blocked.
- `drawing` profile: UI/Win32k is allowed, so the same action runs.

This proves MXC can act as the local enforcement layer for task-scoped capability policies. It does not prove MXC itself is a full RBAC system; identity and task authorization still live above MXC.

Demo 4d is the capability catalog version. It uses a native Win32 probe and shows that `gdi-minimal` / `broad-ui` allow some surfaces (`GDI_GetDC`, `SystemParametersInfo_GETBEEP`, registry read, Media Foundation DLL load) while others still fail in this host/path (`OpenClipboard`, `CreateDesktop`, display setting test, input injection no-op, WMI DLL load). Treat this as a concrete capability matrix, not a blanket claim that all Win32/device APIs are controllable.

Demo 5 is the most direct Hyperlight-vs-processcontainer proof. It now has two proof points:

1. Hyperlight runs the Python artifact returned by SOP-5 APIM GPT-5.4 for the visible problem prompt, against a real CSV, without depending on host Python.
2. Hyperlight hides host identity metadata that processcontainer can still see.

```text
processcontainer (cmd.exe probe)
   USERPROFILE    = C:\Users\<host-user>
   COMPUTERNAME   = <device-name>
   verdict: HOST IDENTITY LEAKED

Hyperlight (Python probe)
   C:\Users       = BLOCKED:FileNotFoundError
   USERNAME       = NOT_FOUND
   winreg         = NOT_AVAILABLE
   sys.platform   = linux
   verdict: HOST IDENTITY INVISIBLE
```

This is the clearest talk track:

> MXC does not make the agent smarter. MXC makes the agent action controllable. Same action, different policy, different outcome.

In the network demos, the policy file does **not** contain the curl command. The task runner passes the action at runtime with `wxc-exec policy.json -- <command>`. This makes the separation clear:

- `policies/sales-network-block.json` and `policies/sales-network-allow.json` define the execution boundary.
- `ACTION_COMMAND` in the terminal shows the action being run under that boundary.

Optional technical tasks are kept under `Technical:*` for deep-dive questions after the main recording.

This is the strongest Hyperlight-specific line for the recording:

> processcontainer is good for normal Windows CLI/tool actions. Hyperlight is for high-risk generated code artifacts. MXC can run that code in a Hyperlight guest and keep guest network access locked down by default.

If the audience asks why both backend types matter, run:

| Task | What it shows |
|------|---------------|
| `MXC Demo 5: Coding assistant (Hyperlight)` | Same generated code path, plus side-by-side host identity visibility: processcontainer leaks host metadata; Hyperlight does not. |

Use this talk track:

> processcontainer is the fast, lightweight Windows backend for normal CLI/tool actions. Hyperlight is the micro-VM backend for higher-risk generated code. MXC is the common execution layer that selects and configures either backend.

For the strongest “why Hyperlight?” story:

> Some workloads are not just Windows commands with restrictions. A Linux guest-specific workload requiring `sys.platform == linux` cannot be satisfied by a Windows processcontainer. Hyperlight supplies the guest runtime, so the same workload succeeds there.

### Current Task Set

Use **Terminal -> Run Task...** and run the current `MXC Demo 1-7` tasks. All tasks are configured to reveal and focus the terminal automatically.

| Task | Evidence to look for |
|------|----------------------|
| `MXC Demo 1: Probe host` | `processcontainer cmd.exe -> PASS` |
| `MXC Demo 2: No policy (full access)` | `Policy file: none` and `HTTP 200` |
| `MXC Demo 3: Block policy (network denied)` | `policies/sales-network-block.json` and `OUTBOUND NETWORK BLOCKED` |
| `MXC Demo 4: Allow policy (network approved)` | `policies/sales-network-allow.json` and `OUTBOUND NETWORK ALLOWED` |
| `MXC Demo 4b: ProcessContainer policy probe` | `win32_ui_01_default_lockdown.log` shows Win32k/UI blocked; `win32_ui_02_allow_windows.log` shows the same action succeeds. |
| `MXC Demo 4c: Task-scoped RBAC probe` | `task_rbac_policy_probe_summary.txt` shows `text profile -> blocked=True`, `draw profile -> allowed=True`, and `capability delta -> True`. |
| `MXC Demo 4d: Capability catalog probe` | `capability_catalog_summary.md` gives the per-capability matrix across `text-lockdown`, `gdi-minimal`, and `broad-ui`. |
| `MXC Demo 5: Coding assistant (Hyperlight)` | `Problem prompt sent to model`, `Model-generated code artifact`, `APIM response id`, `HOST IDENTITY LEAKED`, and `HOST IDENTITY INVISIBLE` |
| `MXC Demo 6: Hyperlight network policy` | `policies/06-hyperlight-network-policy.json` and the dynamic network verdict |
| `MXC Demo 7: Hyperlight lifecycle (long run)` | `requested lifetime -> 120000s` and `cleanup action` |

## Current Talk Track

Use this wording for the recording:

> MXC is a local execution policy layer for agent actions. Demo 2/3/4 prove the same curl action changes behavior only when the MXC network policy changes. Demo 4b proves a ProcessContainer UI/Win32k policy changes whether a Win32/UI-dependent action can initialize. Demo 5 shows why Hyperlight matters for generated code artifacts returned by the model: processcontainer exposes host identity metadata, while Hyperlight hides it. Demo 6 shows Hyperlight network access is controlled by MXC policy. Demo 7 shows a long-running Hyperlight-backed action is visible as `wxc-exec.exe` while alive and can be cleaned up after observation.

## Files

| Path | Purpose |
|------|---------|
| `.vscode/tasks.json` | VS Code task definitions for MXC Demo 1-7. |
| `scripts/Invoke-MXCDemo.ps1` | Main task runner. |
| `policies/sales-network-block.json` | Processcontainer network block policy. |
| `policies/sales-network-allow.json` | Processcontainer network allow policy. |
| `policies/06-hyperlight-network-policy.json` | Hyperlight network policy used by Demo 6. |
| `policies/07-hyperlight-lifecycle.json` | Long-running Hyperlight lifecycle policy used by Demo 7. |
| `coding-scenario/data/product_inventory_q2.csv` | Demo 5 input data. |
| `workspace-output/generated-code/latest_generated_from_prompt.py` | Temporary file created from the SOP-5 APIM response during Demo 5, then deleted after execution. |
| `evidence/` | Generated logs and verification outputs. |

## Production Readiness Gate

Before recording, run `MXC Demo: Run all (1-7)` and the repo-specific production readiness checklist from `/memories/repo/mxc-demo-prt-checklist.md`.
