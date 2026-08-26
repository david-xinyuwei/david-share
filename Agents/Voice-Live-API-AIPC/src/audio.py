"""麦克风采集与扬声器播放。结构沿用 Azure VoiceLive 官方示例的三线程模型。"""

from __future__ import annotations

import asyncio
import array
import base64
import logging
import queue
import time
from typing import Optional

import pyaudio

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000
CHANNELS = 1
CHUNK_SIZE = 1200  # 50ms
_PEAK_FULL_SCALE = 9000.0  # 普通说话音量就能推满波形，不用 32768 满量程
_ECHO_GUARD_SECONDS = 1.0  # 助手说完后的屏蔽时长。调到 2s 能拦住远程桌面的晚到回声，
# 但用户接话的前 2s 也会被吃掉，体感上就是「必须停顿很久才能说话」。
_ECHO_ACTIVE_LEVEL = 0.008  # 尾音很轻也要算作正在播放，否则保护窗口会提前结束
_ECHO_SUPPRESS_RATIO = 1.15  # 回声总比原声小，要求麦克风电平高于播放峰值才算真人抢话
_BARGE_IN_FLOOR = 0.28  # 同时要达到绝对音量下限，避免环境噪声与远处人声误触发打断
_PLAYBACK_PEAK_DECAY = 0.88  # 播放峰值逐帧衰减，让门限在助手说完后平滑降回常规灵敏度


def _half_duplex_enabled() -> bool:
    from . import config

    raw = (config.get("AUDIO_HALF_DUPLEX", "true") or "true").lower()
    return raw not in ("false", "0", "no")


