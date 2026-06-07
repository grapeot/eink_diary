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

### 2026-06-06（续）

- 第一次端到端"昨日八瞬间"日记跑通，方向（瞬间镜头 + 鸭哥）验证成功。
- 重写 PRD/RFC：正文只讲当前状态 + 核心设计决策，alternatives considered & why 全挪到附录。
- 确立核心架构决策：分两层、边界在"素材文件"——采集层确定性代码（瘦编排，shell out CLI / 读数据产物，不 import 别人代码），判断层可插拔 AI（默认单次 API call，需动态补料才升级 agent）。
- 数据源排除业务/对外类（Circle/Stripe/Growth/iMessage/Typefully）；健康量化列为候选第四源。

### 2026-06-06（判断层）

- 实现 synthesize（判断层）：素材文件 → 一段"瞬间"画面描述。OpenAI SDK，base_url/model/api_key 全从 .env 读，provider 无关。
- 新增 `eink-diary synthesize` 子命令（--input/--output，支持 stdin 管道）。
- .env.example 给三个 LLM 例子：GPT-5.5 / 远程 DeepSeek V4 Flash / 本地 DS-V4。.env 用本地 DS-V4。
- DS-V4 配置摸清：`adhoc_jobs/ds4` always-on 服务，openai-compatible，端口 8001，model `deepseek-v4-flash`，base_url `http://localhost:8001/v1`。
- 加 4 个 synthesize offline test（mock client），共 52 test 全过。

### 2026-06-06（display server 上 Pi）

- 精简 display server 实现 + 12 test（67 全过）+ 部署脚本 + README。
- **真硬件端到端跑通**：开发机 POST 鸭哥图 → Pi server 处理成 1200x1600 七色 → Waveshare 驱动刷屏，返回 ok。health/刷屏都验证通过。
- 原 overkill 控制端归档到 adhoc_jobs/archived/pi_eink_control_original。

### 2026-06-06（推送旋转）

- `push_to_server` 推送前可把整张图物理旋转 180°（屏上下颠倒挂反时用）。新增开关 `EINK_ROTATE_180`，默认 true；取 0/false/no 关闭。旋转只作用于推送字节（Pillow `transpose(ROTATE_180)`、原 format 重存），不改原图文件，归档保持正向。.env.example/README 同步说明，加 pipeline 旋转 test，全部 test 通过。

### 2026-06-06（fallback 端到端验证）

- 用 1416 窗口（仅 1 条转发微信、0 session）实测 fallback 全链路，三项全通：
  1. trigger：DS-V4 对稀疏素材正确返回 FALLBACK。
  2. collage：fallback 出图是"今日鸭哥拼贴"——三只鸭哥分身做白天真事（服务器/UPS退货/API key），黏土小羊肖恩风、富细节、对应真实。
  3. 端到端：自动走 FALLBACK→全天采集→collage→出图→旋转180→推 Pi，屏成功刷新。

## Lessons Learned

- **Pi 上装依赖用 uv，别用 pip**：pip 在 ARM 上慢且 pillow 可能编译；uv 几秒装完（pillow 有 ARM wheel）。uv 在 `~/.local/bin/uv`，不在默认 PATH。
- **远程起常驻进程用 tmux，别用 nohup/setsid**：经 SSH 远程 nohup 起的 uvicorn 会被连接关闭带走（表现为"进程没了/log 空/端口不监听"，极易误判为 server 崩溃）。tmux session 才真正存活。诊断时用 `timeout N python -m uvicorn ... > /tmp/x.log 2>&1; cat /tmp/x.log` 能看到真实启动日志。
- FastAPI 单端点不能同时优雅接 JSON body 和 multipart file：url 也走 form 字段，调用方一律 multipart。

- AI sessions 导出 markdown 只有 session 级 `date`、无逐条时间戳，无法精确过滤到两小时。collector 此源退而取"当天" user turns 作近似。若要精确，需改导出器带消息级时间戳。
- 微信 DB 必须只读打开（`file:...?mode=ro`），绝不写回 `Msg/`。消息按库分片不按时间，必须扫全部 `MSG*.db`。
- resend received list 的输出可能是 python-dict 风格文本（单引号 + has_more 尾巴），不是严格 JSON；解析要兼容两种。
- test fixture 里的群 ID/邮箱必须自己编 fake 值，不要从真实 DB/收件箱粘贴。
- **`op` 命令静默挂起的坑**：1Password 升级后首次启动 `op` 时，macOS Gatekeeper 会弹 "downloaded from internet 是否打开" 对话框，`op` 进程会一直等这个系统对话框被点掉。表现是所有走 `op run`/`op read` 的命令无限挂起、后台任务超时、甚至出现 "exit 0 但无产出"（拿到空 key 静默退出）的假象。排查时先 `op whoami` 确认 op 能否非交互工作；若卡住，去电脑前点掉那个 Gatekeeper 对话框。不是 service account token 的问题。

- 局部刷新对 13.3" E6（Spectra 6 / ACeP）是介质级死路，不是固件锁：彩色像素需长多阶段 waveform 做色粒分离，无法截短。厂商无局刷 LUT，自标定有损屏风险。E-Ink Ripple/T2000 的"局部更新"需专用控制器+新面板，标准 Waveshare HAT+ 不具备。后续 agent 不要在驱动层尝试局刷。
- 本项目是编排层，采集与生成两端全部复用 workspace 已有 skill（resend / image_generation / ai_sessions / wechat）。不要重复实现这些能力。
- scene prompt 是必须可单独 inspect/重放的中间产物，要和图一起归档——调风格、重试、审计都依赖它。
- 风格选型样本在 workspace `tmp/ambient_eink_art/`（tmp 随时可能清，正式选定后要把风格描述固化进 config，不要依赖 tmp 里的文件长期存在）。
