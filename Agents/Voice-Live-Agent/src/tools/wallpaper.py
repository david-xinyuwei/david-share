"""桌面壁纸：从网上查找或用 Azure OpenAI 生成图片，并通过 Win32 API 真正换掉 Windows 桌面背景。"""

from __future__ import annotations

import base64
import ctypes
import ipaddress
import socket
import sys
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .. import aoai, config
from . import tool

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02
_SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}

_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
_MAGIC_SUFFIX = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"BM": ".bmp",
}


def _wallpaper_dir() -> Path:
    directory = config.WALLPAPER_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory.resolve()


def _resolve_inside_dir(image_path: str) -> Path:
    root = _wallpaper_dir()
    candidate = Path(image_path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError(f"只允许使用 {root} 目录内的图片作为壁纸")
    if not resolved.is_file():
        raise FileNotFoundError(f"图片不存在: {resolved}")
    if resolved.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ValueError(f"不支持的图片格式: {resolved.suffix}")
    return resolved


def _apply_wallpaper(path: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("更换桌面壁纸只能在 Windows 上执行")

    import winreg

    # 10 = 填充，配合 TileWallpaper=0 让壁纸铺满不同分辨率的屏幕
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "10")
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SystemParametersInfoW.argtypes = [
        wintypes.UINT,
        wintypes.UINT,
        wintypes.LPVOID,
        wintypes.UINT,
    ]
    user32.SystemParametersInfoW.restype = wintypes.BOOL

    ok = user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER,
        0,
        ctypes.c_wchar_p(str(path)),
        SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE,
    )
    if not ok:
        raise OSError(ctypes.get_last_error(), "SystemParametersInfoW 设置壁纸失败")


@tool(
    name="search_wallpaper_image",
    description="从网上搜索并下载一张桌面壁纸图片到本地。用户说找一张壁纸、网上搜张桌面图片时调用。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "图片主题，例如 雪山日出、星空、极简风景"},
        },
        "required": ["query"],
    },
)
def search_wallpaper_image(query: str) -> dict:
    from .. import webiq_client

    response = webiq_client.search_with_retry(
        webiq_client.client().images.search, query=f"{query} wallpaper", max_results=15
    )

    hits = []
    for img in getattr(response, "imageResults", []) or []:
        url = getattr(img, "url", "") or getattr(img, "thumbnailUrl", "") or ""
        if not url:
            continue
        hits.append(
            {
                "url": url,
                "title": getattr(img, "title", "") or "",
                "host_url": getattr(img, "hostPageUrl", "") or "",
                "width": int(getattr(img, "width", 0) or 0),
                "height": int(getattr(img, "height", 0) or 0),
            }
        )
    if not hits:
        return {"ok": False, "error": f"WebIQ 没有搜到与「{query}」相关的壁纸图片"}

    # 壁纸要横向构图，按宽度降序优先试大图
    candidates = sorted(
        (h for h in hits if h["width"] >= h["height"] > 0), key=lambda h: h["width"], reverse=True
    ) or hits

    failures: list[str] = []
    for hit in candidates[:6]:
        try:
            content, suffix = _download_image(hit["url"])
        except Exception as exc:
            failures.append(f"{type(exc).__name__}: {exc}")
            continue

        path = _wallpaper_dir() / f"wallpaper_{datetime.now():%Y%m%d_%H%M%S}{suffix}"
        path.write_bytes(content)
        return {
            "image_path": str(path),
            "title": hit["title"],
            "source_page": hit["host_url"],
            "resolution": f"{hit['width']}x{hit['height']}",
            "bytes": len(content),
            "source": "WebIQ",
            "hint": "可直接调用 set_desktop_wallpaper 并传入该 image_path 应用为桌面背景。",
        }

    return {"ok": False, "error": "候选图片全部下载失败: " + "; ".join(failures[:3])}


def _as_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _assert_public_https(url: str) -> str:
    """只允许 https 且解析到公网地址，避免图片下载被用来探测内网。"""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"只接受 https 图片地址: {url[:80]}")

    for info in socket.getaddrinfo(parsed.hostname, 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise PermissionError(f"图片地址解析到非公网地址，已拒绝: {parsed.hostname}")
    return url


def _download_image(url: str) -> tuple[bytes, str]:
    _assert_public_https(url)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                raise ValueError(f"返回的不是图片: content-type={content_type or '未知'}")

            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > _MAX_DOWNLOAD_BYTES:
                    raise ValueError("图片超过 20MB，已放弃下载")
                chunks.append(chunk)

    content = b"".join(chunks)
    suffix = _detect_suffix(content)
    if suffix is None:
        raise ValueError("文件头不是 JPEG/PNG/BMP，拒绝写入")
    return content, suffix


def _detect_suffix(data: bytes) -> str | None:
    for magic, suffix in _MAGIC_SUFFIX.items():
        if data.startswith(magic):
            return suffix
    return None


@tool(
    name="generate_wallpaper_image",
    description="根据文字描述用 AI 生成一张桌面壁纸图片并保存到本地。用户说生成、画一张壁纸时调用。",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "壁纸画面描述，例如 雪山日出、赛博朋克城市夜景"},
        },
        "required": ["prompt"],
    },
)
def generate_wallpaper_image(prompt: str) -> dict:
    size = config.get("AZURE_OPENAI_IMAGE_SIZE", "1536x1024")
    result = aoai.client().images.generate(
        model=aoai.image_deployment(),
        prompt=f"{prompt}. 适合作为宽屏桌面壁纸的高质量横向构图，画面中不要出现文字。",
        n=1,
        size=size,
    )

    item = result.data[0]
    if getattr(item, "b64_json", None):
        content = base64.b64decode(item.b64_json)
    elif getattr(item, "url", None):
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(item.url)
            resp.raise_for_status()
            content = resp.content
    else:
        raise RuntimeError("图像生成接口既未返回 b64_json 也未返回 url")

    filename = f"wallpaper_{datetime.now():%Y%m%d_%H%M%S}.png"
    path = _wallpaper_dir() / filename
    path.write_bytes(content)

    return {
        "image_path": str(path),
        "size": size,
        "deployment": aoai.image_deployment(),
        "bytes": len(content),
        "hint": "可直接调用 set_desktop_wallpaper 并传入该 image_path 应用为桌面背景。",
    }


@tool(
    name="set_desktop_wallpaper",
    description="把指定图片设置为当前 Windows 桌面壁纸。用户说换桌面、把它设成壁纸时调用。",
    parameters={
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "壁纸图片路径，通常来自 generate_wallpaper_image 的返回值。留空表示使用目录中最新一张。",
            }
        },
        "required": [],
    },
)
def set_desktop_wallpaper(image_path: str | None = None) -> dict:
    if image_path:
        target = _resolve_inside_dir(image_path)
    else:
        candidates = [
            p for p in _wallpaper_dir().iterdir() if p.suffix.lower() in _SUPPORTED_SUFFIXES and p.is_file()
        ]
        if not candidates:
            raise FileNotFoundError(f"{_wallpaper_dir()} 中没有可用的壁纸图片，请先生成一张")
        target = max(candidates, key=lambda p: p.stat().st_mtime)

    _apply_wallpaper(target)
    return {"image_path": str(target), "message": "Windows 桌面壁纸已更换"}
