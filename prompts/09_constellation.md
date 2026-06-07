# 模板 09 · 今夜星座图

把今天画成一张星图：今天的每件活动是一颗命名的星，星座连线把它们连成"今日之座"。带星图的仪式感，但每颗星都标注具体是什么事——避免空泛。

## 适用

晚间时段、想要安静而有仪式感的复盘的日子。可中英混排，中文星名用 gpt-image-2。

## Prompt 模板

```
A celestial star chart for tonight, vertical 3:4, dark navy sky with an off-white star-map aesthetic, antique astronomical engraving feel. Each named star is one real activity from today; constellation lines connect them into "today's constellation". Each star has a small Chinese label:
{{ACTIVITIES}}  ← 每件事是一颗命名的星（中文星名，如 「调研星」「育儿星」「咖啡星」「交易星」），用连线连成一个星座

A small horizon hint of {{TIME}}. Elegant, calm, not cluttered. Limited 6-color e-ink palette: black/navy, warm red, golden yellow, blue, green on off-white. Stars must be specifically labeled to today's activities — not a generic sky. Legible labels.
```
