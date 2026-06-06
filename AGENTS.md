# AGENTS.md — 墨记 eink_diary 项目规则

## 这个项目是什么

一块 13.3" E6 彩色电子纸的视觉日记：每两小时读"用户最近在干什么"（邮件/待办/AI sessions/未来微信），由 AI 生成一幅意象画刷到屏上，一天 8 幅攒成视觉编年史。完整设计见 `docs/prd.md` 和 `docs/rfc.md`。

## 项目结构

- `docs/` — prd / rfc / test / working（持久文档）
- `src/eink_diary/` — 可复用 Python 模块（sources adapters / synthesize / render / display / pipeline / config）
- `scripts/` — 面向人和 cron 的可执行入口
- `tests/` — unit（offline）/ integration（opt-in）
- `skills/` — 本项目的根 skill 文件（公开技术实现）

## 硬约束

- **不做局部刷新。** E6 介质级不支持，自标定 waveform 有损屏风险，且两小时一画下全刷耗时无关紧要。设备刷屏只用 Waveshare 官方 SDK 全刷接口。任何人不要在驱动层尝试局刷 hack。
- **编排层定位，不重复造能力。** 采集与生成全部复用 workspace 已有 skill（`resend_email_skill` / `image_generation_skill` / `ai_sessions/export_sessions.py` / `wechat_messages`）。
- **公开仓库。** 私有联系人/路由/凭证/内部路径不进仓库。凭证走 `.env`（gitignored）+ `.env.example`（fake 占位）。发布前跑隐私扫描，零匹配才算过。

## 工作要求

1. 有意义的改动后更新 `docs/working.md`（`## Changelog` 当天一节 + `## Lessons Learned`）。
2. 小步提交，不要把脚手架、实现、验证塞进一个 commit。
3. Python 环境：激活 workspace 根 `.venv`，依赖用 `uv pip install`。需要隔离时在本项目建独立 `.venv`。
4. scene prompt 是必须归档的中间产物，和图一起存当天日期目录。
