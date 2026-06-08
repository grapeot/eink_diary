"""pipeline.run_once offline 测试：mock 各步，重点验 moderation 重试 + 推送逻辑。"""

from __future__ import annotations

import io
import json

import pytest

from eink_diary import pipeline


@pytest.fixture(autouse=True)
def _stub_collect_and_synth(monkeypatch, tmp_path):
    # collect/format/synthesize 都 stub 掉，不碰真实数据源
    from datetime import datetime

    monkeypatch.setattr(
        pipeline, "collect",
        lambda cfg, end=None, minutes=None: (datetime(2026, 6, 6, 8, 0), datetime(2026, 6, 6, 10, 0), []),
    )
    monkeypatch.setattr(pipeline, "format_text", lambda s, e, r, m: "素材文本")
    # config 有源
    monkeypatch.setattr(pipeline.Config, "from_env", classmethod(lambda cls: type("C", (), {"ai_sessions_repo": None, "enabled_sources": lambda self: ["wechat"]})()))
    monkeypatch.setattr(pipeline, "export_ai_sessions", lambda repo: None)
    monkeypatch.setattr(pipeline.SynthConfig, "from_env", classmethod(lambda cls: None))
    monkeypatch.setenv("EINK_SERVER_URL", "http://pi.test:8080")


def test_moderation_retry_then_success(monkeypatch):
    synth_calls = {"n": 0}

    def fake_synth(text, cfg, mode="moment"):
        synth_calls["n"] += 1
        return f"prompt v{synth_calls['n']}"

    monkeypatch.setattr(pipeline, "synthesize", fake_synth)

    gen_calls = {"n": 0}

    def fake_generate(**kw):
        gen_calls["n"] += 1
        if gen_calls["n"] == 1:
            raise RuntimeError("rejected by the safety system: moderation_blocked")
        return "/tmp/out.png"

    monkeypatch.setattr(pipeline, "push_to_server", lambda p, s, timeout=120: {"status": 200})
    import eink_diary.imagegen.core as core
    monkeypatch.setattr(core, "generate", fake_generate)

    result = pipeline.run_once(push=True, max_moderation_retries=2)
    assert result["image_path"] == "/tmp/out.png"
    assert gen_calls["n"] == 2                 # 第一次 moderation 失败，第二次成功
    assert synth_calls["n"] == 2               # 重试时重新 synthesize 换措辞
    assert "moderation retry" in result["note"]
    assert result["pushed"] is True


