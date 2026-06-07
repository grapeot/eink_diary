# 模板 10 · 一日棋盘

把今天画成一张桌游棋盘：一条带编号格子的路径从「起」到「终」，沿途的格子是今天的事件，配小图标和中文格名。像在玩"今天"这一局。

## 适用

事情多、有推进感、想要游戏化趣味的日子。中文格名用 gpt-image-2。

## Prompt 模板

```
A whimsical board-game board for one day, vertical 3:4, top-down view, a numbered winding track of tiles from "起" (start, morning) to "终" (end, evening). Each tile is an event from today with a small icon and a short Chinese tile-name:
{{ACTIVITIES}}  ← 每件事是一格（图标 + 中文格名，如 「主笔写作」「带娃格」「咖啡格」「夜盘交易」），按时间顺序排在轨道上

Playful board-game art, dice/token motifs in corners. Time of day shades the board ({{TIME}}). Limited 6-color e-ink palette: black, warm red, golden yellow, blue, green on off-white. Tiles must reflect today's specific activities in rough order. Clear, fun, not crowded.
```
