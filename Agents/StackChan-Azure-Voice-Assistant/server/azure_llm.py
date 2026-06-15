"""Azure OpenAI GPT integration with emotion detection.

Supports two auth modes:
  1. Key-based: set AZURE_OPENAI_KEY in .env
  2. Entra token: leave AZURE_OPENAI_KEY empty
     (uses DefaultAzureCredential from az login / Managed Identity)
"""
import json
import logging

from openai import AzureOpenAI

import config

logger = logging.getLogger(__name__)


def _build_client() -> AzureOpenAI:
    if config.AZURE_OPENAI_KEY:
        return AzureOpenAI(
            api_key=config.AZURE_OPENAI_KEY,
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        )

    from azure.identity import AzureCliCredential, get_bearer_token_provider

    credential = AzureCliCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_ad_token_provider=token_provider,
        api_version=config.AZURE_OPENAI_API_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    )


_client = _build_client()

SYSTEM_PROMPT = """\
你是一个名叫 StackChan 的桌面 AI 陪伴机器人。性格友善、活泼、有点萌，喜欢跟用户聊天。

回复要求：
1. 用中文回复，简洁自然，像朋友聊天
2. 每次回复控制在 2-3 句话以内
3. 根据对话内容判断当前情绪

你必须用以下 JSON 格式回复（不要输出其他内容）：
{"text": "你的回复内容", "emotion": "情绪"}

可用的 emotion 值：happy, sad, surprised, angry, neutral, laughing, shy, confused
"""

# Emotion values that the StackChan expression engine supports.
VALID_EMOTIONS = {
    "happy", "sad", "surprised", "angry",
    "neutral", "laughing", "shy", "confused",
}


def chat(user_text: str, history: list[dict]) -> tuple[str, str]:
    """Send *user_text* (with conversation *history*) to GPT-4o.

    Returns ``(reply_text, emotion)``.  Blocking — run via
    ``asyncio.to_thread``.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    try:
        resp = _client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=0.7,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or ""
        logger.info("LLM raw: %s", raw)

        data = json.loads(raw)
        text = data.get("text", "嗯，我没听清楚呢")
        emotion = data.get("emotion", "neutral")
        if emotion not in VALID_EMOTIONS:
            emotion = "neutral"
        return text, emotion

    except (json.JSONDecodeError, KeyError):
        content = raw if "raw" in dir() else ""
        return content or "嗯，我没听清楚呢", "neutral"
    except Exception as exc:
        logger.error("LLM error: %s", exc)
        return "抱歉，我现在有点累了，稍后再聊吧", "sad"
