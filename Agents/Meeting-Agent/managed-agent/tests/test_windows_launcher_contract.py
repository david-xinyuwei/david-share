from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_uses_loopback_private_runtime_and_cli_credential() -> None:
    source = (ROOT / "scripts" / "start-ui.ps1").read_text(encoding="utf-8")

    assert '.services.ai.azure.com' in source
    assert "IsDefaultPort" in source
    assert "UserInfo" in source
    assert 'MANAGED_AGENT_CREDENTIAL = "azure-cli"' in source
    assert 'Join-Path $env:LOCALAPPDATA "ManagedMeetingAgent\\runtime"' in source
    assert 'http://127.0.0.1:$BackendPort/readiness' in source
