# 墨记 eink_diary — 架构设计文档（RFC）

本文件描述架构、边界、关键设计决策。实现尚未开始；这里给出后续实现应遵循的结构与取舍。

## 总体管线

```
[数据源 adapters]            [理解]               [生成]            [输出]
resend received  ┐
ai_sessions      ┼─→ 聚合近况 ─→ AI 写画面描述 ─→ 图像生成模型 ─→ 刷 E6 + 归档
wechat (future)  ┘   (raw context)   (scene prompt)    (3:4 图)
```

四个阶段职责单一、可独立替换：

1. **采集（collect）**：每个数据源是一个 adapter，给定时间窗返回结构化的"近况片段"。adapter 之间互不依赖，可单独开关。
2. **理解（synthesize）**：把多源近况片段喂给一个 AI agent，压缩成一段"此刻在干什么"的画面描述（scene prompt）。这一步是把杂乱事件转成视觉意象的关键。
3. **生成（render）**：把 scene prompt + 选定的风格基调交给图像生成模型，产出竖版 3:4、适配 1200×1600 的图。
4. **输出（display）**：把图刷到 E6，并归档到当天日期目录。

## 关键设计决策

### D1：编排层，不重复造能力

采集、生成两端全部复用 workspace 已有 skill，本项目只写编排逻辑：

- 邮件/待办 → `resend_email_skill`（凭证走 `op run --env-file=.env`）
- AI sessions → `contexts/ai_sessions/export_sessions.py --since-date YYYY-MM-DD`
- 图像生成 → `image_generation_skill`（`generate-image`，中文标注用 `gpt-image-2`，纯意象用 Gemini）
- 微信（future）→ `wechat_messages` skill

理由：这些 skill 已被验证、各自维护，重复实现会制造维护负担和漂移。本项目的价值在"把它们串成一本日记"。

### D2：理解与生成解耦

scene prompt 是中间产物，必须可单独 inspect / 重放。这样：调风格时不必重新拉数据；生成失败可重试同一个 prompt；能审计"AI 把我这两小时理解成了什么"。scene prompt 应连同图一起归档。

### D3：风格基调是配置，不是硬编码

视觉语言（光河 / 海报 / 水墨 / 博物图谱 等）作为可配置项。换风格不应改代码。首轮 5 个样本是选型依据，选定后写入配置。

### D4：调度走树莓派 cron，每两小时一次

8:00–22:00 每两小时触发（一天 8 幅）。时段判断用简单 wall-clock，不做复杂情境感知。

**时效注意**：晨间相关的身体数据（睡眠/HRV）和当前任务是手动录入，一般 9 点前到位。涉及这些字段的画（早 8 点那幅）要么延到 9 点后生成，要么 8 点那幅不依赖身体数据。产出/邮件/session 等自动数据全天可用。

### D5：失败优雅降级，永不白屏

任一数据源不可用：用更宽时间窗补，或退到上一幅，或生成"今日信号不足"占位画。生成失败：重试同一 scene prompt；仍失败则保留屏上现有内容。借鉴 7 寸 dashboard 的 last-good 策略。

### D6：明确不碰局部刷新

见 PRD 非目标。E6 介质级不支持实用局刷，自标定 waveform 有损屏风险且收益为零（两小时一画下全刷耗时无关紧要）。任何后续 agent 不应在驱动层尝试局刷 hack。设备刷新直接用 Waveshare 官方 SDK 的全刷接口。

## 模块边界（建议的 src 结构）

```
src/eink_diary/
├── sources/          # 数据源 adapters，每个 source 一个文件
│   ├── base.py       # adapter 接口：given (start, end) → list[ContextSnippet]
│   ├── resend.py
│   ├── ai_sessions.py
│   └── wechat.py     # future
├── synthesize.py     # 近况片段 → scene prompt（调 AI）
├── render.py         # scene prompt + style → 图（调 image skill）
├── display.py        # 刷 E6 + 归档
├── pipeline.py       # 串起四阶段
└── config.py         # 时间窗、风格基调、数据源开关
```

`scripts/` 放面向人/cron 的入口（如 `run_once.sh`、`run_window.py`）。`src/` 不放面向用户的 shell 入口。

## 公开仓库边界

本仓库设计为只含 fake 示例即可发布：

- 私有联系人、私有路由、真实凭证、内部路径不进公开仓库。
- 凭证用 `.env`（gitignored）+ `.env.example`（fake 占位）。
- 若 skill 涉及私有 alias/路由，放 workspace 全局 `rules/skills/` overlay，公开仓库只放技术实现与工作流，并在文档里指明私有部分在哪找。

## 未决问题

- 设备端用树莓派 Python（Pillow 转六色 + Waveshare SDK 刷屏）还是别的渲染路径——留到实现时定。
- scene prompt 的"风格一致性"如何保证（同一天 8 幅画风格统一）——可能需要在 prompt 里锁定风格描述 + seed 策略。
- 微信数据源接入后的隐私边界（哪些聊天能进画面理解、哪些必须排除）——接入前需单独确认。
