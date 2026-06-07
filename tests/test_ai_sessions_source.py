"""AI sessions 源 offline 测试：用 fake 导出 markdown。"""

from __future__ import annotations

from datetime import datetime

from eink_diary.sources.ai_sessions import AiSessionsSource

FAKE_SESSION = '''---
source: opencode
title: "fake session"
date: "2026-06-06"
---

# fake session

## User

帮我看一下这个项目结构。

## Assistant

好的，我先列目录。

## User

再帮我写个 CLI。
'''

OTHER_DAY = '''---
source: claude_code
date: "2026-06-05"
---

## User

这是昨天的，不该被选中。
'''


def _setup_repo(tmp_path, files: dict[str, str]) -> str:
    for sub in ("opencode", "claude_code"):
        (tmp_path / sub).mkdir()
    for rel, content in files.items():
        (tmp_path / rel).write_text(content, encoding="utf-8")
    return str(tmp_path)


def test_no_timestamp_turns_are_discarded(tmp_path):
    # 无时间戳的 turn（旧格式）一律丢弃，不再"当天背景"兜底（防同质化污染）。
    repo = _setup_repo(
        tmp_path,
        {
            "opencode/today.md": FAKE_SESSION,
            "claude_code/yesterday.md": OTHER_DAY,
        },
    )
    src = AiSessionsSource(repo)
    result = src.collect(
        datetime(2026, 6, 6, 8, 0), datetime(2026, 6, 6, 10, 0)
    )
    assert result.available
    assert result.snippets == []   # 全是无时间戳格式 → 全丢弃


def test_truncates_long_turn(tmp_path):
    long_turn = "啊" * 500
    content = f'---\ndate: "2026-06-06"\nsource: opencode\n---\n\n## User [09:00]\n\n{long_turn}\n'
    repo = _setup_repo(tmp_path, {"opencode/x.md": content})
    src = AiSessionsSource(repo, max_chars_per_turn=50)
    result = src.collect(datetime(2026, 6, 6, 8, 0), datetime(2026, 6, 6, 10, 0))
    assert result.snippets[0].text.endswith("…")
    assert len(result.snippets[0].text) <= 51


def test_unavailable_when_no_repo():
    result = AiSessionsSource(None).collect(datetime.now(), datetime.now())
    assert not result.available


# ── 带逐条时间戳的精确窗口过滤（核心新行为）──────────────────

TIMESTAMPED = '''---
source: opencode
date: "2026-06-06"
---

## User [09:15]

窗口内的话A

## Assistant [09:16]

回复

## User [11:40]

窗口外的话（11点多）

## User [09:50]

窗口内的话B
'''


def test_timestamp_filters_to_window(tmp_path):
    repo = _setup_repo(tmp_path, {"opencode/t.md": TIMESTAMPED})
    src = AiSessionsSource(repo)
    # 窗口 09:00–10:00：只应拿到 09:15 和 09:50，不要 11:40
    result = src.collect(datetime(2026, 6, 6, 9, 0), datetime(2026, 6, 6, 10, 0))
    texts = [s.text for s in result.snippets]
    assert texts == ["窗口内的话A", "窗口内的话B"]   # 已按时间排序
    assert all("窗口外" not in t for t in texts)
    # 时间戳是真实的，不是窗口右端
    assert result.snippets[0].timestamp == datetime(2026, 6, 6, 9, 15)


def test_timestamp_excludes_other_window(tmp_path):
    repo = _setup_repo(tmp_path, {"opencode/t.md": TIMESTAMPED})
    src = AiSessionsSource(repo)
    # 窗口 11:00–12:00：只应拿到 11:40
    result = src.collect(datetime(2026, 6, 6, 11, 0), datetime(2026, 6, 6, 12, 0))
    assert [s.text for s in result.snippets] == ["窗口外的话（11点多）"]


def test_two_windows_get_different_turns(tmp_path):
    """回归：修复同质化 bug——不同窗口拿到不同 turn，不再是当天全量。"""
    repo = _setup_repo(tmp_path, {"opencode/t.md": TIMESTAMPED})
    src = AiSessionsSource(repo)
    w1 = src.collect(datetime(2026, 6, 6, 9, 0), datetime(2026, 6, 6, 10, 0))
    w2 = src.collect(datetime(2026, 6, 6, 11, 0), datetime(2026, 6, 6, 12, 0))
    assert [s.text for s in w1.snippets] != [s.text for s in w2.snippets]
