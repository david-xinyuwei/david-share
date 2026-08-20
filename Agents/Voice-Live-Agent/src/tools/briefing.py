"""新闻简报：抓真实新闻，交给 Azure OpenAI 归纳成结构化简报。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .. import aoai
from . import tool
from .news import fetch_headlines

_SYSTEM_PROMPT = (
    "你是一名资深新闻编辑。基于给定的新闻条目撰写一份中文简报。"
    "要求：1) 开头一句话总览；2) 按主题分 3-5 个要点，每个要点两句以内并标注来源媒体；"
    "3) 结尾给出一句值得关注的趋势判断。只使用给定条目中的事实，不要杜撰。"
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
    description="抓取最新新闻并整理成一份结构化简报。用户说整理新闻简报、总结今天的新闻时调用。",
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "简报主题，例如 人工智能、科技。留空表示综合新闻。"},
            "limit": {"type": "integer", "description": "纳入简报的新闻条数，默认 10，最多 20"},
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

    # gpt-5.x 系列只接受默认 temperature，显式传值会 400
    response = aoai.client().chat.completions.create(
        model=aoai.chat_deployment(),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"简报主题：{topic or '综合新闻'}\n\n新闻条目：\n{source_block}"},
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
