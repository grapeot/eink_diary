"""微信数据源：取时间窗内"我发出的"文本消息，并带少量前后文。

直接读已解密的微信 PC 版 DB（Msg/Multi/MSG*.db）。消息按库分片、不按时间，
所以必须扫所有分片库再按 CreateTime 过滤。

字段（已验证）：MSG 表含 IsSender(1=我发出)、Type(1=文本)、CreateTime(unix epoch)、
StrContent、StrTalker。collector 用"我发的话"作为触发点，但输出同一会话前后各两条文本，
并在正文里标明 speaker + 会话，避免模型把对方的话误归因给用户。
"""

from __future__ import annotations

import glob
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from .base import ContextSnippet, Source, SourceResult


@dataclass(frozen=True)
class _WechatRow:
    db: str
    rowid: int
    create_time: int
    content: str
    talker: str
    is_sender: int


class WechatSource(Source):
    name = "wechat"

    def __init__(self, msg_dir: str | None, context_radius: int = 2):
        self.msg_dir = msg_dir
        self.context_radius = context_radius

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
                    trigger_rows = conn.execute(
                        "SELECT rowid, CreateTime, StrContent, StrTalker, IsSender FROM MSG "
                        "WHERE IsSender=1 AND Type=1 AND CreateTime BETWEEN ? AND ? "
                        "ORDER BY CreateTime ASC",
                        (start_ts, end_ts),
                    ).fetchall()

                    seen_context_rows: set[tuple[str, int]] = set()
                    rows: list[_WechatRow] = []
                    for rowid, create_time, _content, talker, _is_sender in trigger_rows:
                        context = conn.execute(
                            "SELECT rowid, CreateTime, StrContent, StrTalker, IsSender FROM ("
                            "  SELECT rowid, CreateTime, StrContent, StrTalker, IsSender FROM MSG "
                            "  WHERE Type=1 AND StrTalker=? AND CreateTime BETWEEN ? AND ? "
                            "    AND CreateTime<=? "
                            "  ORDER BY CreateTime DESC, rowid DESC LIMIT ?"
                            ") "
                            "UNION ALL "
                            "SELECT rowid, CreateTime, StrContent, StrTalker, IsSender FROM ("
                            "  SELECT rowid, CreateTime, StrContent, StrTalker, IsSender FROM MSG "
                            "  WHERE Type=1 AND StrTalker=? AND CreateTime BETWEEN ? AND ? "
                            "    AND CreateTime>? "
                            "  ORDER BY CreateTime ASC, rowid ASC LIMIT ?"
                            ")",
                            (
                                talker,
                                start_ts,
                                end_ts,
                                create_time,
                                self.context_radius + 1,
                                talker,
                                start_ts,
                                end_ts,
                                create_time,
                                self.context_radius,
                            ),
                        ).fetchall()
                        for ctx_rowid, ctx_time, ctx_content, ctx_talker, ctx_is_sender in context:
                            key = (db, ctx_rowid)
                            if key in seen_context_rows:
                                continue
                            seen_context_rows.add(key)
                            rows.append(
                                _WechatRow(
                                    db=db,
                                    rowid=ctx_rowid,
                                    create_time=ctx_time,
                                    content=ctx_content or "",
                                    talker=ctx_talker or "",
                                    is_sender=ctx_is_sender,
                                )
                            )
                finally:
                    conn.close()
            except sqlite3.Error as exc:
                errors.append(f"{os.path.basename(db)}: {exc}")
                continue
            rows.sort(key=lambda r: (r.create_time, r.rowid))
            for row in rows:
                content = row.content.strip()
                if not content:
                    continue
                speaker = "我" if row.is_sender == 1 else "对方"
                conversation = row.talker or "unknown"
                snippets.append(
                    ContextSnippet(
                        timestamp=datetime.fromtimestamp(row.create_time),
                        text=f"{speaker}（会话: {conversation}）: {content}",
                        label=row.talker,
                    )
                )

        snippets.sort(key=lambda s: s.timestamp)
        if errors and not snippets:
            return self._unavailable("; ".join(errors))
        return self._ok(snippets)
