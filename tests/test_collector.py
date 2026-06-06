"""Collector 编排、时间窗与输出格式的 offline 测试。"""

from __future__ import annotations

from datetime import datetime

from eink_diary.collector import format_text, resolve_window
from eink_diary.config import Config
from eink_diary.sources.base import ContextSnippet, SourceResult


def test_resolve_window_default_length():
    cfg = Config(window_minutes=120)
    end = datetime(2026, 6, 6, 10, 0)
    start, win_end = resolve_window(cfg, end=end)
    assert win_end == end
    assert (win_end - start).total_seconds() == 120 * 60


def test_resolve_window_minutes_override():
    cfg = Config(window_minutes=120)
    end = datetime(2026, 6, 6, 10, 0)
    start, _ = resolve_window(cfg, end=end, minutes=30)
    assert (end - start).total_seconds() == 30 * 60


def _snip(h, m, text, label=""):
    return ContextSnippet(timestamp=datetime(2026, 6, 6, h, m), text=text, label=label)


def test_format_has_header_and_sections():
    start = datetime(2026, 6, 6, 8, 0)
    end = datetime(2026, 6, 6, 10, 0)
    results = [
        SourceResult(name="wechat", snippets=[_snip(8, 31, "我说的话", "grp")]),
        SourceResult(name="resend", snippets=[_snip(8, 12, "邮件主题", "a@example.com")]),
    ]
    out = format_text(start, end, results, 120)
    assert "# eink-diary context window" in out
    assert "window: 2026-06-06T08:00 .. 2026-06-06T10:00 (120 min)" in out
    assert "## 邮件（1 条）" in out
    assert "## 微信（我发出的）（1 条）" in out
    assert "[08:31] grp 我说的话" in out
    assert "[08:12] a@example.com 邮件主题" in out


def test_format_empty_source_marked():
    start = datetime(2026, 6, 6, 8, 0)
    end = datetime(2026, 6, 6, 10, 0)
    results = [SourceResult(name="wechat", snippets=[])]
    out = format_text(start, end, results, 120)
    assert "## 微信（我发出的）（0 条）" in out
    assert "（窗口内无数据）" in out


def test_format_unavailable_source_marked():
    start = datetime(2026, 6, 6, 8, 0)
    end = datetime(2026, 6, 6, 10, 0)
    results = [
        SourceResult(name="resend", snippets=[], available=False, error="凭证缺失")
    ]
    out = format_text(start, end, results, 120)
    assert "## 邮件（不可用：凭证缺失）" in out


def test_format_skips_unconfigured_source():
    # 只给 wechat 结果，邮件/ai_sessions 段不应出现
    start = datetime(2026, 6, 6, 8, 0)
    end = datetime(2026, 6, 6, 10, 0)
    results = [SourceResult(name="wechat", snippets=[_snip(8, 0, "x")])]
    out = format_text(start, end, results, 120)
    assert "邮件" not in out
    assert "AI sessions" not in out
