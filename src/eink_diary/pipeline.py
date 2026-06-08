"""end-to-end one-shot：采集 → 挑瞬间写 prompt → 出图（带 moderation 重试）→ 推送 Pi。

供 crontab 每两小时调一次（`eink-diary run`）。设计：尽量自包含、失败可重试、
不做视觉内容审查（保持简单，crontab 友好）。
"""

from __future__ import annotations

import io
import json
import os
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path

from .collector import collect, format_text
from .config import Config
from .sources.ai_sessions import export_ai_sessions
from .synthesize import SynthConfig, is_fallback, synthesize


def _run_log_root() -> Path | None:
    """Return local debug log root, or None when explicitly disabled."""
    raw = os.environ.get("DIARY_RUN_LOG_DIR", "logs/run_debug")
    if raw.strip().lower() in {"0", "false", "no", "off", ""}:
        return None
    return Path(raw)


def _safe_ts(dt: datetime) -> str:
    return dt.strftime("%Y%m%d_%H%M")


def _new_run_log_dir(start: datetime, end: datetime) -> Path | None:
    root = _run_log_root()
    if root is None:
        return None
    run_dir = root / f"{datetime.now():%Y%m%d_%H%M%S}_{_safe_ts(start)}_{_safe_ts(end)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_debug_text(run_dir: Path | None, name: str, text: str) -> None:
    if run_dir is None:
        return
    (run_dir / name).write_text(text, encoding="utf-8")


def _write_manifest(run_dir: Path | None, manifest: dict) -> None:
    if run_dir is None:
        return
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _archive_root() -> Path | None:
    raw = os.environ.get("DIARY_ARCHIVE_DIR")
    if raw is None or raw.strip() == "":
        return None
    return Path(raw)


def _archive_slot_dir(win_end: datetime) -> Path | None:
    root = _archive_root()
    if root is None:
        return None
    return root / f"{win_end:%Y-%m-%d}" / f"{win_end:%H%M}"


def _archive_image_name(image_path: str) -> str:
    suffix = Path(image_path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".png"
    if suffix == ".jpeg":
        suffix = ".jpg"
    return "image" + suffix


def _write_archive_manifest(archive_dir: Path | None, manifest: dict) -> None:
    if archive_dir is None:
        return
    (archive_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _archive_run(
    win_end: datetime,
    image_path: str,
    prompt: str,
    context_text: str,
    manifest: dict,
) -> Path | None:
    """Persist the generated diary frame under DIARY_ARCHIVE_DIR, if configured."""
    archive_dir = _archive_slot_dir(win_end)
    if archive_dir is None:
        return None
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived_image = archive_dir / _archive_image_name(image_path)
    shutil.copy2(image_path, archived_image)
    (archive_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    (archive_dir / "context_private.md").write_text(context_text, encoding="utf-8")
    manifest["archive"] = {
        "dir": str(archive_dir),
        "image": archived_image.name,
        "prompt": "prompt.txt",
        "context_private": "context_private.md",
    }
    _write_archive_manifest(archive_dir, manifest)
    return archive_dir


def _source_summary(results) -> list[dict]:
    return [
        {
            "name": r.name,
            "available": r.available,
            "count": len(r.snippets),
            "error": r.error,
        }
        for r in results
    ]


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
    run_log_dir = _new_run_log_dir(start, win_end)
    manifest = {
        "window": {"start": start.isoformat(), "end": win_end.isoformat(), "minutes": win_minutes},
        "sources": _source_summary(results),
        "context_chars": len(context_text),
        "export_note": export_note,
    }
    _write_debug_text(run_log_dir, "01_window_context.md", context_text)
    _write_manifest(run_log_dir, manifest)

    # 2) 挑瞬间写 prompt
    synth_cfg = SynthConfig.from_env()
    note = export_note or ""
    prompt = synthesize(context_text, synth_cfg, mode="moment")
    _write_debug_text(run_log_dir, "02_moment_result.txt", prompt)
    manifest["moment_result"] = "fallback" if is_fallback(prompt) else "prompt"
    _write_manifest(run_log_dir, manifest)

    # 2b) fallback：窗口信息不足 → 用【今天整体】素材画拼贴（质地镜头）
    if is_fallback(prompt):
        note = "fallback: collage(全天)"
        # 采集今天从早(默认从 win_end 当天 08:00)到现在的全部素材
        day_start = win_end.replace(hour=8, minute=0, second=0, microsecond=0)
        day_minutes = max(int((win_end - day_start).total_seconds() // 60), win_minutes)
        d_start, d_end, d_results = collect(config, end=win_end, minutes=day_minutes)
        day_context = format_text(d_start, d_end, d_results, day_minutes)
        _write_debug_text(run_log_dir, "03_fallback_day_context.md", day_context)
        manifest["fallback"] = {
            "window": {"start": d_start.isoformat(), "end": d_end.isoformat(), "minutes": day_minutes},
            "sources": _source_summary(d_results),
            "context_chars": len(day_context),
        }
        prompt = synthesize(day_context, synth_cfg, mode="collage")
        _write_debug_text(run_log_dir, "04_collage_prompt.txt", prompt)
        _write_manifest(run_log_dir, manifest)
    else:
        _write_debug_text(run_log_dir, "03_final_prompt.txt", prompt)

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
                _write_debug_text(run_log_dir, f"moderation_retry_{attempt + 1}_prompt.txt", prompt)
                continue
            raise
    if image_path is None:
        raise RuntimeError(f"出图失败: {last_err}")

    manifest.update({
        "final_prompt_chars": len(prompt),
        "image_path": image_path,
        "pushed": False,
        "push_result": None,
        "note": note,
    })
    archive_dir = _archive_run(win_end, image_path, prompt, context_text, manifest)
    _write_manifest(run_log_dir, manifest)

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

    manifest.update({
        "final_prompt_chars": len(prompt),
        "image_path": image_path,
        "pushed": pushed,
        "push_result": push_result,
        "note": note,
    })
    _write_manifest(run_log_dir, manifest)
    _write_archive_manifest(archive_dir, manifest)

    return {
        "window": f"{start:%Y-%m-%dT%H:%M}..{win_end:%H:%M}",
        "context_chars": len(context_text),
        "prompt": prompt,
        "image_path": image_path,
        "pushed": pushed,
        "push_result": push_result,
        "note": note,
        "run_log_dir": str(run_log_dir) if run_log_dir else None,
        "archive_dir": str(archive_dir) if archive_dir else None,
    }
