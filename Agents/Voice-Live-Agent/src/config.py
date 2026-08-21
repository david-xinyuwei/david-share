"""集中读取环境配置，缺失项在第一次真正使用时才报错。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 打包成单文件 exe 后 __file__ 指向每次启动都不同的临时解压目录，
# .env / logs / token 缓存必须落在 exe 所在目录，否则读不到配置且每次都要重新登录。
if getattr(sys, "frozen", False):
    _PROJECT_ROOT = Path(sys.executable).resolve().parent
    # 随 exe 一起打包的默认配置，让单个 exe 免带 .env 即可运行
    _bundled_env = Path(getattr(sys, "_MEIPASS", "")) / ".env"
    if _bundled_env.is_file():
        load_dotenv(_bundled_env, override=True)
else:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent

# exe 同目录的 .env 后加载，因此始终可以覆盖内嵌配置
load_dotenv(_PROJECT_ROOT / ".env", override=True)


class MissingConfig(RuntimeError):
    """必需的环境变量缺失。不做静默降级，直接失败。"""


def get(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if value is not None:
        value = value.strip()
    return value or None


def require(name: str) -> str:
    value = get(name)
    if not value:
        raise MissingConfig(f"缺少环境变量 {name}，请在 .env 中配置后重试")
    return value


def get_list(name: str) -> list[str]:
    raw = get(name)
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


PROJECT_ROOT = _PROJECT_ROOT

VOICELIVE_ENDPOINT = get("AZURE_VOICELIVE_ENDPOINT")
VOICELIVE_MODEL = get("AZURE_VOICELIVE_MODEL", "gpt-realtime")
VOICELIVE_API_KEY = get("AZURE_VOICELIVE_API_KEY")
VOICELIVE_VOICE = get("AZURE_VOICELIVE_VOICE", "zh-CN-XiaoxiaoMultilingualNeural")

REALTIME_ENDPOINT = get("AZURE_OPENAI_ENDPOINT")
REALTIME_API_KEY = get("AZURE_OPENAI_API_KEY")
REALTIME_DEPLOYMENT = get("AZURE_OPENAI_REALTIME_DEPLOYMENT", "gpt-realtime")
REALTIME_VOICE = get("AZURE_OPENAI_REALTIME_VOICE", "alloy")

WALLPAPER_DIR = Path(get("WALLPAPER_DIR") or (_PROJECT_ROOT / "artifacts" / "wallpapers"))
