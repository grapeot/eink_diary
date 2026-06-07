# 墨记 eink_diary — 架构设计文档（RFC）

描述当前架构、边界、核心设计决策。被否决的备选方案见文末附录。

## 总体架构：分层，边界在"素材文件"

```
[采集层 · 确定性代码]                    [判断层 · AI]              [输出]
微信DB ┐                                                            
邮件CLI ┼─→ collector(瘦编排) ─→ 素材文件 ─→ 挑瞬间+写画面描述 ─→ 出图 ─→ 刷E6+归档
sessions┘    (硬过滤时间窗)      (纯文本)    (gpt-image-2)
health ┘
```

核心决策（D1）：**整条管线分两层，边界划在"素材文件"。**

- **采集层 = 确定性代码（collector CLI）**：读 `.env` 判断哪些源 ready，按时间窗硬过滤，合并成一个纯文本素材文件。它可靠、便宜、适合每两小时无人值守 cron。
- **判断层 = 可插拔的 AI 步骤**：读整个素材文件，挑一个瞬间，按 prompt 指南写出画面描述，交给图像 CLI 出图。

为什么这样分：采集的本质是"确定性地按时间窗过滤"，代码最适合；挑瞬间/写 prompt 的本质是"理解 + 临场判断"，AI 最适合。把确定性留给代码、把判断留给 AI，是这个项目最根本的架构取舍。两种纯方案（全 code / 全 agent）都被否决，理由见附录。

## D2：采集层是"瘦编排"——只调 CLI / 读数据产物，不 import 别人的代码

collector 自身很瘦：它**不重新实现、也不 import 任何数据源 skill 的业务逻辑**。它只知道"配置里给的路径/命令"。每个源 adapter 用以下两种瘦耦合之一：

| 源 | 耦合方式 | adapter 知道的是 | 配置项 |
|----|---------|-----------------|--------|
| 微信 | **读数据产物**：只读读已解密 DB（`Multi/MSG*.db`），自写 SQL（`IsSender=1 AND Type=1` + CreateTime 窗口，跨分片 UNION） | DB 目录路径 | `DIARY_WECHAT_MSG_DIR` |
| AI sessions | **读数据产物**：glob + 解析导出 markdown（frontmatter `date`/`source` + `## User`） | 导出目录路径 | `DIARY_AI_SESSIONS_REPO` |
| 邮件 | **shell out 调 CLI**：`op run -- python -m resend_email_skill received list`（需 OAuth/op，重新 code 不值得） | skill 项目目录 | `DIARY_RESEND_SKILL_DIR` + 凭证 |
| 健康（候选） | 待定（读 SQLite 产物 或 调其 CLI） | 待定 | 待定 |

选型原则：

- **数据产物格式稳定的**（微信 DB schema、ai_sessions 导出格式）→ 直接读产物。代价：人家格式变了我们会断（可接受，格式稳定）。
- **需要鉴权/复杂逻辑的**（邮件 op+OAuth、opencode 数据）→ shell out 调人家现成 CLI。
- **绝不 import 别人源码进采集层**——那才是真正的分发地狱。

这解决了"分发"顾虑：collector 分发时依赖那些数据/CLI 存在（由 `.env` 指向），但自身不含别人一行业务逻辑。这是 Unix 管道哲学——瘦编排现成工具。

