"""桌面壁纸：从网上查找或用 Azure OpenAI 生成图片，并通过 Win32 API 真正换掉 Windows 桌面背景。"""

from __future__ import annotations

import base64
import ctypes
import http.client
import ipaddress
import socket
import ssl
import sys
from contextlib import contextmanager
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Iterator
from urllib.parse import urljoin, urlparse

from .. import aoai, config
from . import tool

SPI_SETDESKWALLPAPER = 0x0014
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDWININICHANGE = 0x02
_SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}

_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
_MAX_REDIRECTS = 5
_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_MAGIC_SUFFIX = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"BM": ".bmp",
}


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to a validated IP while verifying TLS against the original hostname."""

    def __init__(self, host: str, pinned_ip: str, timeout: float) -> None:
        super().__init__(host=host, port=443, timeout=timeout, context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._pinned_ip, self.port),
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


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
        # WebIQ 的 url 字段实测常常只是站点根（如 https://static.vecteezy.com/），
        # 直接下它等于抓人家首页 HTML，必然 403 / text/html / 404。
        # thumbnailUrl 实测 15/15 都是带路径的可下载图片地址，因此按"是否可下载"排序，
        # 而不是固定优先 url。两个地址都留着，逐个试。
        urls = _download_candidates(img)
        if not urls:
            continue
        hits.append(
            {
                "urls": urls,
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
    for hit in candidates[:8]:
        downloaded: tuple[bytes, str] | None = None
        for url in hit["urls"]:
            try:
                downloaded = _download_image(url)
            except Exception as exc:
                failures.append(f"{type(exc).__name__}: {exc}")
                continue
            break
        if downloaded is None:
            continue

        content, suffix = downloaded
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


def _has_real_path(url: str) -> bool:
    """区分「真实图片地址」和「只有域名的站点根」。

    实测 WebIQ 的 url 字段 15/15 都是 https://static.vecteezy.com/ 这种光域名，
    下载它拿到的是首页 HTML，于是必然 403 / text/html / 404；
    thumbnailUrl 15/15 都带路径，是可下载的真图。
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return bool(parsed.scheme and parsed.netloc and parsed.path.strip("/"))


def _download_candidates(img: object) -> list[str]:
    """按可下载性排序候选地址：带路径的排前面，只有域名的排后面。"""
    seen: set[str] = set()
    with_path: list[str] = []
    bare_host: list[str] = []

    for field in ("contentUrl", "url", "thumbnailUrl"):
        url = (getattr(img, field, "") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        (with_path if _has_real_path(url) else bare_host).append(url)

    return with_path + bare_host


def _as_int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _validated_public_https(url: str) -> tuple[object, tuple[str, ...]]:
    """只允许 https 且解析到公网地址，避免图片下载被用来探测内网。"""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"只接受 https 图片地址: {url[:80]}")
    if parsed.port not in (None, 443):
        raise ValueError(f"只接受标准 https 端口: {url[:80]}")

    addresses: list[str] = []
    for info in socket.getaddrinfo(
        parsed.hostname,
        443,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    ):
        address = info[4][0].split("%", 1)[0]
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise PermissionError(f"图片地址解析到非公网地址，已拒绝: {parsed.hostname}")
        normalized = str(ip)
        if normalized not in addresses:
            addresses.append(normalized)
    if not addresses:
        raise ConnectionError(f"图片地址没有可用的公网解析结果: {parsed.hostname}")
    return parsed, tuple(addresses)


def _assert_public_https(url: str) -> str:
    _validated_public_https(url)
    return url


@contextmanager
def _open_pinned_response(
    url: str,
    addresses: tuple[str, ...],
    headers: dict[str, str],
) -> Iterator[http.client.HTTPResponse]:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").encode("idna").decode("ascii")
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"

    last_error: Exception | None = None
    for address in addresses:
        connection = _PinnedHTTPSConnection(hostname, address, timeout=20.0)
        try:
            connection.request("GET", target, headers=headers)
            response = connection.getresponse()
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            last_error = exc
            connection.close()
            continue
        try:
            yield response
        finally:
            response.close()
            connection.close()
        return
    raise ConnectionError(f"无法连接图片站点 {hostname}") from last_error


def _download_image(url: str) -> tuple[bytes, str]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    current_url = url
    redirect_count = 0

    while True:
        _parsed, addresses = _validated_public_https(current_url)
        with _open_pinned_response(current_url, addresses, headers) as response:
            if response.status in _REDIRECT_STATUS_CODES:
                location = response.getheader("location")
                if not location:
                    raise ValueError("图片下载重定向缺少 Location")
                if redirect_count >= _MAX_REDIRECTS:
                    raise ValueError(f"图片下载重定向超过 {_MAX_REDIRECTS} 次")
                current_url = urljoin(current_url, location)
                redirect_count += 1
                continue

            if response.status >= 400:
                raise RuntimeError(f"图片下载 HTTP {response.status}")
            content_type = response.getheader("content-type", "")
            if not content_type.startswith("image/"):
                raise ValueError(f"返回的不是图片: content-type={content_type or '未知'}")
            content_length = _as_int(response.getheader("content-length"))
            if content_length > _MAX_DOWNLOAD_BYTES:
                raise ValueError("图片超过 20MB，已放弃下载")

            chunks: list[bytes] = []
            total = 0
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > _MAX_DOWNLOAD_BYTES:
                    raise ValueError("图片超过 20MB，已放弃下载")
                chunks.append(chunk)
            break

    content = b"".join(chunks)
    return content, _validated_suffix(content)


def _detect_suffix(data: bytes) -> str | None:
    for magic, suffix in _MAGIC_SUFFIX.items():
        if data.startswith(magic):
            return suffix
    return None


def _validated_suffix(content: bytes) -> str:
    if len(content) > _MAX_DOWNLOAD_BYTES:
        raise ValueError("图片超过 20MB，已放弃下载")
    suffix = _detect_suffix(content)
    if suffix is None:
        raise ValueError("文件头不是 JPEG/PNG/BMP，拒绝写入")
    return suffix


def _image_generation_available() -> bool:
    """未部署图像模型时不注册生图工具，避免模型选中一个必然失败的工具。"""
    return bool(config.get("AZURE_OPENAI_IMAGE_DEPLOYMENT"))


@tool(
    name="generate_wallpaper_image",
    description="根据文字描述用 AI 生成一张桌面壁纸图片并保存到本地。仅当用户明确说生成、画一张时调用；"
                "用户说从网上找、搜一张时要用 search_wallpaper_image。",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "壁纸画面描述，例如 雪山日出、赛博朋克城市夜景"},
        },
        "required": ["prompt"],
    },
    enabled=_image_generation_available,
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
        content = base64.b64decode(item.b64_json, validate=True)
        suffix = _validated_suffix(content)
    elif getattr(item, "url", None):
        content, suffix = _download_image(str(item.url))
    else:
        raise RuntimeError("图像生成接口既未返回 b64_json 也未返回 url")

    filename = f"wallpaper_{datetime.now():%Y%m%d_%H%M%S}{suffix}"
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
