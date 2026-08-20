"""新闻抓取，数据源为可配置的真实 RSS feed。"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from xml.etree import ElementTree

import httpx

from .. import config
from . import tool

_TIMEOUT = httpx.Timeout(15.0)
_DEFAULT_FEEDS = [
    "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]
_TAG_RE = re.compile(r"<[^>]+>")


def feed_urls() -> list[str]:
    return config.get_list("NEWS_FEEDS") or _DEFAULT_FEEDS


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return html.unescape(_TAG_RE.sub("", text)).replace("\xa0", " ").strip()


def _published(item: ElementTree.Element) -> datetime | None:
    raw = item.findtext("pubDate")
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


async def fetch_headlines(topic: str | None = None, limit: int = 8) -> list[dict]:
    """抓取 RSS 头条。topic 非空时改用 Google News 的主题检索 feed。"""
    limit = max(1, min(int(limit), 20))
    if topic:
        urls = [
            "https://news.google.com/rss/search"
            f"?q={quote_plus(topic)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        ]
    else:
        urls = feed_urls()

    articles: list[dict] = []
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; LenovoVoiceAgent/1.0)"})
                resp.raise_for_status()
                root = ElementTree.fromstring(resp.content)
            except (httpx.HTTPError, ElementTree.ParseError) as exc:
                errors.append(f"{url} -> {type(exc).__name__}: {exc}")
                continue

            for item in root.iterfind(".//item"):
                published = _published(item)
                articles.append(
                    {
                        "title": _clean(item.findtext("title")),
                        "link": item.findtext("link") or "",
                        "source": _clean(item.findtext("source")) or url,
                        "summary": _clean(item.findtext("description"))[:400],
                        "published": published.astimezone(timezone.utc).isoformat() if published else None,
                    }
                )

    if not articles and errors:
        raise RuntimeError("所有新闻源都抓取失败: " + "; ".join(errors))

    articles.sort(key=lambda a: a["published"] or "", reverse=True)
    return articles[:limit]


@tool(
    name="get_news_headlines",
    description="获取最新新闻头条，可按主题检索。用户问新闻、最近发生了什么、某个话题的报道时调用。",
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "新闻主题关键词，例如 人工智能、联想。留空表示综合头条。"},
            "limit": {"type": "integer", "description": "返回条数，默认 8，最多 20"},
        },
        "required": [],
    },
)
async def get_news_headlines(topic: str | None = None, limit: int = 8) -> dict:
    articles = await fetch_headlines(topic=topic, limit=limit)
    return {"topic": topic or "综合头条", "count": len(articles), "articles": articles}
