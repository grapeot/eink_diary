# Markdown 首页显示

`eink-diary render-markdown-first-page` 将本地 Markdown 的可读首页渲染为 `1200x1600` RGB PNG。它不改源文件，不缩小整篇文章，并在页脚显示 `1/N`。

`eink-diary display-markdown` 在渲染后先请求配置 display server 的 `/health`，成功后才将 PNG 上传到 `/api/display`。树莓派负责 Spectra-6 量化与全刷。

这套能力针对树莓派竖屏 display server，不是 E1002 的 `800x480` 多页阅读协议，也不把 server 扩展成 Markdown parser 或翻页器。

```bash
eink-diary render-markdown-first-page report.md \
  --font-path /path/to/cjk-font.ttc \
  --output output/report.png

eink-diary display-markdown report.md \
  --font-path /path/to/cjk-font.ttc \
  --output output/report.png
```
