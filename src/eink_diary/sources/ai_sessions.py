"""AI sessions 数据源：取我最近和 AI 讨论的东西（我的 User turns）。

复用 contexts/ai_sessions 的 export_sessions.py 导出 markdown，本源解析它。

粒度限制（重要）：导出 markdown 只带 session 级的 `date`，没有每条消息的精确
时间戳。所以无法精确过滤到"前两小时"。本源退而取 **end 所在当天** 的 session，
提取其中我的 `## User` 段，作为"最近讨论"的近似。collector 输出会标明这一点。
"""

from __future__ import annotations

import glob
import os
import re
from datetime import datetime

from .base import ContextSnippet, Source, SourceResult


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"')
    return fm


def _extract_user_turns(text: str) -> list[str]:
    """取出所有 '## User' 段的正文（到下一个 '## ' 标题为止）。"""
    turns: list[str] = []
    parts = re.split(r"^## (User|Assistant)\s*$", text, flags=re.MULTILINE)
    # split 后形如 [preamble, 'User', body, 'Assistant', body, ...]
    for i in range(1, len(parts) - 1, 2):
        role = parts[i]
        body = parts[i + 1].strip()
        if role == "User" and body:
            turns.append(body)
    return turns


class AiSessionsSource(Source):
    name = "ai_sessions"

    def __init__(self, repo_dir: str | None, max_chars_per_turn: int = 280):
        self.repo_dir = repo_dir
        self.max_chars = max_chars_per_turn

    def _session_files(self) -> list[str]:
        if not self.repo_dir:
            return []
        files: list[str] = []
        for sub in ("opencode", "claude_code", "second_mind"):
            files.extend(glob.glob(os.path.join(self.repo_dir, sub, "*.md")))
        return files

    def collect(self, start: datetime, end: datetime) -> SourceResult:
        if not self.repo_dir:
            return self._unavailable("未配置 DIARY_AI_SESSIONS_REPO")
        files = self._session_files()
        if not files:
            return self._unavailable(f"未在 {self.repo_dir} 找到导出的 session markdown")

        target_date = end.strftime("%Y-%m-%d")
        snippets: list[ContextSnippet] = []
        for path in files:
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            fm = _parse_frontmatter(text)
            if fm.get("date") != target_date:
                continue
            source_tag = fm.get("source", "ai")
            for turn in _extract_user_turns(text):
                snippet_text = turn.replace("\n", " ").strip()
                if len(snippet_text) > self.max_chars:
                    snippet_text = snippet_text[: self.max_chars] + "…"
                snippets.append(
                    # 无精确时间戳，用窗口右端代表"当天"，label 标来源
                    ContextSnippet(timestamp=end, text=snippet_text, label=source_tag)
                )
        return self._ok(snippets)
