#!/usr/bin/env bash
# Install BotProxyBridge (+ optionally Flowseal tg-ws-proxy).
# https://github.com/argentezzy/botproxybridge
#
# Env:
#   WITH_TG_WS_PROXY=auto|1|0   default auto — install tg-ws-proxy if :1443 is free
#   INSTALL_DIR=/opt/botproxybridge
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/botproxybridge}"
SERVICE_NAME="${SERVICE_NAME:-botproxybridge}"
WITH_TG_WS_PROXY="${WITH_TG_WS_PROXY:-auto}"
TG_PORT="${TG_WS_PROXY_PORT:-1443}"

listening_tg() {
  ss -lnt 2>/dev/null | grep -qE ":${TG_PORT}\\b" || \
    ss -lntp 2>/dev/null | grep -qE ":${TG_PORT}\\b"
}

echo "==> BotProxyBridge install → ${INSTALL_DIR}"
echo "    WITH_TG_WS_PROXY=${WITH_TG_WS_PROXY}"

# --- optional tg-ws-proxy ---
case "${WITH_TG_WS_PROXY}" in
  1|yes|true)
    bash "${ROOT}/scripts/install-tg-ws-proxy.sh"
    ;;
  0|no|false)
    if ! listening_tg; then
      echo "WARN: nothing on :${TG_PORT}. Install tg-ws-proxy later:"
      echo "      WITH_TG_WS_PROXY=1 $0"
      echo "      or https://github.com/Flowseal/tg-ws-proxy/releases"
    else
      echo "==> tg-ws-proxy already on :${TG_PORT}"
    fi
    ;;
  auto|*)
    if listening_tg; then
      echo "==> Port :${TG_PORT} busy — reuse existing MTProto proxy"
    else
      echo "==> No listener on :${TG_PORT} — installing Flowseal tg-ws-proxy"
      bash "${ROOT}/scripts/install-tg-ws-proxy.sh"
    fi
    ;;
esac

# --- bridge ---
mkdir -p "${INSTALL_DIR}/data/sessions" "${INSTALL_DIR}/data/files"

if command -v rsync >/dev/null; then
  rsync -a --delete \
    --exclude '.git' \
    --exclude 'venv' \
    --exclude '.env' \
    --exclude 'data' \
    "${ROOT}/" "${INSTALL_DIR}/"
else
  mkdir -p "${INSTALL_DIR}"
  cp -a "${ROOT}/app" "${ROOT}/deploy" "${ROOT}/scripts" "${ROOT}/requirements.txt" \
    "${ROOT}/.env.example" "${INSTALL_DIR}/" 2>/dev/null || true
  cp -a "${ROOT}/README.md" "${ROOT}/INSTALL.md" "${ROOT}/DEPENDENCIES.md" \
    "${ROOT}/AI_INSTALL_PROMPT.md" "${ROOT}/LICENSE" "${INSTALL_DIR}/" 2>/dev/null || true
fi

cd "${INSTALL_DIR}"
if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "==> Created ${INSTALL_DIR}/.env"
fi

# Pull MTPROXY_SECRET from /etc/tg-ws-proxy/secret if .env has empty/example value
SECRET_FILE="/etc/tg-ws-proxy/secret"
EXAMPLE_SECRET="0123456789abcdef0123456789abcdef"
if [[ -f "${SECRET_FILE}" ]]; then
  SECRET="$(tr -d '[:space:]' < "${SECRET_FILE}")"
  if [[ "${SECRET}" =~ ^(dd|ee)([0-9a-fA-F]{32})$ ]]; then
    SECRET="${BASH_REMATCH[2]}"
  fi
  CUR="$(grep -E '^MTPROXY_SECRET=' .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]' || true)"
  if [[ -z "${CUR}" || "${CUR}" == "${EXAMPLE_SECRET}" || "${CUR}" == your_* ]]; then
    if grep -qE '^MTPROXY_SECRET=' .env; then
      sed -i "s|^MTPROXY_SECRET=.*|MTPROXY_SECRET=${SECRET}|" .env
    else
      printf '\nMTPROXY_SECRET=%s\n' "${SECRET}" >> .env
    fi
    echo "==> Synced MTPROXY_SECRET from ${SECRET_FILE}"
  fi
fi

install -m 644 deploy/botproxybridge.service "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"

sleep 1
systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
curl -fsS "http://127.0.0.1:${LISTEN_PORT:-8096}/health" || true
echo
echo "==> Done."
echo "    Fill TELEGRAM_API_ID / TELEGRAM_API_HASH / ALLOWED_BOT_TOKENS in ${INSTALL_DIR}/.env"
echo "    Bots: TELEGRAM_API_BASE=http://127.0.0.1:8096 (Docker: host.docker.internal:8096)"
echo "    Docs: DEPENDENCIES.md  INSTALL.md"
