"""synthesize（判断层）offline 测试：用 mock client，不打网络。"""

from __future__ import annotations

from eink_diary.synthesize import (
    SYSTEM_PROMPT,
    SynthConfig,
    build_messages,
    synthesize,
)


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("DIARY_LLM_BASE_URL", "http://localhost:8001/v1")
    monkeypatch.setenv("DIARY_LLM_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("DIARY_LLM_API_KEY", "k")
    cfg = SynthConfig.from_env()
    assert cfg.base_url == "http://localhost:8001/v1"
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.api_key == "k"


def test_config_defaults(monkeypatch):
    for k in ("DIARY_LLM_BASE_URL", "DIARY_LLM_MODEL", "DIARY_LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    cfg = SynthConfig.from_env()
    assert cfg.base_url is None          # 留空 → openai 默认
    assert cfg.model == "gpt-5.5"
    assert cfg.api_key == "not-needed"   # 缺 key 也不崩（本地引擎不需要）


def test_build_messages_has_system_and_context():
    msgs = build_messages("窗口素材文本")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == SYSTEM_PROMPT
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "窗口素材文本"


class _FakeResp:
    def __init__(self, text):
        msg = type("M", (), {"content": text})
        choice = type("C", (), {"message": msg})
        self.choices = [choice]


class _FakeClient:
    """记录入参、返回固定内容的 mock，模拟 openai client.chat.completions.create。"""

    def __init__(self, text="  A duck Yage at a desk, one quiet aha moment  "):
        self.text = text
        self.calls = []

        outer = self

        class _Completions:
            def create(self, model, messages):
                outer.calls.append({"model": model, "messages": messages})
                return _FakeResp(outer.text)

        self.chat = type("Chat", (), {"completions": _Completions()})()


def test_synthesize_returns_stripped_prompt():
    client = _FakeClient()
    cfg = SynthConfig(base_url=None, api_key="x", model="m")
    out = synthesize("素材：鸭哥发现 op 卡在系统对话框", config=cfg, client=client)
    # 去了首尾空白 + 程序化追加了 E6 配色后缀
    assert out.startswith("A duck Yage at a desk, one quiet aha moment")
    # 用了配置里的 model，且把素材传进了 user message
    assert client.calls[0]["model"] == "m"
    assert "op 卡" in client.calls[0]["messages"][1]["content"]


# ── fallback 检测 ──────────────────────────────────────────

from eink_diary.synthesize import COLLAGE_SYSTEM_PROMPT, is_fallback


def test_is_fallback_detects_signal():
    assert is_fallback("FALLBACK")
    assert is_fallback("  fallback  ")
    assert is_fallback("FALLBACK\n")
    assert not is_fallback("A clay duck at a desk...")


def test_collage_mode_uses_collage_system_prompt():
    from eink_diary.synthesize import build_messages
    msgs = build_messages("今日全天素材", mode="collage")
    assert msgs[0]["content"] == COLLAGE_SYSTEM_PROMPT


def test_moment_mode_default_system_prompt():
    from eink_diary.synthesize import SYSTEM_PROMPT, build_messages
    msgs = build_messages("素材")
    assert msgs[0]["content"] == SYSTEM_PROMPT


def test_eink_suffix_appended_to_prompt():
    from eink_diary.synthesize import EINK_COLOR_SUFFIX
    client = _FakeClient(text="A clay duck scene")
    cfg = SynthConfig(base_url=None, api_key="x", model="m")
    out = synthesize("素材", config=cfg, client=client)
    assert out.endswith(EINK_COLOR_SUFFIX)
    assert out.startswith("A clay duck scene")


def test_fallback_signal_not_suffixed():
    client = _FakeClient(text="FALLBACK")
    cfg = SynthConfig(base_url=None, api_key="x", model="m")
    out = synthesize("素材", config=cfg, client=client)
    assert out == "FALLBACK"   # 信号原样返回，不追加后缀
