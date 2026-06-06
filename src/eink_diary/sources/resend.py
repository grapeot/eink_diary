"""邮件数据源：取时间窗内收到的邮件。

复用 resend_email_skill 的 `received list`，不重复实现邮件拉取。
凭证走 `op run --env-file=.env`（1Password 引用解析）。

received list 返回的每封邮件含 from / subject / created_at（UTC）。
本源按 created_at 落在 [start, end] 过滤。
"""

from __future__ import annotations

import ast
import json
import subprocess
from datetime import datetime, timezone

from .base import ContextSnippet, Source, SourceResult


def _parse_created_at(value: str) -> datetime | None:
    """resend 的 created_at 形如 '2026-06-06 06:23:19.053296+00'（UTC）。"""
    if not value:
        return None
    txt = value.strip().replace(" ", "T", 1)
    # 兼容 '+00' 这种缺分钟的时区写法
    if txt.endswith("+00"):
        txt = txt[:-3] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class ResendSource(Source):
    name = "resend"

    def __init__(self, skill_dir: str | None, limit: int = 50):
        self.skill_dir = skill_dir
        self.limit = limit

    def _fetch_raw(self) -> list[dict]:
        """调用 resend received list 并解析其输出为邮件 dict 列表。"""
        cmd = [
            "op", "run", "--env-file=.env", "--",
            ".venv/bin/python", "-m", "resend_email_skill",
            "received", "list", "--limit", str(self.limit), "--format", "json",
        ]
        proc = subprocess.run(
            cmd, cwd=self.skill_dir, capture_output=True, text=True, timeout=90
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "resend CLI 调用失败")
        return _extract_emails(proc.stdout)

    def collect(self, start: datetime, end: datetime) -> SourceResult:
        if not self.skill_dir:
            return self._unavailable("未配置 DIARY_RESEND_SKILL_DIR")
        try:
            emails = self._fetch_raw()
        except Exception as exc:  # noqa: BLE001 - 透传原因，单源失败不影响整体
            return self._unavailable(str(exc))

        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)
        snippets: list[ContextSnippet] = []
        for em in emails:
            created = _parse_created_at(str(em.get("created_at", "")))
            if created is None or not (start_utc <= created <= end_utc):
                continue
            sender = em.get("from", "")
            subject = em.get("subject", "")
            snippets.append(
                ContextSnippet(
                    timestamp=created.astimezone(),  # 转本地时区显示
                    text=subject,
                    label=sender,
                )
            )
        snippets.sort(key=lambda s: s.timestamp)
        return self._ok(snippets)


def _extract_emails(stdout: str) -> list[dict]:
    """resend received list 的输出可能是严格 JSON，也可能是 python-dict 风格文本。

    两种都尝试解析，取出 data 列表。
    """
    text = stdout.strip()
    if not text:
        return []
    # 优先严格 JSON
    try:
        obj = json.loads(text)
        return _emails_from_obj(obj)
    except json.JSONDecodeError:
        pass
    # 退回 python 字面量解析（输出里出现单引号 dict 的情况）
    # 截取第一个 'data: [' 之后到末尾，按字面量解析列表
    marker = "data:"
    if marker in text:
        list_part = text.split(marker, 1)[1].strip()
        # 去掉可能的尾随 'has_more: ...'
        end_idx = list_part.rfind("]")
        if end_idx != -1:
            list_part = list_part[: end_idx + 1]
        try:
            return ast.literal_eval(list_part)
        except (ValueError, SyntaxError):
            return []
    try:
        return _emails_from_obj(ast.literal_eval(text))
    except (ValueError, SyntaxError):
        return []


def _emails_from_obj(obj) -> list[dict]:
    if isinstance(obj, dict):
        data = obj.get("data")
        if isinstance(data, list):
            return data
        return []
    if isinstance(obj, list):
        return obj
    return []
