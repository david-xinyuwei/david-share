from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agentignore_excludes_local_state_and_secrets() -> None:
    lines = set((ROOT / ".agentignore").read_text(encoding="utf-8").splitlines())

    assert {".azure/", "runtime/", "logs/", "password.txt", ".env"} <= lines
