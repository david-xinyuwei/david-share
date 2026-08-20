"""两个后端共用的角色设定与工具调用编排。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from . import tools
from .events import emit

logger = logging.getLogger(__name__)

INSTRUCTIONS = """你是联想电脑上的中文桌面语音助手，名字叫小联。
你可以调用工具完成这些事：查天气、查新闻、查股票行情、查时间和时区、修改本机系统时区、联网搜索、
整理新闻简报、把内容发到用户邮箱、生成桌面壁纸图片、更换 Windows 桌面壁纸、
打开或关闭摄像头实时画面、看摄像头当前画面识别物品、查商品哪里有卖、
查看和调节系统音量、静音或取消静音、打开 Windows 内置程序和显示桌面。

对话规则：
- 全程用简洁自然的中文口语回答，一次不超过三句话，不要念 URL 和长串数字。
- 只回答用户当前问的这件事。回答完就停住，不要主动推荐、罗列或询问用户要不要用别的功能。
- 听不清、识别结果不成句或意图不明确时，只说一句「没听清，你再说一遍」，绝不允许猜测意图，更不允许因此调用任何工具。
- 需要工具时先用一句话告诉用户你正在做什么，再调用工具，拿到结果后再口播结论。
- 只陈述工具返回的真实数据，工具报错就如实说明失败原因，绝不编造数据。
- 用户说打开摄像头、开一下视频时调用 open_camera，说关掉摄像头时调用 close_camera。
- 你看不见摄像头画面。摄像头开着不等于你能看到内容，只有 identify_object_with_camera 返回的描述才是你看到的。
- 只要用户问画面里有什么、看看这是什么、我手里拿的是啥，必须先调用 identify_object_with_camera；摄像头没开就先 open_camera 再识别。
- 绝对禁止在没有工具返回结果的情况下描述画面里有什么。不确定就说我看一下，然后调工具，不允许猜测或编造。
- 用户说"生成一张壁纸并换上"这类连续任务时，依次调用生成和设置两个工具。
- 用户说声音大一点、小一点这类相对调节时，先调 get_system_volume 拿到当前值，再换算成目标百分比调 set_system_volume。
- 用户说发到我邮箱时直接发，不要询问也不要填写收件人，系统会用本人默认邮箱；只有发给别人才需要地址。"""


@dataclass
class PendingCall:
    call_id: str
    name: str
    item_id: str | None = None
    arguments: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)


class ToolCallCoordinator:
    """收集一轮 response 内的全部 function call，并发执行后交给后端回传。"""

    def __init__(self) -> None:
        self._pending: dict[str, PendingCall] = {}

    def register(self, call_id: str, name: str, item_id: str | None = None) -> None:
        self._pending[call_id] = PendingCall(call_id=call_id, name=name, item_id=item_id)
        emit(
            "tool_start",
            f"[调用工具] {name}",
            {"call_id": call_id, "name": name},
        )

    def set_arguments(self, call_id: str, arguments: str | None) -> None:
        call = self._pending.get(call_id)
        if call is not None:
            call.arguments = arguments
            emit(
                "tool_start",
                f"[参数] {arguments}",
                {"call_id": call_id, "name": call.name, "arguments": arguments},
            )

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    async def drain(self) -> list[PendingCall]:
        calls = list(self._pending.values())
        self._pending.clear()

        results = await asyncio.gather(*(tools.dispatch(c.name, c.arguments) for c in calls))
        for call, result in zip(calls, results):
            call.result = result
            ok = bool(result.get("ok"))
            elapsed = time.monotonic() - call.started_at
            status = "完成" if ok else f"失败: {result.get('error')}"
            emit(
                "tool_done",
                f"[工具 {call.name}] {status}",
                {
                    "call_id": call.call_id,
                    "name": call.name,
                    "ok": ok,
                    "error": result.get("error"),
                    "elapsed": elapsed,
                },
            )
            logger.info("工具 %s 返回(%.2fs): %s", call.name, elapsed, result)
        return calls


def to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)
