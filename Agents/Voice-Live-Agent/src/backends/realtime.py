"""Azure OpenAI Realtime 后端：直连 gpt-realtime 模型部署，走 GA 的 /openai/v1 端点。

与 Voice Live 的差异：这里没有 Azure 语音层，降噪、回声消除和中文语义 VAD 都不可用，
音色只能用模型原生 voice。作为对照路径，用来向客户说明两条路线的取舍。
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from azure.identity.aio import AzureCliCredential
from openai import AsyncOpenAI

from .. import tools
from ..agent_core import INSTRUCTIONS, ToolCallCoordinator, to_json
from ..audio import SAMPLE_RATE, AudioProcessor
from ..events import emit

logger = logging.getLogger(__name__)

TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

EVT_SESSION_UPDATED = "session.updated"
EVT_SPEECH_STARTED = "input_audio_buffer.speech_started"
EVT_INPUT_TRANSCRIPTION_DONE = "conversation.item.input_audio_transcription.completed"
EVT_RESPONSE_CREATED = "response.created"
EVT_AUDIO_DELTA = "response.output_audio.delta"
EVT_AUDIO_TRANSCRIPT_DONE = "response.output_audio_transcript.done"
EVT_ITEM_ADDED = "conversation.item.added"
EVT_FUNCTION_ARGS_DONE = "response.function_call_arguments.done"
EVT_RESPONSE_DONE = "response.done"
EVT_ERROR = "error"


def build_session(voice: str, instructions: str = INSTRUCTIONS) -> dict[str, Any]:
    return {
        "type": "realtime",
        "instructions": instructions,
        "output_modalities": ["audio"],
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                "turn_detection": {
                    "type": "semantic_vad",
                    "create_response": True,
                    "interrupt_response": True,
                },
                "transcription": {"model": "whisper-1"},
            },
            "output": {
                "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                "voice": voice,
            },
        },
        "tools": [
            {
                "type": "function",
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["parameters"],
            }
            for spec in (dict(t) for t in tools.function_tools())
        ],
        "tool_choice": "auto",
    }


async def build_client(endpoint: str, api_key: str | None) -> tuple[AsyncOpenAI, dict[str, str]]:
    """GA Realtime 用 /openai/v1 端点，不带 api-version，所以走通用 client 而不是 AsyncAzureOpenAI。"""
    base_url = endpoint.rstrip("/") + "/openai/v1/"
    if api_key:
        logger.info("Realtime 使用 API key 认证")
        return AsyncOpenAI(base_url=base_url, api_key=api_key), {"api-key": api_key}

    logger.info("Realtime 使用 Azure CLI 令牌认证")
    async with AzureCliCredential() as credential:
        token = await credential.get_token(TOKEN_SCOPE)
    return AsyncOpenAI(base_url=base_url, api_key=token.token), {}


class RealtimeAgent:
    def __init__(self, endpoint: str, api_key: str | None, deployment: str, voice: str) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.deployment = deployment
        self.voice = voice
        self.connection = None
        self.audio: AudioProcessor | None = None
        self.calls = ToolCallCoordinator()
        self._active_response = False

    async def start(self) -> None:
        client, extra_headers = await build_client(self.endpoint, self.api_key)
        try:
            async with client.realtime.connect(
                model=self.deployment, extra_headers=extra_headers
            ) as connection:
                self.connection = connection
                self.audio = AudioProcessor(connection)
                await connection.session.update(session=build_session(self.voice))
                self.audio.start_playback()

                emit("status", f"已就绪 [Realtime / {self.deployment} / {self.voice}]")
                emit("status", "已注册工具：" + "、".join(tools.registered_names()))

                async for event in connection:
                    await self._handle_event(event)
        finally:
            if self.audio:
                self.audio.shutdown()
            await client.close()

    async def _handle_event(self, event) -> None:
        etype = event.type
        audio = self.audio
        assert audio is not None

        if etype == EVT_SESSION_UPDATED:
            logger.info("Realtime 会话就绪: %s", getattr(event.session, "id", ""))
            audio.start_capture()
            emit("status", "麦克风已打开，请开始说话")

        elif etype == EVT_SPEECH_STARTED:
            emit("status", "[听]")
            audio.skip_pending_audio()
            if self._active_response:
                try:
                    await self.connection.response.cancel()
                except Exception as exc:
                    if "no active response" not in str(exc).lower():
                        logger.warning("打断取消失败: %s", exc)

        elif etype == EVT_INPUT_TRANSCRIPTION_DONE:
            emit("user", event.transcript)

        elif etype == EVT_RESPONSE_CREATED:
            self._active_response = True

        elif etype == EVT_AUDIO_DELTA:
            # Realtime 的 delta 是 base64 文本，Voice Live SDK 那边已经是 bytes
            audio.queue_audio(base64.b64decode(event.delta))

        elif etype == EVT_AUDIO_TRANSCRIPT_DONE:
            emit("assistant", event.transcript)

        elif etype == EVT_ITEM_ADDED:
            if event.item.type == "function_call":
                self.calls.register(event.item.call_id, event.item.name, event.item.id)

        elif etype == EVT_FUNCTION_ARGS_DONE:
            self.calls.set_arguments(event.call_id, event.arguments)

        elif etype == EVT_RESPONSE_DONE:
            self._active_response = False
            if self.calls.has_pending:
                await self._return_tool_results()

        elif etype == EVT_ERROR:
            message = getattr(event.error, "message", str(event.error))
            if "no active response" in message.lower():
                logger.debug("忽略良性取消错误: %s", message)
            else:
                logger.error("Realtime 错误: %s", message)
                emit("error", message)

    async def _return_tool_results(self) -> None:
        for call in await self.calls.drain():
            await self.connection.conversation.item.create(
                item={
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": to_json(call.result),
                }
            )
        await self.connection.response.create()
