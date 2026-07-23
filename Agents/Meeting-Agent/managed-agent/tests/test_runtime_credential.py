from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_selects_azure_cli_credential() -> None:
    source = (ROOT / "scripts" / "start-ui.ps1").read_text(encoding="utf-8")

    assert '$env:MANAGED_AGENT_CREDENTIAL = "azure-cli"' in source
