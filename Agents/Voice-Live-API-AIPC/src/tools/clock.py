"""时间与时区查询。"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from . import tool

_CITY_ALIASES = {
    "北京": "Asia/Shanghai",
    "上海": "Asia/Shanghai",
    "中国": "Asia/Shanghai",
    "香港": "Asia/Hong_Kong",
    "台北": "Asia/Taipei",
    "东京": "Asia/Tokyo",
    "首尔": "Asia/Seoul",
    "新加坡": "Asia/Singapore",
    "伦敦": "Europe/London",
    "巴黎": "Europe/Paris",
    "柏林": "Europe/Berlin",
    "莫斯科": "Europe/Moscow",
    "纽约": "America/New_York",
    "西雅图": "America/Los_Angeles",
    "旧金山": "America/Los_Angeles",
    "洛杉矶": "America/Los_Angeles",
    "芝加哥": "America/Chicago",
    "悉尼": "Australia/Sydney",
    "迪拜": "Asia/Dubai",
    "班加罗尔": "Asia/Kolkata",
}


def _resolve(timezone: str | None) -> ZoneInfo | None:
    if not timezone or timezone.lower() == "local":
        return None
    if timezone in _CITY_ALIASES:
        return ZoneInfo(_CITY_ALIASES[timezone])
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        lowered = timezone.replace(" ", "_").lower()
        for name in available_timezones():
            if name.lower() == lowered or name.lower().endswith("/" + lowered):
                return ZoneInfo(name)
        raise ValueError(f"无法识别的时区: {timezone}")


@tool(
    name="get_current_time",
    description="查询指定时区或城市的当前日期时间。用户问几点了、时差、某地现在几点时调用。",
    parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA 时区名如 Asia/Shanghai，或中文城市名如 北京、纽约。留空表示本机时区。",
            }
        },
        "required": [],
    },
)
def get_current_time(timezone: str | None = None) -> dict:
    zone = _resolve(timezone)
    now = datetime.now(zone) if zone else datetime.now().astimezone()
    # Windows 的 locale codec 无法编码中文格式串，日期用 f-string 拼接而不是 strftime
    return {
        "timezone": str(now.tzinfo),
        "iso": now.isoformat(timespec="seconds"),
        "date": f"{now.year}年{now.month}月{now.day}日",
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        "time": now.strftime("%H:%M"),
        "utc_offset": now.strftime("%z"),
    }