def test_non_moderation_error_not_retried(monkeypatch):
    monkeypatch.setattr(pipeline, "synthesize", lambda text, cfg, mode="moment": "p")
    import eink_diary.imagegen.core as core

    def boom(**kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(core, "generate", boom)
    with pytest.raises(RuntimeError, match="network down"):
        pipeline.run_once(push=False, max_moderation_retries=2)


def test_no_push_when_disabled(monkeypatch):
    monkeypatch.setattr(pipeline, "synthesize", lambda text, cfg, mode="moment": "p")
    import eink_diary.imagegen.core as core
    monkeypatch.setattr(core, "generate", lambda **kw: "/tmp/x.png")
    called = {"push": False}
    monkeypatch.setattr(pipeline, "push_to_server", lambda *a, **k: called.update(push=True))
    result = pipeline.run_once(push=False)
    assert result["pushed"] is False
    assert called["push"] is False


def test_run_archives_image_prompt_context_and_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("DIARY_ARCHIVE_DIR", str(tmp_path / "diary"))
    monkeypatch.setattr(pipeline, "synthesize", lambda text, cfg, mode="moment": "final prompt")

    src_image = tmp_path / "generated.jpg"
    src_image.write_bytes(b"fake image bytes")
    import eink_diary.imagegen.core as core
    monkeypatch.setattr(core, "generate", lambda **kw: str(src_image))

    result = pipeline.run_once(push=False)

    archive_dir = tmp_path / "diary" / "2026-06-06" / "1000"
    assert result["archive_dir"] == str(archive_dir)
    assert (archive_dir / "image.jpg").read_bytes() == b"fake image bytes"
    assert (archive_dir / "prompt.txt").read_text(encoding="utf-8") == "final prompt\n"
    assert (archive_dir / "context_private.md").read_text(encoding="utf-8") == "素材文本"
    manifest = json.loads((archive_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["window"]["start"] == "2026-06-06T08:00:00"
    assert manifest["window"]["end"] == "2026-06-06T10:00:00"
    assert manifest["image_path"] == str(src_image)
    assert manifest["archive"]["image"] == "image.jpg"
    assert manifest["archive"]["prompt"] == "prompt.txt"
    assert manifest["archive"]["context_private"] == "context_private.md"
    assert manifest["pushed"] is False


def test_run_archives_before_push_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("DIARY_ARCHIVE_DIR", str(tmp_path / "diary"))
    monkeypatch.setattr(pipeline, "synthesize", lambda text, cfg, mode="moment": "p")

    src_image = tmp_path / "generated.png"
    src_image.write_bytes(b"png bytes")
    import eink_diary.imagegen.core as core
    monkeypatch.setattr(core, "generate", lambda **kw: str(src_image))

    def push_boom(*args, **kwargs):
        raise RuntimeError("pi offline")

    monkeypatch.setattr(pipeline, "push_to_server", push_boom)

    with pytest.raises(RuntimeError, match="pi offline"):
        pipeline.run_once(push=True)

    archive_dir = tmp_path / "diary" / "2026-06-06" / "1000"
    assert (archive_dir / "image.png").read_bytes() == b"png bytes"
    assert (archive_dir / "prompt.txt").exists()
    manifest = json.loads((archive_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["pushed"] is False
    assert manifest["push_result"] is None


def _make_split_image(path, top_color, bottom_color, size=(4, 8)):
    """构造一张上下两半不同色的图，便于验证 180° 旋转后上下对调。"""
    from PIL import Image

    w, h = size
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        color = top_color if y < h // 2 else bottom_color
        for x in range(w):
            px[x, y] = color
    img.save(path)
    return img


def _extract_posted_file_bytes(body, boundary="----einkdiaryboundary7e8f"):
    """从 multipart body 里抠出 file part 的原始字节。"""
    marker = b"image/png\r\n\r\n"
    start = body.index(marker) + len(marker)
    end = body.index(f"\r\n--{boundary}--\r\n".encode(), start)
    return body[start:end]


def _capture_urlopen(monkeypatch, captured):
    class _Resp:
        status = 200

        def read(self):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=120):
        captured["body"] = req.data
        return _Resp()

    monkeypatch.setattr(pipeline.urllib.request, "urlopen", fake_urlopen)


def test_push_rotates_180_by_default(monkeypatch, tmp_path):
    from PIL import Image

    top = (255, 0, 0)      # 红在上
    bottom = (0, 0, 255)   # 蓝在下
    img_path = tmp_path / "frame.png"
    _make_split_image(img_path, top, bottom)

    monkeypatch.setenv("EINK_ROTATE_180", "true")  # 显式开启才旋转（默认关）
    captured = {}
    _capture_urlopen(monkeypatch, captured)

    pipeline.push_to_server(str(img_path), "http://pi.test:8080")

    sent = Image.open(io.BytesIO(_extract_posted_file_bytes(captured["body"]))).convert("RGB")
    w, h = sent.size
    # 旋转 180° 后：原本在上的红色应跑到下面，原本在下的蓝色应跑到上面
    assert sent.getpixel((0, 0)) == bottom
    assert sent.getpixel((0, h - 1)) == top

    # 原图文件未被改动，仍是正向
    orig = Image.open(img_path).convert("RGB")
    assert orig.getpixel((0, 0)) == top
    assert orig.getpixel((0, orig.size[1] - 1)) == bottom


def test_push_no_rotation_when_disabled(monkeypatch, tmp_path):
    from PIL import Image

    top = (255, 0, 0)
    bottom = (0, 0, 255)
    img_path = tmp_path / "frame.png"
    _make_split_image(img_path, top, bottom)

    monkeypatch.setenv("EINK_ROTATE_180", "false")
    captured = {}
    _capture_urlopen(monkeypatch, captured)

    pipeline.push_to_server(str(img_path), "http://pi.test:8080")

    sent = Image.open(io.BytesIO(_extract_posted_file_bytes(captured["body"]))).convert("RGB")
    h = sent.size[1]
    # 未旋转：上仍是红，下仍是蓝
    assert sent.getpixel((0, 0)) == top
    assert sent.getpixel((0, h - 1)) == bottom


def test_rotate_180_enabled_parsing(monkeypatch):
    for val, expected in [
        (None, False),  # 默认关（opt-in）
        ("true", True), ("1", True), ("yes", True), ("True", True),
        ("0", False), ("false", False), ("no", False),
        ("FALSE", False), ("No", False), (" 0 ", False),
    ]:
        if val is None:
            monkeypatch.delenv("EINK_ROTATE_180", raising=False)
        else:
            monkeypatch.setenv("EINK_ROTATE_180", val)
        assert pipeline._rotate_180_enabled() is expected, val


def test_fallback_triggers_collage(monkeypatch):
    """moment 返回 FALLBACK → 改用 collage 模式重新 synthesize 全天素材。"""
    calls = []

    def fake_synth(text, cfg, mode="moment"):
        calls.append(mode)
        return "FALLBACK" if mode == "moment" else "A collage of duck's day"

    monkeypatch.setattr(pipeline, "synthesize", fake_synth)
    import eink_diary.imagegen.core as core
    monkeypatch.setattr(core, "generate", lambda **kw: "/tmp/c.png")

    result = pipeline.run_once(push=False)
    assert "moment" in calls and "collage" in calls   # 两种模式都调了
    assert "fallback" in result["note"]
    assert result["image_path"] == "/tmp/c.png"


def test_run_writes_debug_log_for_fallback(monkeypatch, tmp_path):
    """run debug log records the decision chain without needing terminal scrollback."""
    calls = []

    monkeypatch.setenv("DIARY_RUN_LOG_DIR", str(tmp_path / "run_debug"))

    def fake_synth(text, cfg, mode="moment"):
        calls.append((mode, text))
        return "FALLBACK" if mode == "moment" else "A collage of duck's day"

    def fake_format(start, end, results, minutes):
        return f"# window: {start:%Y-%m-%dT%H:%M} .. {end:%Y-%m-%dT%H:%M} ({minutes} min)\n"

    monkeypatch.setattr(pipeline, "synthesize", fake_synth)
    monkeypatch.setattr(pipeline, "format_text", fake_format)
    import eink_diary.imagegen.core as core
    monkeypatch.setattr(core, "generate", lambda **kw: "/tmp/c.png")

    result = pipeline.run_once(push=False)

    assert result["run_log_dir"]
    run_dir = tmp_path / "run_debug"
    dirs = list(run_dir.iterdir())
    assert len(dirs) == 1
    logged = dirs[0]
    assert (logged / "01_window_context.md").exists()
    assert (logged / "02_moment_result.txt").read_text(encoding="utf-8") == "FALLBACK"
    assert (logged / "03_fallback_day_context.md").exists()
    assert (logged / "04_collage_prompt.txt").read_text(encoding="utf-8") == "A collage of duck's day"
    manifest = (logged / "manifest.json").read_text(encoding="utf-8")
    assert '"moment_result": "fallback"' in manifest
    assert '"note": "fallback: collage(全天)"' in manifest


def test_exports_ai_sessions_before_collect(monkeypatch):
    calls = []

    monkeypatch.setattr(
        pipeline.Config,
        "from_env",
        classmethod(lambda cls: type("C", (), {"ai_sessions_repo": "/fake/ai", "enabled_sources": lambda self: ["ai_sessions"]})()),
    )
    monkeypatch.setattr(pipeline, "export_ai_sessions", lambda repo: calls.append(("export", repo)) or "exported")

    from datetime import datetime

    def fake_collect(cfg, end=None, minutes=None):
        calls.append(("collect", cfg.ai_sessions_repo))
        return datetime(2026, 6, 6, 8, 0), datetime(2026, 6, 6, 10, 0), []

    monkeypatch.setattr(pipeline, "collect", fake_collect)
    monkeypatch.setattr(pipeline, "synthesize", lambda text, cfg, mode="moment": "p")
    import eink_diary.imagegen.core as core
    monkeypatch.setattr(core, "generate", lambda **kw: "/tmp/exported.png")

    result = pipeline.run_once(push=False)

    assert calls[:2] == [("export", "/fake/ai"), ("collect", "/fake/ai")]
    assert "exported" in result["note"]
