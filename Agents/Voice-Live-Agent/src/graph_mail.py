"""Microsoft Graph 邮件发送。

Outlook.com / Exchange Online 的 SMTP Basic Auth 已于 2026-04-30 退役，
个人 Microsoft 账号只能走 OAuth，因此发信统一用 Graph /me/sendMail。
首次使用需要设备码授权一次，之后靠本地 token cache 静默续期。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import msal

from . import config

logger = logging.getLogger(__name__)

_AUTHORITY = "https://login.microsoftonline.com/consumers"
_SCOPES = ["Mail.Send"]
_SENDMAIL_URL = "https://graph.microsoft.com/v1.0/me/sendMail"
_CACHE_PATH = config.PROJECT_ROOT / ".msal_token_cache.json"


class GraphAuthRequired(RuntimeError):
    """尚未授权，需要用户先完成设备码登录。"""


def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if _CACHE_PATH.exists():
        cache.deserialize(_CACHE_PATH.read_text(encoding="utf-8"))
    return cache


def _save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        _CACHE_PATH.write_text(cache.serialize(), encoding="utf-8")
        # token cache 等同凭据，限制为仅当前用户可读
        try:
            _CACHE_PATH.chmod(0o600)
        except OSError:
            pass


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
