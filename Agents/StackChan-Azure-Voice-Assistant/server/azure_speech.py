"""Azure Speech integration via OpenAI-compatible APIs (Whisper STT + GPT-4o-mini-TTS).

Uses Entra token auth (AzureCliCredential). No Speech SDK, no API key needed.
All STT/TTS calls go through the Azure OpenAI endpoint.
"""
import io
import logging
import wave
from typing import Optional

import httpx
from azure.identity import AzureCliCredential

import config

logger = logging.getLogger(__name__)

_credential = AzureCliCredential()
_base = config.AZURE_OPENAI_ENDPOINT.rstrip("/")


def _get_token() -> str:
    return _credential.get_token(
        "https://cognitiveservices.azure.com/.default"
    ).token


def _pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw 16-bit mono PCM in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _normalize_whisper_language(lang: str) -> Optional[str]:
    """Normalize language code for Whisper.

    Whisper accepts short codes like 'zh' and 'en'.
    """
    if not lang:
        return None
    lang = lang.strip().lower()
    if not lang:
        return None
    if "-" in lang:
        lang = lang.split("-", 1)[0]
    return lang


def _transcribe_once(wav_data: bytes, language: Optional[str]) -> str:
    """Single Whisper transcription request."""
    deployment = config.AZURE_OPENAI_STT_DEPLOYMENT
    url = (
        f"{_base}/openai/deployments/{deployment}/audio/transcriptions"
        f"?api-version={config.AZURE_OPENAI_AUDIO_API_VERSION}"
    )

    data = {"model": deployment}
    if language:
        data["language"] = language

    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {_get_token()}"},
        files={"file": ("audio.wav", wav_data, "audio/wav")},
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()


# ---------------------------------------------------------------------------
# STT — Whisper via Azure OpenAI
# ---------------------------------------------------------------------------
def recognize_speech(pcm_data: bytes) -> str:
    """Transcribe audio via Azure OpenAI Whisper.

    Accepts either raw 16-bit mono PCM or a complete WAV file.
    Blocking — run via ``asyncio.to_thread``.
    """
    if pcm_data[:4] == b"RIFF":
        wav_data = pcm_data  # already WAV
    else:
        wav_data = _pcm_to_wav(pcm_data, config.OPUS_SAMPLE_RATE)
    try:
        # Pass 1: user-configured language hint (faster and often more accurate)
        lang = _normalize_whisper_language(config.AZURE_SPEECH_LANGUAGE)
        text = _transcribe_once(wav_data, language=lang)
        if text:
            logger.info("STT OK: %s", text)
            return text

        # Pass 2 fallback: auto language detection
        text = _transcribe_once(wav_data, language=None)
        if text:
            logger.info("STT OK (fallback): %s", text)
            return text

        logger.warning("STT empty after retry")
        return ""
    except Exception as exc:
        logger.error("STT error: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# TTS — gpt-4o-mini-tts via Azure OpenAI
# ---------------------------------------------------------------------------
def synthesize_speech(text: str) -> bytes:
    """Synthesize text to raw PCM via Azure OpenAI TTS.

    Returns raw 24 kHz 16-bit mono PCM bytes.  Blocking.
    """
    deployment = config.AZURE_OPENAI_TTS_DEPLOYMENT
    url = (
        f"{_base}/openai/deployments/{deployment}/audio/speech"
        f"?api-version={config.AZURE_OPENAI_AUDIO_API_VERSION}"
    )

    try:
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {_get_token()}",
                "Content-Type": "application/json",
            },
            json={
                "model": deployment,
                "input": text,
                "voice": "alloy",
                "response_format": "pcm",
            },
            timeout=30,
        )
        resp.raise_for_status()
        pcm = resp.content
        logger.info("TTS OK: %d bytes PCM", len(pcm))
        return pcm
    except Exception as exc:
        logger.error("TTS error: %s", exc)
        return b""
