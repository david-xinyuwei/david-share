"""Create a structured news briefing from live articles with Azure OpenAI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .. import aoai
from . import tool
from .news import fetch_headlines

_SYSTEM_PROMPT = (
    "You are a senior news editor. Write a Chinese briefing using only the supplied news items. "
    "Start with a one-sentence overview, organize three to five thematic points, keep each point "
    "to at most two sentences with the source publication named, and end with one noteworthy trend. "
    "Do not invent facts."
)


@dataclass
class Briefing:
    topic: str
    generated_at: str
    markdown: str
    article_count: int


_last: Briefing | None = None


def last_briefing() -> Briefing | None:
    return _last


@tool(
    name="create_news_briefing",
    description="Fetch current news and create a structured briefing when the user asks for a news summary.",
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Briefing topic, such as artificial intelligence or technology. Omit for general news."},
            "limit": {"type": "integer", "description": "Number of articles to include. The default is 10 and the maximum is 20."},
        },
        "required": [],
    },
)
async def create_news_briefing(topic: str | None = None, limit: int = 10) -> dict:
    global _last

    articles = await fetch_headlines(topic=topic, limit=limit)
    if not articles:
        return {"ok": False, "error": "未抓取到任何新闻条目"}

    source_block = "\n".join(
        f"{i}. [{a['source']}] {a['title']}\n   {a['summary']}\n   {a['link']}"
        for i, a in enumerate(articles, start=1)
    )

    # GPT-5.x accepts only the default temperature; an explicit value returns HTTP 400.
    response = aoai.client().chat.completions.create(
        model=aoai.chat_deployment(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Briefing topic: {topic or 'general news'}\n\nNews items:\n{source_block}"},
        ],
    )
    markdown = response.choices[0].message.content or ""

    _last = Briefing(
        topic=topic or "综合新闻",
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        markdown=markdown,
        article_count=len(articles),
    )

    return {
        "topic": _last.topic,
        "generated_at": _last.generated_at,
        "article_count": _last.article_count,
        "briefing": markdown,
        "hint": "简报已生成并暂存，可直接调用 send_email 并设置 include_last_briefing=true 发送全文。",
    }
