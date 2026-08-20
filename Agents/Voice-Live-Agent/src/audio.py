"""麦克风采集与扬声器播放。结构沿用 Azure VoiceLive 官方示例的三线程模型。"""

from __future__ import annotations

import asyncio
import array
import base64
import logging
import queue
import threading
import time
from collections import deque
from typing import Optional

import pyaudio

logger = logging.getLogger(__name__)

SAMPLE_RATE = 24000
CHANNELS = 1
CHUNK_SIZE = 1200  # 50ms
_PEAK_FULL_SCALE = 9000.0  # 普通说话音量就能推满波形，不用 32768 满量程
_ECHO_GUARD_SECONDS = 2.0  # 助手说完后的屏蔽时长；远程桌面回声到达很晚，窗口短了就会把自己的声音当成提问
_ECHO_ACTIVE_LEVEL = 0.008  # 尾音很轻也要算作正在播放，否则保护窗口会提前结束
_ECHO_SUPPRESS_RATIO = 1.6  # 回声总比原声小，要求麦克风电平高于播放峰值才算真人抢话
_BARGE_IN_FLOOR = 0.28  # 同时要达到绝对音量下限，避免环境噪声与远处人声误触发打断
_PLAYBACK_PEAK_DECAY = 0.88  # 播放峰值逐帧衰减，让门限在助手说完后平滑降回常规灵敏度
_BARGE_IN_CONSECUTIVE_FRAMES = 3  # 单帧尖峰不算抢话，连续超阈值才确认，避免抖动误打断
_BARGE_IN_RELEASE_FRAMES = 6  # 确认后需连续低于保持阈值才退出，防止说话停顿被判定为结束
_BARGE_IN_HOLD_RATIO = 0.65  # 施密特迟滞：确认后放宽阈值，避免在门限附近反复进出
_BARGE_IN_PREBUFFER_FRAMES = 4  # 确认打断时补发这些帧，否则确认期被静音的字头会丢失
_REF_BUFFER_MAX_BYTES = SAMPLE_RATE * 2 // 2  # 0.5s；超出说明采集与播放已漂移，丢旧数据重对齐


def _live_reference_enabled() -> bool:
    from . import config

    raw = (config.get("AUDIO_LIVE_REFERENCE_AEC", "true") or "true").lower()
    return raw not in ("false", "0", "no")


def _interleave(mic: bytes, ref: bytes) -> bytes:
    """按 Live-Reference AEC 要求交错：每对采样先麦克风后播放参考。"""
    m = array.array("h")
    m.frombytes(mic[: len(mic) // 2 * 2])
    r = array.array("h")
    ref = ref[: len(m) * 2]
    r.frombytes(ref[: len(ref) // 2 * 2])
    if len(r) < len(m):
        r.extend([0] * (len(m) - len(r)))
    stereo = array.array("h", bytes(len(m) * 4))
    stereo[0::2] = m
    stereo[1::2] = r
    return stereo.tobytes()


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
        self._barge_in_active = False
        self._barge_in_candidate_frames = 0
        self._barge_in_release_counter = 0
        self._prebuffer: deque[bytes] = deque(maxlen=_BARGE_IN_PREBUFFER_FRAMES)
        self.live_reference = _live_reference_enabled()
        if self.live_reference:
            # 服务端拿到真实播放参考后自己做 AEC，再静音上行反而会掩盖真人抢话。
            self.half_duplex = False
        self._ref_buffer = bytearray()
        self._ref_lock = threading.Lock()

    def _reset_barge_in(self) -> None:
        self._barge_in_active = False
        self._barge_in_candidate_frames = 0
        self._barge_in_release_counter = 0
        self._prebuffer.clear()

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

        def _send(data: bytes) -> None:
            if self.live_reference:
                with self._ref_lock:
                    ref = bytes(self._ref_buffer[: len(data)])
                    del self._ref_buffer[: len(data)]
                data = _interleave(data, ref)
            audio_base64 = base64.b64encode(data).decode("utf-8")
            asyncio.run_coroutine_threadsafe(
                self.connection.input_audio_buffer.append(audio=audio_base64), self.loop
            )

        def _callback(in_data, _frame_count, _time_info, _status_flags):
            level = _peak_level(in_data)
            if self.half_duplex and time.monotonic() < self._mute_input_until:
                # 保护窗口内不一刀切静音：回声总比原始播放小，真人抢话则能越过门限。
                gate = max(_BARGE_IN_FLOOR, self._playback_peak * _ECHO_SUPPRESS_RATIO)
                if self._barge_in_active:
                    hold = max(_BARGE_IN_FLOOR * _BARGE_IN_HOLD_RATIO, gate * _BARGE_IN_HOLD_RATIO)
                    if level >= hold:
                        self._barge_in_release_counter = 0
                    else:
                        self._barge_in_release_counter += 1
                        if self._barge_in_release_counter >= _BARGE_IN_RELEASE_FRAMES:
                            self._reset_barge_in()
                elif level >= gate:
                    self._barge_in_candidate_frames += 1
                    if self._barge_in_candidate_frames >= _BARGE_IN_CONSECUTIVE_FRAMES:
                        # 不清 _mute_input_until：保护窗口继续计时，放行与否改由状态机决定，
                        # 这样用户说完停顿后能自动退回回声保护，迟滞释放才有意义。
                        self._barge_in_active = True
                        self._barge_in_release_counter = 0
                        while self._prebuffer:  # 补发确认期被静音的帧，否则字头丢失
                            _send(self._prebuffer.popleft())
                else:
                    self._barge_in_candidate_frames = 0

                if self._barge_in_active:
                    self.echo_guarded = False
                    self.input_level = level
                else:
                    self.echo_guarded = True
                    self.input_level = 0.0
                    self._prebuffer.append(in_data)
                    in_data = b"\x00" * len(in_data)  # 保持音频流连续，只是不把回声传上去
            else:
                self._reset_barge_in()
                self.echo_guarded = False
                self.input_level = level
            _send(in_data)
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
                if self.live_reference:
                    with self._ref_lock:
                        self._ref_buffer.extend(out)
                        if len(self._ref_buffer) > _REF_BUFFER_MAX_BYTES:
                            del self._ref_buffer[:-_REF_BUFFER_MAX_BYTES]
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