def _peak_level(data: bytes) -> float:
    if not data:
        return 0.0
    samples = array.array("h")
    samples.frombytes(data[: len(data) // 2 * 2])
    if not samples:
        return 0.0
    return min(1.0, max(abs(s) for s in samples) / _PEAK_FULL_SCALE)


class AudioProcessor:
    """PCM16 / 24kHz / 单声道，符合 Voice Live 的音频要求。

    half_duplex 为真时，助手出声期间发送静音帧：远程桌面、外放扬声器等场景下，
    服务端回声消除拿不到本地回环，不屏蔽就会把自己的声音当成用户插话。
    代价是失去这段时间的打断能力；戴耳机或设备自带回声消除时可关闭。
    """

    class Packet:
        def __init__(self, seq_num: int, data: Optional[bytes]):
            self.seq_num = seq_num
            self.data = data

    def __init__(self, connection):
        self.connection = connection
        self.audio = pyaudio.PyAudio()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.input_stream: Optional[pyaudio.Stream] = None
        self.output_stream: Optional[pyaudio.Stream] = None
        self.playback_queue: queue.Queue[AudioProcessor.Packet] = queue.Queue()
        self.playback_base = 0
        self.next_seq_num = 0
        self.input_level = 0.0
        self.output_level = 0.0
        self.half_duplex = _half_duplex_enabled()
        self.echo_guarded = False
        self._mute_input_until = 0.0
        self._playback_peak = 0.0
        self._muted_frames = 0
        self._muted_peak = 0.0

    def _report_muted(self, gate: float) -> None:
        """屏蔽结束时报一次：峰值接近门限说明吹掉的是真人说话，不是回声。"""
        if not self._muted_frames:
            return
        logger.info(
            "[gate] 屏蔽 %dms, 期间峰值 %.3f, 门限 %.3f",
            self._muted_frames * CHUNK_SIZE * 1000 // SAMPLE_RATE,
            self._muted_peak,
            gate,
        )
        self._muted_frames = 0
        self._muted_peak = 0.0

    @staticmethod
    def check_devices() -> None:
        audio = pyaudio.PyAudio()
        try:
            inputs = [
                i
                for i in range(audio.get_device_count())
                if (audio.get_device_info_by_index(i).get("maxInputChannels") or 0) > 0
            ]
            outputs = [
                i
                for i in range(audio.get_device_count())
                if (audio.get_device_info_by_index(i).get("maxOutputChannels") or 0) > 0
            ]
        finally:
            audio.terminate()
        if not inputs:
            raise RuntimeError("未检测到麦克风输入设备")
        if not outputs:
            raise RuntimeError("未检测到音频输出设备")

    def start_capture(self) -> None:
        if self.input_stream:
            return
        self.loop = asyncio.get_event_loop()

        def _callback(in_data, _frame_count, _time_info, _status_flags):
            level = _peak_level(in_data)
            if self.half_duplex and time.monotonic() < self._mute_input_until:
                # 保护窗口内不一刀切静音：回声总比原始播放小，真人抢话则能越过门限。
                gate = max(_BARGE_IN_FLOOR, self._playback_peak * _ECHO_SUPPRESS_RATIO)
                if level >= gate:
                    self._report_muted(gate)
                    self._mute_input_until = 0.0
                    self._playback_peak = 0.0
                    self.echo_guarded = False
                    self.input_level = level
                else:
                    self._muted_frames += 1
                    self._muted_peak = max(self._muted_peak, level)
                    self.echo_guarded = True
                    self.input_level = 0.0
                    in_data = b"\x00" * len(in_data)  # 保持音频流连续，只是不把回声传上去
            else:
                if self._muted_frames:
                    self._report_muted(max(_BARGE_IN_FLOOR, self._playback_peak * _ECHO_SUPPRESS_RATIO))
                self.echo_guarded = False
                self.input_level = level
            audio_base64 = base64.b64encode(in_data).decode("utf-8")
            asyncio.run_coroutine_threadsafe(
                self.connection.input_audio_buffer.append(audio=audio_base64), self.loop
            )
            return (None, pyaudio.paContinue)

        self.input_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            stream_callback=_callback,
        )
        logger.info("麦克风采集已启动")

    def start_playback(self) -> None:
        if self.output_stream:
            return

        remaining = bytes()

        def _callback(_in_data, frame_count, _time_info, _status_flags):
            nonlocal remaining
            frame_count *= pyaudio.get_sample_size(pyaudio.paInt16)

            out = remaining[:frame_count]
            remaining = remaining[frame_count:]

            while len(out) < frame_count:
                try:
                    packet = self.playback_queue.get_nowait()
                except queue.Empty:
                    out += bytes(frame_count - len(out))
                    continue

                if not packet or not packet.data:
                    break
                if packet.seq_num < self.playback_base:
                    remaining = bytes()
                    continue

                take = frame_count - len(out)
                out += packet.data[:take]
                remaining = packet.data[take:]

            if len(out) >= frame_count:
                level = _peak_level(out)
                self.output_level = level
                self._playback_peak = max(self._playback_peak * _PLAYBACK_PEAK_DECAY, level)
                if level > _ECHO_ACTIVE_LEVEL:
                    self._mute_input_until = time.monotonic() + _ECHO_GUARD_SECONDS
                return (out, pyaudio.paContinue)
            self.output_level = 0.0
            return (out, pyaudio.paComplete)

        self.output_stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            output=True,
            frames_per_buffer=CHUNK_SIZE,
            stream_callback=_callback,
        )
        logger.info("音频播放已就绪")

    def _next_seq(self) -> int:
        seq = self.next_seq_num
        self.next_seq_num += 1
        return seq

    def queue_audio(self, data: Optional[bytes]) -> None:
        self.playback_queue.put(AudioProcessor.Packet(self._next_seq(), data))

    def skip_pending_audio(self) -> None:
        """用户插话时丢弃尚未播放的助手音频。"""
        self.playback_base = self._next_seq()

    def shutdown(self) -> None:
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
        if self.output_stream:
            self.skip_pending_audio()
            self.queue_audio(None)
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
        self.audio.terminate()
        logger.info("音频资源已释放")
