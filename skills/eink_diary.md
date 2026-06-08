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
- **AI sessions** — 我和 AI 的讨论（我的 `## User` turns）。导出 markdown 的 turn 标题已带逐条 `HH:MM` 时间戳（OpenCode export + Claude Code JSONL 均已补），collector 用 frontmatter date + turn HH:MM 组合出精确 datetime 后按窗口过滤。

输出是分三段的纯文本，缺失/不可用的源给出明确标记，不静默省略。每个源独立降级，单源失败不影响整体。

## Synthesize CLI（判断层，已实现）

把 collector 的素材文件提炼成一段"瞬间"画面描述（image prompt）：不是概括，而是挑一个最有张力的瞬间，写成有鸭哥、有场景、有情绪的单场景画面。

```bash
eink-diary collect --end 2026-06-06T10:00 --output ctx.txt
eink-diary synthesize --input ctx.txt --output prompt.txt
# 或管道：eink-diary collect ... | eink-diary synthesize
eink-diary-image -p "$(cat prompt.txt)" --aspect-ratio 3:4 --size 2K --quality medium -o out.png
```

LLM 后端 provider 无关，由 `.env` 三个变量驱动（换 provider 只改这三个）：

- `DIARY_LLM_BASE_URL`（留空=OpenAI 默认；本地 DS-V4 用 `http://localhost:8001/v1`）
- `DIARY_LLM_MODEL`（如 `gpt-5.5` / `deepseek-v4-flash`）
- `DIARY_LLM_API_KEY`（本地引擎填 `not-needed`）

三个示例（GPT-5.5 / 远程 DeepSeek / 本地 DS-V4）见 `.env.example`。本地 DS-V4 是 `adhoc_jobs/ds4` 的 always-on 服务（openai-compatible，端口 8001，model `deepseek-v4-flash`）。

## eink-diary run（one-shot，供 crontab）

把整条管线串成一条命令，crontab 每两小时调一次：

```bash
eink-diary run                          # 默认前两小时，2K medium，出图后推送 Pi
eink-diary run --end 2026-06-06T20:00   # 回放历史窗口
eink-diary run --full-day               # 全天：0-2 点取昨天完整一天，其余时间取今天 00:00 到现在
eink-diary run --no-push                # 只出图不推送
```

它做：采集（collect）→ 挑瞬间写 prompt（synthesize，本地 DS-V4）→ 出图（gpt-image-2）
→ 推送到 Pi display server 刷屏。

- **moderation 自动重试**：出图遇 gpt-image-2 的 moderation_blocked，自动重跑 synthesize
  换措辞再试（默认最多 2 次）。不做视觉内容审查（保持简单、cron 友好）。
- **推送目标**从 `.env` 的 `EINK_SERVER_URL` 读（如 `http://<pi-ip>:8080`），multipart POST
  到 `/api/display`。未配置则跳过推送。
- **全天语义**：用户说“今天全天/全天版本”时优先用 `--full-day`，不要手算
  `--minutes`。本地时间 00:00–02:00 之间，`--full-day` 自动解释为昨天完整一天
  （`yesterday 00:00..today 00:00`）；其他时间解释为今天从 00:00 到当前时刻。

crontab 示例（每两小时，白天）：

```
0 8,10,12,14,16,18,20,22 * * * cd /path/to/eink_diary && op run --env-file=.env -- .venv/bin/eink-diary run >> run.log 2>&1
```

## 方法论建议（非硬约束）

- scene prompt 与图解耦：先产出可单独 inspect 的画面描述，再生成图。这样调风格不必重拉数据，生成失败可重放同一 prompt。
- 风格基调作为配置（`DIARY_STYLE`），换风格不改代码。候选风格选型样本见 workspace `tmp/ambient_eink_art/`。
- 同一天 8 幅画尽量保持风格统一：在 prompt 里锁定风格描述。
- 晨间身体数据（睡眠/HRV）和当前任务是手动录入、一般 9 点前到位；早 8 点那幅要么延到 9 点后，要么不依赖这些字段。

## 降级行为（必须覆盖）

- 数据源返回空：用更宽时间窗补，或退到上一幅，或生成"今日信号不足"占位画。
- 图像生成失败：重试同一 scene prompt；仍失败则保留屏上现有内容（last-good），不要白屏。

## 输出规格

- 图：竖版 3:4，适配 1200×1600。
- 归档根目录由 `DIARY_ARCHIVE_DIR` 配置（本地，不进仓库）。配置后，每次成功出图都会写入 `DIARY_ARCHIVE_DIR/YYYY-MM-DD/HHMM/`，其中 `HHMM` 是刷新时刻（时间窗右端）。
- 每个归档槽包含 `image.*`、`prompt.txt`、`context_private.md`、`manifest.json`。`context_private.md` 是私有审计材料，后续公开站不得直接读取。

## Local Preview（本地浏览）

归档图可以生成一个本地静态 preview 页面，方便按天回看。这个 preview 只做本地浏览，不做发布、不做隐私审核、不上传。

```bash
python scripts/build_preview.py --diary-dir diary --output diary/index.html
```

生成后打开 `diary/index.html`。页面按天显示日历卡片；点开某一天后展开当天所有图，桌面端固定四列，prompt 默认折叠。

当用户要求“生成 diary preview / 本地浏览 / 看所有墨记图”时，直接运行上述命令。`diary/` 已被 gitignore，生成的 `index.html` 和图片归档不会进仓库。

## 已知陷阱

（暂无。实现并实际踩坑后再补——不预测编造。）
