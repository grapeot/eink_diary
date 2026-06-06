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
    for sub in ("opencode", "claude_code", "second_mind"):
        (tmp_path / sub).mkdir()
    for rel, content in files.items():
        (tmp_path / rel).write_text(content, encoding="utf-8")
    return str(tmp_path)


def test_extracts_my_user_turns_of_target_day(tmp_path):
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
    texts = [s.text for s in result.snippets]
    assert texts == ["帮我看一下这个项目结构。", "再帮我写个 CLI。"]
    # 昨天的不该出现
    assert "昨天" not in " ".join(texts)
    assert result.snippets[0].label == "opencode"


def test_truncates_long_turn(tmp_path):
    long_turn = "啊" * 500
    content = f'---\ndate: "2026-06-06"\nsource: opencode\n---\n\n## User\n\n{long_turn}\n'
    repo = _setup_repo(tmp_path, {"opencode/x.md": content})
    src = AiSessionsSource(repo, max_chars_per_turn=50)
    result = src.collect(datetime(2026, 6, 6, 8, 0), datetime(2026, 6, 6, 10, 0))
    assert result.snippets[0].text.endswith("…")
    assert len(result.snippets[0].text) <= 51


def test_unavailable_when_no_repo():
    result = AiSessionsSource(None).collect(datetime.now(), datetime.now())
    assert not result.available
