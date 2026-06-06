"""微信源 offline 测试：用 fake sqlite DB，绝不用真实消息。"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from eink_diary.sources.wechat import WechatSource


def _make_fake_db(path: str, rows: list[tuple]):
    """rows: (CreateTime, StrContent, StrTalker, IsSender, Type)。"""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE MSG (CreateTime INT, StrContent TEXT, StrTalker TEXT, "
        "IsSender INT, Type INT)"
    )
    conn.executemany(
        "INSERT INTO MSG (CreateTime, StrContent, StrTalker, IsSender, Type) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


def _setup_msg_dir(tmp_path, rows) -> str:
    multi = tmp_path / "Multi"
    multi.mkdir()
    _make_fake_db(str(multi / "MSG0.db"), rows)
    return str(tmp_path)


def test_only_my_text_messages_in_window(tmp_path):
    base = int(datetime(2026, 6, 6, 9, 0).timestamp())
    rows = [
        (base + 60, "我说的话A", "alice", 1, 1),        # 我发的文本，窗口内 ✓
        (base + 120, "别人说的", "alice", 0, 1),         # 别人发的 ✗
        (base + 180, "我发的图片", "alice", 1, 3),       # 我发的但非文本 ✗
        (base + 240, "我说的话B", "grp@chatroom", 1, 1), # 我发的文本 ✓
        (base + 99999, "窗口外", "alice", 1, 1),         # 窗口外 ✗
    ]
    msg_dir = _setup_msg_dir(tmp_path, rows)
    src = WechatSource(msg_dir)
    start = datetime(2026, 6, 6, 9, 0)
    end = datetime(2026, 6, 6, 9, 30)
    result = src.collect(start, end)

    assert result.available
    texts = [s.text for s in result.snippets]
    assert texts == ["我说的话A", "我说的话B"]
    assert result.snippets[1].label == "grp@chatroom"


def test_multiple_shards_unioned(tmp_path):
    base = int(datetime(2026, 6, 6, 9, 0).timestamp())
    multi = tmp_path / "Multi"
    multi.mkdir()
    _make_fake_db(str(multi / "MSG0.db"), [(base + 10, "分片0", "a", 1, 1)])
    _make_fake_db(str(multi / "MSG1.db"), [(base + 20, "分片1", "a", 1, 1)])
    src = WechatSource(str(tmp_path))
    result = src.collect(datetime(2026, 6, 6, 9, 0), datetime(2026, 6, 6, 9, 30))
    assert sorted(s.text for s in result.snippets) == ["分片0", "分片1"]


def test_unavailable_when_no_dir():
    result = WechatSource(None).collect(datetime.now(), datetime.now())
    assert not result.available
    assert "未配置" in result.error


def test_unavailable_when_no_db(tmp_path):
    result = WechatSource(str(tmp_path)).collect(datetime.now(), datetime.now())
    assert not result.available
    assert "MSG" in result.error
