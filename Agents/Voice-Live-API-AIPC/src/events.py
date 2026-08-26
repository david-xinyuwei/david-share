"""进程内事件总线，让 GUI 能拿到语音会话的实时状态。

控制台模式下没有订阅者，emit 退化为 print，行为与原来一致。
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Literal

EventKind = Literal["status", "user", "assistant", "tool", "tool_start", "tool_done", "error"]
Listener = Callable[[str, str, dict[str, Any]], None]

_listeners: list[Listener] = []
_lock = threading.Lock()


def subscribe(listener: Listener) -> None:
    with _lock:
        _listeners.append(listener)


def emit(kind: EventKind, text: str, meta: dict[str, Any] | None = None) -> None:
    with _lock:
        listeners = list(_listeners)

    if not listeners:
        try:
            print(text, flush=True)
        except (OSError, ValueError, UnicodeError, AttributeError):
            pass  # windowed 进程可能没有可用 stdout
        return

    for listener in listeners:
        try:
            listener(kind, text, meta or {})
        except Exception:  # UI 异常不能影响语音链路
            pass
