from __future__ import annotations

from typing import Any


def user_to_bot_api(user) -> dict[str, Any]:
    if not user:
        return {}
    return {
        "id": int(user.id),
        "is_bot": bool(getattr(user, "bot", False)),
        "first_name": getattr(user, "first_name", None) or "",
        "last_name": getattr(user, "last_name", None) or "",
        "username": getattr(user, "username", None) or "",
    }


def chat_to_bot_api(chat) -> dict[str, Any]:
    if not chat:
        return {}
    chat_id = int(getattr(chat, "id", 0))
    is_channel = getattr(chat, "broadcast", False)
    is_mega = getattr(chat, "megagroup", False)
    if (is_channel or is_mega) and chat_id > 0:
        chat_id = int(f"-100{chat_id}")
    if is_channel and not is_mega:
        chat_type = "channel"
    elif is_mega:
        chat_type = "supergroup"
    elif getattr(chat, "title", None):
        chat_type = "group"
    else:
        chat_type = "private"
    return {
        "id": chat_id,
        "type": chat_type,
        "title": getattr(chat, "title", None) or "",
        "username": getattr(chat, "username", None) or "",
        "first_name": getattr(chat, "first_name", None) or "",
    }


def _file_id(chat_id: int, message_id: int, kind: str) -> str:
    return f"lw:{chat_id}:{message_id}:{kind}"


async def message_to_bot_api(event, file_registry) -> dict[str, Any]:
    msg = event.message
    chat = await event.get_chat()
    sender = await event.get_sender()
    chat_api = chat_to_bot_api(chat)
    chat_id = int(chat_api["id"])
    data: dict[str, Any] = {
        "message_id": msg.id,
        "date": int(msg.date.timestamp()) if getattr(msg, "date", None) else 0,
        "chat": chat_api,
        "from": user_to_bot_api(sender),
        "text": msg.message or "",
    }
    if getattr(msg, "reply_to", None) and getattr(msg.reply_to, "forum_topic", False):
        data["message_thread_id"] = msg.reply_to.reply_to_msg_id

    if msg.voice:
        fid = _file_id(chat_id, msg.id, "voice")
        file_registry.register(fid, chat_id, msg.id, "voice")
        data["voice"] = {
            "file_id": fid,
            "file_unique_id": fid,
            "duration": int(getattr(msg.voice, "duration", 0) or 0),
            "mime_type": getattr(msg.file, "mime_type", None) or "audio/ogg",
            "file_size": int(getattr(msg.file, "size", 0) or 0),
        }
    elif msg.audio:
        fid = _file_id(chat_id, msg.id, "audio")
        file_registry.register(fid, chat_id, msg.id, "audio")
        data["audio"] = {
            "file_id": fid,
            "file_unique_id": fid,
            "duration": int(getattr(msg.audio, "duration", 0) or 0),
            "mime_type": getattr(msg.file, "mime_type", None) or "audio/mpeg",
            "file_size": int(getattr(msg.file, "size", 0) or 0),
            "file_name": getattr(msg.file, "name", None) or "audio",
        }
    elif msg.photo:
        fid = _file_id(chat_id, msg.id, "photo")
        file_registry.register(fid, chat_id, msg.id, "photo")
        size = int(getattr(msg.file, "size", 0) or 0)
        data["photo"] = [
            {
                "file_id": fid,
                "file_unique_id": fid,
                "width": int(getattr(msg.photo, "w", 0) or 0),
                "height": int(getattr(msg.photo, "h", 0) or 0),
                "file_size": size,
            }
        ]
    elif msg.document:
        fid = _file_id(chat_id, msg.id, "document")
        file_registry.register(fid, chat_id, msg.id, "document")
        data["document"] = {
            "file_id": fid,
            "file_unique_id": fid,
            "file_name": getattr(msg.file, "name", None) or "file",
            "mime_type": getattr(msg.file, "mime_type", None) or "application/octet-stream",
            "file_size": int(getattr(msg.file, "size", 0) or 0),
        }

    if not data.get("text") and msg.message:
        data["caption"] = msg.message

    return data


async def callback_to_bot_api(event) -> dict[str, Any]:
    chat = await event.get_chat()
    sender = await event.get_sender()
    msg = await event.get_message()
    data_raw = event.data.decode("utf-8", errors="replace") if event.data else ""
    result: dict[str, Any] = {
        "id": str(event.query.query_id),
        "from": user_to_bot_api(sender),
        "data": data_raw,
        "chat_instance": str(getattr(event.query, "chat_instance", "") or ""),
    }
    if msg:
        result["message"] = {
            "message_id": msg.id,
            "date": int(msg.date.timestamp()) if getattr(msg, "date", None) else 0,
            "chat": chat_to_bot_api(chat),
            "from": user_to_bot_api(await event.get_sender()),
            "text": msg.message or "",
        }
    return result
