"""数据源 adapter 的共享类型与接口。

每个数据源给定一个时间窗 [start, end]，返回一组 ContextSnippet。
adapter 之间互不依赖，可单独开关、单独失败。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ContextSnippet:
    """时间窗内的一条近况片段。"""

    timestamp: datetime
    text: str
    # 来源内的细分标签，例如邮件的发件人、微信的群名、session 的工具名
    label: str = ""

    def time_str(self) -> str:
        return self.timestamp.strftime("%H:%M")


@dataclass
class SourceResult:
    """一个数据源在某时间窗的采集结果。

    available=False 表示该源不可用（DB 缺失、凭证缺失、导出失败等），
    error 给出原因。这样输出层能区分"无数据"和"源不可用"，
    并保证单源失败不影响整体。
    """

    name: str
    snippets: list[ContextSnippet] = field(default_factory=list)
    available: bool = True
    error: str = ""


class Source:
    """数据源 adapter 接口。"""

    name = "base"

    def collect(self, start: datetime, end: datetime) -> SourceResult:
        raise NotImplementedError

    def _ok(self, snippets: list[ContextSnippet]) -> SourceResult:
        return SourceResult(name=self.name, snippets=snippets, available=True)

    def _unavailable(self, error: str) -> SourceResult:
        return SourceResult(name=self.name, snippets=[], available=False, error=error)
