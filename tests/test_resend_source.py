"""Resend 源 offline 测试：只测纯解析逻辑，不打网络。"""

from __future__ import annotations

from datetime import datetime, timezone

from eink_diary.sources.resend import _extract_emails, _parse_created_at


def test_parse_created_at_with_short_tz():
    dt = _parse_created_at("2026-06-06 06:23:19.053296+00")
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.astimezone(timezone.utc).hour == 6


def test_parse_created_at_bad():
    assert _parse_created_at("") is None
    assert _parse_created_at("not-a-date") is None


def test_extract_emails_strict_json():
    raw = '{"data": [{"from": "a@example.com", "subject": "hi"}]}'
    emails = _extract_emails(raw)
    assert emails == [{"from": "a@example.com", "subject": "hi"}]


def test_extract_emails_python_dict_style():
    # resend CLI 的 text 输出形如 python dict（单引号），带 has_more 尾巴
    raw = (
        "object: list\n"
        "data: [{'from': 'a@example.com', 'subject': 'hi', "
        "'created_at': '2026-06-06 06:23:19+00'}]\n"
        "has_more: True"
    )
    emails = _extract_emails(raw)
    assert len(emails) == 1
    assert emails[0]["from"] == "a@example.com"


def test_extract_emails_empty():
    assert _extract_emails("") == []
