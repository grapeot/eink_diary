# 墨记 eink_diary Skill（根 skill）

## 类型与适用场景

- **类型**: Workflow
- **适用场景**: 把"用户最近在干什么"渲染成一幅画并刷到彩色电子纸，定时积累成视觉日记。当用户要求"生成今天/这个时段的电子纸日记画"、"刷新墙上电子纸"、"看我最近在干啥画一幅"时使用。
- **创建日期**: 2026-06-05

## 目标

给定一个时间窗，自动完成：读取该窗口内用户的真实近况 → 让 AI 把它理解成一段画面描述 → 用图像模型生成一幅竖版 3:4 适配 1200×1600 的意象画 → 刷到 13.3" E6 电子纸 → 归档当天图与画面描述。一天 8 幅（8:00–22:00 每两小时）连成视觉编年史。

## 验收标准

一个无上下文的 agent 拿到以下标准即可判断任务是否完成：

1. 产出物落盘：当天日期目录下同时存在 **一张图**（竖版 3:4）和 **对应的 scene prompt 文本**（中间产物）。
2. scene prompt 内容可合理对应该时间窗的真实近况（人工可核对"理解对了吗"）。
3. 图为色块清晰、适配 E6 六色的画面，不要求照片级还原。
4. 全程无人值守即可完成；任一数据源缺失时走降级分支而非报错或白屏。
5. 设备在场时，图正确刷上屏。

## 可用资源与边界

采集与生成**全部复用 workspace 已有 skill**，本 skill 只负责编排：

- 邮件 / 待办 → `resend_email_skill`（`received list/get`；凭证走 `op run --env-file=.env`）
- 最近 AI sessions → `contexts/ai_sessions/export_sessions.py --since-date YYYY-MM-DD`
- 微信"我说了什么"+ 上下文 → `wechat_messages` skill（待接入）
- 图像生成 → `image_generation_skill` 的 `generate-image`；**中文标注用 `gpt-image-2`，纯意象用 Gemini**；竖版用 `--aspect-ratio 3:4`

边界：

- **不做局部刷新。** E6 介质级不支持，自标定 waveform 有损屏风险；设备刷屏只用 Waveshare 官方 SDK 全刷。不要在驱动层尝试局刷。
- **不重复实现上述 skill 的能力。**
- 私有联系人 / 路由 / 凭证不进公开仓库；私有 alias 见 workspace `rules/skills/` overlay。

## Collector CLI（采集阶段，已实现）

采集阶段已独立实现为一个 CLI：把最近一个时间窗内的多源近况收集、过滤、合并成一个纯文本文件，给后续"理解→生成"当输入。

安装：在项目根 `uv pip install -e '.[dev]'`，得到 `eink-diary` 命令。

```bash
eink-diary collect                        # 前两小时，全部已配置的源，打印到 stdout
eink-diary collect --minutes 30           # 改时间窗长度
eink-diary collect --end 2026-06-06T10:00 # 回放历史窗口（便于测试/补刷）
eink-diary collect --sources wechat       # 只采集指定源
eink-diary collect --output ctx.txt       # 写文件
```

**配置驱动的源启用**（public-ready）：config 只是 schema，真实配置全从 `.env` 拿（`.env` 被 .gitignore）。某个源的关键配置出现就启用、不出现就跳过：

- 邮件：`DIARY_RESEND_SKILL_DIR` + `RESEND_API_KEY`（或 1Password 引用）
- 微信：`DIARY_WECHAT_MSG_DIR`（已解密 PC 版 DB 目录，含 `Multi/MSG*.db`）
- AI sessions：`DIARY_AI_SESSIONS_REPO`（导出 markdown 目录）

各源取什么：

- **邮件** — 时间窗内收到的邮件（按 `created_at` 过滤；subject + from）。
- **微信** — 时间窗内**我发出的**文本消息（`IsSender=1 AND Type=1` + CreateTime 窗口，跨所有分片 DB UNION）。
- **AI sessions** — 我和 AI 的讨论（我的 `## User` turns）。注意：导出 markdown 只有 session 级 date，无逐条时间戳，所以此源取**当天** session 的 user turns 作近似，不能精确到两小时。

输出是分三段的纯文本，缺失/不可用的源给出明确标记，不静默省略。每个源独立降级，单源失败不影响整体。

## 方法论建议（非硬约束）

- scene prompt 与图解耦：先产出可单独 inspect 的画面描述，再生成图。这样调风格不必重拉数据，生成失败可重放同一 prompt。
- 风格基调作为配置（`DIARY_STYLE`），换风格不改代码。候选风格选型样本见 workspace `tmp/ambient_eink_art/`。
- 同一天 8 幅画尽量保持风格统一：在 prompt 里锁定风格描述。
- 晨间身体数据（睡眠/HRV）和当前任务是手动录入、一般 9 点前到位；早 8 点那幅要么延到 9 点后，要么不依赖这些字段。

## 降级行为（必须覆盖）

- 数据源返回空：用更宽时间窗补，或退到上一幅，或生成"今日信号不足"占位画。
- 图像生成失败：重试同一 scene prompt；仍失败则保留屏上现有内容（last-good），不要白屏。

## 输出规格

- 图：竖版 3:4，适配 1200×1600，存当天日期目录。
- scene prompt：与图同目录的文本文件。
- 归档根目录由 `DIARY_ARCHIVE_DIR` 配置（本地，不进仓库）。

## 已知陷阱

（暂无。实现并实际踩坑后再补——不预测编造。）
