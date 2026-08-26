"""Voice Live Agent 后端：连 Azure AI Foundry 里托管的 Agent，而不是直连模型。

与 voicelive.py 的唯一区别是「谁来编排」：
- voicelive.py  connect(model=...)       提示词和工具都由客户端在 session 里下发
- 本文件        connect(agent_name=...)  Agent 托管在云端，多端共享同一套人设

事件处理、工具执行、音频链路全部复用父类，确保两种模式行为一致。
"""

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
    InputAudioFormat,
    Modality,
    OutputAudioFormat,
    RequestSession,
    ServerEventType,
    ToolChoiceLiteral,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential

from .. import tools
from ..audio import AudioProcessor
from ..events import emit
from .voicelive import VoiceLiveAgent, _echo_cancellation

logger = logging.getLogger(__name__)


def build_agent_credential() -> AsyncTokenCredential:
    """Foundry Agent 模式服务端拒绝 API Key（"Key authentication is not supported"），只能用 Entra。"""
    from azure.identity.aio import AzureCliCredential

    logger.info("Voice Live Agent 使用 Entra 令牌认证（Agent 模式不支持 Key）")
    return AzureCliCredential()


def build_agent_session(voice: str, with_tools: bool = False) -> RequestSession:
    """Agent 模式下服务端两条硬约束（均为实测得出）：

    - instructions 不能下发，人设以 Agent 里配的为准
    - tools 不能运行时下发（"Configuring tools at runtime ... is not supported"），
      必须写在 agent definition 里；客户端仍然负责接 function call 并执行
    """
    session = RequestSession(
        modalities=[Modality.TEXT, Modality.AUDIO],
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
            interrupt_response=True,
        ),
        input_audio_echo_cancellation=_echo_cancellation(),
        input_audio_noise_reduction=AudioNoiseReduction(type="azure_deep_noise_suppression"),
        input_audio_transcription=AudioInputTranscriptionOptions(
            model="azure-speech", language="zh-CN"
        ),
    )
    if with_tools:
        session.tools = tools.function_tools()
        session.tool_choice = ToolChoiceLiteral.AUTO
    return session


class VoiceLiveFoundryAgent(VoiceLiveAgent):
    """连接 Foundry 托管 Agent；工具仍在本机执行，因此桌面操作能力与直连模式一致。"""

    def __init__(
        self,
        endpoint: str,
        credential: Union[AzureKeyCredential, AsyncTokenCredential],
        agent_name: str,
        project_name: str,
        voice: str,
        agent_version: str | None = None,
    ) -> None:
        super().__init__(endpoint=endpoint, credential=credential, model="", voice=voice)
        self.agent_name = agent_name
        self.project_name = project_name
        self.agent_version = agent_version
        self._tools_accepted = True

    async def start(self) -> None:
        try:
            async with connect(
                endpoint=self.endpoint,
                credential=self.credential,
                agent_name=self.agent_name,
                project_name=self.project_name,
                agent_version=self.agent_version,
            ) as connection:
                self.connection = connection
                self.audio = AudioProcessor(connection)
                await self._setup_session()
                self.audio.start_playback()

                emit("status", f"已就绪 [Voice Live Agent / {self.agent_name} @ {self.project_name}]")
                emit("status", "工具由 Foundry Agent 定义，调用仍在本机执行："
                               + "、".join(tools.registered_names()))

                async for event in connection:
                    await self._handle_event(event)
        finally:
            if self.audio:
                self.audio.shutdown()

    async def _setup_session(self) -> None:
        await self.connection.session.update(session=build_agent_session(self.voice))
        logger.info("Agent 会话配置已发送（工具由 Agent definition 提供）")

    async def _handle_event(self, event) -> None:
        logger.info("[agent-event] %s", event.type)
        await super()._handle_event(event)

        # Agent 模式下服务端不会在用户说完后自动生成回复，需要客户端显式触发。
        if event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED and not self._active_response:
            try:
                await self.connection.response.create()
                logger.info("[agent-event] response.create 已发送")
            except Exception as exc:
                logger.warning("[agent-event] response.create 失败: %s", exc)
