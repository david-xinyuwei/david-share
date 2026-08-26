from __future__ import annotations

import socket
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from src.tools import wallpaper


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
    ) -> None:
        self.status = status_code
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}
        self._chunks = list(chunks or [])

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name.lower(), default)

    def read(self, _amount: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


def _install_network(
    monkeypatch: pytest.MonkeyPatch,
    responder: Callable[[str], FakeResponse],
    addresses: dict[str, str | list[str]],
) -> list[str]:
    requests: list[str] = []

    def fake_getaddrinfo(host: str, port: int, **_kwargs: object):
        values = addresses.get(host, host)
        values = [values] if isinstance(values, str) else values
        results = []
        for address in values:
            family = socket.AF_INET6 if ":" in address else socket.AF_INET
            sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
            results.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr))
        return results

    @contextmanager
    def fake_open(url: str, pinned: tuple[str, ...], _headers: dict[str, str]):
        assert pinned
        requests.append(url)
        yield responder(url)

    monkeypatch.setattr(wallpaper.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(wallpaper, "_open_pinned_response", fake_open)
    return requests


@pytest.mark.parametrize(
    "target",
    [
        "https://127.0.0.1/image.png",
        "https://169.254.169.254/latest/meta-data",
        "https://10.1.2.3/image.png",
        "https://192.168.1.2/image.png",
        "https://100.64.0.1/image.png",
        "https://[::ffff:127.0.0.1]/image.png",
    ],
)
def test_redirect_to_non_public_address_is_blocked(
    monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    start = "https://safe.example/start"
    requests = _install_network(
        monkeypatch,
        lambda _url: FakeResponse(302, {"location": target}),
        {"safe.example": "93.184.216.34"},
    )

    with pytest.raises(PermissionError, match="非公网地址"):
        wallpaper._download_image(start)

    assert requests == [start]


def test_redirect_limit_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    start = "https://safe.example/start"
    requests = _install_network(
        monkeypatch,
        lambda _url: FakeResponse(
            302, {"location": f"https://safe.example/redirect-{len(requests) + 1}"}
        ),
        {"safe.example": "93.184.216.34"},
    )

    with pytest.raises(ValueError, match="重定向超过 5 次"):
        wallpaper._download_image(start)

    assert len(requests) == 6


def test_non_image_content_type_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    start = "https://safe.example/image"
    _install_network(
        monkeypatch,
        lambda _url: FakeResponse(200, {"content-type": "text/html"}, [b"<html>"]),
        {"safe.example": "93.184.216.34"},
    )

    with pytest.raises(ValueError, match="返回的不是图片"):
        wallpaper._download_image(start)


def test_invalid_image_magic_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    start = "https://safe.example/image"
    _install_network(
        monkeypatch,
        lambda _url: FakeResponse(200, {"content-type": "image/png"}, [b"not-an-image"]),
        {"safe.example": "93.184.216.34"},
    )

    with pytest.raises(ValueError, match="文件头不是"):
        wallpaper._download_image(start)


def test_public_redirect_downloads_valid_image(monkeypatch: pytest.MonkeyPatch) -> None:
    start = "https://safe.example/start"
    image_url = "https://cdn.example/image.png"
    image = b"\x89PNG\r\n\x1a\ncontent"

    def responder(url: str) -> FakeResponse:
        if url == start:
            return FakeResponse(302, {"location": image_url})
        return FakeResponse(200, {"content-type": "image/png"}, [image])

    requests = _install_network(
        monkeypatch,
        responder,
        {"safe.example": "93.184.216.34", "cdn.example": "93.184.216.35"},
    )

    assert wallpaper._download_image(start) == (image, ".png")
    assert requests == [start, image_url]


def test_mixed_public_and_non_global_dns_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    start = "https://mixed.example/image.png"
    _install_network(
        monkeypatch,
        lambda _url: FakeResponse(200, {"content-type": "image/png"}),
        {"mixed.example": ["93.184.216.34", "100.64.0.1"]},
    )

    with pytest.raises(PermissionError, match="非公网地址"):
        wallpaper._download_image(start)


def test_pinned_connection_uses_validated_ip_and_original_sni(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tcp_calls: list[tuple[tuple[str, int], float | None]] = []
    tls_calls: list[tuple[object, str]] = []
    raw_socket = object()
    wrapped_socket = object()

    def fake_create_connection(address, timeout, _source_address):
        tcp_calls.append((address, timeout))
        return raw_socket

    class FakeContext:
        def wrap_socket(self, sock, server_hostname):
            tls_calls.append((sock, server_hostname))
            return wrapped_socket

    monkeypatch.setattr(wallpaper.socket, "create_connection", fake_create_connection)
    connection = wallpaper._PinnedHTTPSConnection(
        "images.example", "93.184.216.34", timeout=20.0
    )
    connection._context = FakeContext()

    connection.connect()

    assert tcp_calls == [(('93.184.216.34', 443), 20.0)]
    assert tls_calls == [(raw_socket, "images.example")]
    assert connection.sock is wrapped_socket


def test_generated_image_url_uses_secure_downloader(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    generated_url = "https://cdn.example/generated.png"
    image = b"\x89PNG\r\n\x1a\ncontent"
    calls: list[str] = []
    result = SimpleNamespace(data=[SimpleNamespace(b64_json=None, url=generated_url)])
    fake_client = SimpleNamespace(images=SimpleNamespace(generate=lambda **_kwargs: result))

    monkeypatch.setattr(wallpaper.aoai, "client", lambda: fake_client)
    monkeypatch.setattr(wallpaper.aoai, "image_deployment", lambda: "image-deployment")
    monkeypatch.setattr(wallpaper, "_wallpaper_dir", lambda: tmp_path)
    monkeypatch.setattr(
        wallpaper,
        "_download_image",
        lambda url: (calls.append(url) or image, ".png"),
    )

    output = wallpaper.generate_wallpaper_image("mountain sunrise")

    assert calls == [generated_url]
    assert output["bytes"] == len(image)
    assert Path(output["image_path"]).read_bytes() == image
