"""天气查询，数据源为 Open-Meteo 公开 API（真实实时数据，无需 API key）。"""

from __future__ import annotations

import httpx

from . import tool

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = httpx.Timeout(10.0)

# Open-Meteo WMO weather code
_WMO = {
    0: "晴", 1: "多云转晴", 2: "局部多云", 3: "阴",
    45: "有雾", 48: "冻雾",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪",
    80: "阵雨", 81: "强阵雨", 82: "暴雨",
    85: "阵雪", 86: "强阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "强雷阵雨伴冰雹",
}


@tool(
    name="get_weather",
    description="Get current weather and a three-day forecast for a city.",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name, such as Beijing, Seattle, or Tokyo."},
        },
        "required": ["location"],
    },
)
async def get_weather(location: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        geo_resp = await client.get(
            _GEOCODE_URL, params={"name": location, "count": 1, "language": "zh", "format": "json"}
        )
        geo_resp.raise_for_status()
        results = geo_resp.json().get("results")
        if not results:
            return {"ok": False, "error": f"未找到城市: {location}"}
        place = results[0]

        forecast_resp = await client.get(
            _FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 3,
            },
        )
        forecast_resp.raise_for_status()
        data = forecast_resp.json()

    current = data["current"]
    daily = data["daily"]
    return {
        "location": f"{place['name']}, {place.get('country', '')}".strip(", "),
        "observed_at": current["time"],
        "temperature_c": current["temperature_2m"],
        "feels_like_c": current["apparent_temperature"],
        "humidity_pct": current["relative_humidity_2m"],
        "wind_speed_kmh": current["wind_speed_10m"],
        "condition": _WMO.get(current["weather_code"], f"weather_code={current['weather_code']}"),
        "forecast": [
            {
                "date": daily["time"][i],
                "condition": _WMO.get(daily["weather_code"][i], str(daily["weather_code"][i])),
                "high_c": daily["temperature_2m_max"][i],
                "low_c": daily["temperature_2m_min"][i],
                "precipitation_probability_pct": daily["precipitation_probability_max"][i],
            }
            for i in range(len(daily["time"]))
        ],
        "source": "Open-Meteo",
    }
