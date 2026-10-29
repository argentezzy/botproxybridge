from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import unquote

from aiohttp import web

from app.config import load_settings
from app.methods import call_bot_api
from app.pool import BotPool

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("botproxybridge")

BOT_PATH = re.compile(r"^/bot(?P<token>[^/]+)/(?P<method>[a-zA-Z0-9_]+)$")
FILE_PATH = re.compile(r"^/file/bot(?P<token>[^/]+)/(?P<path>.+)$")


class AppState:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.pool = BotPool(self.settings)


STATE = AppState()


def _ok(result: Any) -> web.Response:
    return web.json_response({"ok": True, "result": result})


def _fail(description: str, status: int = 400, error_code: int = 400) -> web.Response:
    return web.json_response(
        {"ok": False, "error_code": error_code, "description": description},
        status=status,
    )


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "ok": True,
            "service": "botproxybridge",
            "bots": len(STATE.settings.allowed_tokens),
        }
    )


async def _parse_payload(request: web.Request) -> tuple[dict[str, Any], tuple[str, bytes, str] | None]:
    ctype = request.content_type or ""
    upload = None
    payload: dict[str, Any] = {}

    if request.method == "GET":
        payload = dict(request.rel_url.query)
    elif "multipart/form-data" in ctype:
        reader = await request.multipart()
        while True:
            part = await reader.next()
            if part is None:
                break
            name = part.name or ""
            if part.filename:
                content = await part.read(decode=False)
                upload = (part.filename, content, part.headers.get("Content-Type", "application/octet-stream"))
                # Bot API uses field name document/photo/etc.
                payload["_upload_field"] = name
            else:
                payload[name] = (await part.text()).strip()
    elif "application/json" in ctype:
        try:
            body = await request.json()
            if isinstance(body, dict):
                payload = body
        except Exception:
            payload = {}
    else:
        # x-www-form-urlencoded or raw
        try:
            data = await request.post()
            payload = {k: data.getone(k) for k in data.keys()}
        except Exception:
            text = await request.text()
            if text:
                try:
                    body = json.loads(text)
                    if isinstance(body, dict):
                        payload = body
                except Exception:
                    pass

    # normalize booleans / nested json fields commonly sent as strings
    for key in list(payload.keys()):
        if key == "reply_markup" and isinstance(payload[key], str):
            try:
                payload[key] = json.loads(payload[key])
            except Exception:
                pass
        if key == "commands" and isinstance(payload[key], str):
            try:
                payload[key] = json.loads(payload[key])
            except Exception:
                pass
        if key == "allowed_updates" and isinstance(payload[key], str):
            try:
                payload[key] = json.loads(payload[key])
            except Exception:
                pass
    return payload, upload


async def bot_api(request: web.Request) -> web.Response:
    token = unquote(str(request.match_info.get("token") or ""))
    method = str(request.match_info.get("method") or "")
    if not token or not method:
        match = BOT_PATH.match(request.path)
        if not match:
            return _fail("Not Found", status=404, error_code=404)
        token = unquote(match.group("token"))
        method = match.group("method")
    if token not in STATE.settings.allowed_tokens:
        return _fail("Unauthorized", status=401, error_code=401)

    payload, upload = await _parse_payload(request)

    try:
        if method == "getUpdates":
            offset = payload.get("offset")
            timeout = payload.get("timeout") or 0
            allowed = payload.get("allowed_updates")
            if isinstance(allowed, str):
                raw = allowed.strip()
                if raw.startswith("["):
                    allowed = json.loads(raw)
                elif raw:
                    allowed = [x.strip() for x in raw.split(",") if x.strip()]
                else:
                    allowed = None
            result = await STATE.pool.get_updates(
                token,
                offset=int(offset) if offset not in (None, "") else None,
                timeout=int(timeout or 0),
                allowed_updates=list(allowed) if allowed else None,
            )
            return _ok(result)

        runtime = await STATE.pool.get(token)
        field = payload.pop("_upload_field", None)
        file_tuple = upload
        if upload and field in ("document", "photo", "audio", "voice", "video"):
            # already set
            pass
        result = await call_bot_api(
            runtime.client,
            method,
            payload,
            file_registry=runtime.files,
            token_key=runtime.token_key,
            upload=file_tuple,
        )
        return _ok(result)
    except PermissionError as exc:
        return _fail(str(exc), status=401, error_code=401)
    except ValueError as exc:
        return _fail(str(exc), status=400, error_code=400)
    except Exception as exc:
        logger.exception("method failed: %s", method)
        return _fail(str(exc), status=500, error_code=500)


async def file_api(request: web.Request) -> web.Response:
    token = unquote(str(request.match_info.get("token") or ""))
    rel = str(request.match_info.get("path") or "")
    if not token or not rel:
        match = FILE_PATH.match(request.path)
        if not match:
            return _fail("Not Found", status=404, error_code=404)
        token = unquote(match.group("token"))
        rel = match.group("path")
    if token not in STATE.settings.allowed_tokens:
        return _fail("Unauthorized", status=401, error_code=401)
    runtime = await STATE.pool.get(token)
    assert runtime.files is not None
    path = (runtime.files.root / rel).resolve()
    if not str(path).startswith(str(runtime.files.root.resolve())):
        return _fail("Forbidden", status=403, error_code=403)
    if not path.exists():
        return _fail("File not found", status=404, error_code=404)
    return web.FileResponse(path)


async def on_cleanup(app: web.Application) -> None:
    await STATE.pool.close()


def create_app() -> web.Application:
    app = web.Application(client_max_size=64 * 1024 * 1024)
    app.router.add_get("/health", health)
    app.router.add_route("*", "/bot{token}/{method}", bot_api)
    app.router.add_get("/file/bot{token}/{path:.*}", file_api)
    app.on_cleanup.append(on_cleanup)
    return app


def main() -> None:
    settings = STATE.settings
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    app = create_app()
    logger.info(
        "Starting Bot API bridge on %s:%s tokens=%s",
        settings.listen_host,
        settings.listen_port,
        len(settings.allowed_tokens),
    )
    web.run_app(app, host=settings.listen_host, port=settings.listen_port, print=logger.info)


if __name__ == "__main__":
    main()
