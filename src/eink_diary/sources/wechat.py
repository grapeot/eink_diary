"""微信数据源：取时间窗内"我发出的"文本消息。

直接读已解密的微信 PC 版 DB（Msg/Multi/MSG*.db）。消息按库分片、不按时间，
所以必须扫所有分片库再按 CreateTime 过滤。

字段（已验证）：MSG 表含 IsSender(1=我发出)、Type(1=文本)、CreateTime(unix epoch)、
StrContent、StrTalker。
"""

from __future__ import annotations

import glob
import os
import sqlite3
from datetime import datetime

from .base import ContextSnippet, Source, SourceResult


class WechatSource(Source):
    name = "wechat"

    def __init__(self, msg_dir: str | None):
        self.msg_dir = msg_dir

    def _db_paths(self) -> list[str]:
        if not self.msg_dir:
            return []
        # 兼容 --data-dir 既可能指 Msg/ 也可能指仓库根的两种写法
        patterns = [
            os.path.join(self.msg_dir, "Multi", "MSG*.db"),
            os.path.join(self.msg_dir, "Msg", "Multi", "MSG*.db"),
        ]
        found: list[str] = []
        for p in patterns:
            found.extend(glob.glob(p))
        return sorted(set(found))

    def collect(self, start: datetime, end: datetime) -> SourceResult:
        if not self.msg_dir:
            return self._unavailable("未配置 DIARY_WECHAT_MSG_DIR")
        dbs = self._db_paths()
        if not dbs:
            return self._unavailable(f"未在 {self.msg_dir} 找到 Multi/MSG*.db")

        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())
        snippets: list[ContextSnippet] = []
        errors: list[str] = []

        for db in dbs:
            try:
                # 只读打开，绝不写回
                conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                try:
                    rows = conn.execute(
                        "SELECT CreateTime, StrContent, StrTalker FROM MSG "
                        "WHERE IsSender=1 AND Type=1 "
                        "AND CreateTime BETWEEN ? AND ? "
                        "ORDER BY CreateTime ASC",
                        (start_ts, end_ts),
                    ).fetchall()
                finally:
                    conn.close()
            except sqlite3.Error as exc:
                errors.append(f"{os.path.basename(db)}: {exc}")
                continue
            for create_time, content, talker in rows:
                if not content:
                    continue
                snippets.append(
                    ContextSnippet(
                        timestamp=datetime.fromtimestamp(create_time),
                        text=content.strip(),
                        label=talker or "",
                    )
                )

        snippets.sort(key=lambda s: s.timestamp)
        if errors and not snippets:
            return self._unavailable("; ".join(errors))
        return self._ok(snippets)
