"""精简 E-Ink display server。

端点：
- GET  /health        — 存活 + 是否配了刷屏脚本
- GET  /api/state     — 当前显示的图信息
- POST /api/display   — 统一刷屏入口：JSON {url} 或 multipart 文件 → 处理 → 刷屏

设计：server 只做"收图 → 预处理 → 刷屏 → 记录当前图"。不生成、不存历史、无前端。
"""

from __future__ import annotations

from io import BytesIO

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from . import display
from .image_ops import DISPLAY_HEIGHT, DISPLAY_WIDTH, process_for_eink

app = FastAPI(title="eink-diary display")


def _render_and_push(raw: bytes) -> dict:
    """字节 → 处理 → 刷屏 → 存 current。返回结果信息。"""
    try:
        image = Image.open(BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"无法识别图片: {exc}")

    processed = process_for_eink(image)
    current = display.current_image_path()
    processed.save(current, format="PNG")

    try:
        display.push_to_panel(current)
    except (RuntimeError, Exception) as exc:  # noqa: BLE001
        # 透传刷屏错误（非 Pi 环境会到这）；图已存为 current。
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "ok": True,
        "width": DISPLAY_WIDTH,
        "height": DISPLAY_HEIGHT,
        "current": str(current),
    }


@app.get("/health")
async def health() -> dict:
    script = display.display_script()
    return {
        "status": "ok",
        "display_script_configured": script is not None and script.exists(),
    }


@app.get("/api/state")
async def state() -> dict:
    current = display.current_image_path()
    return {
        "has_current": current.exists(),
        "current": str(current) if current.exists() else "",
        "width": DISPLAY_WIDTH,
        "height": DISPLAY_HEIGHT,
    }


@app.post("/api/display")
async def display_image(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
) -> dict:
    """统一刷屏入口（multipart/form）。带 file（文件）或 url（文本字段）二选一。

    （FastAPI 不能在同一端点同时优雅接 JSON body 和 multipart file，所以 url
    也走 form 字段，语义统一、调用方一律用 multipart。）
    """
    if file is not None:
        raw = await file.read(display.max_image_bytes() + 1)
        if len(raw) > display.max_image_bytes():
            raise HTTPException(status_code=413, detail="图片超过大小上限")
        return _render_and_push(raw)

    if url and url.strip():
        try:
            raw = display.download_image(url.strip())
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"下载失败: {exc}")
        return _render_and_push(raw)

    raise HTTPException(status_code=400, detail="需要提供 url 或上传文件")
