"""Microsoft Graph 邮件发送。

Outlook.com / Exchange Online 的 SMTP Basic Auth 已于 2026-04-30 退役，
个人 Microsoft 账号只能走 OAuth，因此发信统一用 Graph /me/sendMail。
首次使用需要设备码授权一次，之后靠本地 token cache 静默续期。
"""

from __future__ import annotations

import csv
import ctypes
import json
import locale
import logging
import os
import re
import subprocess
import tempfile
from ctypes import wintypes
from pathlib import Path
import stat

import httpx
import msal

from . import config

logger = logging.getLogger(__name__)

_AUTHORITY = "https://login.microsoftonline.com/consumers"
_SCOPES = ["Mail.Send"]
_SENDMAIL_URL = "https://graph.microsoft.com/v1.0/me/sendMail"
_CACHE_NAME = ".msal_token_cache.json"
_CACHE_PATH = config.PROJECT_ROOT / _CACHE_NAME


class GraphAuthRequired(RuntimeError):
    """尚未授权，需要用户先完成设备码登录。"""


def _fallback_cache_paths() -> list[Path]:
    """打包成 exe 后 PROJECT_ROOT 是 exe 目录，拿不到源码目录里已授权的 token。

    重新构建 exe 时很容易忘记把 .msal_token_cache.json 复制过去，
    表现就是"源码能发邮件、exe 说没授权"。这里按顺序找一遍旧位置，
    只读不写，找到就继承，避免每次换 exe 都要重新做设备码授权。
    """
    candidates: list[Path] = []
    src_root = Path(__file__).resolve().parent.parent
    for base in (src_root, Path.cwd()):
        candidate = base / _CACHE_NAME
        if candidate != _CACHE_PATH and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _read_cache_text() -> str | None:
    if _CACHE_PATH.is_file():
        _assert_cache_file_secure(_CACHE_PATH)
        return _CACHE_PATH.read_text(encoding="utf-8")

    for candidate in _fallback_cache_paths():
        if candidate.is_file():
            _assert_cache_file_secure(candidate)
            logger.info("从已验证权限的旧位置继承 Graph token 缓存")
            _write_cache_text(candidate.read_text(encoding="utf-8"))
            _assert_cache_file_secure(_CACHE_PATH)
            return _CACHE_PATH.read_text(encoding="utf-8")
    return None


def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    text = _read_cache_text()
    if text:
        cache.deserialize(text)
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        _write_cache_text(cache.serialize())


