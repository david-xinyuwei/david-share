"""Code-enforced confirmation for high-impact local and external side effects."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

_CONFIRMATION_TTL_SECONDS = 120.0
_PROTECTED_ACTIONS = {
    "send_email": "send the email",
    "open_camera": "open the camera",
    "identify_object_with_camera": "capture and analyze the current camera frame",
    "set_system_timezone": "change the Windows timezone",
    "set_power_mode": "change the Windows power mode",
    "set_power_timeout": "change display, sleep, or hibernate timeouts",
    "set_desktop_wallpaper": "change the Windows wallpaper",
    "generate_wallpaper_image": "generate a billable image",
}
_AFFIRMATIVE_RE = re.compile(
    r"^(?:确认|我确认|同意|可以|继续|执行|发送|发吧|打开|开吧|修改|改吧|换吧|"
    r"yes|confirm|confirmed|proceed|go ahead|send it)$",
    re.IGNORECASE,
)
_NEGATIVE_RE = re.compile(r"(?:不|别|取消|停止|no|cancel|stop)", re.IGNORECASE)


@dataclass(frozen=True)
class PendingConfirmation:
    token: str
    tool_name: str
    argument_digest: str
    issued_turn: int
    expires_at: float


_lock = threading.Lock()
_turn_id = 0
_latest_transcript = ""
_pending: dict[str, PendingConfirmation] = {}


def is_protected(tool_name: str) -> bool:
    return tool_name in _PROTECTED_ACTIONS


def note_user_turn(transcript: str | None) -> None:
    """Record a completed user transcript as a new authorization turn."""
    global _turn_id, _latest_transcript
    text = (transcript or "").strip()
    with _lock:
        _turn_id += 1
        _latest_transcript = text
        _purge_expired(time.monotonic())


def augment_parameters(tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Expose the optional one-time token only on protected tool schemas."""
    result = copy.deepcopy(parameters)
    if not is_protected(tool_name):
        return result
    properties = result.setdefault("properties", {})
    properties["confirmation_token"] = {
        "type": "string",
        "description": (
            "One-time token returned by an earlier confirmation_required result. "
            "Use only after the user gives a new explicit confirmation, and repeat all "
            "original arguments unchanged."
        ),
    }
    return result


def authorize(
    tool_name: str, arguments: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return executable arguments or a fail-closed confirmation response."""
    if not is_protected(tool_name):
        return arguments, None

    executable = dict(arguments)
    supplied_token = str(executable.pop("confirmation_token", "") or "")
    digest = _argument_digest(executable)
    now = time.monotonic()

    with _lock:
        _purge_expired(now)
        if supplied_token:
            pending = _pending.get(supplied_token)
            if pending is None:
                return None, _denied("Confirmation token is invalid or expired.")
            if pending.tool_name != tool_name or pending.argument_digest != digest:
                return None, _denied(
                    "Action arguments changed after confirmation was requested. Start again."
                )
            if _turn_id <= pending.issued_turn:
                return None, _confirmation_response(
                    pending,
                    "Wait for a new user utterance that explicitly confirms or cancels the action.",
                )
            if _NEGATIVE_RE.search(_latest_transcript) or not _AFFIRMATIVE_RE.fullmatch(
                _latest_transcript.strip()
            ):
                _pending.pop(supplied_token, None)
                return None, _denied("The latest user utterance was not an explicit confirmation.")
            _pending.pop(supplied_token, None)
            return executable, None

        for pending in _pending.values():
            if pending.tool_name == tool_name and pending.argument_digest == digest:
                return None, _confirmation_response(
                    pending,
                    "Ask the user to explicitly confirm this action in a new turn.",
                )
            return None, _denied(
                "Another protected action is awaiting confirmation. Resolve or cancel it first."
            )

        token = secrets.token_urlsafe(18)
        pending = PendingConfirmation(
            token=token,
            tool_name=tool_name,
            argument_digest=digest,
            issued_turn=_turn_id,
            expires_at=now + _CONFIRMATION_TTL_SECONDS,
        )
        _pending[token] = pending
        return None, _confirmation_response(
            pending,
            "Ask the user to explicitly confirm this action in a new turn.",
        )


def reset_for_tests() -> None:
    global _turn_id, _latest_transcript
    with _lock:
        _turn_id = 0
        _latest_transcript = ""
        _pending.clear()


def _argument_digest(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _purge_expired(now: float) -> None:
    expired = [token for token, item in _pending.items() if item.expires_at <= now]
    for token in expired:
        _pending.pop(token, None)


def _confirmation_response(pending: PendingConfirmation, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "confirmation_required": True,
        "confirmation_token": pending.token,
        "action": pending.tool_name,
        "action_summary": _PROTECTED_ACTIONS[pending.tool_name],
        "expires_in_seconds": int(max(0.0, pending.expires_at - time.monotonic())),
        "message": message,
    }


def _denied(message: str) -> dict[str, Any]:
    return {"ok": False, "confirmation_required": False, "error": message}
