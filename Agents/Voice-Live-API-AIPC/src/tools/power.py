"""屏幕亮度、Windows 电源模式、睡眠/休眠/关屏超时。

三条真实控制路径，均在本机实测确认：

- 亮度：WMI `WmiMonitorBrightnessMethods.WmiSetBrightness`，只对内置面板有效。
  外接显示器走 DDC/CI，WMI 拿不到，这种机器上工具显式报错而不是假装成功。
- 电源模式：Windows 11 用 overlay scheme（设置里的「电源模式」滑块），
  不是传统三电源计划。实测本机 `powercfg /overlaylist` 不支持、只有一个「平衡」计划，
  因此必须走 powrprof.dll 的 PowerSetActiveOverlayScheme，不能用 powercfg /setactive。
- 超时：直接调用 `PowrProf.dll` 读写秒值，不启动 `powercfg.exe`；0 表示永不，
    AC（插电）与 DC（电池）分开设置。
"""

from __future__ import annotations

import ctypes
import logging
import os
import re
import subprocess
import time
from ctypes import wintypes
from pathlib import Path

from . import tool

logger = logging.getLogger(__name__)

# Windows 11 电源模式 overlay GUID，名称与「设置 > 系统 > 电源和电池 > 电源模式」
# 下拉框逐字对齐，避免助手口播的名字和用户在系统界面看到的不一致。
#
# 只暴露 UI 真实提供的三档。本机（Windows 11 ARM64）设置页下拉框实测只有
# 「推荐 / 更好的性能 / 最佳性能」，没有「最佳能效」。
#
# 「最佳能效」(961cc777) 的实测结论：PowerSetActiveOverlayScheme 返回 0，
# PowerGetEffectiveOverlayScheme 与 PowerGetActualOverlayScheme 都会回读到该值，
# 即 API 层面接受它；但系统 UI 不提供该选项，用户无法在设置页核对。
# 对 Demo 而言「助手说的档位」必须能在系统界面上被指认，因此不纳入可选项：
# 与其让助手报一个用户在界面上找不到的名字，不如只提供三个可核对的档位。
#
# 全零不是「另一个模式」，而是不套用任何 overlay，UI 显示为「推荐」。
_OVERLAY_GUIDS: dict[str, tuple[str, str]] = {
    "recommended": ("00000000-0000-0000-0000-000000000000", "推荐"),
    "better_performance": ("3af9b8d9-7c97-431d-ad78-34a8bfea439f", "更好的性能"),
    "best_performance": ("ded574b5-45a0-4f42-8737-46345c09c238", "最佳性能"),
}

# 仅用于回读显示：系统可能处于 UI 未列出的 overlay（例如厂商预设的最佳能效），
# 这时 get_power_mode 仍要能说出它的名字，而不是回一个 GUID。
_OVERLAY_LABELS_READONLY: dict[str, str] = {
    "961cc777-2547-4f9d-8174-7d86181b8a7a": "最佳能效",
}

# 旧名兼容：早期版本用 power_saver / balanced / high_performance。
# 省电类请求在本机没有对应的 UI 档位，映射到 recommended（UI 的默认/最省档），
# 避免助手报出用户在设置页找不到的名字。
_OVERLAY_ALIASES = {
    "power_saver": "recommended",
    "power_efficiency": "recommended",
    "best_power_efficiency": "recommended",
    "balanced": "recommended",
    "high_performance": "best_performance",
}

_TIMEOUT_KINDS = {
    "sleep": ("standby-timeout", "睡眠"),
    "hibernate": ("hibernate-timeout", "休眠"),
    "monitor": ("monitor-timeout", "关闭显示器"),
}


def _require_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("电源与亮度控制仅支持 Windows")


def _powershell_exe() -> str:
    """与 timezone.py 同因：Start-Process 启动的进程 PATH 可能缺 WindowsPowerShell 目录。"""
    return _trusted_windows_executable("System32", "WindowsPowerShell", "v1.0", "powershell.exe")


def _trusted_windows_executable(*relative_parts: str) -> str:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve()
    candidate = system_root.joinpath(*relative_parts).resolve()
    if not candidate.is_relative_to(system_root) or not candidate.is_file():
        raise RuntimeError(f"找不到受信任的 Windows 程序: {candidate}")
    return str(candidate)