def _write_cache_text(text: str) -> None:
    """Atomically replace the credential cache only after permissions are secured."""
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{_CACHE_PATH.name}.",
            suffix=".tmp",
            dir=_CACHE_PATH.parent,
            delete=False,
        ) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_path = Path(stream.name)
        _restrict_cache_file(temporary_path)
        os.replace(temporary_path, _CACHE_PATH)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _restrict_cache_file(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o600)
        return

    icacls = _trusted_system_tool("icacls.exe")
    current_account, current_sid = _current_windows_identity()
    result = subprocess.run(
        [
            str(icacls),
            str(path),
            "/inheritance:r",
            "/remove:g",
            "*S-1-5-32-544",
            "*S-1-5-32-545",
            "*S-1-1-0",
            "*S-1-5-11",
            "*S-1-3-4",
            "/grant:r",
            f"*{current_sid}:(F)",
            "*S-1-5-18:(F)",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("无法限制 Graph token cache 的 Windows ACL，已拒绝写入")
    _assert_cache_file_secure(path)


def _assert_cache_file_secure(path: Path) -> None:
    """Reject credential caches readable by any principal except this user and SYSTEM."""
    if not path.is_file():
        raise FileNotFoundError(path)
    if os.name != "nt":
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise PermissionError("Graph token cache 权限必须是 0600")
        return

    current_account, current_sid = _current_windows_identity()
    acl_path: Path | None = None
    try:
        descriptor = tempfile.NamedTemporaryFile(
            prefix=".voice-agent-acl.", suffix=".txt", dir=path.parent, delete=False
        )
        acl_path = Path(descriptor.name)
        descriptor.close()
        acl_path.unlink()
        result = subprocess.run(
            [
                str(_trusted_system_tool("icacls.exe")),
                str(path),
                "/save",
                str(acl_path),
                "/c",
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or not acl_path.is_file():
            raise PermissionError("无法导出 Graph token cache 的 Windows ACL，已拒绝读取")
        sddl = _read_sddl(acl_path)
        _validate_cache_sddl(
            sddl,
            current_sid,
            allow_local_administrator_alias=_is_local_builtin_administrator(
                current_account, current_sid
            ),
        )
    finally:
        if acl_path is not None:
            acl_path.unlink(missing_ok=True)


def _trusted_system_tool(name: str) -> Path:
    if os.name != "nt":
        raise RuntimeError("Windows security tools are unavailable on this platform")
    buffer = ctypes.create_unicode_buffer(32_768)
    length = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
    if length <= 0 or length >= len(buffer):
        raise RuntimeError("无法读取受信任的 Windows System32 路径")
    system_directory = Path(buffer.value).resolve()
    candidate = (system_directory / name).resolve()
    if not candidate.is_relative_to(system_directory) or not candidate.is_file():
        raise RuntimeError(f"无法定位受信任的 Windows 程序: {candidate}")
    return candidate


def _current_windows_sid() -> str:
    return _current_windows_identity()[1]


def _current_windows_identity() -> tuple[str, str]:
    result = subprocess.run(
        [str(_trusted_system_tool("whoami.exe")), "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise PermissionError("无法读取当前 Windows SID，已拒绝读取 Graph token cache")
    text = _decode_command_output(result.stdout)
    try:
        row = next(csv.reader([text.strip()]))
        account = row[0].strip()
        sid = row[1].strip().upper()
    except (IndexError, StopIteration, csv.Error) as exc:
        raise PermissionError("无法解析当前 Windows SID，已拒绝读取 Graph token cache") from exc
    if not re.fullmatch(r"S-\d+(?:-\d+)+", sid):
        raise PermissionError("当前 Windows SID 格式无效，已拒绝读取 Graph token cache")
    if "\\" not in account:
        raise PermissionError("当前 Windows 账号格式无效，已拒绝读取 Graph token cache")
    return account, sid


def _windows_computer_name() -> str:
    if os.name != "nt":
        raise RuntimeError("Windows computer identity is unavailable on this platform")
    buffer = ctypes.create_unicode_buffer(256)
    size = wintypes.DWORD(len(buffer))
    if not ctypes.windll.kernel32.GetComputerNameW(buffer, ctypes.byref(size)):
        raise RuntimeError("无法读取 Windows computer name")
    return buffer.value


def _is_local_builtin_administrator(account: str, sid: str) -> bool:
    account_domain, separator, _username = account.partition("\\")
    return (
        bool(separator)
        and sid.upper().endswith("-500")
        and account_domain.casefold() == _windows_computer_name().casefold()
    )


def _read_sddl(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-16", "utf-8-sig", locale.getpreferredencoding(False)):
        try:
            text = data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError, LookupError):
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("D:"):
                return stripped
    raise PermissionError("无法解析 Graph token cache 的 SDDL，已拒绝读取")


def _decode_command_output(data: bytes) -> str:
    for encoding in ("utf-8-sig", locale.getpreferredencoding(False), "utf-16"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError, LookupError):
            continue
    raise PermissionError("无法解析 Windows 安全命令输出")


def _validate_cache_sddl(
    sddl: str,
    current_sid: str,
    *,
    allow_local_administrator_alias: bool = False,
) -> None:
    first_ace = sddl.find("(")
    if not sddl.startswith("D:") or first_ace < 0 or "P" not in sddl[2:first_ace]:
        raise PermissionError("Graph token cache 仍继承目录权限，已拒绝读取")

    aces = re.findall(r"\(([^()]*)\)", sddl)
    if len(aces) != 2:
        raise PermissionError("Graph token cache ACL 必须只包含当前用户和 SYSTEM")
    expected = {current_sid.upper(), "S-1-5-18"}
    grants: set[str] = set()
    for ace in aces:
        fields = ace.split(";")
        if len(fields) != 6:
            raise PermissionError("Graph token cache ACL 结构无效")
        ace_type, flags, rights, _object_guid, _inherit_guid, trustee = fields
        trustee = trustee.upper()
        if trustee == "SY":
            normalized = "S-1-5-18"
        elif trustee == "LA" and allow_local_administrator_alias:
            normalized = current_sid.upper()
        else:
            normalized = trustee
        if ace_type != "A" or flags or rights != "FA" or normalized not in expected:
            raise PermissionError("Graph token cache 向其他 Windows principal 授权，已拒绝读取")
        grants.add(normalized)
    if grants != expected:
        raise PermissionError("Graph token cache ACL 必须只包含当前用户和 SYSTEM")


def _build_app(cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    client_id = config.require("GRAPH_CLIENT_ID")
    authority = config.get("GRAPH_AUTHORITY", _AUTHORITY)
    return msal.PublicClientApplication(client_id, authority=authority, token_cache=cache)


def acquire_token_silent() -> str:
    """从本地 cache 取 token；没有就抛 GraphAuthRequired，不做交互。"""
    cache = _load_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()
    if not accounts:
        raise GraphAuthRequired("尚未授权 Graph 邮件权限，请先运行 python -m scripts.graph_login")

    result = app.acquire_token_silent(_SCOPES, account=accounts[0])
    _save_cache(cache)
    if not result or "access_token" not in result:
        raise GraphAuthRequired("Graph token 已失效，请重新运行 python -m scripts.graph_login")
    return result["access_token"]


def signed_in_user() -> str | None:
    cache = _load_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()
    return accounts[0].get("username") if accounts else None


def device_code_login(printer=print) -> str:
    """交互式设备码授权，仅由 scripts/graph_login.py 调用。"""
    cache = _load_cache()
    app = _build_app(cache)

    flow = app.initiate_device_flow(scopes=_SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"发起设备码流程失败: {json.dumps(flow, ensure_ascii=False)}")

    printer(flow["message"])
    result = app.acquire_token_by_device_flow(flow)
    _save_cache(cache)

    if "access_token" not in result:
        raise RuntimeError(
            f"授权失败: {result.get('error')} - {result.get('error_description')}"
        )
    return result.get("id_token_claims", {}).get("preferred_username", "")


def send_mail(to: str, subject: str, body: str) -> dict:
    token = acquire_token_silent()
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": True,
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            _SENDMAIL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )

    if resp.status_code != 202:
        raise RuntimeError(f"Graph sendMail 失败 HTTP {resp.status_code}: {resp.text[:300]}")

    return {
        "transport": "graph",
        "status_code": resp.status_code,
        "request_id": resp.headers.get("request-id", ""),
    }
