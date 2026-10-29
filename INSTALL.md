# Установка BotProxyBridge

Целевая ОС: **Linux** (Debian/Ubuntu), root или sudo. Нужны: Python ≥ 3.11, systemd, исходящий интернет.

---

## 0. Архитектура (что должно получиться)

1. **tg-ws-proxy** слушает `127.0.0.1:1443` (MTProto / WS-туннель)
2. **BotProxyBridge** слушает `0.0.0.0:8096` (HTTP, совместимый с Bot API path `/bot<token>/<method>`)
3. Ваши боты указывают `TELEGRAM_API_BASE` на мост и **не** используют HTTP/SOCKS к Aeza/`api.telegram.org`

---

## 1. Установить tg-ws-proxy (MTProto)

Мост **не** заменяет tg-ws-proxy. Без него Telethon не достучится до DC.

Вариант A — уже есть Flowseal / CLI `tg-ws-proxy` на хосте:

```bash
ss -lntp | grep 1443
# ожидаем LISTEN 127.0.0.1:1443
```

Вариант B — поставить CLI (пример, проверьте актуальный релиз проекта tg-ws-proxy):

1. Скачайте linux amd64 бинарь
2. Сгенерируйте secret (32 hex)
3. Сохраните secret в `/etc/tg-ws-proxy/secret` (chmod 600)
4. Запустите как systemd unit `tg-ws-proxy.service` на `127.0.0.1:1443`

**Важно для Telethon:** в `.env` моста `MTPROXY_SECRET` — **сырой 32-hex**, без префиксов `dd`/`ee`.  
Если secret в файле с `dd…`, мост сам обрежет префикс.

Проверка: после старта моста в логах должно быть `Bot ready @YourBot`.

---

## 2. API ID / API Hash

1. Зайдите на https://my.telegram.org/apps
2. Создайте приложение (platform: Other)
3. Скопируйте `api_id` и `api_hash`

Один `api_id`/`api_hash` можно использовать для нескольких бот-токенов на одном мосте (у каждого токена своя Telethon-сессия).

---

## 3. Установка моста

```bash
git clone https://github.com/argentezzy/botproxybridge.git /opt/botproxybridge
cd /opt/botproxybridge
chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

Скрипт:

- копирует код в `/opt/botproxybridge`
- создаёт venv и ставит зависимости
- кладёт `.env` из `.env.example` (если ещё нет)
- ставит systemd unit `botproxybridge`
- делает `enable` + `restart`

### Заполнить `.env`

```bash
sudo nano /opt/botproxybridge/.env
sudo chmod 600 /opt/botproxybridge/.env
```

Обязательно:

```env
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
ALLOWED_BOT_TOKENS=TOKEN1,TOKEN2
MTPROXY_HOST=127.0.0.1
MTPROXY_PORT=1443
MTPROXY_SECRET=...   # или файл /etc/tg-ws-proxy/secret
LISTEN_HOST=0.0.0.0
LISTEN_PORT=8096
DATA_DIR=/opt/botproxybridge/data
```

Перезапуск:

```bash
sudo systemctl restart botproxybridge
sudo systemctl status botproxybridge --no-pager
curl -sS http://127.0.0.1:8096/health
```

Ожидаем: `{"ok": true, "service": "botproxybridge", ...}`

Проверка токена:

```bash
curl -sS "http://127.0.0.1:8096/bot<TOKEN>/getMe"
```

---

## 4. Подключить ботов

### 4.1. Общий принцип

Замените базу API на мост и **уберите** исходящий HTTP/SOCKS-прокси к Telegram (иначе запросы уйдут мимо localhost).

```env
TELEGRAM_API_BASE=http://127.0.0.1:8096
TELEGRAM_PROXY_URL=
```

### 4.2. Docker

Внутри контейнера `127.0.0.1` — это сам контейнер. Нужен хост:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

```env
TELEGRAM_API_BASE=http://host.docker.internal:8096
TELEGRAM_PROXY_URL=
```

Мост должен слушать `0.0.0.0:8096` (по умолчанию так и есть).

### 4.3. python-telegram-bot (v20+)

```python
api_base = os.environ["TELEGRAM_API_BASE"].rstrip("/")
app = (
    Application.builder()
    .token(token)
    .base_url(f"{api_base}/bot")
    .base_file_url(f"{api_base}/file/bot")
    .build()
)
```

### 4.4. Сырой httpx / свой клиент

```text
POST {API_BASE}/bot{token}/sendMessage
GET  {API_BASE}/bot{token}/getUpdates?timeout=25
GET  {API_BASE}/file/bot{token}/{file_path}
```

Ответ — JSON вида `{"ok": true, "result": ...}` как у официального Bot API.

### 4.5. aiogram 3

Задайте свой `TelegramAPIServer` / base URL на мост (см. доку aiogram `BaseTelegramClient` / `TelegramAPIServer.from_base`).  
Либо оставьте HTTP-клиент с `base_url=http://host.docker.internal:8096`.

---

## 5. Поведение, о котором важно знать

1. **Входящие апдейты** собираются из Telethon events, не из long-poll официального Bot API.  
   `getUpdates` читает локальную очередь моста.
2. **`file_id`** для входящих медиа — локальные (`lw:chat:msg:kind`), скачивание только через этот мост.
3. **`chat_id` строкой из цифр** мост приводит к `int` (иначе Telethon думает, что это телефон).
4. Клиент с «огромным» `offset` от старого Bot API не ломает очередь — мост игнорирует нерелевантный offset.
5. Не все методы Bot API реализованы. Недостающий метод → 400 `Unsupported method` → добавьте в `app/methods.py`.
6. Один токен = одна Telethon-сессия в `DATA_DIR/sessions/`. Не гоняйте один и тот же токен параллельно через официальный API и мост.

---

## 6. Диагностика

```bash
systemctl status botproxybridge tg-ws-proxy --no-pager
journalctl -u botproxybridge -n 80 --no-pager
ss -lntp | grep -E ':(1443|8096)\b'
curl -sS http://127.0.0.1:8096/health
curl -sS "http://127.0.0.1:8096/bot$TOKEN/getMe"
```

Типичные проблемы:

| Симптом | Что проверить |
|---|---|
| `getMe` таймаут | tg-ws-proxy / secret / firewall |
| `token not allowed` | `ALLOWED_BOT_TOKENS` |
| `sendMessage` про entity/phone | chat_id должен быть numeric; мост сам кастит строки |
| Docker `connection refused` | `extra_hosts` + listen `0.0.0.0` |
| Пустой `getUpdates` | бот не получает MTProto updates — смотрите journal Telethon/proxy |

---

## 7. Обновление

```bash
cd /opt/botproxybridge
sudo git pull
sudo ./scripts/install.sh
```

`.env` и `data/` скрипт не затирает.
