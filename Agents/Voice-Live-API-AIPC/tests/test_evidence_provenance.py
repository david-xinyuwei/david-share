from __future__ import annotations

from pathlib import Path

from scripts.evidence_provenance import canonical_sha256_file, source_snapshot


def test_source_snapshot_is_deterministic_and_excludes_runtime_outputs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('one')\n", encoding="utf-8")
    (tmp_path / "evidence").mkdir()
    generated = tmp_path / "evidence" / "publication-validation.json"
    generated.write_text("{}", encoding="utf-8")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "app.exe").write_bytes(b"runtime")

    first = source_snapshot(tmp_path)
    generated.write_text('{"changed":true}', encoding="utf-8")
    (tmp_path / "dist" / "app.exe").write_bytes(b"different runtime")
    second = source_snapshot(tmp_path)

    assert first == second
    assert first["file_count"] == 1

    (tmp_path / "src" / "app.py").write_text("print('two')\n", encoding="utf-8")
    assert source_snapshot(tmp_path)["sha256"] != first["sha256"]


def test_text_hash_is_independent_of_windows_line_endings(tmp_path: Path) -> None:
    text = tmp_path / "config.yml"
    text.write_bytes(b"name: test\r\nvalue: one\r\n")
    windows_hash = canonical_sha256_file(text)
    windows_snapshot = source_snapshot(tmp_path)

    text.write_bytes(b"name: test\nvalue: one\n")

    assert canonical_sha256_file(text) == windows_hash
    assert source_snapshot(tmp_path) == windows_snapshot