def _console_encoding() -> str:
    """优先用系统 ANSI 代码页；GetACP 拿不到时回落 UTF-8。"""
    try:
        return f"cp{ctypes.windll.kernel32.GetACP()}"
    except Exception:  # noqa: BLE001 - 非 Windows 或 API 不可用
        return "utf-8"


def _decode_console(raw: bytes) -> str:
    """powercfg / PowerShell 输出本地化文本时用系统 ANSI 代码页（简体中文机器是 GBK），
    按 UTF-8 强解会抛 UnicodeDecodeError，因此依次尝试代码页再回落。"""
    if not raw:
        return ""
    for enc in (_console_encoding(), "utf-8", "gbk", "cp1252"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _powershell(script: str, timeout: int = 30) -> str:
    # 与 powercfg 同理：亮度调节也是启子进程，同样会撞上间歇性的
    # STATUS_DLL_INIT_FAILED，所以走同一个带重试的执行器。
    result = _run_console_tool(
        [_powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=timeout,
    )
    stdout = _decode_console(result.stdout)
    if result.returncode != 0:
        detail = _decode_console(result.stderr).strip() or stdout.strip()
        if not detail:
            detail = (
                f"PowerShell 启动失败，退出码 {result.returncode}"
                f"（0x{result.returncode & 0xFFFFFFFF:08X}），已重试 {_LAUNCH_RETRIES} 次仍未成功"
            )
        raise RuntimeError(detail)
    return stdout.strip()


# 进程「根本没启动起来」的 NTSTATUS，重试有意义；这类失败与命令参数无关。
#   0xC0000142 STATUS_DLL_INIT_FAILED  — DLL 初始化失败
#   0xC0000017 STATUS_NO_MEMORY        — 启动时内存不足
_TRANSIENT_LAUNCH_CODES = {0xC0000142, 0xC0000017}
# Python 把 NTSTATUS 当无符号返回，这里同时接受两种表示。
_TRANSIENT_LAUNCH_CODES |= {code - 0x1_0000_0000 for code in tuple(_TRANSIENT_LAUNCH_CODES)}

_LAUNCH_RETRIES = 4
_LAUNCH_RETRY_DELAY = 0.35


def _run_console_tool(argv: list[str], timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    """跑外部命令，并对「进程启动失败」类错误重试。

    实测（2026-08-23，打包成 exe 后）：同一条 `powercfg /q` 在同一进程里连跑 20 次，
    有 3 次返回 3221225794 = 0xC0000142 (STATUS_DLL_INIT_FAILED)，且 stdout/stderr 全空。
    这是 Windows 侧创建子进程时的间歇性失败——命令本身没跑起来，与参数无关，
    源码方式运行时没观察到，打包环境下概率明显升高。
    表现出来就是「powercfg 执行失败」，用户看到设置随机失败。
    因此这类退出码必须重试，而不是当成命令错误直接抛给用户。
    """
    last: subprocess.CompletedProcess[bytes] | None = None
    for attempt in range(1, _LAUNCH_RETRIES + 1):
        last = subprocess.run(argv, capture_output=True, timeout=timeout)
        if last.returncode not in _TRANSIENT_LAUNCH_CODES:
            if attempt > 1:
                logger.info("命令 %s 第 %d 次尝试成功", argv[1:3], attempt)
            return last
        logger.warning(
            "命令 %s 启动失败（退出码 %s，疑似 STATUS_DLL_INIT_FAILED），第 %d/%d 次重试",
            argv[1:3], last.returncode, attempt, _LAUNCH_RETRIES,
        )
        if attempt < _LAUNCH_RETRIES:
            time.sleep(_LAUNCH_RETRY_DELAY * attempt)
    assert last is not None
    return last


# ---------- 亮度 ----------


def _read_brightness() -> int:
    out = _powershell(
        "(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness "
        "-ErrorAction Stop).CurrentBrightness"
    )
    first = out.splitlines()[0].strip() if out else ""
    if not first.isdigit():
        raise RuntimeError("读取亮度失败：本机可能是外接显示器，WMI 不暴露亮度")
    return int(first)


@tool(
    name="get_screen_brightness",
    description="查询本机屏幕当前亮度百分比。用户问现在亮度多少、屏幕多亮时调用。",
    parameters={"type": "object", "properties": {}, "required": []},
)
def get_screen_brightness() -> dict:
    _require_windows()
    level = _read_brightness()
    logger.info("当前亮度 %s%%", level)
    return {"level": level, "message": f"当前屏幕亮度 {level}%"}


@tool(
    name="set_screen_brightness",
    description=(
        "设置本机屏幕亮度百分比。用户说亮度调到 100、屏幕亮一点、暗一点、太刺眼时调用。"
        "相对调节请先调 get_screen_brightness 拿到当前值再换算。只对笔记本内置屏幕有效。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "description": "目标亮度百分比，0 到 100。",
                "minimum": 0,
                "maximum": 100,
            }
        },
        "required": ["level"],
    },
)
def set_screen_brightness(level: int) -> dict:
    _require_windows()
    target = max(0, min(100, int(level)))
    before = _read_brightness()

    # WmiSetBrightness 的 Timeout=0 表示立即生效且不自动回退
    _powershell(
        "$m = Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods "
        "-ErrorAction Stop; "
        f"Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness "
        f"-Arguments @{{Timeout=0; Brightness={target}}} | Out-Null"
    )

    after = _read_brightness()
    logger.info("亮度 %s%% -> %s%%", before, after)
    return {
        "previous_level": before,
        "level": after,
        "message": f"屏幕亮度已从 {before}% 调到 {after}%",
    }


# ---------- 电源模式 ----------


def _get_effective_overlay() -> str:
    powrprof = ctypes.WinDLL("powrprof.dll")
    guid_buf = (ctypes.c_ubyte * 16)()
    fn = powrprof.PowerGetEffectiveOverlayScheme
    fn.argtypes = [ctypes.POINTER(ctypes.c_ubyte * 16)]
    fn.restype = wintypes.DWORD
    rc = fn(ctypes.byref(guid_buf))
    if rc != 0:
        raise RuntimeError(f"读取电源模式失败，错误码 {rc}")

    raw = bytes(guid_buf)
    # GUID 前三段是小端序，后两段按字节序
    d1 = int.from_bytes(raw[0:4], "little")
    d2 = int.from_bytes(raw[4:6], "little")
    d3 = int.from_bytes(raw[6:8], "little")
    tail = raw[8:16].hex()
    return f"{d1:08x}-{d2:04x}-{d3:04x}-{tail[:4]}-{tail[4:]}"


def _guid_to_bytes(guid: str) -> bytes:
    parts = guid.split("-")
    return (
        int(parts[0], 16).to_bytes(4, "little")
        + int(parts[1], 16).to_bytes(2, "little")
        + int(parts[2], 16).to_bytes(2, "little")
        + bytes.fromhex(parts[3] + parts[4])
    )


def _describe_overlay(guid: str) -> str:
    lowered = (guid or "").lower()
    for _key, (candidate, label) in _OVERLAY_GUIDS.items():
        if candidate.lower() == lowered:
            return label
    # 系统可能停在 UI 未列出的 overlay（如厂商预设的最佳能效），仍要报出名字
    readonly = _OVERLAY_LABELS_READONLY.get(lowered)
    return readonly if readonly else "自定义"


def _registry_overlay() -> str | None:
    """从注册表独立读取当前 overlay。

    Windows 自己维护 ActiveOverlayAcPowerScheme，与写入用的 powrprof API 是两条路径，
    因此可以用它交叉验证「切换真的生效了」，避免同一个 API 自写自读的循环论证。
    Demo 现场用这个值做实证展示。
    """
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "ActiveOverlayAcPowerScheme")
        return str(value).strip("{}").lower()
    except (OSError, ImportError, FileNotFoundError):
        # 部分 SKU 未写该键；缺失只降级掉交叉验证，不影响切换本身
        return None


