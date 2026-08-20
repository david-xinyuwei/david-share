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
        "看一眼摄像头当前画面，识别用户举着或镜头里的物品是什么，并给出选购关键词。"
        "用户说看看这是什么、我手里拿的是啥、这个东西认一下时调用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "想让助手重点关注的问题，例如 这是什么牌子的水。留空则做通用识别。",
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
    ask = question or "镜头里最主要的物品是什么？"

    response = aoai.client().chat.completions.create(
        model=aoai.chat_deployment(),
        messages=[
            {
                "role": "system",
                "content": (
                    "你在帮用户识别摄像头拍到的物品。先用一句话说出物品是什么，"
                    "尽量给出品类、品牌、型号等可辨认的信息，包括包装上的文字；"
                    "只描述画面里真实可见的内容，看不清就直说看不清，不要猜。"
                    "回答要具体，避免只说「一个瓶子」「一个物体」这类笼统的描述。"
                    "最后单独一行输出：购物关键词：<适合在购物网站搜索的中文关键词>"
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
    keyword = ""
    for line in answer.splitlines():
        if "购物关键词" in line:
            keyword = line.split("：", 1)[-1].split(":", 1)[-1].strip()
    logger.info("摄像头识物: %s", answer.replace("\n", " ")[:200])

    return {
        "description": answer,
        "shopping_keyword": keyword or (question or "").strip(),
        "image_path": str(path),
        "camera_source": camera_source,
        "brightness": round(brightness, 1),
        "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
        "hint": "可继续调用 search_where_to_buy 并传入 shopping_keyword，查询哪里有卖。",
    }


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
