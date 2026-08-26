"""工具注册表：声明 schema、分发调用，并把工具执行挪出事件循环线程。"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from azure.ai.voicelive.models import FunctionTool, Tool

from .. import confirmation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]


_REGISTRY: dict[str, ToolSpec] = {}


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    enabled: Callable[[], bool] | None = None,
):
    """enabled 用于按运行时配置决定是否注册，避免把必然失败的工具暴露给模型。"""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if enabled is not None and not enabled():
            logger.info("工具 %s 未启用（缺少所需配置），跳过注册", name)
            return fn
        if name in _REGISTRY:
            raise ValueError(f"工具重复注册: {name}")
        _REGISTRY[name] = ToolSpec(name, description, parameters, fn)
        return fn

    return decorator


def function_tools() -> list[Tool]:
    return [
        FunctionTool(
            name=spec.name,
            description=spec.description,
            parameters=confirmation.augment_parameters(spec.name, spec.parameters),
        )
        for spec in _REGISTRY.values()
    ]


def registered_names() -> list[str]:
    return list(_REGISTRY)


def _parse_arguments(arguments: str | Mapping[str, Any] | None) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, Mapping):
        return dict(arguments)
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        parsed = _loads_lenient(arguments)
    if not isinstance(parsed, dict):
        raise ValueError("模型返回的参数不是 JSON 对象")
    return parsed


def _loads_lenient(raw: str) -> Any:
    """流式函数调用偶尔会吐出未加引号的键或多余逗号，这里做一次保守修复再解析。"""
    repaired = re.sub(r",\s*([}\]])", r"\1", raw)
    repaired = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', repaired)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型返回的参数不是合法 JSON: {exc}") from exc


async def dispatch(name: str, arguments: str | Mapping[str, Any] | None) -> dict[str, Any]:
    """执行工具。同步实现放到线程池，避免阻塞 WebSocket 事件循环导致音频卡顿。"""
    spec = _REGISTRY.get(name)
    if spec is None:
        return {"ok": False, "error": f"未注册的工具: {name}"}

    try:
        kwargs = _parse_arguments(arguments)
        kwargs, confirmation_response = confirmation.authorize(name, kwargs)
        if confirmation_response is not None:
            return confirmation_response
        assert kwargs is not None
        if inspect.iscoroutinefunction(spec.handler):
            result = await spec.handler(**kwargs)
        else:
            result = await asyncio.to_thread(spec.handler, **kwargs)
    except TypeError as exc:
        logger.exception("工具 %s 参数不匹配", name)
        return {"ok": False, "error": f"参数不匹配: {exc}"}
    except Exception as exc:  # 工具失败必须显式回传，不能伪装成功
        logger.exception("工具 %s 执行失败", name)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if not isinstance(result, dict):
        result = {"result": result}
    result.setdefault("ok", True)
    return result


from . import (  # noqa: E402,F401  注册副作用导入，必须在 registry 定义之后
    briefing,
    clock,
    desktop,
    mailer,
    news,
    power,
    stocks,
    timezone,
    vision,
    wallpaper,
    weather,
    websearch,
)
