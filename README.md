# BotProxyBridge

Локальный HTTP-фасад под [Telegram Bot API](https://core.telegram.org/bots/api). Снаружи бот ходит как на `api.telegram.org`, внутри — [Telethon](https://github.com/LonamiWebs/Telethon) через [tg-ws-proxy](https://github.com/Flowseal/tg-ws-proxy) (MTProto).

Задуман под **aiogram** (и вообще Bot API-клиенты: PTB, httpx): когда с сервера HTTPS к Telegram мёртв, а MTProto через прокси жив — бот продолжает слать обычные `bot.send_message` / polling, без переписывания на Telethon.

> Проект написан нейросетью.

```
bot  →  :8096 BotProxyBridge  →  Telethon  →  :1443 tg-ws-proxy  →  Telegram
```

[Установка](#установка) · [Требования](#требования) · [Что скачать](#что-скачать) · [Подключение бота](#подключение-бота) · [Методы](#методы) · [Промпт для AI](AI_INSTALL_PROMPT.md) · [INSTALL](INSTALL.md) · [DEPENDENCIES](DEPENDENCIES.md)

## Требования

- Linux, Python **3.11+**, systemd, sudo
- Рабочий **tg-ws-proxy** (MTProto) на `127.0.0.1:1443` — не SOCKS5 под Bot API
- `api_id` / `api_hash` с [my.telegram.org/apps](https://my.telegram.org/apps)
- Токены ботов для `ALLOWED_BOT_TOKENS` (от [@BotFather](https://t.me/BotFather))
- Порты по умолчанию: **1443** (прокси), **8096** (мост)

## Что скачать

Ссылки: **[DEPENDENCIES.md](DEPENDENCIES.md)**.

По умолчанию `install.sh` (`WITH_TG_WS_PROXY=auto`) сам ставит [Flowseal tg-ws-proxy](https://github.com/Flowseal/tg-ws-proxy) CLI, если **:1443 свободен**. Свой прокси на этом порту не трогает.

| | URL |
|---|---|
| tg-ws-proxy | https://github.com/Flowseal/tg-ws-proxy |
| релизы | https://github.com/Flowseal/tg-ws-proxy/releases |
| CLI / BuildFromSource | https://github.com/Flowseal/tg-ws-proxy/blob/main/docs/EN/BuildFromSource.md |
| api_id / api_hash | https://my.telegram.org/apps |
| BotProxyBridge | https://github.com/argentezzy/botproxybridge |
| Telethon / aiohttp | `pip` из [`requirements.txt`](requirements.txt) |
| Go-порт (опц.) | https://github.com/spatiumstas/tg-ws-proxy-go |

## Установка

Полный разбор: [INSTALL.md](INSTALL.md).

```bash
git clone https://github.com/argentezzy/botproxybridge.git /opt/botproxybridge
cd /opt/botproxybridge
chmod +x scripts/install.sh scripts/install-tg-ws-proxy.sh
sudo ./scripts/install.sh
# принудительно без прокси:  WITH_TG_WS_PROXY=0 sudo -E ./scripts/install.sh
# принудительно с прокси:   WITH_TG_WS_PROXY=1 sudo -E ./scripts/install.sh
sudo nano /opt/botproxybridge/.env   # API_ID/HASH + ALLOWED_BOT_TOKENS
sudo systemctl restart botproxybridge
curl -sS http://127.0.0.1:8096/health
curl -sS "http://127.0.0.1:8096/bot<TOKEN>/getMe"
```

## Подключение бота

```env
TELEGRAM_API_BASE=http://127.0.0.1:8096
TELEGRAM_PROXY_URL=
```

Docker — не `127.0.0.1`, а хост:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

```env
TELEGRAM_API_BASE=http://host.docker.internal:8096
```

python-telegram-bot:

```python
Application.builder().token(TOKEN).base_url(f"{API_BASE}/bot").base_file_url(f"{API_BASE}/file/bot").build()
```

## Методы

Сейчас: `getMe`, `getUpdates`, `sendMessage`, `editMessageText`, `deleteMessage`, `answerCallbackQuery`, `setMyCommands`, `sendDocument`, `sendPhoto`, `getFile` (+ `/file/bot…`), `getChat`, заглушки webhook.

Остальное — в `app/methods.py` по мере надобности. Входящие апдейты из Telethon events, не из официального long-poll.

## Промпт для AI

Готовый текст для Cursor/Codex: **[AI_INSTALL_PROMPT.md](AI_INSTALL_PROMPT.md)** — вставить агенту, подставить SSH/`api_id`/токены, не светить секреты в чат.

Коротко:

```text
Поставь https://github.com/argentezzy/botproxybridge по INSTALL.md
(sudo ./scripts/install.sh — auto поставит tg-ws-proxy, если :1443 свободен).
Подключи боты к TELEGRAM_API_BASE=http://host.docker.internal:8096,
TELEGRAM_PROXY_URL очисти. Секреты не печатай. В конце — status + getMe.
```

## Файлы

| | |
|---|---|
| [INSTALL.md](INSTALL.md) | установка, Docker, отладка |
| [DEPENDENCIES.md](DEPENDENCIES.md) | ссылки: что скачать |
| [AI_INSTALL_PROMPT.md](AI_INSTALL_PROMPT.md) | промпт агенту |
| [.env.example](.env.example) | конфиг |
| [scripts/install.sh](scripts/install.sh) | мост + auto tg-ws-proxy |
| [scripts/install-tg-ws-proxy.sh](scripts/install-tg-ws-proxy.sh) | только Flowseal CLI |
| [deploy/botproxybridge.service](deploy/botproxybridge.service) | systemd |

## Thanks

- [Telethon](https://github.com/LonamiWebs/Telethon) — MTProto
- [Flowseal/tg-ws-proxy](https://github.com/Flowseal/tg-ws-proxy), [tg-ws-proxy-go](https://github.com/spatiumstas/tg-ws-proxy-go) — туннель
- [aiohttp](https://github.com/aio-libs/aiohttp) — HTTP
- [Telegram Bot API](https://core.telegram.org/bots/api)

## License

[MIT](LICENSE). Неофициальный инструмент, не связан с Telegram. Соблюдайте [ToS](https://telegram.org/tos), не коммитьте `.env` и session-файлы.
