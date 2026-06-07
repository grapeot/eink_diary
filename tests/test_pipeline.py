"""pipeline.run_once offline 测试：mock 各步，重点验 moderation 重试 + 推送逻辑。"""

from __future__ import annotations

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
    monkeypatch.setattr(pipeline.Config, "from_env", classmethod(lambda cls: type("C", (), {"enabled_sources": lambda self: ["wechat"]})()))
    monkeypatch.setattr(pipeline.SynthConfig, "from_env", classmethod(lambda cls: None))
    monkeypatch.setenv("EINK_SERVER_URL", "http://pi.test:8080")


def test_moderation_retry_then_success(monkeypatch):
    synth_calls = {"n": 0}

    def fake_synth(text, cfg):
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
    monkeypatch.setattr(pipeline, "synthesize", lambda text, cfg: "p")
    import eink_diary.imagegen.core as core

    def boom(**kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(core, "generate", boom)
    with pytest.raises(RuntimeError, match="network down"):
        pipeline.run_once(push=False, max_moderation_retries=2)


def test_no_push_when_disabled(monkeypatch):
    monkeypatch.setattr(pipeline, "synthesize", lambda text, cfg: "p")
    import eink_diary.imagegen.core as core
    monkeypatch.setattr(core, "generate", lambda **kw: "/tmp/x.png")
    called = {"push": False}
    monkeypatch.setattr(pipeline, "push_to_server", lambda *a, **k: called.update(push=True))
    result = pipeline.run_once(push=False)
    assert result["pushed"] is False
    assert called["push"] is False
