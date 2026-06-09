# 墨记 eink_diary — Working Log

## Changelog

### 2026-06-08

- 修复本地 preview 展开态用固定 `max-height: 5000px` 的隐性裁切问题；当天图片或 prompt 较多时，展开区域改为按内容自然高度显示，避免最后一排图被截断。
- 调整 synthesize 系统提示：英文 image prompt 中主角名字必须保留中文 `鸭哥`，禁止生成 `Duck哥` / `duck哥` 这类半翻译称呼。
- 新增 `eink-diary run --full-day`，把“全天版本”的时间窗语义固化到 CLI：本地时间 00:00–02:00 之间自动取昨天完整一天；其他时间取今天 00:00 到当前时刻。避免午夜后 agent 手算成当天前几分钟。
- 新增 `docs/preview.md`，把当前阶段从公开分享站收敛为本地静态 preview：`diary/index.html` 按天展示视觉日记，发布和隐私审核留给后续独立流程。
- 打通正式图像归档链路：`DIARY_ARCHIVE_DIR` 配置后，`eink-diary run` 会按刷新时刻写入 `YYYY-MM-DD/HHMM/`，保存 `image.*`、`prompt.txt`、`context_private.md`、`manifest.json`；归档发生在推送 Pi 前，设备离线不会导致已生成图片丢失。

### 2026-06-07

- 修复 `eink-diary run` / `collect` 读取 AI sessions 前不刷新导出的问题：若配置了 `DIARY_AI_SESSIONS_REPO`，采集前会自动调用该 repo 内的 `scripts/export_sessions.sh` / `export_sessions.sh` / `export_sessions.py`。
- 新增 `DIARY_AI_SESSIONS_AUTO_EXPORT=0/false/no` 逃生开关和 `DIARY_AI_SESSIONS_EXPORT_TIMEOUT` 超时配置；默认每次分析前刷新，避免两小时图只读到凌晨 04:00 的旧导出。
- 新增 `eink-diary run` 本地 debug log：默认写入 `logs/run_debug/`（gitignored），记录两小时 context、moment 判断结果、fallback 全天 context、最终 prompt 和 manifest，方便复盘 AI 判断链路。
- 调整 moment prompt 的 fallback 标准：多主题/多线程/素材分散不再等同于信息不足；只要有具体工程动作、判断、调试或决定，就优先挑一个单一瞬间来画。
- 微信源从只取“我发出的文本”改为“以我发出的文本为触发点，带同一会话窗口内前后各两条文本上下文”，并按 DB row 去重，避免模型只看到回应、看不到对话背景。

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
- 微信片段只看我说的话会丢掉语义锚点。更好的边界是用我发出的消息作为触发点，但把同一会话局部前后文带上；上下文仍限制在当前时间窗内，避免历史回放时引入窗口之后的未来消息。
- resend received list 的输出可能是 python-dict 风格文本（单引号 + has_more 尾巴），不是严格 JSON；解析要兼容两种。
- test fixture 里的群 ID/邮箱必须自己编 fake 值，不要从真实 DB/收件箱粘贴。
- **`op` 命令静默挂起的坑**：1Password 升级后首次启动 `op` 时，macOS Gatekeeper 会弹 "downloaded from internet 是否打开" 对话框，`op` 进程会一直等这个系统对话框被点掉。表现是所有走 `op run`/`op read` 的命令无限挂起、后台任务超时、甚至出现 "exit 0 但无产出"（拿到空 key 静默退出）的假象。排查时先 `op whoami` 确认 op 能否非交互工作；若卡住，去电脑前点掉那个 Gatekeeper 对话框。不是 service account token 的问题。

- 局部刷新对 13.3" E6（Spectra 6 / ACeP）是介质级死路，不是固件锁：彩色像素需长多阶段 waveform 做色粒分离，无法截短。厂商无局刷 LUT，自标定有损屏风险。E-Ink Ripple/T2000 的"局部更新"需专用控制器+新面板，标准 Waveshare HAT+ 不具备。后续 agent 不要在驱动层尝试局刷。
- 本项目是编排层，采集与生成两端全部复用 workspace 已有 skill（resend / image_generation / ai_sessions / wechat）。不要重复实现这些能力。
- scene prompt 是必须可单独 inspect/重放的中间产物，要和图一起归档——调风格、重试、审计都依赖它。
- 风格选型样本在 workspace `tmp/ambient_eink_art/`（tmp 随时可能清，正式选定后要把风格描述固化进 config，不要依赖 tmp 里的文件长期存在）。
- 定时视觉日记依赖 AI sessions 时，导出刷新必须属于 e-ink pipeline 自己的前置步骤，而不能只依赖每日 cron；两小时窗口对新鲜度的要求高于每日索引任务。
- `FALLBACK` 不能只看主题数量。高信号但多线程的窗口仍然适合画单一瞬间；fallback 应保留给几乎没有主动行为、只有自动通知、或全是无上下文测试句的窗口。AI 判断链路必须落 debug log，否则事后只能从最终图反推原因。
