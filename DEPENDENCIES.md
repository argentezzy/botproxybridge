# Что скачать / поставить

`scripts/install.sh` ставит **BotProxyBridge** и по умолчанию (`WITH_TG_WS_PROXY=auto`) — **Flowseal tg-ws-proxy CLI**, если на `:1443` ещё никто не слушает.

- Уже есть свой прокси на 1443 → скрипт его не трогает  
- `WITH_TG_WS_PROXY=0` → только мост  
- `WITH_TG_WS_PROXY=1` → всегда вызвать `scripts/install-tg-ws-proxy.sh` (если порт свободен)  
- Отдельно: `sudo ./scripts/install-tg-ws-proxy.sh`

## Обязательно

| Что | Ссылка | Зачем |
|---|---|---|
| **tg-ws-proxy** (MTProto) | [github.com/Flowseal/tg-ws-proxy](https://github.com/Flowseal/tg-ws-proxy) | Туннель для Telethon |
| Релизы (бинари) | [Flowseal/tg-ws-proxy/releases](https://github.com/Flowseal/tg-ws-proxy/releases) | Готовые сборки Linux/Windows/macOS |
| Сборка CLI из исходников | [docs: BuildFromSource](https://github.com/Flowseal/tg-ws-proxy/blob/main/docs/EN/BuildFromSource.md) | `pip install -e .` → `tg-ws-proxy` |
| **api_id / api_hash** | [my.telegram.org/apps](https://my.telegram.org/apps) | Учётка приложения для Telethon |
| **Токены ботов** | [@BotFather](https://t.me/BotFather) | Список в `ALLOWED_BOT_TOKENS` |
| **Этот мост** | [argentezzy/botproxybridge](https://github.com/argentezzy/botproxybridge) | HTTP Bot API → Telethon |

Python-зависимости моста подтянет `pip` из [`requirements.txt`](requirements.txt):

- [Telethon](https://github.com/LonamiWebs/Telethon) — [docs](https://docs.telethon.dev/)
- [aiohttp](https://github.com/aio-libs/aiohttp)
- [python-dotenv](https://github.com/theskumar/python-dotenv)

## Опционально

| Что | Ссылка | Зачем |
|---|---|---|
| tg-ws-proxy (Go) | [spatiumstas/tg-ws-proxy-go](https://github.com/spatiumstas/tg-ws-proxy-go) | Альтернативная сборка / SOCKS5-режим |
| Zapret-Manager / GUI-обвязки | не требуются для моста | Не ставить «заодно», если не просили |
| [aiogram](https://github.com/aiogram/aiogram) | клиент бота | Типичный потребитель моста |
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | клиент бота | То же |
| [Telegram Bot API](https://core.telegram.org/bots/api) | спецификация | Контракт, который эмулирует фасад |

## Минимальный путь на Linux (сервер)

1. Поставить **tg-ws-proxy** (релиз или CLI):
   - релизы: https://github.com/Flowseal/tg-ws-proxy/releases  
   - или из исходников: https://github.com/Flowseal/tg-ws-proxy + [BuildFromSource](https://github.com/Flowseal/tg-ws-proxy/blob/main/docs/EN/BuildFromSource.md)
2. Слушать `127.0.0.1:1443`, secret сохранить (например `/etc/tg-ws-proxy/secret`)
3. Взять `api_id`/`api_hash`: https://my.telegram.org/apps
4. Клонировать мост: https://github.com/argentezzy/botproxybridge  
   → `sudo ./scripts/install.sh`
