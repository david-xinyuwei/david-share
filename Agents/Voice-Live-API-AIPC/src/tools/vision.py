"""摄像头识物：拍一张照片，用多模态模型认出是什么，再用 WebIQ 找哪里有卖。

摄像头可以是本机内置的，也可以是远程桌面重定向过来的；两者在 OpenCV 看来都是普通视频设备。
"""

from __future__ import annotations

import base64
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from .. import aoai, camera, config, events
from . import tool

logger = logging.getLogger(__name__)

_MAX_CAMERA_INDEX = 3
_WARMUP_SECONDS = 4.0  # 自动曝光需要时间收敛，尤其是远程桌面重定向过来的摄像头
_BRIGHT_ENOUGH = 18.0  # 0-255 灰度均值，低于这个基本就是全黑帧
_PREVIEW_WIDTH = 360


def _log_vision_metadata(answer: str, shopping_keyword: str) -> None:
    logger.info(
        "摄像头识别完成 answer_chars=%d shopping_keyword=%s",
        len(answer),
        bool(shopping_keyword),
    )


def _snapshot_dir() -> Path:
    directory = Path(config.get("SNAPSHOT_DIR") or (config.PROJECT_ROOT / "artifacts" / "snapshots"))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _capture_frame():
    """优先用常开的实时流取当前帧；流没开时才临时打开一次摄像头。"""
    frame = camera.stream.latest_frame()
    if frame is not None:
        return frame, f"{camera.stream.source}(实时流)", float(frame.mean())

    import cv2

    # 远程桌面重定向的摄像头只暴露给 Media Foundation，DirectShow 只能看到永远全黑的残留过滤器。
    backends = [("MSMF", cv2.CAP_MSMF), ("DSHOW", cv2.CAP_DSHOW)]

    tried = []
    for backend_name, backend in backends:
        for index in range(_MAX_CAMERA_INDEX):
            capture = cv2.VideoCapture(index, backend)
            try:
                if not capture.isOpened():
                    tried.append(f"{backend_name}[{index}]: 打不开")
                    continue

                frame = None
                brightness = 0.0
                deadline = time.monotonic() + _WARMUP_SECONDS
                while time.monotonic() < deadline:
                    ok, candidate = capture.read()
                    if not ok or candidate is None:
                        time.sleep(0.05)
                        continue
                    frame = candidate
                    brightness = float(candidate.mean())
                    if brightness >= _BRIGHT_ENOUGH:
                        break
                    time.sleep(0.1)

                if frame is None:
                    tried.append(f"{backend_name}[{index}]: 打开了但读不到画面")
                    continue
                if brightness < _BRIGHT_ENOUGH:
                    tried.append(f"{backend_name}[{index}]: 全黑（亮度 {brightness:.1f}）")
                    continue
                logger.info("摄像头命中 %s index=%s 亮度=%.1f", backend_name, index, brightness)
                return frame, f"{backend_name}[{index}]", brightness
            finally:
                capture.release()

    detail = "; ".join(tried)
    if os.environ.get("SESSIONNAME", "").startswith("RDP-"):
        raise RuntimeError(
            f"拿不到摄像头画面（{detail}）。当前是远程桌面会话：请确认连接时勾选了"
            "「本地资源 → 详细信息 → 视频捕获设备」，且本机摄像头没有被 Teams 等程序占用。"
        )
    raise RuntimeError(
        f"拿不到摄像头画面（{detail}）。"
        "常见原因是镜头被物理遮挡、笔记本摄像头开关关着，"
        "或 Windows 设置 → 隐私和安全性 → 相机 里禁止了桌面应用访问。"
    )


def _emit_preview(frame, path: Path) -> None:
    """存一张 PNG 缩略图并通知界面显示，让用户直接看到镜头拍到了什么。"""
    import cv2

    height, width = frame.shape[:2]
    scale = _PREVIEW_WIDTH / float(width)
    preview = cv2.resize(frame, (_PREVIEW_WIDTH, max(1, int(height * scale))))
    preview_path = path.with_name(path.stem + "_preview.png")
    if cv2.imwrite(str(preview_path), preview):
        events.emit("camera_frame", str(preview_path))


@tool(
    name="open_camera",
    description=(
        "打开摄像头实时画面并一直保持开启。用户说打开摄像头、开一下视频、把摄像头打开时调用。"
        "开启后画面会持续显示在界面上，用户可以随时举起物品提问。"
    ),
    parameters={"type": "object", "properties": {}, "required": []},
)
def open_camera() -> dict:
    if camera.stream.running:
        return {
            "message": "摄像头本来就开着",
            "source": camera.stream.source,
            "already_on": True,
            "you_cannot_see_yet": True,
            "hint": "要知道画面里有什么，必须调用 identify_object_with_camera。",
        }

    camera.stream.start()
    events.emit("camera_on", camera.stream.source)
    return {
        "message": "摄像头实时画面已打开",
        "source": camera.stream.source,
        "you_cannot_see_yet": True,
        "hint": "摄像头开着不代表你能看到画面内容。用户问画面里有什么时，"
                "必须调用 identify_object_with_camera 才能知道，不得自行描述或猜测。",
    }


