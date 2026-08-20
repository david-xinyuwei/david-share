"""Voice Live 后端：Azure 托管的 speech-to-speech，自带降噪、回声消除与中文语义 VAD。"""

from __future__ import annotations

import logging
from typing import Union

from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioInputTranscriptionOptions,
    AudioNoiseReduction,
    AzureSemanticVadMultilingual,
    AzureStandardVoice,
    FunctionCallOutputItem,
    InputAudioFormat,
    ItemType,
    Modality,
    OutputAudioFormat,
    RequestSession,
    ServerEventType,
    ToolChoiceLiteral,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import AzureCliCredential

from .. import tools
from ..agent_core import INSTRUCTIONS, ToolCallCoordinator, to_json
from ..audio import AudioProcessor
from ..events import emit

logger = logging.getLogger(__name__)


def build_credential(api_key: str | None) -> Union[AzureKeyCredential, AsyncTokenCredential]:
    if api_key:
        logger.info("Voice Live 使用 API key 认证")
        return AzureKeyCredential(api_key)
    logger.info("Voice Live 使用 Azure CLI 令牌认证")
    return AzureCliCredential()


def _echo_cancellation() -> AudioEchoCancellation:
    """远程桌面下播放延迟常超过服务端内部参考的 2s 假设，改由客户端上报真实播放信号。"""
    from ..audio import _live_reference_enabled

    if _live_reference_enabled():
        return AudioEchoCancellation(
            type="server_echo_cancellation", reference_source="client", channels=2
        )
    return AudioEchoCancellation()


def build_session(voice: str, instructions: str = INSTRUCTIONS) -> RequestSession:
    return RequestSession(
        modalities=[Modality.TEXT, Modality.AUDIO],
        instructions=instructions,
        voice=AzureStandardVoice(name=voice) if "-" in voice else voice,
        input_audio_format=InputAudioFormat.PCM16,
        output_audio_format=OutputAudioFormat.PCM16,
        turn_detection=AzureSemanticVadMultilingual(
            threshold=0.7,
            prefix_padding_ms=400,
            silence_duration_ms=700,
            speech_duration_ms=250,
            languages=["zh", "en"],
            remove_filler_words=True,
            # 回声由客户端动态门限拦在上行之前（见 audio.py），这里必须保持灵敏：
            # speech_duration_ms 调高会把「你好」这类短词整个吞掉，只剩残缺尾音被误识。
            interrupt_response=True,
        ),
        input_audio_echo_cancellation=_echo_cancellation(),
        input_audio_noise_reduction=AudioNoiseReduction(type="azure_deep_noise_suppression"),
        input_audio_transcription=AudioInputTranscriptionOptions(model="whisper-1"),
        tools=tools.function_tools(),
        tool_choice=ToolChoiceLiteral.AUTO,
    )


class VoiceLiveAgent:
    def __init__(
        self,
        endpoint: str,
        credential: Union[AzureKeyCredential, AsyncTokenCredential],
        model: str,
        voice: str,
    ) -> None:
        self.endpoint = endpoint
        self.credential = credential
        self.model = model
        self.voice = voice
        self.connection = None
        self.audio: AudioProcessor | None = None
        self.calls = ToolCallCoordinator()
        self._active_response = False

    async def start(self) -> None:
        try:
            async with connect(
                endpoint=self.endpoint, credential=self.credential, model=self.model
            ) as connection:
                self.connection = connection
                self.audio = AudioProcessor(connection)
                await self._setup_session()
                self.audio.start_playback()

                emit("status", f"已就绪 [Voice Live / {self.model} / {self.voice}]")
                emit("status", "已注册工具：" + "、".join(tools.registered_names()))

                async for event in connection:
                    await self._handle_event(event)
        finally:
            if self.audio:
                self.audio.shutdown()

    async def _setup_session(self) -> None:
        await self.connection.session.update(session=build_session(self.voice))
        logger.info("Voice Live 会话配置已发送，工具数=%d", len(tools.registered_names()))

    async def _handle_event(self, event) -> None:
        etype = event.type
        audio = self.audio
        assert audio is not None

        if etype == ServerEventType.SESSION_UPDATED:
            logger.info("会话就绪: %s", event.session.id)
            audio.start_capture()
            emit("status", "麦克风已打开，请开始说话")

        elif etype == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
            emit("status", "[听]")
            audio.skip_pending_audio()
            if self._active_response:
                try:
                    await self.connection.response.cancel()
                except Exception as exc:
                    if "no active response" not in str(exc).lower():
                        logger.warning("打断取消失败: %s", exc)

        elif etype == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
            emit("user", event.transcript)

        elif etype == ServerEventType.RESPONSE_CREATED:
            self._active_response = True

        elif etype == ServerEventType.RESPONSE_AUDIO_DELTA:
            audio.queue_audio(event.delta)

        elif etype == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
            emit("assistant", event.transcript)

        elif etype == ServerEventType.CONVERSATION_ITEM_CREATED:
            if event.item.type == ItemType.FUNCTION_CALL:
                self.calls.register(event.item.call_id, event.item.name, event.item.id)

        elif etype == ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
            self.calls.set_arguments(event.call_id, event.arguments)

        elif etype == ServerEventType.RESPONSE_DONE:
            self._active_response = False
            if self.calls.has_pending:
                await self._return_tool_results()

        elif etype == ServerEventType.ERROR:
            message = event.error.message
            if "Cancellation failed: no active response" in message:
                logger.debug("忽略良性取消错误: %s", message)
            else:
                logger.error("Voice Live 错误: %s", message)
                emit("error", message)

    async def _return_tool_results(self) -> None:
        for call in await self.calls.drain():
            await self.connection.conversation.item.create(
                previous_item_id=call.item_id,
                item=FunctionCallOutputItem(call_id=call.call_id, output=to_json(call.result)),
            )
        await self.connection.response.create()
