from __future__ import annotations

import os
from pathlib import Path

import pytest

from src import graph_mail


def test_cache_write_is_atomic_and_secured_before_replace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / ".msal_token_cache.json"
    secured: list[Path] = []
    monkeypatch.setattr(graph_mail, "_CACHE_PATH", target)
    monkeypatch.setattr(graph_mail, "_restrict_cache_file", lambda path: secured.append(path))

    graph_mail._write_cache_text('{"token":"new"}')

    assert target.read_text(encoding="utf-8") == '{"token":"new"}'
    assert len(secured) == 1
    assert secured[0] != target
    assert not secured[0].exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_cache_acl_failure_preserves_existing_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / ".msal_token_cache.json"
    target.write_text('{"token":"old"}', encoding="utf-8")
    monkeypatch.setattr(graph_mail, "_CACHE_PATH", target)

    def reject_acl(_path: Path) -> None:
        raise RuntimeError("acl failure")

    monkeypatch.setattr(graph_mail, "_restrict_cache_file", reject_acl)

    with pytest.raises(RuntimeError, match="acl failure"):
        graph_mail._write_cache_text('{"token":"new"}')

    assert target.read_text(encoding="utf-8") == '{"token":"old"}'
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL validation")
def test_windows_cache_acl_keeps_current_user_access(tmp_path: Path) -> None:
    cache = tmp_path / ".msal_token_cache.json"
    cache.write_text("before", encoding="utf-8")
    injected = graph_mail.subprocess.run(
        [
            str(graph_mail._trusted_system_tool("icacls.exe")),
            str(cache),
            "/grant:r",
            "*S-1-5-32-544:(F)",
            "*S-1-3-4:(F)",
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert injected.returncode == 0

    graph_mail._restrict_cache_file(cache)
    graph_mail._assert_cache_file_secure(cache)
    cache.write_text("after", encoding="utf-8")

    assert cache.read_text(encoding="utf-8") == "after"


def test_insecure_primary_cache_is_rejected_before_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / ".msal_token_cache.json"
    target.write_text("credential", encoding="utf-8")
    monkeypatch.setattr(graph_mail, "_CACHE_PATH", target)
    monkeypatch.setattr(
        graph_mail,
        "_assert_cache_file_secure",
        lambda _path: (_ for _ in ()).throw(PermissionError("insecure")),
    )

    with pytest.raises(PermissionError, match="insecure"):
        graph_mail._read_cache_text()


def test_insecure_fallback_cache_is_not_migrated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "target" / ".msal_token_cache.json"
    fallback = tmp_path / "legacy" / ".msal_token_cache.json"
    fallback.parent.mkdir()
    fallback.write_text("credential", encoding="utf-8")
    writes: list[str] = []
    monkeypatch.setattr(graph_mail, "_CACHE_PATH", target)
    monkeypatch.setattr(graph_mail, "_fallback_cache_paths", lambda: [fallback])
    monkeypatch.setattr(
        graph_mail,
        "_assert_cache_file_secure",
        lambda _path: (_ for _ in ()).throw(PermissionError("insecure fallback")),
    )
    monkeypatch.setattr(graph_mail, "_write_cache_text", writes.append)

    with pytest.raises(PermissionError, match="insecure fallback"):
        graph_mail._read_cache_text()

    assert writes == []
    assert not target.exists()


def test_secure_fallback_is_migrated_and_revalidated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "target" / ".msal_token_cache.json"
    fallback = tmp_path / "legacy" / ".msal_token_cache.json"
    fallback.parent.mkdir()
    fallback.write_text("credential", encoding="utf-8")
    validated: list[Path] = []
    monkeypatch.setattr(graph_mail, "_CACHE_PATH", target)
    monkeypatch.setattr(graph_mail, "_fallback_cache_paths", lambda: [fallback])
    monkeypatch.setattr(graph_mail, "_assert_cache_file_secure", validated.append)
    monkeypatch.setattr(graph_mail, "_restrict_cache_file", lambda _path: None)

    assert graph_mail._read_cache_text() == "credential"
    assert target.read_text(encoding="utf-8") == "credential"
    assert validated == [fallback, target]


def test_sddl_validator_accepts_only_current_user_and_system() -> None:
    sid = "S-1-12-1-1-2-3-4"
    graph_mail._validate_cache_sddl(
        f"D:PAI(A;;FA;;;SY)(A;;FA;;;{sid})",
        sid,
    )

    with pytest.raises(PermissionError):
        graph_mail._validate_cache_sddl(
            f"D:PAI(A;;FA;;;BU)(A;;FA;;;{sid})",
            sid,
        )
    with pytest.raises(PermissionError):
        graph_mail._validate_cache_sddl(
            f"D:AI(A;;FA;;;SY)(A;;FA;;;{sid})",
            sid,
        )
    with pytest.raises(PermissionError):
        graph_mail._validate_cache_sddl(
            f"D:PAI(A;ID;FA;;;SY)(A;;FA;;;{sid})",
            sid,
        )


def test_sddl_validator_maps_local_administrator_only_to_current_500_sid() -> None:
    administrator_sid = "S-1-5-21-1-2-3-500"
    graph_mail._validate_cache_sddl(
        "D:PAI(A;;FA;;;SY)(A;;FA;;;LA)",
        administrator_sid,
    )

    with pytest.raises(PermissionError):
        graph_mail._validate_cache_sddl(
            "D:PAI(A;;FA;;;SY)(A;;FA;;;LA)",
            "S-1-5-21-1-2-3-1001",
        )
    with pytest.raises(PermissionError):
        graph_mail._validate_cache_sddl(
            "D:PAI(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;LA)",
            administrator_sid,
        )
