"""刷屏 + URL 下载。硬件相关隔离在这里（通过 subprocess 调 Waveshare 刷屏脚本）。

配置从环境读（schema 在此，真实值在 .env）：
- EINK_DISPLAY_SCRIPT: Waveshare 刷屏脚本路径（接受一个图片路径参数，刷到屏上）
- EINK_PYTHON: 跑刷屏脚本的 python（默认当前解释器；Pi 上指向带驱动库的 venv）
- EINK_STATE_DIR: 存当前显示图 / 落盘的目录
- EINK_MAX_IMAGE_BYTES: 上传/下载图片大小上限（默认 16MB）
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
from pathlib import Path


def display_script() -> Path | None:
    p = os.environ.get("EINK_DISPLAY_SCRIPT")
    return Path(p) if p else None


def display_python() -> str:
    return os.environ.get("EINK_PYTHON") or sys.executable


def state_dir() -> Path:
    d = Path(os.environ.get("EINK_STATE_DIR", "./eink_state"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def max_image_bytes() -> int:
    return int(os.environ.get("EINK_MAX_IMAGE_BYTES", 16 * 1024 * 1024))


def current_image_path() -> Path:
    return state_dir() / "current.png"


def download_image(url: str, timeout: int = 15) -> bytes:
    """从 URL 下载图片字节，带大小上限。"""
    req = urllib.request.Request(url, headers={"User-Agent": "eink-diary/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        data = resp.read(max_image_bytes() + 1)
    if len(data) > max_image_bytes():
        raise ValueError("图片超过大小上限")
    return data


def push_to_panel(image_path: Path) -> None:
    """调 Waveshare 刷屏脚本把图刷到 E-Ink。脚本不存在则抛错（非 Pi 环境）。"""
    script = display_script()
    if script is None or not script.exists():
        raise RuntimeError(
            "未配置可用的 EINK_DISPLAY_SCRIPT（非 Pi 环境或路径错误）"
        )
    result = subprocess.run(
        [display_python(), str(script), str(image_path)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "刷屏失败"
        )