例外：**图像生成 CLI 是唯一被内化进本项目的**（`src/eink_diary/imagegen/`，含 test，暴露 `eink-diary-image`），因为本项目对它的用法高度特化（特定 prompt 范式 + E6/3:4 固定取向），需独立演化。来源 [grapeot/image-generation-skill](https://github.com/grapeot/image-generation-skill)。它属于输出端，不属于采集端。

## D3：配置驱动的源启用（public-ready）

`config.py` 只是 schema，真实配置全从 `.env`（gitignored）拿，`.env.example` 给 fake 占位。某源的关键配置出现就启用、不出现就跳过。仓库本身不绑定任何私有路径/凭证，拿到手只要填 `.env` 就能用。

## D4：三个镜头，以"瞬间"为主（内容哲学）

每幅画选一个镜头，**默认瞬间**。三镜头对应三种"有用"、三种时间跨度、三种数据窗口：

| 镜头 | 显示什么 | 时间跨度 | 数据窗口 |
|------|---------|---------|---------|
| **瞬间（主力）** | 挑一个最有张力的细节放大成画，丢掉其余 | 此刻两小时 | 前两小时 |
| **质地（点缀）** | 一天的感觉/形状，抽象 | 今天整体 | 全天 |
| **慢变量（点缀）** | 一个内在读数，带刻度、跨天可比 | 跨天 | 跨天 |

对判断层的契约：**synthesize 不是"概括窗口干了啥"（那必然画出清单），而是"按选定镜头从对应窗口提炼"**。瞬间 = 选择 + 放大单点；质地 = 抽象氛围；慢变量 = 读数 + 刻度。

时序精度的硬事实：**微信有逐条真实时间戳，是精确的窗口时序信号源；AI sessions 导出只有 session 级 date、无逐条时间戳，只能作"当天背景"**。所以"瞬间"按窗口取料主要靠微信。要让 sessions 也精确到窗口，需上游导出器补消息级时间戳。

陷阱（昨日八瞬间实验发现）：**某个窗口微信沉默 ≠ 你在休息**，很可能恰是深度工作。不能把"无信号"解读成"低能量"。这正是引入健康数据源的动机（身体状态能补这个判断）。

## D5：判断层可插拔，默认单次 API call

"读素材文件 → 挑瞬间 → 写 prompt"是有明确输入输出的任务，做成**可插拔**：接口固定（给素材文件，要回一个画面描述/prompt），后端可换：

- **默认：单次 API call**（确定性最高、最适合 cron）。符合"单文件确定性转换用单次 API call、不用多轮 agent"的既有经验。
- **需要动态补料时升级为 agent / opencode**：比如某个瞬间涉及"那条新闻具体说了啥"，需临场调 tavily 等别的 skill 去查。只有这种"需要边判断边取额外信息"的场景才值得上 agent。

## D6：prompt 是 enablement，不是死模板

`prompts/` 是给 AI 的**理念和例子**，不是 programmatic 填空的字符串。AI 拿到素材后自己写一个贴合那个具体瞬间的新 prompt。一批画之间刻意求多样（构图/视角/情绪/光线都变），避免八张像一个模子。`prompts/01..10` 是早期"活动清单"范式，已降级备选。

默认图像模型 **gpt-image-2**（中文渲染可靠），由 `.env` 的 `IMAGE_GENERATION_MODEL` 设置（不改上游代码）。

## D7：理解与生成解耦，产物可重放

画面描述（scene prompt）是中间产物，必须可单独 inspect / 重放：调风格不必重拉数据，生成失败可重试同一 prompt，能审计"AI 把这两小时理解成了什么"。scene prompt 连同图一起归档。

## D8：调度 cron，每两小时；失败优雅降级

8:00–22:00 每两小时一幅，wall-clock 判断时段，不做复杂情境感知。晨间身体数据手动录入、一般 9 点前到位，早 8 点那幅要么延后要么不依赖身体数据。

任一数据源不可用：更宽窗口补 / 退到上一幅 / "信号不足"占位画。生成失败：重试同一 prompt；仍失败保留屏上现有内容（last-good）。绝不白屏。

## D9：不碰局部刷新

E6 介质级不支持实用局刷，设备刷新只用 Waveshare 官方 SDK 全刷。任何后续 agent 不在驱动层尝试局刷 hack。完整理由见 PRD 附录。

## 模块结构

```
src/eink_diary/
├── sources/          # 采集 adapters（base/wechat/ai_sessions/resend，health 候选）
├── collector.py      # 瘦编排：按窗口采集、合并素材文件
├── cli.py            # eink-diary collect（采集层入口）
├── imagegen/         # 内化的图像生成 CLI（输出端，eink-diary-image）
├── synthesize.py     # 判断层：素材文件 → 画面描述（可插拔后端）  [待实现]
├── render.py         # 画面描述 → 图  [待实现]
├── display.py        # 刷 E6 + 归档  [待实现]
└── config.py         # schema，从 .env 读
```

`scripts/` 放面向人/cron 的入口。`src/` 不放面向用户的 shell 入口。

## 当前实现状态

- ✅ 采集层 collector CLI（微信/sessions/邮件三源，配置驱动，瘦编排），48 offline test。
- ✅ 图像生成 CLI 内化。
- ✅ prompt 指南 + 早期模板（降级备选）。
- ⏳ 判断层 synthesize（挑瞬间 + 写 prompt）：实验阶段（手工跑通过昨日八瞬间），未沉淀成自动逻辑。
- ⏳ render / display / cron 调度：未实现。
- ⏳ 健康数据源：候选未接。

## 未决问题

- 挑"瞬间"的自动标准（最有情绪 / 最有代表性 / 最意外 / 轮换）——用 candidate 实验中，未定。
- 同一天 8 幅的风格一致性如何保证（prompt 锁风格 + seed 策略？）。
- 设备端渲染路径（树莓派 Pillow + Waveshare SDK，还是别的）。
- 健康数据源的接入方式（读 SQLite 产物 vs 调 CLP）。
- 微信内容隐私边界（默认取全部我发出的文本；将来若需排除某些群/联系人，加黑名单配置）。

---

## 附录：Alternatives Considered & Why

### A1. 全 code vs 全 agent（最核心的取舍）

- **全 code CLI**：连"挑瞬间/写 prompt"都用代码模板。否决——这步需要理解和临场判断，硬编码做不好、覆盖不了长尾。
- **全 agent（每两小时 submit 一个 skill，AI 主导连采集都临场调别的 skill）**：灵活、松耦合、易分发。但否决为"全局方案"——采集这步是确定性的时间窗过滤，交给 agent 平添不确定性、且每次跑都贵；它的灵活性真正有价值的地方在采集之后（挑瞬间、动态补料）。
- **最终（D1+D5）**：采集用 code（确定性、可 cron、瘦编排易分发），判断用可插拔 AI（默认单次 API，需要补料时才升级 agent）。边界在素材文件。这正是两者各取所长。

### A2. 采集层耦合方式

考虑过把各数据源 skill 的代码 import/集成进来——否决，那是分发地狱（要把别人所有逻辑搬进来）。最终用"读稳定数据产物 + shell out 调现成 CLI"两种瘦耦合（D2），一行别人的业务逻辑都不抄。

### A3. 内容形态 / 主角 / 局部刷新

详见 PRD 附录（数据仪表盘→活动清单→三镜头的两次否决；泛泛的人→鸭哥；不碰局部刷新的完整理由）。
