"""桌面设备控制：系统音量与常用应用启动。

音量走 pycaw 的 IAudioEndpointVolume（Core Audio API），比模拟音量键可靠：
能读到精确百分比，也不受焦点窗口影响。工具经 asyncio.to_thread 在线程池执行，
每次调用都要自己初始化 COM 套间。
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import tool

logger = logging.getLogger(__name__)


class _CoInit:
    """pycaw 依赖 COM，线程池线程默认没有套间。"""

    def __enter__(self) -> None:
        from comtypes import CoInitialize

        CoInitialize()

    def __exit__(self, *_exc: Any) -> None:
        from comtypes import CoUninitialize

        CoUninitialize()


def _require_windows() -> None:
    if not sys.platform.startswith("win"):
        raise RuntimeError("音量与桌面控制仅支持 Windows")


def _endpoint_volume():
    _require_windows()
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    # 新版 pycaw 直接暴露 EndpointVolume，旧版需要自己 Activate
    endpoint = getattr(devices, "EndpointVolume", None)
    if endpoint is not None:
        return endpoint
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def _read_state() -> dict:
    ev = _endpoint_volume()
    scalar = float(ev.GetMasterVolumeLevelScalar())
    return {
        "level": int(round(max(0.0, min(1.0, scalar)) * 100)),
        "muted": bool(ev.GetMute()),
    }


@tool(
    name="get_system_volume",
    description="Get the current system volume percentage and mute state.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def get_system_volume() -> dict:
    with _CoInit():
        state = _read_state()
    logger.info("当前音量 %s%% muted=%s", state["level"], state["muted"])
    return {"message": f"当前音量 {state['level']}%", **state}


@tool(
    name="set_system_volume",
    description=(
        "Set the system volume percentage. For a relative change, get the current volume first "
        "and convert the request to an absolute target percentage."
    ),
    parameters={
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "description": "Target volume percentage from 0 to 100.",
                "minimum": 0,
                "maximum": 100,
            }
        },
        "required": ["level"],
    },
)
def set_system_volume(level: int) -> dict:
    with _CoInit():
        ev = _endpoint_volume()
        before = _read_state()
        clamped = max(0, min(100, int(level)))
        ev.SetMasterVolumeLevelScalar(clamped / 100.0, None)
        after = _read_state()
    logger.info("音量 %s%% -> %s%%", before["level"], after["level"])
    return {
        "message": f"音量已调到 {after['level']}%",
        "previous_level": before["level"],
        **after,
    }


@tool(
    name="set_system_mute",
    description="Mute or unmute the system audio.",
    parameters={
        "type": "object",
        "properties": {
            "muted": {"type": "boolean", "description": "Use true to mute and false to unmute."}
        },
        "required": ["muted"],
    },
)
def set_system_mute(muted: bool) -> dict:
    with _CoInit():
        ev = _endpoint_volume()
        ev.SetMute(bool(muted), None)
        state = _read_state()
    logger.info("静音状态 -> %s", state["muted"])
    return {"message": "已静音" if state["muted"] else "已取消静音", **state}


_APPS: dict[str, tuple[Path, str]] = {
    "calculator": (Path("System32", "calc.exe"), "计算器"),
    "notepad": (Path("System32", "notepad.exe"), "记事本"),
    "explorer": (Path("explorer.exe"), "文件资源管理器"),
    "taskmgr": (Path("System32", "taskmgr.exe"), "任务管理器"),
    "mspaint": (Path("System32", "mspaint.exe"), "画图"),
}


def _resolve_system_executable(relative_path: Path) -> Path:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve()
    candidate = (system_root / relative_path).resolve()
    if not candidate.is_relative_to(system_root) or not candidate.is_file():
        raise FileNotFoundError(f"Windows 系统程序不存在: {candidate}")
    return candidate


@tool(
    name="open_windows_app",
    description=(
        "Open an allowlisted built-in Windows application or show the desktop. Supported targets "
        "are Calculator, Notepad, File Explorer, Task Manager, Paint, Settings, and Show desktop."
    ),
    parameters={
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": "Allowlisted application or desktop action to open.",
                "enum": ["calculator", "notepad", "explorer", "taskmgr",
                         "mspaint", "settings", "show_desktop"],
            }
        },
        "required": ["app"],
    },
)
def open_windows_app(app: str) -> dict:
    _require_windows()
    key = (app or "").strip().lower()

    if key == "settings":
        os.startfile("ms-settings:")  # type: ignore[attr-defined]
        logger.info("已打开 Windows 设置")
        return {"message": "已打开 Windows 设置", "app": "settings"}

    if key == "show_desktop":
        import ctypes

        user32 = ctypes.windll.user32
        vk_lwin, vk_d, key_up = 0x5B, 0x44, 0x0002
        user32.keybd_event(vk_lwin, 0, 0, 0)
        user32.keybd_event(vk_d, 0, 0, 0)
        user32.keybd_event(vk_d, 0, key_up, 0)
        user32.keybd_event(vk_lwin, 0, key_up, 0)
        logger.info("已显示桌面")
        return {"message": "已显示桌面", "app": "show_desktop"}

    entry = _APPS.get(key)
    if entry is None:
        raise RuntimeError(f"不支持的程序: {app}")

    relative_path, label = entry
    resolved = _resolve_system_executable(relative_path)
    subprocess.Popen([str(resolved)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logger.info("已打开 %s", label)
    return {"message": f"已打开{label}", "app": key}
