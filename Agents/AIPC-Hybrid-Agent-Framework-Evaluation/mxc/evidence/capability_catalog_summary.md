# MXC Capability Catalog Probe

Time: 2026-07-05T18:42:04.0083822+08:00
Probe: G:\AI-Super-Agent\Lenovo-Open source agent AI framework discussion\mxc-copilot-demo\vscode-workspace-demo\workspace-output\native-win32-probe\NativeWin32CapabilityProbe.exe
Host log: G:\AI-Super-Agent\Lenovo-Open source agent AI framework discussion\mxc-copilot-demo\vscode-workspace-demo\evidence\capability_catalog_00_host_baseline.log (exit=0)

| Capability probe | Host baseline | text-lockdown | gdi-minimal | broad-ui |
|---|---|---|---|---|
| CameraStack_Load_MF_DLL | PASS | PROCESS_BLOCKED(-1073741502) | PASS | PASS |
| Clipboard_OpenClipboard | PASS | PROCESS_BLOCKED(-1073741502) | FAIL | FAIL |
| Desktop_CreateDesktop | PASS | PROCESS_BLOCKED(-1073741502) | FAIL | FAIL |
| Display_ChangeDisplaySettings_CDS_TEST | PASS | PROCESS_BLOCKED(-1073741502) | FAIL | FAIL |
| GDI_GetDC | PASS | PROCESS_BLOCKED(-1073741502) | PASS | PASS |
| Input_SendInput_Zero | FAIL | PROCESS_BLOCKED(-1073741502) | FAIL | FAIL |
| Registry_HKCU_Software_Read | PASS | PROCESS_BLOCKED(-1073741502) | PASS | PASS |
| SystemParametersInfo_GETBEEP | PASS | PROCESS_BLOCKED(-1073741502) | PASS | PASS |
| WMI_Load_wbemuuid_DLL | FAIL | PROCESS_BLOCKED(-1073741502) | FAIL | FAIL |

## Logs
- text-lockdown: G:\AI-Super-Agent\Lenovo-Open source agent AI framework discussion\mxc-copilot-demo\vscode-workspace-demo\evidence\capability_catalog_text-lockdown.log (exit=-1073741502)
- gdi-minimal: G:\AI-Super-Agent\Lenovo-Open source agent AI framework discussion\mxc-copilot-demo\vscode-workspace-demo\evidence\capability_catalog_gdi-minimal.log (exit=0)
- broad-ui: G:\AI-Super-Agent\Lenovo-Open source agent AI framework discussion\mxc-copilot-demo\vscode-workspace-demo\evidence\capability_catalog_broad-ui.log (exit=0)
