"""配置 schema 与源启用逻辑的 offline 测试。"""

from __future__ import annotations

import pytest

from eink_diary.config import Config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in (
        "DIARY_WINDOW_MINUTES", "DIARY_RESEND_SKILL_DIR", "RESEND_API_KEY",
        "RESEND_API_KEY_1PASSWORD_REF", "DIARY_WECHAT_MSG_DIR",
        "DIARY_AI_SESSIONS_REPO",
    ):
        monkeypatch.delenv(key, raising=False)


def test_no_env_means_no_sources():
    cfg = Config.from_env()
    assert cfg.enabled_sources() == []
    assert cfg.window_minutes == 120


def test_wechat_enabled_when_configured(monkeypatch):
    monkeypatch.setenv("DIARY_WECHAT_MSG_DIR", "/some/Msg")
    assert Config.from_env().enabled_sources() == ["wechat"]


def test_resend_needs_both_dir_and_cred(monkeypatch):
    monkeypatch.setenv("DIARY_RESEND_SKILL_DIR", "/skill")
    # 只有目录、没凭证 → 不启用
    assert "resend" not in Config.from_env().enabled_sources()
    monkeypatch.setenv("RESEND_API_KEY", "fake")
    assert "resend" in Config.from_env().enabled_sources()


def test_resend_accepts_1password_ref(monkeypatch):
    monkeypatch.setenv("DIARY_RESEND_SKILL_DIR", "/skill")
    monkeypatch.setenv("RESEND_API_KEY_1PASSWORD_REF", "op://v/i/f")
    assert "resend" in Config.from_env().enabled_sources()


def test_window_minutes_override(monkeypatch):
    monkeypatch.setenv("DIARY_WINDOW_MINUTES", "30")
    assert Config.from_env().window_minutes == 30


def test_all_three_sources(monkeypatch):
    monkeypatch.setenv("DIARY_WECHAT_MSG_DIR", "/Msg")
    monkeypatch.setenv("DIARY_AI_SESSIONS_REPO", "/ai")
    monkeypatch.setenv("DIARY_RESEND_SKILL_DIR", "/skill")
    monkeypatch.setenv("RESEND_API_KEY", "fake")
    assert set(Config.from_env().enabled_sources()) == {"resend", "wechat", "ai_sessions"}
