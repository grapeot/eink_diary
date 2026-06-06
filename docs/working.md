# 墨记 eink_diary — Working Log

## Changelog

### 2026-06-05

- 初始化项目脚手架：docs（prd/rfc/test/working）、src/scripts/tests/skills 目录、AGENTS.md、.gitignore、.env.example、README、根 skill 文件。
- 定方向：视觉日记形态（每两小时一幅画，8:00–22:00，一天 8 幅，攒成视觉编年史）。
- 明确非目标：不做局部刷新（E6 介质级不支持，且两小时一画下全刷耗时无关紧要）。
- 仅文档，未实现代码。按公开 skill 标准初始化。

## Lessons Learned

- 局部刷新对 13.3" E6（Spectra 6 / ACeP）是介质级死路，不是固件锁：彩色像素需长多阶段 waveform 做色粒分离，无法截短。厂商无局刷 LUT，自标定有损屏风险。E-Ink Ripple/T2000 的"局部更新"需专用控制器+新面板，标准 Waveshare HAT+ 不具备。后续 agent 不要在驱动层尝试局刷。
- 本项目是编排层，采集与生成两端全部复用 workspace 已有 skill（resend / image_generation / ai_sessions / wechat）。不要重复实现这些能力。
- scene prompt 是必须可单独 inspect/重放的中间产物，要和图一起归档——调风格、重试、审计都依赖它。
- 风格选型样本在 workspace `tmp/ambient_eink_art/`（tmp 随时可能清，正式选定后要把风格描述固化进 config，不要依赖 tmp 里的文件长期存在）。
