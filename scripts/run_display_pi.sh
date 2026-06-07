#!/bin/bash
# 在 Pi 上启动精简 display server。从部署目录运行。
# 首次使用前：python -m venv .venv && .venv/bin/pip install -e '.[server]'
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# Waveshare 13.3 E6 刷屏脚本（随部署一起传上来的驱动库示例）
export EINK_DISPLAY_SCRIPT="${EINK_DISPLAY_SCRIPT:-$HERE/RaspberryPi/python/examples/display_image.py}"
# 刷屏脚本用的 python（需能 import 驱动库；通常就是本 venv）
export EINK_PYTHON="${EINK_PYTHON:-$HERE/.venv/bin/python}"
# 当前图等状态落盘目录
export EINK_STATE_DIR="${EINK_STATE_DIR:-$HERE/eink_state}"

PORT="${EINK_PORT:-8080}"
echo "启动 display server  http://0.0.0.0:${PORT}"
echo "  EINK_DISPLAY_SCRIPT=$EINK_DISPLAY_SCRIPT"

exec "$HERE/.venv/bin/python" -m uvicorn server.app:app --host 0.0.0.0 --port "$PORT"
