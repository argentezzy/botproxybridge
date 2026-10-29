from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    mtproxy_host: str
    mtproxy_port: int
    mtproxy_secret: str
    listen_host: str
    listen_port: int
    data_dir: Path
    allowed_tokens: frozenset[str]


def load_settings() -> Settings:
    secret = os.getenv("MTPROXY_SECRET", "").strip()
    if not secret and Path("/etc/tg-ws-proxy/secret").exists():
        secret = Path("/etc/tg-ws-proxy/secret").read_text(encoding="utf-8").strip()
    if secret.startswith(("dd", "ee")) and len(secret) > 32:
        secret = secret[2:]

    tokens_raw = os.getenv("ALLOWED_BOT_TOKENS", "").strip()
    tokens = frozenset(t.strip() for t in tokens_raw.split(",") if t.strip())
    if not tokens:
        raise RuntimeError("ALLOWED_BOT_TOKENS is empty")

    return Settings(
        api_id=int(_require("TELEGRAM_API_ID")),
        api_hash=_require("TELEGRAM_API_HASH"),
        mtproxy_host=os.getenv("MTPROXY_HOST", "127.0.0.1").strip() or "127.0.0.1",
        mtproxy_port=int(os.getenv("MTPROXY_PORT", "1443") or 1443),
        mtproxy_secret=secret or _require("MTPROXY_SECRET"),
        listen_host=os.getenv("LISTEN_HOST", "0.0.0.0").strip() or "0.0.0.0",
        listen_port=int(os.getenv("LISTEN_PORT", "8096") or 8096),
        data_dir=Path(os.getenv("DATA_DIR", "/opt/botproxybridge/data")),
        allowed_tokens=tokens,
    )
