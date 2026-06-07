#!/bin/bash
# 把精简 display server 部署到 Pi。
# 从 .env 读 deploy 目标（schema 与私有配置分离），再 rsync 传上去。
#
# .env 需要：
#   EINK_DEPLOY_HOST=grapeot@192.168.x.x      # Pi 的 ssh 目标（passwordless）
#   EINK_DEPLOY_PATH=~/co/eink_diary_display   # Pi 上的部署路径
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# 加载 .env（只取需要的两个变量）
if [ ! -f .env ]; then echo "缺 .env（参考 .env.example）"; exit 1; fi
EINK_DEPLOY_HOST="$(grep -E '^EINK_DEPLOY_HOST=' .env | head -1 | cut -d= -f2-)"
EINK_DEPLOY_PATH="$(grep -E '^EINK_DEPLOY_PATH=' .env | head -1 | cut -d= -f2-)"

if [ -z "${EINK_DEPLOY_HOST:-}" ] || [ -z "${EINK_DEPLOY_PATH:-}" ]; then
  echo "请在 .env 配置 EINK_DEPLOY_HOST 和 EINK_DEPLOY_PATH"; exit 1
fi

echo "部署 display server → ${EINK_DEPLOY_HOST}:${EINK_DEPLOY_PATH}"

# 传：server 代码 + Waveshare 驱动 + Pi 端脚本 + pyproject
# 注意：RaspberryPi 驱动库来自归档（原样复用），部署时一并带上。
DRIVER_SRC="../archived/pi_eink_control_original/RaspberryPi"

ssh "$EINK_DEPLOY_HOST" "mkdir -p ${EINK_DEPLOY_PATH}"
rsync -az --delete \
  --exclude='__pycache__' --exclude='*.pyc' \
  server/ "${EINK_DEPLOY_HOST}:${EINK_DEPLOY_PATH}/server/"
rsync -az pyproject.toml "${EINK_DEPLOY_HOST}:${EINK_DEPLOY_PATH}/"
rsync -az scripts/run_display_pi.sh "${EINK_DEPLOY_HOST}:${EINK_DEPLOY_PATH}/"
rsync -az "$DRIVER_SRC/" "${EINK_DEPLOY_HOST}:${EINK_DEPLOY_PATH}/RaspberryPi/"

echo "已传完。Pi 上启动见 README（首次需 uv pip install -e '.[server]' 并配 .env）。"
