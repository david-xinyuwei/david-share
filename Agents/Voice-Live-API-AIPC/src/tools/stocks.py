"""股票行情，数据源为 Yahoo Finance chart 接口（真实实时报价，无需 API key）。"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from . import tool

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_TENCENT_URL = "https://qt.gtimg.cn/q={symbol}"
_TIMEOUT = httpx.Timeout(10.0)
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_TENCENT_FALLBACK_STATUSES = {401, 403, 429}
_TENCENT_INDEX_SYMBOLS = {
    "^GSPC": "usINX",
    "^IXIC": "usIXIC",
    "^DJI": "usDJI",
    "^HSI": "hkHSI",
}

_ALIASES = {
    "苹果": "AAPL", "apple": "AAPL",
    "微软": "MSFT", "microsoft": "MSFT",
    "英伟达": "NVDA", "nvidia": "NVDA",
    "谷歌": "GOOGL", "google": "GOOGL",
    "亚马逊": "AMZN", "amazon": "AMZN",
    "特斯拉": "TSLA", "tesla": "TSLA",
    "meta": "META", "脸书": "META",
    "台积电": "TSM",
    "联想": "0992.HK", "lenovo": "0992.HK",
    "腾讯": "0700.HK", "阿里巴巴": "9988.HK", "小米": "1810.HK",
    "标普500": "^GSPC", "标普": "^GSPC", "sp500": "^GSPC",
    "纳斯达克": "^IXIC", "nasdaq": "^IXIC",
    "道琼斯": "^DJI", "道指": "^DJI",
    "恒生指数": "^HSI", "恒指": "^HSI",
    "上证指数": "000001.SS", "上证": "000001.SS",
    "深证成指": "399001.SZ",
}


def _normalize(symbol: str) -> str:
    key = symbol.strip()
    return _ALIASES.get(key.lower(), _ALIASES.get(key, key.upper()))


def _tencent_symbol(ticker: str) -> str | None:
    if ticker in _TENCENT_INDEX_SYMBOLS:
        return _TENCENT_INDEX_SYMBOLS[ticker]

    for suffix, prefix, width in ((".HK", "hk", 5), (".SS", "sh", 6), (".SZ", "sz", 6)):
        if ticker.endswith(suffix):
            code = ticker[: -len(suffix)]
            return f"{prefix}{code.zfill(width)}" if code.isdigit() else None

    if ticker and ticker[0].isalpha() and all(char.isalnum() or char in ".-" for char in ticker):
        return f"us{ticker.replace('-', '.')}"
    return None


def _number(value: str) -> int | float | None:
    if not value:
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


async def _get_tencent_quote(client: httpx.AsyncClient, ticker: str, requested: str) -> dict:
    provider_symbol = _tencent_symbol(ticker)
    if not provider_symbol:
        return {"ok": False, "error": f"备用行情源不支持代码 {ticker}"}

    response = await client.get(_TENCENT_URL.format(symbol=provider_symbol))
    response.raise_for_status()
    text = response.content.decode("gb18030").strip()
    _, separator, payload = text.partition('="')
    if not separator or not payload.endswith('";'):
        return {"ok": False, "error": f"备用行情源未返回有效数据: {ticker}"}

    fields = payload[:-2].split("~")
    if len(fields) <= 34:
        return {"ok": False, "error": f"备用行情源未找到代码 {ticker}"}

    price = _number(fields[3])
    if price is None:
        return {"ok": False, "error": f"{ticker} 无最新成交价"}

    market = provider_symbol[:2]
    currency = {"us": "USD", "hk": "HKD", "sh": "CNY", "sz": "CNY"}.get(market)
    exchange = {"us": "US", "hk": "Hong Kong", "sh": "Shanghai", "sz": "Shenzhen"}.get(
        market
    )
    quoted_at = fields[30].replace("/", "-") if fields[30] else None
    return {
        "symbol": ticker,
        "name": fields[1] or requested,
        "currency": currency,
        "exchange": exchange,
        "price": price,
        "previous_close": _number(fields[4]),
        "change": _number(fields[31]),
        "change_percent": _number(fields[32]),
        "day_high": _number(fields[33]),
        "day_low": _number(fields[34]),
        "volume": _number(fields[6]),
        "quoted_at": quoted_at,
        "source": "Tencent Stock Quote",
    }


@tool(
    name="get_stock_quote",
    description="查询股票或股指的最新行情。用户问股价、涨跌、大盘时调用。",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "股票代码或公司名，例如 MSFT、苹果、纳斯达克、0992.hk",
            }
        },
        "required": ["symbol"],
    },
)
async def get_stock_quote(symbol: str) -> dict:
    ticker = _normalize(symbol)
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
        resp = await client.get(
            _CHART_URL.format(symbol=ticker), params={"range": "1d", "interval": "1d"}
        )

        if resp.status_code in _TENCENT_FALLBACK_STATUSES:
            return await _get_tencent_quote(client, ticker, symbol)

    if resp.status_code == 404:
        return {"ok": False, "error": f"未找到代码 {ticker} 对应的行情，请确认股票代码"}
    resp.raise_for_status()

    chart = resp.json().get("chart") or {}
    if chart.get("error"):
        return {"ok": False, "error": f"行情接口返回错误: {chart['error']}"}
    results = chart.get("result")
    if not results:
        return {"ok": False, "error": f"未返回行情数据: {ticker}"}

    meta = results[0]["meta"]
    price = meta.get("regularMarketPrice")
    previous_close = meta.get("chartPreviousClose") or meta.get("previousClose")
    if price is None:
        return {"ok": False, "error": f"{ticker} 无最新成交价"}

    change = round(price - previous_close, 4) if previous_close else None
    change_pct = round(change / previous_close * 100, 2) if change is not None and previous_close else None
    market_time = meta.get("regularMarketTime")

    return {
        "symbol": meta.get("symbol", ticker),
        "name": meta.get("longName") or meta.get("shortName") or symbol,
        "currency": meta.get("currency"),
        "exchange": meta.get("fullExchangeName"),
        "price": price,
        "previous_close": previous_close,
        "change": change,
        "change_percent": change_pct,
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "volume": meta.get("regularMarketVolume"),
        "quoted_at": (
            datetime.fromtimestamp(market_time, tz=timezone.utc).isoformat(timespec="seconds")
            if market_time
            else None
        ),
        "source": "Yahoo Finance",
    }