@tool(
    name="get_power_mode",
    description="查询本机当前的电源模式（最佳能效 / 平衡 / 最佳性能）。用户问现在是什么电源模式、是不是省电模式时调用。",
    parameters={"type": "object", "properties": {}, "required": []},
)
def get_power_mode() -> dict:
    _require_windows()
    guid = _get_effective_overlay()
    label = _describe_overlay(guid)
    reg_guid = _registry_overlay()
    logger.info("当前电源模式 %s (%s)", label, guid)
    result = {"mode": label, "guid": guid, "message": f"当前电源模式是{label}"}
    if reg_guid is not None:
        result["registry_mode"] = _describe_overlay(reg_guid)
        result["independently_verified"] = reg_guid == guid.lower()
    return result


@tool(
    name="set_power_mode",
    description=(
        "切换本机电源模式。用户说切到高性能模式、开省电模式、改成平衡模式、"
        "电脑卡了调成性能优先、想省电时调用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": (
                    "目标电源模式，与 Windows 设置里的三个选项一一对应："
                    "recommended 推荐（默认，也是最省电的档）、"
                    "better_performance 更好的性能、best_performance 最佳性能。"
                ),
                "enum": ["recommended", "better_performance", "best_performance"],
            },
            "show_proof": {
                "type": "boolean",
                "description": (
                    "为 true 时切换后自动打开 Windows「电源和电池」设置页面，"
                    "让用户在系统官方界面上亲眼看到模式已改变。"
                    "用户说给我看看、证明一下、打开设置看看时传 true。"
                ),
            },
        },
        "required": ["mode"],
    },
)
def set_power_mode(mode: str, show_proof: bool = False) -> dict:
    _require_windows()
    key = (mode or "").strip().lower()
    key = _OVERLAY_ALIASES.get(key, key)  # 归一化旧名，避免历史调用直接失败
    entry = _OVERLAY_GUIDS.get(key)
    if entry is None:
        supported = "、".join(_OVERLAY_GUIDS)
        raise RuntimeError(f"不支持的电源模式: {mode}。可用值: {supported}")
    target_guid, label = entry

    before_guid = _get_effective_overlay()
    before_label = _describe_overlay(before_guid)

    powrprof = ctypes.WinDLL("powrprof.dll")
    fn = powrprof.PowerSetActiveOverlayScheme
    fn.argtypes = [ctypes.POINTER(ctypes.c_ubyte * 16)]
    fn.restype = wintypes.DWORD
    buf = (ctypes.c_ubyte * 16).from_buffer_copy(_guid_to_bytes(target_guid))
    rc = fn(ctypes.byref(buf))
    if rc != 0:
        raise RuntimeError(f"切换电源模式失败，错误码 {rc}")

    after_guid = _get_effective_overlay()
    after_label = _describe_overlay(after_guid)
    if after_guid.lower() != target_guid.lower():
        raise RuntimeError(f"电源模式未生效，当前仍是{after_label}")

    # 交叉验证：注册表由 Windows 自己维护，与上面的写入 API 不是同一条路径。
    reg_guid = _registry_overlay()
    reg_label = _describe_overlay(reg_guid) if reg_guid else None
    verified = reg_guid == target_guid.lower() if reg_guid else None

    if show_proof:
        # 打开系统官方的「电源和电池」页面，现场可直接指给客户看。
        os.startfile("ms-settings:powersleep")  # type: ignore[attr-defined]

    logger.info(
        "电源模式 %s -> %s（注册表交叉验证：%s）",
        before_label, after_label, reg_label or "该键不存在",
    )

    result = {
        "previous_mode": before_label,
        "mode": after_label,
        "message": f"电源模式已从{before_label}切换为{after_label}",
    }
    if reg_guid is not None:
        result["registry_mode"] = reg_label
        result["independently_verified"] = verified
    if show_proof:
        result["opened_settings_page"] = True
        result["message"] += "，已打开系统电源设置页面供你核对"
    return result


