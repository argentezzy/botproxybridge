from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FileRef:
    file_id: str
    chat_id: int
    message_id: int
    kind: str


class FileRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._refs: dict[str, FileRef] = {}

    def register(self, file_id: str, chat_id: int, message_id: int, kind: str) -> None:
        self._refs[file_id] = FileRef(file_id, chat_id, message_id, kind)

    def get(self, file_id: str) -> FileRef | None:
        return self._refs.get(file_id)

    def local_path(self, token_key: str, file_id: str) -> Path:
        safe = file_id.replace(":", "_").replace("/", "_")
        return self.root / token_key / safe

    async def ensure_downloaded(self, client, token_key: str, file_id: str) -> dict[str, Any]:
        ref = self.get(file_id)
        if not ref:
            raise ValueError("Unknown file_id")
        path = self.local_path(token_key, file_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.stat().st_size == 0:
            msg = await client.get_messages(ref.chat_id, ids=ref.message_id)
            if not msg:
                raise ValueError("Source message not found")
            await client.download_media(msg, file=str(path))
        rel = f"{token_key}/{path.name}"
        return {
            "file_id": file_id,
            "file_unique_id": file_id,
            "file_path": rel,
            "file_size": path.stat().st_size,
        }
