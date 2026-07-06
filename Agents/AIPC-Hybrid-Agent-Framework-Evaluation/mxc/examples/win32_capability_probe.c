#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

static void report_bool(const char* name, BOOL ok, DWORD detail) {
    printf("PROBE %s %s detail=%lu\n", name, ok ? "PASS" : "FAIL", (unsigned long)detail);
}

static void probe_get_dc(void) {
    SetLastError(0);
    HDC dc = GetDC(NULL);
    DWORD err = GetLastError();
    if (dc) {
        ReleaseDC(NULL, dc);
    }
    report_bool("GDI_GetDC", dc != NULL, err);
}

static void probe_clipboard_open(void) {
    SetLastError(0);
    BOOL ok = OpenClipboard(NULL);
    DWORD err = GetLastError();
    if (ok) {
        CloseClipboard();
    }
    report_bool("Clipboard_OpenClipboard", ok, err);
}

static void probe_create_desktop(void) {
    WCHAR name[80];
    wsprintfW(name, L"MXCProbe_%lu", GetTickCount());
    SetLastError(0);
    HDESK desktop = CreateDesktopW(name, NULL, NULL, 0, GENERIC_ALL, NULL);
    DWORD err = GetLastError();
    if (desktop) {
        CloseDesktop(desktop);
    }
    report_bool("Desktop_CreateDesktop", desktop != NULL, err);
}

static void probe_system_parameters_read(void) {
    BOOL beep = FALSE;
    SetLastError(0);
    BOOL ok = SystemParametersInfoW(SPI_GETBEEP, 0, &beep, 0);
    DWORD err = GetLastError();
    printf("PROBE SystemParametersInfo_GETBEEP %s value=%d detail=%lu\n", ok ? "PASS" : "FAIL", beep ? 1 : 0, (unsigned long)err);
}

static void probe_change_display_test(void) {
    SetLastError(0);
    LONG rc = ChangeDisplaySettingsW(NULL, CDS_TEST);
    DWORD err = GetLastError();
    printf("PROBE Display_ChangeDisplaySettings_CDS_TEST %s return=%ld detail=%lu\n", rc == DISP_CHANGE_SUCCESSFUL ? "PASS" : "FAIL", rc, (unsigned long)err);
}

static void probe_send_input_zero(void) {
    SetLastError(0);
    UINT sent = SendInput(0, NULL, sizeof(INPUT));
    DWORD err = GetLastError();
    // This is a no-op safety probe. Success means the API entrypoint is callable; no input is injected.
    printf("PROBE Input_SendInput_Zero %s sent=%u detail=%lu\n", (sent == 0 && err == 0) ? "PASS" : "FAIL", sent, (unsigned long)err);
}

static void probe_registry_read(void) {
    HKEY key = NULL;
    SetLastError(0);
    LSTATUS rc = RegOpenKeyExW(HKEY_CURRENT_USER, L"Software", 0, KEY_READ, &key);
    DWORD err = (DWORD)rc;
    if (key) {
        RegCloseKey(key);
    }
    report_bool("Registry_HKCU_Software_Read", rc == ERROR_SUCCESS, err);
}

static void probe_load_camera_dll(void) {
    SetLastError(0);
    HMODULE mod = LoadLibraryW(L"mf.dll");
    DWORD err = GetLastError();
    if (mod) {
        FreeLibrary(mod);
    }
    report_bool("CameraStack_Load_MF_DLL", mod != NULL, err);
}

static void probe_load_wmi_dll(void) {
    SetLastError(0);
    HMODULE mod = LoadLibraryW(L"wbemuuid.dll");
    DWORD err = GetLastError();
    if (mod) {
        FreeLibrary(mod);
    }
    report_bool("WMI_Load_wbemuuid_DLL", mod != NULL, err);
}

int main(void) {
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    printf("PROBE_START NativeWin32CapabilityProbe\n");
    printf("PID=%lu\n", (unsigned long)GetCurrentProcessId());
    probe_get_dc();
    probe_clipboard_open();
    probe_create_desktop();
    probe_system_parameters_read();
    probe_change_display_test();
    probe_send_input_zero();
    probe_registry_read();
    probe_load_camera_dll();
    probe_load_wmi_dll();
    printf("PROBE_DONE NativeWin32CapabilityProbe\n");
    fflush(stdout);
    return 0;
}
