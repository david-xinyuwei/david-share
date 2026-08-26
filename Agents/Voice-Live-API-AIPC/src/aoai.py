"""共享的 Azure OpenAI 客户端，供简报整理与壁纸生图使用。

走 GA 的 /openai/v1 端点并使用当前锁定的 OpenAI client。API Key 与 Entra token
都只在进程内传给 client，不进入源码、日志或浏览器。
"""

from __future__ import annotations

import threading
import time

from azure.identity import AzureCliCredential
from openai import OpenAI

from . import config

_SCOPE = "https://cognitiveservices.azure.com/.default"
_REFRESH_MARGIN_SECONDS = 300

_client: OpenAI | None = None
_expires_on: float = 0.0
_lock = threading.Lock()


def client() -> OpenAI:
    global _client, _expires_on

    with _lock:
        if _client is not None and time.time() < _expires_on - _REFRESH_MARGIN_SECONDS:
            return _client

        endpoint = config.require("AZURE_OPENAI_ENDPOINT").rstrip("/")
        api_key = config.get("AZURE_OPENAI_API_KEY")

        if api_key:
            _client = OpenAI(base_url=f"{endpoint}/openai/v1/", api_key=api_key)
            _expires_on = float("inf")
            return _client

        token = AzureCliCredential().get_token(_SCOPE)
        _client = OpenAI(base_url=f"{endpoint}/openai/v1/", api_key=token.token)
        _expires_on = float(token.expires_on)
        return _client


def chat_deployment() -> str:
    return config.require("AZURE_OPENAI_CHAT_DEPLOYMENT")


def image_deployment() -> str:
    return config.require("AZURE_OPENAI_IMAGE_DEPLOYMENT")