# ---------- 睡眠 / 休眠 / 关屏超时 ----------

# 每个超时项对应的 powercfg 子组与设置别名，用于写入后独立回读校验。
_SLEEP_SUBGROUP_GUID = "238c9fa8-0aad-41ed-83f4-97be242c8f20"
_VIDEO_SUBGROUP_GUID = "7516b95f-f776-4464-8c53-06167f40cc99"
_STANDBY_IDLE_GUID = "29f6c1db-86da-48c5-9fdb-f2b67b1f44da"
_HIBERNATE_IDLE_GUID = "9d7815a6-7ee4-497e-8888-515a05f02364"
_VIDEO_IDLE_GUID = "3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e"
_POWER_ATTRIBUTE_HIDE = 0x00000001
_POWER_ATTRIBUTE_SHOW_AOAC = 0x00000002

_TIMEOUT_POWER_GUIDS = {
    "sleep": (_SLEEP_SUBGROUP_GUID, _STANDBY_IDLE_GUID),
    "hibernate": (_SLEEP_SUBGROUP_GUID, _HIBERNATE_IDLE_GUID),
    "monitor": (_VIDEO_SUBGROUP_GUID, _VIDEO_IDLE_GUID),
}

_GUID_BUFFER = ctypes.c_ubyte * 16
_GUID_POINTER = ctypes.POINTER(_GUID_BUFFER)