@tool(
    name="close_camera",
    description="关闭摄像头实时画面。用户说关掉摄像头、把视频关了时调用。",
    parameters={"type": "object", "properties": {}, "required": []},
)
def close_camera() -> dict:
    if not camera.stream.running:
        return {"message": "摄像头本来就是关着的", "already_off": True}
    camera.stream.stop()
    events.emit("camera_off", "")
    return {"message": "摄像头已关闭"}


@tool(
    name="identify_object_with_camera",
    description=(
        "看一眼摄像头当前画面并回答关于画面的问题。"
        "用户问画面里有什么、我在干什么、这是什么、我手里拿的是啥时调用。"
        "把用户的原话放进 question，工具会照着这个问题看图回答。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": (
                    "用户关于画面的原始问题，例如 我在干什么、这是什么牌子的水。"
                    "尽量照抄用户原话，不要改写成识别物品。留空则做通用画面描述。"
                ),
            }
        },
        "required": [],
    },
)
def identify_object_with_camera(question: str | None = None) -> dict:
    import cv2

    frame, camera_source, brightness = _capture_frame()
    path = _snapshot_dir() / f"snapshot_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"照片写入失败: {path}")
    _emit_preview(frame, path)

    b64 = base64.b64encode(path.read_bytes()).decode()
    ask = question or "画面里有什么？"

    response = aoai.client().chat.completions.create(
        model=aoai.chat_deployment(),
        messages=[
            {
                "role": "system",
                "content": (
                    "你在看一张摄像头照片，帮用户回答他关于这张照片的问题。"
                    "直接回答用户问的那个问题，不要答成别的问题："
                    "问「我在干什么」就描述人物的动作、姿态、所处环境和正在使用的东西，"
                    "再据此推测他可能在做什么；问「这是什么」才去识别物品的品类、品牌、型号和包装文字。"
                    "只描述画面里真实可见的内容，看不清就直说看不清，不要猜。"
                    "避免只说「一个瓶子」「一个物体」这类笼统描述。\n"
                    "只有当用户的问题本身是在问某个商品是什么、值不值得买、哪里能买时，"
                    "才在最后单独一行输出：购物关键词：<中文搜索关键词>。"
                    "用户只是问画面内容或自己在干什么时，绝对不要输出购物关键词这一行。"
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ask},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            },
        ],
        max_completion_tokens=400,
    )

    answer = (response.choices[0].message.content or "").strip()

    # 只有视觉模型判定这是个购物问题时才会输出这一行；用户问「我在干什么」时不会有。
    # 绝对不要用 question 兜底：那等于把「你看我在干什么」变成购物关键词，
    # 于是模型顺手去查购买链接——这正是之前硬推购物的根因。
    keyword = ""
    for line in answer.splitlines():
        if "购物关键词" in line:
            keyword = line.split("：", 1)[-1].split(":", 1)[-1].strip()
    # 关键词行是给模型看的内部信号，不该念给用户听
    description = "\n".join(
        line for line in answer.splitlines() if "购物关键词" not in line
    ).strip()

    _log_vision_metadata(answer, keyword)

    result = {
        "description": description or answer,
        "image_path": str(path),
        "camera_source": camera_source,
        "brightness": round(brightness, 1),
        "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
        "answered_question": ask,
    }
    if keyword:
        # 仅在确实是购物类提问时才给出后续动作，且明确要求先问过用户
        result["shopping_keyword"] = keyword
        result["hint"] = (
            "用户如果接着问哪里买、多少钱，再调用 search_where_to_buy 并传入 shopping_keyword。"
            "用户没主动问价格或购买渠道时，不要提购买链接。"
        )
    else:
        result["hint"] = (
            "这不是购物类提问：直接照着 description 回答用户问的那件事即可，"
            "不要查询购买信息，也不要主动推荐商品或链接。"
        )
    return result


@tool(
    name="search_where_to_buy",
    description="查询某个商品在网上哪里有卖、大概什么价位。用户问哪儿能买到、多少钱时调用。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "商品关键词，例如 罗技 MX Master 3S 鼠标"},
        },
        "required": ["keyword"],
    },
)
def search_where_to_buy(keyword: str) -> dict:
    from .. import webiq_client
    from .websearch import _strip_html

    response = webiq_client.search_with_retry(
        webiq_client.client().web.search, query=f"{keyword} 价格 购买", max_results=8
    )

    offers = []
    for item in getattr(response, "webResults", None) or []:
        offers.append(
            {
                "title": getattr(item, "title", "") or "",
                "url": getattr(item, "url", "") or "",
                "snippet": _strip_html(getattr(item, "content", ""))[:200],
            }
        )
    if not offers:
        return {"ok": False, "error": f"WebIQ 没有搜到「{keyword}」的购买信息"}

    return {"keyword": keyword, "results": offers[:5], "source": "WebIQ"}
