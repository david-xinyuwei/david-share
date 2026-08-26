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

from .. import confirmation, tools
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
    """服务端默认参考信号。客户端上报参考（Live-Reference AEC）需双声道严格时间对齐，
    本实现无时间戳对齐，实测会把真人语音当回声消掉导致识别率下降，因此不启用。"""
    return AudioEchoCancellation()


def build_session(voice: str, instructions: str = INSTRUCTIONS) -> RequestSession:
    return RequestSession(
        modalities=[Modality.TEXT, Modality.AUDIO],
        instructions=instructions,
        voice=AzureStandardVoice(name=voice) if "-" in voice else voice,
        input_audio_format=InputAudioFormat.PCM16,
        output_audio_format=OutputAudioFormat.PCM16,
        turn_detection=AzureSemanticVadMultilingual(
            # silence 调到 500ms 会把长句从句中换气处切断，只识别前半句；
            # speech 调到 150ms 会让键盘声、咳嗽触发一次误判分段。这组是实测可用值。
            threshold=0.7,
            prefix_padding_ms=400,
            silence_duration_ms=700,
            speech_duration_ms=250,
            languages=["zh", "en"],  # 中文里夹英文词（calculator、weather）也要能断句
            remove_filler_words=True,
            interrupt_response=True,
        ),
        input_audio_echo_cancellation=_echo_cancellation(),
        input_audio_noise_reduction=AudioNoiseReduction(type="azure_deep_noise_suppression"),
        # 这一项只决定「UI 上显示的用户文字」，不参与模型理解和工具决策。
        # 选型依据（官方兼容表）：azure-speech 面向非多模态模型和 Agent，
        # gpt-4o-transcribe 才是给 gpt-realtime / gpt-realtime-mini 用的；
        # 本模式 chat model 是 gpt-realtime，因此用 gpt-4o-transcribe。
        #
        # 已知缺陷（2026-08-23 实测，未解决）：同一场会话里 gpt-4o-transcribe 会把部分
        # 短句判成别的语种并输出对应文字，33 条中 6 条跑偏：'Usiamolo.'（意）、
        # '사랑.'（韩）、'On repart sur.'（法）、'上圖。'（繁），用户实拍还见过日文假名。
        # 跑偏集中在 3-14 字符的短句，长句正常。
        #
        # language 参数在这条路径上收敛不了它：逐个提交 zh / zh-CN / zh-Hans / zh-hans-CN，
        # 服务端一律回显 'zh'，即区域后缀被静默规范化掉。这里写 zh-CN 只是表明意图，
        # 不要以为它真的生效了，也不要再花时间调这个值。
        #
        # 影响范围仅限「UI 字幕偶尔显示错语种」：gpt-realtime 直接吃音频做理解与工具决策，
        # 实测转录成日文那次仍正确执行了用户的中文指令。
        # 真要根治得换 azure-speech（实测 zh-CN 不被降级且支持 phrase_list），
        # 但它在官方兼容表里面向非多模态模型，替换前必须先做真人 A/B 对比，不能凭配置好看就换。
        #
        # 这里不要加 phrase_list：SDK 能构造，但服务端实测明确拒绝整个 session.update——
        #   invalid_session_update_message: Value error, phrase_list is only supported for
        #   azure-mrs, mai-transcribe-1.5, azure-fast-transcription, mai-transcribe, azure-speech
        # 加了会导致会话配置失败、转录彻底不工作，比偶尔跑偏严重得多。
        # prompt 参数同理不可用：官方文档说 gpt-4o-transcribe 支持，但当前 SDK 版本
        # 不接受该 kwarg（TypeError）。升级 SDK 前两者都别再尝试。
        input_audio_transcription=AudioInputTranscriptionOptions(
            model="gpt-4o-transcribe",
            language="zh-CN",
        ),
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
            logger.info("[vad] speech_started")
            emit("status", "[听]")
            audio.skip_pending_audio()
            if self._active_response:
                try:
                    await self.connection.response.cancel()
                except Exception as exc:
                    if "no active response" not in str(exc).lower():
                        logger.warning("打断取消失败: %s", exc)

        elif etype == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
            # 只为诊断：VAD 检测不到语音结束时这条不会出现，是"完全不识别"的判据
            logger.info("[vad] speech_stopped")

        elif etype == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
            logger.info("[vad] transcript_chars=%d", len(event.transcript or ""))
            confirmation.note_user_turn(event.transcript)
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
