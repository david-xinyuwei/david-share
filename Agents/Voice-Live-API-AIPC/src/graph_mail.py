"""Microsoft Graph 邮件发送。

Outlook.com / Exchange Online 的 SMTP Basic Auth 已于 2026-04-30 退役，
个人 Microsoft 账号只能走 OAuth，因此发信统一用 Graph /me/sendMail。
首次使用需要设备码授权一次，之后靠本地 token cache 静默续期。
"""

from __future__ import annotations

import getpass
import json
import logging
import os
import subprocess
import tempfile
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

    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    icacls = system_root / "System32" / "icacls.exe"
    if not icacls.is_file():
        raise RuntimeError("无法定位 icacls.exe，拒绝写入 Graph token cache")

    username = os.environ.get("USERNAME") or getpass.getuser()
    domain = os.environ.get("USERDOMAIN")
    principal = f"{domain}\\{username}" if domain else username
    result = subprocess.run(
        [
            str(icacls),
            str(path),
            "/inheritance:r",
            "/grant:r",
            f"{principal}:(F)",
            "*S-1-5-18:(F)",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("无法限制 Graph token cache 的 Windows ACL，已拒绝写入")


def _assert_cache_file_secure(path: Path) -> None:
    """Reject credential caches readable by any principal except this user and SYSTEM."""
    if not path.is_file():
        raise FileNotFoundError(path)
    if os.name != "nt":
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise PermissionError("Graph token cache 权限必须是 0600")
        return

    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve()
    powershell = (
        system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    ).resolve()
    if not powershell.is_relative_to(system_root) or not powershell.is_file():
        raise RuntimeError("无法定位受信任的 powershell.exe，拒绝读取 Graph token cache")

    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$acl = Get-Acl -LiteralPath $env:VOICE_AGENT_CACHE_PATH
$rules = @($acl.Access | ForEach-Object {
    [pscustomobject]@{
        sid = $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        type = $_.AccessControlType.ToString()
        inherited = [bool]$_.IsInherited
        rights = [int64]$_.FileSystemRights
    }
})
[pscustomobject]@{
    current_sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    protected = [bool]$acl.AreAccessRulesProtected
    rules = $rules
} | ConvertTo-Json -Compress -Depth 4
"""
    result = subprocess.run(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        timeout=10,
        check=False,
        env={**os.environ, "VOICE_AGENT_CACHE_PATH": str(path)},
    )
    if result.returncode != 0:
        raise PermissionError("无法验证 Graph token cache 的 Windows ACL，已拒绝读取")
    try:
        state = json.loads(result.stdout.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PermissionError("无法解析 Graph token cache 的 Windows ACL，已拒绝读取") from exc

    current_sid = str(state.get("current_sid", "")).upper()
    allowed_sids = {current_sid, "S-1-5-18"}
    if not current_sid or state.get("protected") is not True:
        raise PermissionError("Graph token cache 仍继承目录权限，已拒绝读取")

    grants: set[str] = set()
    rules = state.get("rules") or []
    if isinstance(rules, dict):
        rules = [rules]
    full_control = 0x1F01FF
    for rule in rules:
        if str(rule.get("type", "")).lower() != "allow":
            continue
        sid = str(rule.get("sid", "")).upper()
        rights = int(rule.get("rights", 0))
        if rule.get("inherited") or sid not in allowed_sids:
            raise PermissionError("Graph token cache 向其他 Windows principal 授权，已拒绝读取")
        if rights & full_control != full_control:
            raise PermissionError("Graph token cache 缺少受控 principal 的 Full Control")
        grants.add(sid)
    if grants != allowed_sids:
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
