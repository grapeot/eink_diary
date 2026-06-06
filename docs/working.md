# 墨记 eink_diary — Working Log

## Changelog

### 2026-06-05

- 初始化项目脚手架：docs（prd/rfc/test/working）、src/scripts/tests/skills 目录、AGENTS.md、.gitignore、.env.example、README、根 skill 文件。
- 定方向：视觉日记形态（每两小时一幅画，8:00–22:00，一天 8 幅，攒成视觉编年史）。
- 明确非目标：不做局部刷新（E6 介质级不支持，且两小时一画下全刷耗时无关紧要）。
- 仅文档，未实现代码。按公开 skill 标准初始化。

### 2026-06-06

- 实现 collector CLI（`eink-diary collect`）：三个数据源 adapter（resend 邮件 / wechat 我发出的话 / ai_sessions 我的 user turns）+ 时间窗 + 纯文本输出。
- 配置改为 public-ready：config.py 只是 schema，真实配置全从 .env 拿；某源配置缺失即自动跳过该源。
- 微信源直接读已解密 DB（`Multi/MSG*.db`，只读模式），跨分片 UNION，`IsSender=1 AND Type=1` + CreateTime 过滤——真实 DB 历史窗口冒烟测试通过（拉出 67 条我发的消息）。
- 写 24 个 offline unit test（fake fixture），全过。隐私扫描通过，fixture 无真实数据。
- 实验图归档：5 张移入 experiments/（gitignored，只留 README）。

## Lessons Learned

- AI sessions 导出 markdown 只有 session 级 `date`、无逐条时间戳，无法精确过滤到两小时。collector 此源退而取"当天" user turns 作近似。若要精确，需改导出器带消息级时间戳。
- 微信 DB 必须只读打开（`file:...?mode=ro`），绝不写回 `Msg/`。消息按库分片不按时间，必须扫全部 `MSG*.db`。
- resend received list 的输出可能是 python-dict 风格文本（单引号 + has_more 尾巴），不是严格 JSON；解析要兼容两种。
- test fixture 里的群 ID/邮箱必须自己编 fake 值，不要从真实 DB/收件箱粘贴。

- 局部刷新对 13.3" E6（Spectra 6 / ACeP）是介质级死路，不是固件锁：彩色像素需长多阶段 waveform 做色粒分离，无法截短。厂商无局刷 LUT，自标定有损屏风险。E-Ink Ripple/T2000 的"局部更新"需专用控制器+新面板，标准 Waveshare HAT+ 不具备。后续 agent 不要在驱动层尝试局刷。
- 本项目是编排层，采集与生成两端全部复用 workspace 已有 skill（resend / image_generation / ai_sessions / wechat）。不要重复实现这些能力。
- scene prompt 是必须可单独 inspect/重放的中间产物，要和图一起归档——调风格、重试、审计都依赖它。
- 风格选型样本在 workspace `tmp/ambient_eink_art/`（tmp 随时可能清，正式选定后要把风格描述固化进 config，不要依赖 tmp 里的文件长期存在）。
