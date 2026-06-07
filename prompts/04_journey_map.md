# 模板 04 · 一日旅程地图

把今天画成一张手绘的"旅程地图"：一条蜿蜒的小路从早到晚串起若干站点，每个站点是今天的一件真实活动，配一个小图标和地名感的中文短标签。

## 适用

事情有时间先后、想表达"一天走过这些地方"的日子。中文短标签用 gpt-image-2。

## Prompt 模板

```
A hand-drawn whimsical "journey map" of one day, vertical 3:4, in the style of an illustrated treasure/adventure map. A winding path runs from top (morning) to bottom (evening), passing through several stops. Each stop is a small landmark icon标注 with a short Chinese place-name-style label, and each stands for one real activity today:
{{ACTIVITIES}}  ← 把每件事变成路上的一个站点（图标 + 中文短地名标签，如 「调研岭」「带娃湾」「咖啡驿」「交易峰」）

Time of day flows along the path. Decorative compass and dashed trail. Limited 6-color e-ink palette: black, warm red, golden yellow, blue, green on off-white aged paper. The stops must correspond to today's specific activities in rough chronological order. Keep it clear and not crowded.
```
