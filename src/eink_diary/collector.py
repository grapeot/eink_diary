"""Collector：把一个时间窗内的多源近况收集、合并成纯文本。

collector 只采集与合并，不做理解、不碰图像。每个源独立采集、独立降级：
任一源不可用，该段标注原因，其余照常。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .config import Config
from .sources import (
    AiSessionsSource,
    ResendSource,
    SourceResult,
    WechatSource,
)


# 各源在输出里的中文标题
_SECTION_TITLES = {
    "resend": "邮件",
    "wechat": "微信（我发出的）",
    "ai_sessions": "AI sessions（当天讨论）",
}


def build_sources(config: Config) -> dict[str, object]:
    """按配置构造启用的源实例。配置缺失的源不会出现在这里。"""
    available = config.enabled_sources()
    built: dict[str, object] = {}
    if "resend" in available:
        built["resend"] = ResendSource(config.resend_skill_dir)
    if "wechat" in available:
        built["wechat"] = WechatSource(config.wechat_msg_dir)
    if "ai_sessions" in available:
        built["ai_sessions"] = AiSessionsSource(config.ai_sessions_repo)
    return built


def resolve_window(
    config: Config, end: datetime | None = None, minutes: int | None = None
) -> tuple[datetime, datetime]:
    """计算时间窗 [start, end]。end 默认 now，长度默认配置值。"""
    win_end = end or datetime.now()
    win_minutes = minutes if minutes is not None else config.window_minutes
    win_start = win_end - timedelta(minutes=win_minutes)
    return win_start, win_end


def collect(
    config: Config,
    end: datetime | None = None,
    minutes: int | None = None,
    only: list[str] | None = None,
) -> tuple[datetime, datetime, list[SourceResult]]:
    """对每个启用的源采集，返回 (start, end, results)。"""
    start, win_end = resolve_window(config, end=end, minutes=minutes)
    sources = build_sources(config)
    results: list[SourceResult] = []
    for name, src in sources.items():
        if only and name not in only:
            continue
        results.append(src.collect(start, win_end))
    return start, win_end, results


def format_text(
    start: datetime, end: datetime, results: list[SourceResult], minutes: int
) -> str:
    """把采集结果格式化成纯文本。"""
    lines: list[str] = []
    lines.append("# eink-diary context window")
    lines.append(
        f"# window: {start:%Y-%m-%dT%H:%M} .. {end:%Y-%m-%dT%H:%M} ({minutes} min)"
    )
    lines.append("")

    by_name = {r.name: r for r in results}
    for name, title in _SECTION_TITLES.items():
        result = by_name.get(name)
        if result is None:
            continue  # 该源未启用，整段不出现
        if not result.available:
            lines.append(f"## {title}（不可用：{result.error}）")
            lines.append("")
            continue
        count = len(result.snippets)
        lines.append(f"## {title}（{count} 条）")
        if count == 0:
            lines.append("（窗口内无数据）")
        else:
            for s in result.snippets:
                label = f" {s.label}" if s.label else ""
                lines.append(f"[{s.time_str()}]{label} {s.text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
