# Single-Variable Capability Matrix
Time: 2026-07-06T14:54:04.282098
MXC SDK: @microsoft/mxc-sdk@0.7.0
Tier: appcontainer-dacl
Probe: NativeWin32CapabilityProbe.exe

Each column changes exactly ONE JSON field from the base policy.

| Capability probe | base-locked | clipboard-all | injection-true | isolation-desktop | desktopSystemControl-true | systemSettings-all | ime-true |
|---|---|---|---|---|---|---|---|
| GDI_GetDC | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Clipboard_OpenClipboard | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Desktop_CreateDesktop | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Display_ChangeDisplaySettings | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SystemParametersInfo | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Input_SendInput | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Registry_HKCU | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| CameraStack_Load_MF_DLL | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| WMI_Load_wbemuuid_DLL | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

## Changed field per column
- base-locked: ui.disable=false, all UI fields locked
- clipboard-all: ONLY ui.clipboard changed to 'all'
- injection-true: ONLY ui.injection changed to true
- isolation-desktop: ONLY processContainer.ui.isolation changed to 'desktop'
- desktopSystemControl-true: ONLY processContainer.ui.desktopSystemControl changed to true
- systemSettings-all: ONLY processContainer.ui.systemSettings changed to 'all'
- ime-true: ONLY processContainer.ui.ime changed to true