# 模板 06 · 纪念邮票套票

把今天画成一版邮票（a sheet of postage stamps）：每一枚邮票是今天的一件真实活动，带齿孔、面值感和一行中文小标题。像在给这一天发行纪念邮票。

## 适用

想要收藏感、把一天切成几枚"值得纪念的小事"的日子。中文小标题用 gpt-image-2。

## Prompt 模板

```
A sheet of commemorative postage stamps for today, vertical 3:4, classic perforated stamp edges, a unifying header. Each stamp illustrates one real activity from today, with a tiny Chinese caption and a faux denomination:
{{ACTIVITIES}}  ← 每枚邮票画一件事（图案 + 中文小标题，如 「主笔调研」「陪娃时光」「一杯手冲」「夜半交易」）

Time of day tints the overall palette ({{TIME}}). Vintage philatelic aesthetic, fine engraving feel. Limited 6-color e-ink palette: black, warm red, golden yellow, blue, green on off-white. Each stamp must depict a specific activity from today, not generic icons. Keep captions short and legible.
```
