"""display server 端点测试（非硬件 integration）。

用 FastAPI TestClient，mock 掉刷屏（push_to_panel）和网络（download_image），
验证 HTTP 层 + 处理链 + 当前图落盘的完整路径，不依赖 Pi 硬件。
"""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server import app as app_module
from server import display


@pytest.fixture
def client(tmp_path, monkeypatch):
    # 状态目录指向 tmp；刷屏替换成 no-op（记录被调用）
    monkeypatch.setenv("EINK_STATE_DIR", str(tmp_path / "state"))
    pushed = {}

    def fake_push(path):
        pushed["path"] = str(path)

    monkeypatch.setattr(display, "push_to_panel", fake_push)
    c = TestClient(app_module.app)
    c._pushed = pushed
    return c


def _png_bytes(size=(900, 700), color="red") -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_state_empty(client):
    r = client.get("/api/state")
    assert r.status_code == 200
    assert r.json()["has_current"] is False


def test_display_via_upload(client):
    r = client.post(
        "/api/display",
        files={"file": ("x.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["width"] == 1200 and body["height"] == 1600
    assert "path" in client._pushed          # 刷屏被调用
    # 当前图已落盘
    assert client.get("/api/state").json()["has_current"] is True


def test_display_via_url(client, monkeypatch):
    monkeypatch.setattr(display, "download_image", lambda url, timeout=15: _png_bytes())
    r = client.post("/api/display", data={"url": "http://example.com/a.png"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert "path" in client._pushed


def test_display_requires_input(client):
    r = client.post("/api/display")
    assert r.status_code == 400


def test_display_rejects_garbage(client):
    r = client.post(
        "/api/display",
        files={"file": ("x.png", b"not an image", "image/png")},
    )
    assert r.status_code == 400


def test_display_url_download_failure(client, monkeypatch):
    def boom(url, timeout=15):
        raise ValueError("boom")

    monkeypatch.setattr(display, "download_image", boom)
    r = client.post("/api/display", data={"url": "http://x/y.png"})
    assert r.status_code == 400
