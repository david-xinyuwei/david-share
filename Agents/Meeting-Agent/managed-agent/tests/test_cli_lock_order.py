from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_constructs_analyzer_inside_output_lock() -> None:
    source = (ROOT / "src" / "meeting_agent" / "cli.py").read_text(encoding="utf-8")

    lock_index = source.index("with FileLock")
    analyzer_index = source.index("analyzer = ManagedAgentAnalyzer()")
    assert lock_index < analyzer_index
