"""end-to-end one-shot：采集 → 挑瞬间写 prompt → 出图（带 moderation 重试）→ 推送 Pi。

供 crontab 每两小时调一次（`eink-diary run`）。设计：尽量自包含、失败可重试、
不做视觉内容审查（保持简单，crontab 友好）。
"""

from __future__ import annotations

import io
import os
import urllib.request
from datetime import datetime

from .collector import collect, format_text
from .config import Config
from .sources.ai_sessions import export_ai_sessions
from .synthesize import SynthConfig, is_fallback, synthesize


def _is_moderation_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return "moderation" in s or "safety system" in s or "moderation_blocked" in s


def _rotate_180_enabled() -> bool:
    """是否在推送前把图整体旋转 180°（屏物理挂反时用）。**默认关**（opt-in）。

    功能保留：仅当 EINK_ROTATE_180 显式取 "1"/"true"/"yes"（不分大小写）时开启。
    （用户重新摆放了屏，正向安装，故默认不旋转。）
    """
    raw = os.environ.get("EINK_ROTATE_180")
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes"}


def push_to_server(image_path: str, server_url: str, timeout: int = 120) -> dict:
    """把图 multipart POST 到 Pi display server 的 /api/display。

    用标准库拼 multipart，避免新增 requests 依赖。

    若 EINK_ROTATE_180 开启（默认），推送前把图整体物理旋转 180°（屏挂反时用）。
    只旋转传出去的字节，不改原图文件本身（归档保持正向）。
    """
    boundary = "----einkdiaryboundary7e8f"
    if _rotate_180_enabled():
        from PIL import Image

        with Image.open(image_path) as img:
            rotated = img.transpose(Image.ROTATE_180)
            buf = io.BytesIO()
            save_format = img.format or "PNG"
            rotated.save(buf, format=save_format)
            file_data = buf.getvalue()
    else:
        with open(image_path, "rb") as fh:
            file_data = fh.read()
    filename = os.path.basename(image_path)
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: image/png\r\n\r\n",
        file_data,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        server_url.rstrip("/") + "/api/display",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return {"status": resp.status, "body": resp.read().decode("utf-8", "replace")}


def run_once(
    end: datetime | None = None,
    minutes: int | None = None,
    output_prefix: str = "eink_diary_out",
    image_size: str = "2K",
    quality: str = "medium",
    max_moderation_retries: int = 2,
    push: bool = True,
):
    """跑一个时间窗的完整管线，返回结果 dict。

    返回 keys: window, context_chars, prompt, image_path, pushed, push_result, note。
    """
    from .imagegen.core import generate

    config = Config.from_env()
    if not config.enabled_sources():
        raise RuntimeError("没有已配置的数据源（见 .env）")

    export_note = export_ai_sessions(config.ai_sessions_repo)

    # 1) 采集（这个窗口）
    start, win_end, results = collect(config, end=end, minutes=minutes)
    win_minutes = int((win_end - start).total_seconds() // 60)
    context_text = format_text(start, win_end, results, win_minutes)

    # 2) 挑瞬间写 prompt
    synth_cfg = SynthConfig.from_env()
    note = export_note or ""
    prompt = synthesize(context_text, synth_cfg, mode="moment")

    # 2b) fallback：窗口信息不足 → 用【今天整体】素材画拼贴（质地镜头）
    if is_fallback(prompt):
        note = "fallback: collage(全天)"
        # 采集今天从早(默认从 win_end 当天 08:00)到现在的全部素材
        day_start = win_end.replace(hour=8, minute=0, second=0, microsecond=0)
        day_minutes = max(int((win_end - day_start).total_seconds() // 60), win_minutes)
        d_start, d_end, d_results = collect(config, end=win_end, minutes=day_minutes)
        day_context = format_text(d_start, d_end, d_results, day_minutes)
        prompt = synthesize(day_context, synth_cfg, mode="collage")

    # 3) 出图，moderation 失败重试（重跑 synthesize 换措辞）
    image_path = None
    last_err = None
    for attempt in range(max_moderation_retries + 1):
        try:
            image_path = generate(
                prompt=prompt,
                output_prefix=output_prefix,
                image_size=image_size,
                aspect_ratio="3:4",
                quality=quality,
            )
            break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if _is_moderation_error(exc) and attempt < max_moderation_retries:
                # 重新换措辞再试（LLM 有随机性，换个说法常能过审）
                note = (note + "; " if note else "") + f"moderation retry #{attempt + 1}"
                prompt = synthesize(context_text, synth_cfg, mode="moment")
                continue
            raise
    if image_path is None:
        raise RuntimeError(f"出图失败: {last_err}")

    # 4) 推送 Pi
    pushed = False
    push_result = None
    if push:
        server = os.environ.get("EINK_SERVER_URL")
        if not server:
            note = (note + "; " if note else "") + "未配置 EINK_SERVER_URL，跳过推送"
        else:
            push_result = push_to_server(image_path, server)
            pushed = True

    return {
        "window": f"{start:%Y-%m-%dT%H:%M}..{win_end:%H:%M}",
        "context_chars": len(context_text),
        "prompt": prompt,
        "image_path": image_path,
        "pushed": pushed,
        "push_result": push_result,
        "note": note,
    }
