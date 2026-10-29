#!/usr/bin/env bash
# Install Flowseal tg-ws-proxy CLI (MTProto) for headless Linux.
# Source: https://github.com/Flowseal/tg-ws-proxy
set -euo pipefail

TG_DIR="${TG_WS_PROXY_DIR:-/opt/tg-ws-proxy}"
TG_REPO="${TG_WS_PROXY_REPO:-https://github.com/Flowseal/tg-ws-proxy.git}"
TG_HOST="${TG_WS_PROXY_HOST:-127.0.0.1}"
TG_PORT="${TG_WS_PROXY_PORT:-1443}"
SECRET_FILE="${TG_WS_PROXY_SECRET_FILE:-/etc/tg-ws-proxy/secret}"
ENV_FILE="${TG_WS_PROXY_ENV_FILE:-/etc/tg-ws-proxy/env}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

listening() {
  ss -lnt 2>/dev/null | grep -qE ":${TG_PORT}\\b" || \
    ss -lntp 2>/dev/null | grep -qE ":${TG_PORT}\\b"
}

if listening; then
  echo "==> Port ${TG_PORT} already in use — skip tg-ws-proxy install"
  exit 0
fi

if ! command -v git >/dev/null || ! command -v python3 >/dev/null; then
  echo "ERROR: need git and python3" >&2
  exit 1
fi

echo "==> Installing tg-ws-proxy into ${TG_DIR}"
echo "    repo: ${TG_REPO}"
mkdir -p "${TG_DIR}" /etc/tg-ws-proxy

if [[ -d "${TG_DIR}/.git" ]]; then
  git -C "${TG_DIR}" fetch --depth 1 origin
  git -C "${TG_DIR}" reset --hard origin/HEAD 2>/dev/null || git -C "${TG_DIR}" pull --ff-only || true
else
  rm -rf "${TG_DIR}"
  git clone --depth 1 "${TG_REPO}" "${TG_DIR}"
fi

cd "${TG_DIR}"
if [[ ! -d venv ]]; then
  python3 -m venv venv
fi
./venv/bin/pip install -U pip
./venv/bin/pip install -e .

if [[ ! -x ./venv/bin/tg-ws-proxy ]]; then
  echo "ERROR: tg-ws-proxy entrypoint missing after pip install -e ." >&2
  echo "Check https://github.com/Flowseal/tg-ws-proxy/blob/main/docs/EN/BuildFromSource.md" >&2
  exit 1
fi

if [[ -f "${SECRET_FILE}" ]]; then
  SECRET="$(tr -d '[:space:]' < "${SECRET_FILE}")"
  # Telethon wants raw 32-hex; strip dd/ee if present
  if [[ "${SECRET}" =~ ^(dd|ee)([0-9a-fA-F]{32})$ ]]; then
    SECRET="${BASH_REMATCH[2]}"
  fi
else
  SECRET="$(openssl rand -hex 16)"
  printf '%s\n' "${SECRET}" > "${SECRET_FILE}"
  chmod 600 "${SECRET_FILE}"
  echo "==> Generated secret → ${SECRET_FILE}"
fi

printf 'TG_WS_PROXY_SECRET=%s\n' "${SECRET}" > "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

install -m 644 "${ROOT}/deploy/tg-ws-proxy.service" /etc/systemd/system/tg-ws-proxy.service
# Bake host/port into override if non-default — keep unit simple via drop-in
mkdir -p /etc/systemd/system/tg-ws-proxy.service.d
cat > /etc/systemd/system/tg-ws-proxy.service.d/override.conf <<EOF
[Service]
ExecStart=
ExecStart=${TG_DIR}/venv/bin/tg-ws-proxy --host ${TG_HOST} --port ${TG_PORT} --secret \${TG_WS_PROXY_SECRET}
EOF

systemctl daemon-reload
systemctl enable tg-ws-proxy.service
systemctl restart tg-ws-proxy.service
sleep 1
systemctl --no-pager --full status tg-ws-proxy.service || true

if ! listening; then
  echo "ERROR: tg-ws-proxy did not bind ${TG_HOST}:${TG_PORT}" >&2
  journalctl -u tg-ws-proxy -n 40 --no-pager || true
  exit 1
fi

echo "==> tg-ws-proxy listening on ${TG_HOST}:${TG_PORT}"
echo "    secret file: ${SECRET_FILE}"
