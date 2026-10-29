from __future__ import annotations

import json
import logging
import re
from typing import Any

from telethon import Button, TelegramClient
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.functions.messages import SetBotCallbackAnswerRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault

logger = logging.getLogger(__name__)


def _markup_to_buttons(reply_markup: dict | None):
    if not reply_markup:
        return None
    if isinstance(reply_markup, str):
        try:
            reply_markup = json.loads(reply_markup)
        except json.JSONDecodeError:
            return None
    rows = reply_markup.get("inline_keyboard")
    if not rows:
        return None
    buttons = []
    for row in rows:
        line = []
        for btn in row:
            text = str(btn.get("text") or "")
            if btn.get("url"):
                line.append(Button.url(text, str(btn["url"])))
            elif btn.get("callback_data") is not None:
                line.append(Button.inline(text, data=str(btn["callback_data"]).encode("utf-8")))
            else:
                line.append(Button.inline(text, data=b"noop"))
        if line:
            buttons.append(line)
    return buttons or None


def _parse_mode(value: Any) -> str | None:
    if not value:
        return None
    mode = str(value).upper()
    if mode == "HTML":
        return "html"
    if mode in ("MARKDOWN", "MARKDOWNV2"):
        return "md"
    return None


def _chat_id(value: Any) -> Any:
    """Telethon bots must use int IDs; string digits are treated as phone numbers."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return value


def _msg_result(msg, chat_id) -> dict[str, Any]:
    return {
        "message_id": msg.id,
        "date": int(msg.date.timestamp()) if getattr(msg, "date", None) else 0,
        "chat": {"id": int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id},
        "text": msg.message or "",
    }


async def call_bot_api(
    client: TelegramClient,
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    file_registry=None,
    token_key: str = "",
    upload: tuple[str, bytes, str] | None = None,
) -> Any:
    payload = dict(payload or {})
    method = str(method or "").strip()

    if method == "getMe":
        me = await client.get_me()
        return {
            "id": me.id,
            "is_bot": bool(me.bot),
            "first_name": me.first_name or "",
            "username": me.username or "",
            "can_join_groups": True,
            "can_read_all_group_messages": False,
            "supports_inline_queries": False,
        }

    if method in ("deleteWebhook", "setWebhook", "close", "logOut"):
        return True

    if method == "getWebhookInfo":
        return {
            "url": "",
            "has_custom_certificate": False,
            "pending_update_count": 0,
        }

    if method == "setMyCommands":
        commands = []
        for item in payload.get("commands") or []:
            if isinstance(item, str):
                item = json.loads(item)
            commands.append(
                BotCommand(
                    command=str(item.get("command") or "").lstrip("/"),
                    description=str(item.get("description") or "")[:256],
                )
            )
        await client(
            SetBotCommandsRequest(scope=BotCommandScopeDefault(), lang_code="", commands=commands)
        )
        return True

    if method == "sendMessage":
        chat_id = _chat_id(payload["chat_id"])
        text = payload.get("text") or ""
        parse_mode = _parse_mode(payload.get("parse_mode"))
        buttons = _markup_to_buttons(payload.get("reply_markup"))
        kwargs: dict[str, Any] = {
            "entity": chat_id,
            "message": text,
            "link_preview": not bool(
                str(payload.get("disable_web_page_preview", True)).lower() in ("1", "true", "yes")
                if not isinstance(payload.get("disable_web_page_preview"), bool)
                else payload.get("disable_web_page_preview", True)
            ),
            "buttons": buttons,
        }
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        if payload.get("reply_to_message_id") is not None:
            kwargs["reply_to"] = int(payload["reply_to_message_id"])
        msg = await client.send_message(**kwargs)
        return _msg_result(msg, chat_id)

    if method == "editMessageText":
        chat_id = _chat_id(payload["chat_id"])
        message_id = int(payload["message_id"])
        text = payload.get("text") or ""
        parse_mode = _parse_mode(payload.get("parse_mode"))
        buttons = _markup_to_buttons(payload.get("reply_markup"))
        kwargs: dict[str, Any] = {
            "entity": chat_id,
            "message": message_id,
            "text": text,
            "link_preview": not bool(payload.get("disable_web_page_preview", True)),
            "buttons": buttons,
        }
        if parse_mode:
            kwargs["parse_mode"] = parse_mode
        try:
            msg = await client.edit_message(**kwargs)
        except Exception as exc:
            if "not modified" in str(exc).lower() or "MessageNotModified" in type(exc).__name__:
                return {"message_id": message_id, "chat": {"id": chat_id}, "text": text}
            raise
        return _msg_result(msg, chat_id)

    if method == "deleteMessage":
        await client.delete_messages(_chat_id(payload["chat_id"]), [int(payload["message_id"])])
        return True

    if method == "answerCallbackQuery":
        await client(
            SetBotCallbackAnswerRequest(
                query_id=int(payload["callback_query_id"]),
                cache_time=int(payload.get("cache_time") or 0),
                message=str(payload.get("text") or "") or None,
                alert=bool(payload.get("show_alert")),
            )
        )
        return True

    if method == "sendDocument":
        chat_id = _chat_id(payload["chat_id"])
        caption = payload.get("caption") or None
        if not upload:
            raise ValueError("sendDocument requires multipart file")
        filename, content, _ctype = upload
        from io import BytesIO

        bio = BytesIO(content)
        bio.name = filename
        msg = await client.send_file(
            chat_id,
            bio,
            caption=caption,
            force_document=True,
            parse_mode=_parse_mode(payload.get("parse_mode")),
        )
        return _msg_result(msg, chat_id)

    if method == "sendPhoto":
        chat_id = _chat_id(payload["chat_id"])
        caption = payload.get("caption") or None
        if not upload:
            # photo may be file_id string — not supported yet
            raise ValueError("sendPhoto requires multipart file in this bridge")
        from io import BytesIO

        filename, content, _ctype = upload
        bio = BytesIO(content)
        bio.name = filename
        msg = await client.send_file(chat_id, bio, caption=caption, parse_mode=_parse_mode(payload.get("parse_mode")))
        return _msg_result(msg, chat_id)

    if method == "getFile":
        if not file_registry:
            raise ValueError("file registry missing")
        file_id = str(payload.get("file_id") or "")
        return await file_registry.ensure_downloaded(client, token_key, file_id)

    if method == "getChat":
        entity = await client.get_entity(_chat_id(payload["chat_id"]))
        username = getattr(entity, "username", None)
        title = getattr(entity, "title", None) or getattr(entity, "first_name", None) or str(payload["chat_id"])
        is_channel = getattr(entity, "broadcast", False) or type(entity).__name__ == "Channel"
        is_megagroup = getattr(entity, "megagroup", False)
        if is_channel and not is_megagroup:
            chat_type = "channel"
        elif is_megagroup:
            chat_type = "supergroup"
        elif getattr(entity, "title", None):
            chat_type = "group"
        else:
            chat_type = "private"
        return {
            "id": entity.id if getattr(entity, "id", None) is not None else payload["chat_id"],
            "type": chat_type,
            "title": title,
            "username": username,
        }

    raise ValueError(f"Unsupported method: {method}")
