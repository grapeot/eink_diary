# 墨记 eink_diary

一块挂在墙上的彩色电子纸，每两小时把"你最近在干什么"画成一幅画；一天下来，这些画连起来就是一本不用动手写的视觉日记。

## 它是什么

不是仪表盘，是视觉日记。白天 8:00–22:00，每两小时一次，系统读取你这个时间窗的真实近况（最近邮件 / 待办 / AI 编程会话 / 未来的聊天记录），让 AI 把它理解成一段画面描述，再用图像模型生成一幅意象画，刷到 13.3" 彩色电子纸（E-Ink Spectra 6）上。一天 8 幅，攒成当天的视觉编年史。

电子纸的价值在于不发光、被动常驻、纸感、彩色——适合"低频更新、值得反复瞥见"的内容。两小时一画的慢节奏恰好用对了这块介质（全刷十几秒在这个频率下完全无所谓），彩色则让画作成立。

## 当前状态

**文档脚手架阶段，尚未实现代码。** 设计已定稿，见 `docs/`：

- `docs/prd.md` — 产品定义、数据源、成功标准、非目标、物理约束
- `docs/rfc.md` — 四阶段管线架构（采集 → 理解 → 生成 → 输出）与关键设计决策
- `docs/test.md` — 测试策略
- `docs/working.md` — changelog 与 lessons learned

## 架构一览

```
[数据源 adapters] ─→ 聚合近况 ─→ AI 写画面描述 ─→ 图像生成模型 ─→ 刷 E6 + 归档
```

编排层定位：采集与生成两端复用已有 skill，本项目只把它们串成一本日记。

## 明确不做的事

- **不做局部刷新。** Spectra 6 彩色电子纸介质级不支持实用局刷（彩色像素需长 waveform 做色粒分离），自标定波形有损屏风险，且两小时一画下全刷耗时无关紧要。
- 不做密集实时仪表盘、不做照片相框、不做通用天气日历、不做云端服务。

## 作为 skill 安装（给 coding agent）

本仓库的根 skill 在 `skills/eink_diary.md`。把本仓库的 GitHub URL 交给 Codex / Claude Code / Cursor / OpenCode 等 coding agent，让它：

1. 从目标 workspace 的 `AGENTS.md` 或 `CLAUDE.md` 读起，遵循其中的路由文件（如 `WORKSPACE.md`）。
2. 把 `skills/eink_diary.md` 加入 workspace 的 skill 发现链：若有 `rules/skills/INDEX.md` 或 `skills/INDEX.md` 就更新该索引；否则在 `AGENTS.md`/`CLAUDE.md` 里加一行指针。
3. 复制 `.env.example` 为 `.env` 并填入真实凭证（`.env` 已被 gitignore）。

本 skill 依赖宿主 workspace 提供的若干能力 skill（邮件、图像生成、AI session 导出、聊天记录）；安装时确认这些已就位或按各自文档安装。

## 依赖的公开 skill（方便使用与继续开发）

本项目是编排层，采集与生成端复用以下能力 skill。其中几个已开源，可直接参考或安装：

- **图像生成** — [grapeot/image-generation-skill](https://github.com/grapeot/image-generation-skill)。本项目已把其 CLI 代码内化进 `src/eink_diary/imagegen/`（特化用途，独立演化），上游 repo 是其来源与通用版本。
- **邮件采集** — [grapeot/resend_email_skill](https://github.com/grapeot/resend_email_skill)。collector 的邮件源通过它的 `received list` 拉取。
- **AI session 导出** — 由 [grapeot/opencode_skill](https://github.com/grapeot/opencode_skill) 提供导出 CLI，输出 markdown 兼容 collector 的 ai_sessions 源（frontmatter `date`/`source` + `## User`/`## Assistant`）。
- **微信聊天记录** — 由 `wechat_db_parser` 提供已解密 PC 版 DB 的解析；该项目当前未公开，collector 的微信源直接只读读其 `Multi/MSG*.db`。

各源是配置驱动的：在 `.env` 配置了某源的关键变量才启用它，未配置则自动跳过（见 `.env.example`）。

## E-Ink Display Server（部署到树莓派）

`server/` 是一个精简的 FastAPI，跑在驱动 13.3" E6 屏的树莓派上。它只做一件事：收一张图 → 处理成 1200×1600 / Spectra-6 七色 → 刷到屏上。端点：

- `GET /health` — 存活
- `GET /api/state` — 当前显示的图
- `POST /api/display` — 统一刷屏入口（multipart/form）：带 `file`（图片文件）或 `url`（文本字段）二选一

刷图示例：

```bash
# 直推本地图片文件（推荐）
curl -F "file=@out.png" http://<pi-ip>:8080/api/display
# 或给一个 Pi 能访问的 URL
curl -F "url=https://example.com/a.png" http://<pi-ip>:8080/api/display
```

### 部署

部署配置走 `.env`（schema 见 `.env.example`，真实值不进仓库）：

```
EINK_DEPLOY_HOST=pi-user@<pi-ip>      # passwordless SSH 目标
EINK_DEPLOY_PATH=~/co/eink_diary_display
```

从开发机一键传到 Pi（rsync server 代码 + Waveshare 驱动 + Pi 启动脚本）：

```bash
bash scripts/deploy_display.sh
```

### 在 Pi 上首次配置与启动

传完后 SSH 到 Pi，在部署目录：

```bash
cd ~/co/eink_diary_display
python3 -m venv .venv
.venv/bin/pip install -e '.[server]'      # ARM 上装 pillow 可能稍慢
bash scripts/run_display_pi.sh            # 启动，默认 http://0.0.0.0:8080
```

`run_display_pi.sh` 会自动设好 `EINK_DISPLAY_SCRIPT`（指向随部署带上的 Waveshare 刷屏脚本）。可用环境变量覆盖：`EINK_PORT`、`EINK_STATE_DIR`、`EINK_PYTHON`。要常驻可用 pm2 / systemd / nohup 包一层。

驱动库 `RaspberryPi/` 是 Waveshare 官方的，原样复用（来源见 `adhoc_jobs/archived/pi_eink_control_original`，那是 Pi 上原控制端的完整归档）。

## 隐私

This repository is designed to be publishable with only fake examples. 所有公开文件使用 fake handles / domains / keys。私有联系人、私有路由、真实凭证只存在本地 `.env` 与 workspace 全局 overlay（如 `rules/skills/`），不进本仓库。
