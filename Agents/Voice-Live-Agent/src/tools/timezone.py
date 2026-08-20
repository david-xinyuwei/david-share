"""修改 Windows 系统时区。

语音里说的是「西雅图」「洛杉矶」这类城市，Windows 认的却是 "Pacific Standard Time" 这类时区 ID，
所以这里做一层城市到时区 ID 的映射，并允许模型直接传标准 ID。
"""

from __future__ import annotations

import logging
import subprocess

from . import tool

logger = logging.getLogger(__name__)

# 覆盖 Demo 常用城市；其余情况允许模型直接传 Windows 时区 ID。
_CITY_TO_TIMEZONE = {
    "北京": "China Standard Time",
    "上海": "China Standard Time",
    "中国": "China Standard Time",
    "深圳": "China Standard Time",
    "香港": "China Standard Time",
    "台北": "Taipei Standard Time",
    "东京": "Tokyo Standard Time",
    "日本": "Tokyo Standard Time",
    "首尔": "Korea Standard Time",
    "新加坡": "Singapore Standard Time",
    "西雅图": "Pacific Standard Time",
    "旧金山": "Pacific Standard Time",
    "洛杉矶": "Pacific Standard Time",
    "硅谷": "Pacific Standard Time",
    "温哥华": "Pacific Standard Time",
    "丹佛": "Mountain Standard Time",
    "芝加哥": "Central Standard Time",
    "纽约": "Eastern Standard Time",
    "华盛顿": "Eastern Standard Time",
    "多伦多": "Eastern Standard Time",
    "伦敦": "GMT Standard Time",
    "巴黎": "W. Europe Standard Time",
    "柏林": "W. Europe Standard Time",
    "阿姆斯特丹": "W. Europe Standard Time",
    "莫斯科": "Russian Standard Time",
    "迪拜": "Arabian Standard Time",
    "悉尼": "AUS Eastern Standard Time",
    "印度": "India Standard Time",
    "新德里": "India Standard Time",
}


def _powershell(script: str) -> str:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "").strip() or "PowerShell 执行失败")
    return (result.stdout or "").strip()


def _resolve_timezone_id(target: str) -> str:
    text = target.strip()
    for city, tz_id in _CITY_TO_TIMEZONE.items():
        if city in text:
            return tz_id

    # 允许直接给 Windows 时区 ID，先确认系统确实认识它。
    listed = _powershell(
        "Get-TimeZone -ListAvailable | Where-Object { $_.Id -eq "
        f"'{text.replace(chr(39), chr(39) * 2)}' }} | Select-Object -ExpandProperty Id"
    )
    if listed:
        return listed.splitlines()[0].strip()

    raise ValueError(
        f"认不出「{target}」对应的时区。可以说城市名（如 西雅图、北京、纽约），"
        "或直接给 Windows 时区 ID（如 Pacific Standard Time）。"
    )


@tool(
    name="set_system_timezone",
    description=(
        "修改这台 Windows 电脑的系统时区。用户说把时区改成某个城市、切到某地时间时调用。"
        "只改时区，不改具体时刻。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "目标城市或 Windows 时区 ID，例如 西雅图、北京、Pacific Standard Time",
            }
        },
        "required": ["target"],
    },
)
def set_system_timezone(target: str) -> dict:
    timezone_id = _resolve_timezone_id(target)
    before = _powershell("(Get-TimeZone).Id")

    escaped = timezone_id.replace("'", "''")
    _powershell(f"Set-TimeZone -Id '{escaped}' -ErrorAction Stop")

    after = _powershell("(Get-TimeZone).Id")
    if after != timezone_id:
        raise RuntimeError(f"时区设置未生效，当前仍是 {after}")

    now = _powershell("Get-Date -Format 'yyyy-MM-dd HH:mm'")
    logger.info("系统时区: %s -> %s", before, after)
    return {
        "previous_timezone": before,
        "timezone": after,
        "local_time_now": now,
        "message": f"系统时区已从 {before} 改为 {after}，当前本地时间 {now}",
    }
