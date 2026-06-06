"""配置 schema。

设计原则（public-ready）：本文件只定义 schema 和如何从环境读取，**不含任何真实配置值**。
真实配置全部来自 `.env`（被 .gitignore 排除）；`.env.example` 给 fake 占位模板。

数据源的启用是**配置驱动的**：一个源所需的关键配置在环境里出现，就启用该源；
不出现，就跳过。例如配置了微信 DB 路径才采集微信；配置了 Resend key 才采集邮件。
这样仓库本身不绑定任何私有路径/凭证，拿到别人手里只要填 .env 就能用。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_WINDOW_MINUTES = 120


@dataclass
class Config:
    window_minutes: int = DEFAULT_WINDOW_MINUTES

    # 各源的关键配置。为 None 表示该源未配置 → 自动跳过，不采集。
    wechat_msg_dir: str | None = None          # 微信已解密 DB 目录（含 Multi/MSG*.db）
    ai_sessions_repo: str | None = None         # ai_sessions 导出脚本所在目录
    resend_skill_dir: str | None = None         # resend skill 项目目录（用于 op run）
    resend_configured: bool = False             # 是否具备 Resend 凭证条件

    @classmethod
    def from_env(cls) -> "Config":
        window = int(os.environ.get("DIARY_WINDOW_MINUTES", DEFAULT_WINDOW_MINUTES))

        resend_dir = os.environ.get("DIARY_RESEND_SKILL_DIR") or None
        # 只要给了 key 或 1Password 引用就视为具备凭证条件
        resend_has_cred = bool(
            os.environ.get("RESEND_API_KEY")
            or os.environ.get("RESEND_API_KEY_1PASSWORD_REF")
        )

        return cls(
            window_minutes=window,
            wechat_msg_dir=os.environ.get("DIARY_WECHAT_MSG_DIR") or None,
            ai_sessions_repo=os.environ.get("DIARY_AI_SESSIONS_REPO") or None,
            resend_skill_dir=resend_dir,
            resend_configured=resend_has_cred and resend_dir is not None,
        )

    def enabled_sources(self) -> list[str]:
        """根据配置齐备情况，返回应启用的数据源名称列表。"""
        enabled: list[str] = []
        if self.resend_configured:
            enabled.append("resend")
        if self.wechat_msg_dir:
            enabled.append("wechat")
        if self.ai_sessions_repo:
            enabled.append("ai_sessions")
        return enabled
