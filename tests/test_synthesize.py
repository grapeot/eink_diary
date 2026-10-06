"""synthesize（判断层）offline 测试：用 mock client，不打网络。"""

from __future__ import annotations

import httpx
import openai
import pytest

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
    for k in ("DIARY_LLM_BASE_URL", "DIARY_LLM_MODEL", "DIARY_LLM_API_KEY",
              "DIARY_LLM_TIMEOUT_SECONDS", "DIARY_LLM_MAX_RETRIES"):
        monkeypatch.delenv(k, raising=False)
    cfg = SynthConfig.from_env()
    assert cfg.base_url is None          # 留空 → openai 默认
    assert cfg.model == "gpt-5.5"
    assert cfg.api_key == "not-needed"   # 缺 key 也不崩（本地引擎不需要）
    assert cfg.timeout_s == 120
    assert cfg.max_retries == 1


def test_timeout_and_retry_config_from_env(monkeypatch):
    monkeypatch.setenv("DIARY_LLM_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("DIARY_LLM_MAX_RETRIES", "0")
    cfg = SynthConfig.from_env()
    assert cfg.timeout_s == 90
    assert cfg.max_retries == 0


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_timeout_and_retry_config_uses_defaults(monkeypatch, value):
    monkeypatch.setenv("DIARY_LLM_TIMEOUT_SECONDS", value)
    monkeypatch.setenv("DIARY_LLM_MAX_RETRIES", value)
    cfg = SynthConfig.from_env()
    assert cfg.timeout_s == 120
    assert cfg.max_retries == 1


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_rejected(timeout):
    with pytest.raises(ValueError, match="TIMEOUT_SECONDS"):
        SynthConfig(None, "fake-key", "fake-model", timeout_s=timeout)


@pytest.mark.parametrize("retries", [-1, True, False, 1.5])
def test_invalid_retries_rejected(retries):
    with pytest.raises(ValueError, match="MAX_RETRIES"):
        SynthConfig(None, "fake-key", "fake-model", max_retries=retries)


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


def test_moment_prompt_discourages_fallback_for_multithreaded_work():
    from eink_diary.synthesize import SYSTEM_PROMPT

    assert "多主题、多线程、素材分散，不等于不够画" in SYSTEM_PROMPT
    assert "只要素材里出现了一个具体动作" in SYSTEM_PROMPT
    assert "就必须从里面挑最强的一个" in SYSTEM_PROMPT


def test_system_prompt_keeps_duck_name_in_chinese():
    from eink_diary.synthesize import COLLAGE_SYSTEM_PROMPT, SYSTEM_PROMPT

    assert '写成 "鸭哥"' in SYSTEM_PROMPT
    assert '禁止写 "Duck哥"' in SYSTEM_PROMPT
    assert '禁止写 "Duck哥"' in COLLAGE_SYSTEM_PROMPT


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


def _install_mock_transport(monkeypatch, handler):
    """Exercise the real SDK retry loop with a local transport and short backoff."""
    real_openai = openai.OpenAI
    clients = []

    def factory(**kwargs):
        client = real_openai(
            **kwargs,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        clients.append(client)
        return client

    monkeypatch.setattr(openai, "OpenAI", factory)
    return clients


def _completion_response():
    return httpx.Response(200, json={
        "id": "fake-completion",
        "object": "chat.completion",
        "created": 0,
        "model": "fake-model",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "A duck at a desk"},
        }],
    })


@pytest.mark.parametrize("failure", ["timeout", "connection", 408, 409, 429, 500, 503])
def test_transient_failure_retries_once_and_recovers(monkeypatch, failure):
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("fake timeout", request=request)
            if failure == "connection":
                raise httpx.ConnectError("fake connection failure", request=request)
            return httpx.Response(failure, json={"error": {"message": "temporary"}})
        return _completion_response()

    clients = _install_mock_transport(monkeypatch, handler)
    try:
        cfg = SynthConfig("https://example.test/v1", "fake-key", "fake-model")
        assert synthesize("fake context", config=cfg).startswith("A duck at a desk")
        assert len(requests) == 2
        assert clients[0].timeout == 120
        assert clients[0].max_retries == 1
    finally:
        for client in clients:
            client.close()


def test_repeated_timeout_stops_after_two_attempts(monkeypatch, capsys):
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("private provider error text", request=request)

    clients = _install_mock_transport(monkeypatch, handler)
    try:
        cfg = SynthConfig("https://example.test/v1", "fake-key", "fake-model")
        with pytest.raises(openai.APITimeoutError):
            synthesize("private request content", config=cfg)
        assert len(requests) == 2
        stderr = capsys.readouterr().err
        assert "request failed error=APITimeoutError" in stderr
        assert "private" not in stderr
    finally:
        for client in clients:
            client.close()


@pytest.mark.parametrize("status", [400, 401, 403])
def test_permanent_api_failure_is_not_retried(monkeypatch, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": "permanent"}})

    clients = _install_mock_transport(monkeypatch, handler)
    try:
        cfg = SynthConfig("https://example.test/v1", "fake-key", "fake-model")
        with pytest.raises(openai.APIStatusError):
            synthesize("fake context", config=cfg)
        assert len(requests) == 1
    finally:
        for client in clients:
            client.close()
