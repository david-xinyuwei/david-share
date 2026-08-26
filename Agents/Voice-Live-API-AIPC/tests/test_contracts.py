from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src import tools
from src.backends.voicelive import build_session
from src.tools import desktop, mailer, power, stocks, timezone, wallpaper


CORE_TOOLS = {
    "create_news_briefing",
    "get_current_time",
    "get_system_volume",
    "set_system_volume",
    "set_system_mute",
    "open_windows_app",
    "send_email",
    "get_news_headlines",
    "get_screen_brightness",
    "set_screen_brightness",
    "get_power_mode",
    "set_power_mode",
    "get_power_timeouts",
    "set_power_timeout",
    "get_stock_quote",
    "set_system_timezone",
    "open_camera",
    "close_camera",
    "identify_object_with_camera",
    "search_where_to_buy",
    "search_wallpaper_image",
    "set_desktop_wallpaper",
    "get_weather",
    "web_search",
}


def test_default_registry_has_24_real_tools() -> None:
    assert set(tools.registered_names()) == CORE_TOOLS
    assert len(tools.function_tools()) == 24


def test_voice_live_session_contract() -> None:
    session = build_session("zh-CN-XiaoxiaoMultilingualNeural")
    assert session.input_audio_transcription.model == "gpt-4o-transcribe"
    assert session.input_audio_transcription.language == "zh-CN"
    assert len(session.tools or []) == 24
    assert "2.1" not in str(session)


def test_dispatch_rejects_unknown_tool() -> None:
    result = asyncio.run(tools.dispatch("not_a_real_tool", {}))
    assert result == {"ok": False, "error": "未注册的工具: not_a_real_tool"}


def test_lenient_tool_arguments_are_still_an_object() -> None:
    assert tools._parse_arguments('{location: "Seattle",}') == {"location": "Seattle"}
    with pytest.raises(ValueError):
        tools._parse_arguments("[1, 2, 3]")


def test_mail_recipient_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAIL_ALLOWED_RECIPIENTS", "user@example.com")
    assert mailer._validate("user at example dot com") == "user@example.com"
    with pytest.raises(PermissionError):
        mailer._validate("other@example.com")


def test_stock_provider_symbol_mapping() -> None:
    assert stocks._tencent_symbol("MSFT") == "usMSFT"
    assert stocks._tencent_symbol("0992.HK") == "hk00992"
    assert stocks._tencent_symbol("^GSPC") == "usINX"


def test_wallpaper_candidate_prefers_downloadable_path() -> None:
    item = type(
        "ImageResult",
        (),
        {
            "url": "https://example.com/",
            "contentUrl": "",
            "thumbnailUrl": "https://cdn.example.com/image.jpg",
        },
    )()
    assert wallpaper._download_candidates(item)[0].endswith("image.jpg")


def test_power_timeout_path_is_in_process() -> None:
    assert callable(power._read_power_value)
    assert callable(power._write_power_value)
    assert not hasattr(power, "_powercfg")


def test_windows_app_resolution_ignores_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    system_root = tmp_path / "Windows"
    trusted = system_root / "System32" / "calc.exe"
    malicious = tmp_path / "malicious" / "calc.exe"
    trusted.parent.mkdir(parents=True)
    malicious.parent.mkdir()
    trusted.write_bytes(b"trusted")
    malicious.write_bytes(b"malicious")
    monkeypatch.setenv("SystemRoot", str(system_root))
    monkeypatch.setenv("PATH", str(malicious.parent))

    assert desktop._resolve_system_executable(Path("System32", "calc.exe")) == trusted.resolve()


def test_powershell_resolution_ignores_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    system_root = tmp_path / "Windows"
    trusted = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    malicious = tmp_path / "malicious" / "powershell.exe"
    trusted.parent.mkdir(parents=True)
    malicious.parent.mkdir()
    trusted.write_bytes(b"trusted")
    malicious.write_bytes(b"malicious")
    monkeypatch.setenv("SystemRoot", str(system_root))
    monkeypatch.setenv("PATH", str(malicious.parent))

    assert power._powershell_exe() == str(trusted.resolve())
    assert timezone._powershell_exe() == str(trusted.resolve())


def test_power_settings_proof_uses_trusted_taskkill(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    system_root = tmp_path / "Windows"
    trusted = system_root / "System32" / "taskkill.exe"
    malicious = tmp_path / "malicious" / "taskkill.exe"
    trusted.parent.mkdir(parents=True)
    malicious.parent.mkdir()
    trusted.write_bytes(b"trusted")
    malicious.write_bytes(b"malicious")
    monkeypatch.setenv("SystemRoot", str(system_root))
    monkeypatch.setenv("PATH", str(malicious.parent))
    launches: list[list[str]] = []
    monkeypatch.setattr(
        power.subprocess,
        "run",
        lambda argv, **_kwargs: launches.append(argv),
    )
    monkeypatch.setattr(power.os, "startfile", lambda _uri: None, raising=False)

    assert power._open_power_settings_refreshed() is True
    assert launches == [[str(trusted.resolve()), "/IM", "SystemSettings.exe", "/F"]]
