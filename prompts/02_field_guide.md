# 模板 02 · 复古博物图鉴

源自首轮成功版本「05 field guide」。把今天的活动画成一张老式博物学标本图——每个活动是一枚可辨认的标本，排列在带装饰边框的图鉴页上。

## 适用

活动种类多而杂、想要趣味与具体兼得的日子。默认用 gpt-image-2。

## Prompt 模板

```
Retro scientific botanical-plate / antique specimen-chart style poster, vertical 3:4, on aged off-white paper. A whimsical "field guide to today" depicting today's activities as labeled specimens arranged like a naturalist's plate. Each specimen must be a recognizable object standing for one real activity from today:
{{ACTIVITIES}}  ← 把每类活动画成一枚具体标本（如 写作=羽毛笔+手稿, 调研=放大镜+文献, 教学=小讲台, 带娃=纸船/积木, 咖啡=咖啡杯, 红酒=酒瓶, 编程=小机器人, 交易=K线星座）

Fine ink line-art with hand-drawn flourishes and a decorative border. Time of day: {{TIME}}. Limited 6-color e-ink palette: black ink, warm red, golden yellow, blue, green on cream paper. Decorative but uncluttered. Ornamental flourishes only — no real paragraph text. The specimens must be specific to today's activities, not a generic set.
```