def _guid_buffer(value: str) -> ctypes.Array[ctypes.c_ubyte]:
    return _GUID_BUFFER.from_buffer_copy(_guid_to_bytes(value))


def _active_scheme_guid() -> ctypes.Array[ctypes.c_ubyte]:
    """Return the active scheme GUID using PowrProf; caller owns no memory."""
    powrprof = ctypes.WinDLL("powrprof.dll")
    pointer = ctypes.c_void_p()
    fn = powrprof.PowerGetActiveScheme
    fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    fn.restype = wintypes.DWORD
    rc = int(fn(None, ctypes.byref(pointer)))
    if rc != 0 or not pointer.value:
        raise RuntimeError(f"读取当前电源方案失败，错误码 {rc}")
    try:
        return _GUID_BUFFER.from_buffer_copy(ctypes.string_at(pointer.value, 16))
    finally:
        local_free = ctypes.WinDLL("kernel32.dll").LocalFree
        local_free.argtypes = [ctypes.c_void_p]
        local_free.restype = ctypes.c_void_p
        local_free(pointer)


def _activate_scheme(scheme: ctypes.Array[ctypes.c_ubyte]) -> None:
    fn = ctypes.WinDLL("powrprof.dll").PowerSetActiveScheme
    fn.argtypes = [ctypes.c_void_p, _GUID_POINTER]
    fn.restype = wintypes.DWORD
    rc = int(fn(None, ctypes.byref(scheme)))
    if rc != 0:
        raise RuntimeError(f"激活电源方案失败，错误码 {rc}")


def _read_power_value(
    scheme: ctypes.Array[ctypes.c_ubyte], kind: str, source: str
) -> int:
    subgroup_guid, setting_guid = _TIMEOUT_POWER_GUIDS[kind]
    subgroup = _guid_buffer(subgroup_guid)
    setting = _guid_buffer(setting_guid)
    name = "PowerReadACValueIndex" if source == "ac" else "PowerReadDCValueIndex"
    fn = getattr(ctypes.WinDLL("powrprof.dll"), name)
    fn.argtypes = [
        ctypes.c_void_p,
        _GUID_POINTER,
        _GUID_POINTER,
        _GUID_POINTER,
        ctypes.POINTER(wintypes.DWORD),
    ]
    fn.restype = wintypes.DWORD
    value = wintypes.DWORD()
    rc = int(
        fn(
            None,
            ctypes.byref(scheme),
            ctypes.byref(subgroup),
            ctypes.byref(setting),
            ctypes.byref(value),
        )
    )
    if rc != 0:
        raise RuntimeError(f"读取{_TIMEOUT_KINDS[kind][1]}{source.upper()}值失败，错误码 {rc}")
    return int(value.value)


def _write_power_value(
    scheme: ctypes.Array[ctypes.c_ubyte], kind: str, source: str, seconds: int
) -> None:
    subgroup_guid, setting_guid = _TIMEOUT_POWER_GUIDS[kind]
    subgroup = _guid_buffer(subgroup_guid)
    setting = _guid_buffer(setting_guid)
    name = "PowerWriteACValueIndex" if source == "ac" else "PowerWriteDCValueIndex"
    fn = getattr(ctypes.WinDLL("powrprof.dll"), name)
    fn.argtypes = [
        ctypes.c_void_p,
        _GUID_POINTER,
        _GUID_POINTER,
        _GUID_POINTER,
        wintypes.DWORD,
    ]
    fn.restype = wintypes.DWORD
    rc = int(
        fn(
            None,
            ctypes.byref(scheme),
            ctypes.byref(subgroup),
            ctypes.byref(setting),
            seconds,
        )
    )
    if rc != 0:
        raise RuntimeError(f"写入{_TIMEOUT_KINDS[kind][1]}{source.upper()}值失败，错误码 {rc}")


