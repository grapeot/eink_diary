# 模板 01 · 今日图景信息海报

源自首轮成功版本「02 dashboard poster」。把今天的活动组织成一张克制的信息海报，每个板块对应一类真实活动，带简短中文标注。

## 适用

活动可归成几类、想要"一眼读懂今天"的日子。中文标注用 gpt-image-2。

## Prompt 模板

```
An elegant ambient information poster for a wall-mounted e-ink display, vertical 3:4 layout, designed like a tasteful daily journal page. Clean editorial infographic style. A title in Chinese "今日图景" at the top. Below it, a small grid of illustrated icon clusters, each cluster标注 a real activity from today and labeled with a short Chinese word:
{{ACTIVITIES}}  ← 把今天每类活动转成一个图标簇 + 一个中文小标签（如 搭建 / 调研 / 教学 / 带娃 / 理财 / 手作）

Time of day: {{TIME}} — let the lighting and accent warmth reflect it.
Refined, calm, generous spacing, magazine-quality. Limited 6-color e-ink palette: black, warm red, golden yellow, blue, green on off-white. Crisp, legible, uncluttered. The icons must clearly correspond to the listed activities, not generic decoration.
```
