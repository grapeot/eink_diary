# 模板 08 · 今日食谱卡

把今天画成一张复古"食谱卡"：今天的活动是这道"今日菜"的配料，每样配料画成图标配中文份量标注。一种俏皮的隐喻——今天由这些料煮成。

## 适用

想要俏皮、把一天看成一道菜的日子。中文标注用 gpt-image-2。

## Prompt 模板

```
A vintage recipe card titled in Chinese "今日配方", vertical 3:4, like an old illustrated cookbook page. Today's activities are the ingredients of "today's dish". Each ingredient is a small illustration with a Chinese label and a faux quantity:
{{ACTIVITIES}}  ← 每件事是一味配料（图标 + 中文标注 + 俏皮份量，如 「调研 三勺」「带娃 满杯」「咖啡 一盏」「交易 少许」）

Warm kitchen palette tinted by time of day ({{TIME}}). Charming hand-lettered look, dashed dividers. Limited 6-color e-ink palette: black, warm red, golden yellow, blue, green on cream. Ingredients must map to today's specific activities. Keep it readable and not crowded.
```
