# 墨记 eink_diary — 测试策略

本文件定义"什么算验证完成"。collector / synthesize / display server 均已实现并有 offline test（pytest 全过）。

## Unit tests（纯逻辑，offline）

- 时间窗计算：给定当前时间，正确算出 8:00–22:00 内的两小时窗口边界；窗口外不触发。
- 数据源 adapter 的解析逻辑：给定 fixture（fake 邮件 / fake session 导出），正确产出 `ContextSnippet`。adapter 必须能用 fake fixture 离线测试，不打真实网络。
- 降级逻辑：数据源返回空时，pipeline 走到占位画分支而非抛异常。
- 配置解析：风格基调、数据源开关、时间窗能正确从 config 读出。
- 直显 CLI：`eink-diary display IMAGE` 能解析参数、校验图片存在、读取 `EINK_SERVER_URL` / `--server-url`，并调用统一推送函数；测试中 mock 网络，不碰真实设备。

默认测试必须 offline，不调用真实的 Resend / 图像生成 / 设备。

## Integration tests（依赖本地服务/凭证，opt-in）

通过环境变量显式开启，默认 skip：

- Resend adapter 对真实收件箱拉一个小窗口，断言返回结构合法。
- image skill 真实生成一张图，断言文件产出且尺寸为 3:4 适配 1200×1600。
- 设备刷屏：在有硬件时手动验证，不进自动化。

## E2E

暂无自动化 E2E。理由：终点是物理屏上出现一幅画，需要硬件在场，无法纯软件断言。手工验证方式见下。

## 手工验证看什么 artifact

- 一次完整 run 后，当天日期目录下应有：一张图 + 对应的 scene prompt（中间产物）。
- 配置 `DIARY_ARCHIVE_DIR` 后，一次完整 run 应写入 `YYYY-MM-DD/HHMM/image.*`、`prompt.txt`、`context_private.md`、`manifest.json`。即使 Pi 推送失败，只要图像生成成功，归档也应存在。
- scene prompt 内容应能合理对应那个时间窗的真实近况（可人工核对"AI 把我这两小时理解对了吗"）。
- 图应为竖版 3:4、色块清晰、适配 E6 六色（无需照片级还原）。
- 设备在场时：图正确刷上屏，无白屏、无残留报错画面。
- 直显手工验证：`eink-diary display path/to/image.png` 返回 server `ok=true`，Pi 的 `/api/state` 显示已有 current image。

## 文字文档直显

当电子纸用于阅读现有 Markdown，而不是展示视觉日记时，先把完整原文排版为一张 `1200 x 1600` 的白底 RGB 图片，再通过 `eink-diary display` 推送。Pi 服务会统一转换为 Spectra 6 七色并全刷；调用方不自行实现局部刷新或设备端排版。

当前经过实屏验证、适合一页中文 PRD 的阅读比例：

- 左右边距 `72px`，顶部边距 `64px`。
- 文档标题 `40px`，行距 `52px`。
- 二级标题 `29px`，行距 `38px`，标题前留白 `30px`。
- 正文与列表 `24px`，行距 `33px`，条目前留白 `8px`。

这相当于先前 60% 预览版的 125%，并保持完整 PRD 在一页中。它是文字阅读的当前默认比例，不适用于视觉日记插画。

文字排版必须使用包含实际中文字符的 CJK 字体。按字符宽度换行时，英文标识符和数字串不得拆开，中文标点不得单独落在新行行首。生成后必须人工查看 PNG：确认中文没有缺字方框、原文所有标题/段落/列表都存在、没有孤立标点或被切断的英文词，再推送并检查 `/api/state`。

## 隐私验证（公开仓库强制）

发布前跑隐私扫描。允许 `.env.example`、README 和测试里的 fake placeholder / generic `op://your-vault/...` 示例；真实邮箱、真实手机号、真实主机、真实私有路径、真实 1Password item 名称必须零匹配。

```bash
rg -n --glob '!docs/test.md' "grapeot@|ya@|outlook|pomail|/Users/grapeot|op://dev|sk-[A-Za-z0-9]{20,}" .
```

fixture 必须用 fake 数据（`alice@example.com` 等），不能用真实邮件/聊天内容。