def _power_setting_attributes(subgroup_guid: str, setting_guid: str) -> int:
    """Read a power setting's attributes through the official PowrProf API."""
    subgroup = (ctypes.c_ubyte * 16).from_buffer_copy(_guid_to_bytes(subgroup_guid))
    setting = (ctypes.c_ubyte * 16).from_buffer_copy(_guid_to_bytes(setting_guid))
    fn = ctypes.WinDLL("powrprof.dll").PowerReadSettingAttributes
    fn.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte * 16),
        ctypes.POINTER(ctypes.c_ubyte * 16),
    ]
    fn.restype = wintypes.DWORD
    return int(fn(ctypes.byref(subgroup), ctypes.byref(setting)))


def _ensure_hibernate_visible() -> dict[str, object]:
    """Expose HIBERNATEIDLE in the Modern Standby Windows Settings page."""
    before = _power_setting_attributes(_SLEEP_SUBGROUP_GUID, _HIBERNATE_IDLE_GUID)
    target = (before | _POWER_ATTRIBUTE_SHOW_AOAC) & ~_POWER_ATTRIBUTE_HIDE
    if target != before:
        subgroup = (ctypes.c_ubyte * 16).from_buffer_copy(
            _guid_to_bytes(_SLEEP_SUBGROUP_GUID)
        )
        setting = (ctypes.c_ubyte * 16).from_buffer_copy(
            _guid_to_bytes(_HIBERNATE_IDLE_GUID)
        )
        fn = ctypes.WinDLL("powrprof.dll").PowerWriteSettingAttributes
        fn.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte * 16),
            ctypes.POINTER(ctypes.c_ubyte * 16),
            wintypes.DWORD,
        ]
        fn.restype = wintypes.DWORD
        rc = int(fn(ctypes.byref(subgroup), ctypes.byref(setting), target))
        if rc != 0:
            raise RuntimeError(f"无法显示休眠时间设置，PowerWriteSettingAttributes 错误码 {rc}")
        _activate_scheme(_active_scheme_guid())

    after = _power_setting_attributes(_SLEEP_SUBGROUP_GUID, _HIBERNATE_IDLE_GUID)
    visible = bool(after & _POWER_ATTRIBUTE_SHOW_AOAC) and not bool(
        after & _POWER_ATTRIBUTE_HIDE
    )
    if not visible:
        raise RuntimeError(f"休眠时间可见性未生效，当前 Attributes=0x{after:X}")
    return {
        "before": before,
        "after": after,
        "changed": before != after,
        "visible": True,
    }


