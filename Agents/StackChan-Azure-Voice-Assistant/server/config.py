"""Configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Azure Speech ----------
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")  # optional, leave empty for Entra token auth
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastasia")
AZURE_SPEECH_RESOURCE_ID = os.getenv("AZURE_SPEECH_RESOURCE_ID", "")  # for Entra auth
AZURE_SPEECH_VOICE = os.getenv(
    "AZURE_SPEECH_VOICE", "zh-CN-XiaoxiaoMultilingualNeural"
)
AZURE_SPEECH_LANGUAGE = os.getenv("AZURE_SPEECH_LANGUAGE", "zh-CN")

# ---------- Azure OpenAI ----------
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")  # optional, leave empty for Entra token auth
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_STT_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_STT_DEPLOYMENT", "gpt-4o-mini-transcribe"
)
AZURE_OPENAI_TTS_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_TTS_DEPLOYMENT", "gpt-4o-mini-tts"
)
AZURE_OPENAI_AUDIO_API_VERSION = os.getenv(
    "AZURE_OPENAI_AUDIO_API_VERSION", "2025-04-01-preview"
)
AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
)

# ---------- Server ----------
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))

# ---------- Audio (XiaoZhi protocol defaults) ----------
# Device uplink: XiaoZhi sends microphone audio as 16 kHz mono Opus frames.
OPUS_SAMPLE_RATE = 16000
OPUS_CHANNELS = 1
OPUS_FRAME_DURATION_MS = 60       # matches device OPUS_FRAME_DURATION_MS
OPUS_FRAME_SIZE = OPUS_SAMPLE_RATE * OPUS_FRAME_DURATION_MS // 1000  # 960 samples

# Server downlink: Azure OpenAI TTS returns 24 kHz PCM; XiaoZhi can accept
# server-advertised Opus downlink at 24 kHz and resample on-device if needed.
TTS_SAMPLE_RATE = int(os.getenv("TTS_SAMPLE_RATE", "24000"))
TTS_FRAME_SIZE = TTS_SAMPLE_RATE * OPUS_FRAME_DURATION_MS // 1000    # 960 samples
