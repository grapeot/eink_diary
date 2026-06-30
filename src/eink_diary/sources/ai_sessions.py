"""AI sessions 数据源：取我在时间窗内和 AI 讨论的东西（我的 User turns）。

复用 contexts/ai_sessions 导出的 markdown，本源解析它。

时间戳：导出 markdown 的 turn 标题现在带逐条时间戳 `## User [HH:MM]`（见上游
export 改动）。本源用 frontmatter 的 `date` + turn 的 `HH:MM` 组合出真实 datetime，
按 [start, end] 精确过滤——每个窗口拿到的是该窗口真正发生的 turn，不再是当天全量。

向后兼容：旧格式 `## User`（无时间戳）的 turn 没有精确时间，按"当天背景"处理——
仅当窗口右端落在该 session 当天时纳入，时间戳记为窗口右端。
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .base import ContextSnippet, Source, SourceResult


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# 可选时间戳的 turn 标题：## User / ## User [09:15]
_TURN_RE = re.compile(
    r"^## (User|Assistant)(?: \[(\d{2}):(\d{2})\])?\s*$", re.MULTILINE
)


def _auto_export_enabled() -> bool:
    raw = os.environ.get("DIARY_AI_SESSIONS_AUTO_EXPORT", "1")
    return raw.strip().lower() not in {"0", "false", "no"}


def export_ai_sessions(repo_dir: str | None) -> str | None:
    """Refresh exported AI session markdown before reading it.

    Returns a short status string when an export ran. Missing repo/export script is a
    no-op so the public package does not assume a private workspace layout.
    """
    if not repo_dir or not _auto_export_enabled():
        return None

    repo = Path(repo_dir)
    candidates = [
        repo / "scripts" / "export_sessions.sh",
        repo / "export_sessions.sh",
        repo / "export_sessions.py",
    ]
    script = next((p for p in candidates if p.exists()), None)
    if script is None:
        return None

    timeout = int(os.environ.get("DIARY_AI_SESSIONS_EXPORT_TIMEOUT", "300"))
    if script.suffix == ".py":
        cmd = [sys.executable, str(script)]
    else:
        cmd = ["bash", str(script)]

    proc = subprocess.run(
        cmd,
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        if len(stderr) > 1000:
            stderr = stderr[-1000:]
        raise RuntimeError(f"AI sessions export failed ({proc.returncode}): {stderr}")
    return f"ai_sessions exported via {script.name}"


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


def _iter_user_turns(text: str):
    """产出 (hour, minute or None, body) for each '## User' 段。

    用 finditer 切分：每个标题到下一个标题之间是正文。
    """
    matches = list(_TURN_RE.finditer(text))
    for idx, m in enumerate(matches):
        role = m.group(1)
        if role != "User":
            continue
        body_start = m.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        if not body:
            continue
        if m.group(2) is not None:
            yield int(m.group(2)), int(m.group(3)), body
        else:
            yield None, None, body


class AiSessionsSource(Source):
    name = "ai_sessions"

    def __init__(self, repo_dir: str | None, max_chars_per_turn: int = 280):
        self.repo_dir = repo_dir
        self.max_chars = max_chars_per_turn

    def _session_files(self) -> list[str]:
        if not self.repo_dir:
            return []
        files: list[str] = []
        for sub in ("opencode", "claude_code", "antigravity"):
            files.extend(glob.glob(os.path.join(self.repo_dir, sub, "*.md")))
        return files

    def _clip(self, body: str) -> str:
        s = body.replace("\n", " ").strip()
        if len(s) > self.max_chars:
            s = s[: self.max_chars] + "…"
        return s

    def collect(self, start: datetime, end: datetime) -> SourceResult:
        if not self.repo_dir:
            return self._unavailable("未配置 DIARY_AI_SESSIONS_REPO")
        files = self._session_files()
        if not files:
            return self._unavailable(f"未在 {self.repo_dir} 找到导出的 session markdown")

        snippets: list[ContextSnippet] = []
        for path in files:
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            fm = _parse_frontmatter(text)
            date_str = fm.get("date", "")
            try:
                sess_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            source_tag = fm.get("source", "ai")

            for hour, minute, body in _iter_user_turns(text):
                # 只接受有精确时间戳的 turn。无时间戳的（旧格式 / 未补时间戳的导出）
                # 直接丢弃——"瞬间"要求精确时序，拿不到精确时间的内容不能进窗口。
                # （早期"当天背景"兜底被证明有毒：把一大坨无时间戳内容全灌进每个窗口、
                #   打上假整点时间戳，制造同质化。见 today_e2e_v2 的 66 条 [12:00] bug。）
                if hour is None:
                    continue
                ts = datetime(
                    sess_date.year, sess_date.month, sess_date.day, hour, minute
                )
                if not (start <= ts <= end):
                    continue
                snippets.append(
                    ContextSnippet(
                        timestamp=ts, text=self._clip(body), label=source_tag
                    )
                )

        snippets.sort(key=lambda s: s.timestamp)
        return self._ok(snippets)