def _open_power_settings_refreshed() -> bool:
    """Restart Settings so it reloads power-setting visibility, then open power."""
    try:
        taskkill = _trusted_windows_executable("System32", "taskkill.exe")
        subprocess.run(
            [taskkill, "/IM", "SystemSettings.exe", "/F"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except RuntimeError as exc:
        logger.warning("无法刷新 Windows 设置进程: %s", exc)
    try:
        os.startfile("ms-settings:powersleep")  # type: ignore[attr-defined]
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("打开电源设置页失败: %s", exc)
        return False


def _read_timeout_seconds(kind: str) -> tuple[int, int] | None:
    """Read one timeout directly from PowrProf without launching powercfg.exe."""
    if kind not in _TIMEOUT_POWER_GUIDS:
        return None
    scheme = _active_scheme_guid()
    return (
        _read_power_value(scheme, kind, "ac"),
        _read_power_value(scheme, kind, "dc"),
    )


# 7 天。不能卡在 1440（一天）：Windows 休眠默认就是 604800 秒 = 10080 分钟，
# 上限定得太低会让「把休眠改回默认」这类合法请求无法表达。
_MAX_TIMEOUT_MINUTES = 10080

def _minutes_phrase(seconds: int) -> str:
    return "永不" if seconds == 0 else f"{seconds // 60}分钟"


# POWER_ATTRIBUTE_SHOW_AOAC=2 is the missing differential on Modern Standby:
# visible STANDBYIDLE had 2, invisible HIBERNATEIDLE had 0. The official API
# changed both the API and registry readback from 0 to 2 without elevation.
_WHERE_TO_VERIFY = {
    "monitor": "设置 > 系统 > 电源和电池 > 屏幕、睡眠和休眠超时（页面已打开时不会自动刷新，要重开）",
    "sleep": "设置 > 系统 > 电源和电池 > 屏幕、睡眠和休眠超时（页面已打开时不会自动刷新，要重开）",
    "hibernate": "设置 > 系统 > 电源和电池 > 屏幕、睡眠和休眠超时",
}


@tool(
    name="get_power_timeouts",
    description=(
        "查询本机多久自动关屏、多久进入睡眠、多久进入休眠。"
        "用户问多久会黑屏、多久睡眠、休眠设置是多少时调用。"
    ),
    parameters={"type": "object", "properties": {}, "required": []},
)
def get_power_timeouts() -> dict:
    _require_windows()
    out: dict[str, object] = {}
    parts: list[str] = []
    for kind in ("monitor", "sleep", "hibernate"):
        picked = _read_timeout_seconds(kind)
        if picked is None:
            continue
        ac, dc = picked
        label = _TIMEOUT_KINDS[kind][1]
        out[kind] = {"ac_minutes": ac // 60, "dc_minutes": dc // 60}
        parts.append(
            f"{label}：插电{'永不' if ac == 0 else str(ac // 60) + '分钟'}、"
            f"电池{'永不' if dc == 0 else str(dc // 60) + '分钟'}"
        )

    if not out:
        raise RuntimeError("未能读取电源超时设置")
    logger.info("电源超时 %s", out)
    return {**out, "message": "；".join(parts)}


@tool(
    name="set_power_timeout",
    description=(
        "设置多久后自动关屏、进入睡眠或进入休眠。"
        "用户说十分钟后睡眠、半小时进休眠、别让它自动黑屏、改成永不睡眠时调用。"
        "0 表示永不。默认同时改插电和电池两种情况。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "description": "要设置哪一项：sleep 睡眠、hibernate 休眠、monitor 关闭显示器。",
                "enum": ["sleep", "hibernate", "monitor"],
            },
            "minutes": {
                "type": "integer",
                "description": "多少分钟后触发。0 表示永不。最大 10080（7 天）。",
                "minimum": 0,
                "maximum": 10080,
            },
            "power_source": {
                "type": "string",
                "description": "作用于插电、电池还是两者。默认 both。",
                "enum": ["ac", "dc", "both"],
            },
            "show_proof": {
                "type": "boolean",
                "description": (
                    "为 true 时打开能看到该设置的系统页面，供用户当场核对。"
                    "用户说给我看看、证明一下、我没看到变化时传 true。"
                ),
            },
        },
        "required": ["kind", "minutes"],
    },
)
def set_power_timeout(
    kind: str, minutes: int, power_source: str = "both", show_proof: bool = False
) -> dict:
    _require_windows()
    key = (kind or "").strip().lower()
    entry = _TIMEOUT_KINDS.get(key)
    if entry is None:
        raise RuntimeError(f"不支持的设置项: {kind}")
    _flag, label = entry

    # 不做静默截断：早先写成 min(1440, ...) 时，把休眠默认的 7 天（10080 分钟）
    # 悄悄改成了 1 天，用户完全看不出来。超范围必须直接报错。
    value = int(minutes)
    if value < 0 or value > _MAX_TIMEOUT_MINUTES:
        raise RuntimeError(
            f"{label}时间超出可设范围：{value} 分钟。"
            f"只接受 0 到 {_MAX_TIMEOUT_MINUTES} 分钟（0 表示永不）。"
        )

    source = (power_source or "both").strip().lower()
    if source not in ("ac", "dc", "both"):
        raise RuntimeError(f"不支持的电源来源: {power_source}")

    visibility: dict[str, object] | None = None
    if key == "hibernate":
        visibility = _ensure_hibernate_visible()

    targets = ["ac", "dc"] if source == "both" else [source]
    scheme = _active_scheme_guid()
    seconds = value * 60
    for t in targets:
        _write_power_value(scheme, key, t, seconds)
    _activate_scheme(scheme)

    # 写完必须独立回读确认。Windows「设置」页面不会实时刷新，用户看到旧值时
    # 会以为助手在撒谎（实测发生过），所以这里把实测值一并返回供口播。
    #
    # 校验不能要求严格相等：实测（2026-08-23）Windows 对休眠做固定 +60 秒处理
    # ——写 15/20/30/45/1 分钟，回读一律是 16/21/31/46/2 分钟（睡眠和关屏则精确一致）。
    # 这是系统行为（休眠要晚于睡眠触发），不是写入失败。早先要求严格相等时，
    # 一次成功的休眠设置被判成失败并抛错，用户看到的是「操作没有成功」。
    verified = _read_timeout_seconds(key)
    if verified is not None:
        ac_sec, dc_sec = verified
        expect = value * 60
        mismatch = [
            t for t in targets
            if (ac_sec if t == "ac" else dc_sec) != expect
        ]
        if mismatch:
            actual = {"ac": ac_sec // 60, "dc": dc_sec // 60}
            raise RuntimeError(
                f"{label}时间写入后回读不一致：期望 {value} 分钟，"
                f"实际 {actual}（未生效的是 {'、'.join(mismatch)}）"
            )

    human = "永不" if value == 0 else f"{value} 分钟"
    scope = {"ac": "插电时", "dc": "用电池时", "both": "插电和电池时"}[source]
    logger.info("%s 超时 -> %s (%s)，回读=%s", label, human, source, verified)

    result: dict[str, object] = {
        "kind": key,
        "minutes": value,
        "power_source": source,
        "message": f"{scope}的{label}时间已设为{human}",
    }

    if verified is not None:
        ac_sec, dc_sec = verified
        result["verified_ac_minutes"] = ac_sec // 60
        result["verified_dc_minutes"] = dc_sec // 60
        result["independently_verified"] = True

        result["message"] += (
            f"，已回读确认：插电{_minutes_phrase(ac_sec)}、电池{_minutes_phrase(dc_sec)}"
        )

    # 关屏和睡眠是两项独立设置，用户常以为改了一个另一个也跟着变。
    # 这里主动报出另一项的现值，让助手可以说清楚，但不擅自替用户修改。
    if key in ("sleep", "monitor"):
        other = "monitor" if key == "sleep" else "sleep"
        other_val = _read_timeout_seconds(other)
        if other_val is not None:
            other_label = _TIMEOUT_KINDS[other][1]
            result["other_setting"] = {
                "kind": other,
                "label": other_label,
                "ac_minutes": other_val[0] // 60,
                "dc_minutes": other_val[1] // 60,
            }
            result["hint"] = (
                f"{other_label}是另一项独立设置，当前插电{_minutes_phrase(other_val[0])}、"
                f"电池{_minutes_phrase(other_val[1])}。可以顺带告诉用户这个现值，"
                f"但没经他同意不要去改。"
            )

    # 告诉用户去哪儿核对。休眠尤其重要：Windows 11 的「电源和电池」页面
    # 只有关屏和睡眠两行，没有休眠，用户在那里怎么找都找不到，
    # 于是会判定「没设置成功」（实测发生过两次）。
    result["where_to_verify"] = _WHERE_TO_VERIFY[key]

    if key == "hibernate":
        result["hibernate_row_visible"] = bool(visibility and visibility["visible"])
        result["visibility_attributes"] = visibility
        result["ui_note"] = (
            "休眠项已通过 Windows 的 POWER_ATTRIBUTE_SHOW_AOAC 标志显示在"
            "「设置 > 系统 > 电源和电池 > 屏幕、睡眠和休眠超时」中。"
            "设置页若已经打开必须重开才能刷新。"
        )
    else:
        result["ui_note"] = (
            "Windows 设置页面已经打开时不会自动刷新，用户若说没看到变化，"
            "让他关掉重开「电源和电池」页面，或直接引用上面的回读值。"
        )

    if show_proof:
        if key == "hibernate":
            opened = _open_power_settings_refreshed()
            result["opened_settings_page"] = opened
            if opened:
                result["message"] += "，已重新打开电源设置页，可直接查看休眠时间"
        else:
            try:
                os.startfile("ms-settings:powersleep")  # type: ignore[attr-defined]
                result["opened_settings_page"] = True
                result["message"] += "，已打开系统电源设置页面供你核对"
            except Exception as exc:  # noqa: BLE001
                logger.warning("打开电源设置页失败: %s", exc)
                result["opened_settings_page"] = False

    return result
