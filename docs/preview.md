# 墨记本地 Preview 设计

## 当前结论

当前阶段只做本地浏览，不做发布。`diary/` 是本地视觉日记 archive，preview 是这个 archive 的入口页：`diary/index.html`。用户打开这个静态 HTML，就能按天浏览已经生成的图。

发布先从本项目里拿掉。未来真的要公开发布时，可以在 preview 之外另起一个 publish skill 或复用已有分享 skill。隐私审核也不属于当前本地 preview；它应该发生在上传之前，而不是本地浏览时。

## PRD

### 一句话

把 `diary/YYYY-MM-DD/HHMM/` 里的视觉日记图生成一个本地静态 HTML，让用户像翻日历一样浏览每天的图。

### 用户目标

用户打开 `diary/index.html`，先看到一个按天排列的日历/相册入口。每一天是一张 day card，显示日期、当天图片数量，以及当天的第一张图或四宫格预览。用户点开某一天，day card 展开成当天所有图，按时间顺序显示。

这个页面是回看工具，不是审核工具。它要让人快速感受到“这几天的视觉日记长什么样”，再进入某一天细看。它不需要 approve/reject，不需要上传按钮，也不需要 Cloudflare 配置。

### 核心行为

Preview builder 扫描 `diary/20??-??-??/*/manifest.json`，找到每个 slot 的 `image.*`、`prompt.txt` 和 metadata。它生成 `diary/index.html`，并尽量使用相对路径直接引用 archive 里的图片，而不是复制一份到别处。这样 `diary/` 是一个完整的本地浏览目录。

默认视图按天分组。每个 day card 折叠时显示：日期、slot 数量、时间范围、封面图。封面优先用当天第一张图；如果当天有四张以上，可以用四宫格。展开后显示当天所有 slot，卡片上显示时间、图、source counts，prompt 默认折叠。

页面应该能离线打开，不依赖后端，不依赖 npm build，不依赖网络资源。它可以包含内联 CSS 和少量 JavaScript。

### 非目标

不做发布，不做 Cloudflare 部署，不做隐私审核，不做在线编辑，不做多用户状态同步。

不把 localStorage 当长期状态。当前页面主要用于浏览；如果未来要做审核状态，应另开 publish/review flow。

## RFC

### 输入输出

输入：

```text
diary/
  2026-06-07/
    0800/
      image.jpg
      prompt.txt
      context_private.md
      manifest.json
```

输出：

```text
diary/index.html
```

`diary/` 已被 `.gitignore` 忽略，所以 preview artifact 不进 git。

### CLI

第一版命令：

```bash
python scripts/build_preview.py --diary-dir diary --output diary/index.html
```

为了兼容旧用法，脚本可以继续接受 `--output-dir`，但推荐入口是 `--output diary/index.html`。如果两者都不传，默认写 `diary/index.html`。

### 数据 contract

每个 slot 至少需要 `manifest.json` 和 `image.*`。`prompt.txt` 可选，缺失时 prompt 折叠区显示为空。`context_private.md` 不展示正文，只显示字符数。

Manifest 只用于本地展示 metadata，例如 window、sources、backfill prompt kind。页面不能把 context 正文塞进去。

## Design

### Design Intent

Preview 的主任务是“按天回看视觉日记”。它不是作品集，也不是审核后台。用户应该先看到时间结构，再进入某一天看图。

### 界面方向

界面像一本会展开的桌面日历。折叠态是 day card，展开态是当天的 contact sheet。视觉可以比审核后台更有情绪，但仍然要服务浏览：日历感、纸感、轻微动效、清楚的日期层级。

避免做成 SaaS dashboard。不要左侧复杂导航、不要表格、不要发布状态标签。也不要做成单张大图 hero，否则会破坏“按天回看”的主任务。

### 交互

页面顶部是简洁标题和统计：总天数、总图片数。主体是 responsive day grid。桌面上 day card 可以两到三列；移动端单列。

Day card 折叠时展示四宫格或封面图。点击 day card 后，卡片在原位置展开，显示当天所有 slot。展开/收起使用 CSS transition，让布局有“打开日历页”的感觉。再次点击标题或 close 按钮收起。

Slot 图片按时间顺序排列。桌面端展开某一天后固定四列，让四张图接近占满一屏宽度；八张图就是两排。这样用户能在一个视口里比较半天的视觉节奏，而不是看到一堆缩略图。移动端降为单列或双列。

每张图下方显示 slot、window 和 source counts。Metadata 必须比图片弱，不能抢视觉焦点。Prompt 用 `<details>` 折叠，默认不打开。

### 空状态

如果 `diary/` 没有任何 frame，`index.html` 显示空状态：还没有归档图，请先运行 `eink-diary run` 或 backfill。
