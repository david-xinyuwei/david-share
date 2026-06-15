"""Opus encode / decode wrappers around libopus via opuslib."""
import logging
import opuslib

logger = logging.getLogger(__name__)


class OpusDecoder:
    """Decode device-uploaded Opus frames to 16-bit PCM."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_size = sample_rate * 60 // 1000  # 960 samples for 60 ms
        self._dec = opuslib.Decoder(sample_rate, channels)

    def decode(self, opus_data: bytes) -> bytes | None:
        """Return raw PCM bytes (16-bit LE) or None on error."""
        try:
            return self._dec.decode(opus_data, self.frame_size)
        except opuslib.OpusError as exc:
            logger.warning("Opus decode error: %s", exc)
            return None


class OpusEncoder:
    """Encode server PCM (TTS output) to Opus frames for the device."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_size = sample_rate * 60 // 1000  # 960 samples
        self._enc = opuslib.Encoder(
            sample_rate, channels, opuslib.APPLICATION_AUDIO
        )

    def encode_all(self, pcm_data: bytes) -> list[bytes]:
        """Chop PCM into 60 ms frames and return a list of Opus packets."""
        bytes_per_frame = self.frame_size * self.channels * 2  # 16-bit = 2 B
        # pad tail to frame boundary
        remainder = len(pcm_data) % bytes_per_frame
        if remainder:
            pcm_data += b"\x00" * (bytes_per_frame - remainder)

        frames: list[bytes] = []
        for offset in range(0, len(pcm_data), bytes_per_frame):
            chunk = pcm_data[offset : offset + bytes_per_frame]
            try:
                frames.append(self._enc.encode(chunk, self.frame_size))
            except opuslib.OpusError as exc:
                logger.warning("Opus encode error at offset %d: %s", offset, exc)
        return frames
