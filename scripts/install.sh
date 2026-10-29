#!/usr/bin/env bash
# Install BotProxyBridge on a Linux host (Debian/Ubuntu-like).
# Prerequisites: Python 3.11+, systemd, working local MTProto proxy (tg-ws-proxy).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/botproxybridge}"
SERVICE_NAME="${SERVICE_NAME:-botproxybridge}"

echo "==> Install dir: ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}/data/sessions" "${INSTALL_DIR}/data/files"

rsync -a --delete \
  --exclude '.git' \
  --exclude 'venv' \
  --exclude '.env' \
  --exclude 'data' \
  "${ROOT}/" "${INSTALL_DIR}/"

cd "${INSTALL_DIR}"
if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "==> Created ${INSTALL_DIR}/.env — FILL TELEGRAM_API_ID/HASH, TOKENS, MTPROXY_SECRET"
fi

install -m 644 deploy/botproxybridge.service "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

sleep 1
systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
curl -fsS "http://127.0.0.1:${LISTEN_PORT:-8096}/health" || true
echo
echo "==> Done. Point bots to TELEGRAM_API_BASE=http://127.0.0.1:8096 (or host.docker.internal:8096 from Docker)."
