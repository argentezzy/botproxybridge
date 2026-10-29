# Промпт для нейросети / агента

Скопируйте блок ниже целиком в Cursor / Codex / другого агента с доступом к серверу по SSH.  
Подставьте свои значения в секции `СЕКРЕТЫ И ПАРАМЕТРЫ`.

Ссылки «что скачать»: [DEPENDENCIES.md](DEPENDENCIES.md).

---

## Промпт

```text
Ты DevOps/агент. Установи на Linux-сервере проект BotProxyBridge из
https://github.com/argentezzy/botproxybridge
и подключи к нему указанные Telegram-боты так, чтобы они ходили на локальный Bot API
мост, а мост — в Telegram через уже существующий (или тобой установленный) tg-ws-proxy MTProto.

Ссылки:
- tg-ws-proxy: https://github.com/Flowseal/tg-ws-proxy
- релизы: https://github.com/Flowseal/tg-ws-proxy/releases
- CLI из исходников: https://github.com/Flowseal/tg-ws-proxy/blob/main/docs/EN/BuildFromSource.md
- опционально Go: https://github.com/spatiumstas/tg-ws-proxy-go
- api_id/hash: https://my.telegram.org/apps
- DEPENDENCIES: https://github.com/argentezzy/botproxybridge/blob/main/DEPENDENCIES.md
- INSTALL: https://github.com/argentezzy/botproxybridge/blob/main/INSTALL.md

install.sh по умолчанию (WITH_TG_WS_PROXY=auto) сам ставит Flowseal CLI, если :1443 свободен.
Если прокси уже есть — не переустанавливай. Не ставь Zapret-Manager.

ЖЁСТКИЕ ПРАВИЛА:
- Не печатай токены, api_hash, MTPROXY_SECRET в чат/логи доступа.
- Не коммить .env и session-файлы.
- Не ставь Zapret-Manager, если не попросили явно.
- Не ломай уже работающие сервисы без бэкапа unit/.env.
- После установки покажи только статус (active/ports/usernames), без секретов.
- Отвечай пользователю на русском, коротко.

СЕКРЕТЫ И ПАРАМЕТРЫ (заполни до запуска):
- SSH: host=… user=… (ключ или уже настроенный доступ)
- TELEGRAM_API_ID=…
- TELEGRAM_API_HASH=…
- ALLOWED_BOT_TOKENS=token1,token2   # боты, которые пойдут через мост
- MTPROXY: если tg-ws-proxy уже на 127.0.0.1:1443 — используй его и secret из /etc/tg-ws-proxy/secret
  иначе скачай/поставь с https://github.com/Flowseal/tg-ws-proxy/releases
  (или CLI по BuildFromSource), secret 32-hex, systemd на 127.0.0.1:1443 MTProto
  (не SOCKS5)
- LISTEN_PORT=8096
- Пути ботов на сервере (если есть): …
  Для каждого бота: выставить TELEGRAM_API_BASE на мост и очистить TELEGRAM_PROXY_URL.
  Если бот в Docker — добавить extra_hosts host.docker.internal:host-gateway и
  TELEGRAM_API_BASE=http://host.docker.internal:8096
  Для python-telegram-bot — base_url={API_BASE}/bot и base_file_url={API_BASE}/file/bot
  (патч кода допустим, с .bak).

ПЛАН РАБОТЫ (выполни по порядку, сам проверяй команды):
1) Проверь ОС, python3, systemd, свободный порт 8096, наличие listen :1443.
2) Убедись что tg-ws-proxy MTProto жив; если нет — поставь и проверь.
3) git clone https://github.com/argentezzy/botproxybridge.git /opt/botproxybridge
   (если каталог есть — git pull).
4) Запусти sudo ./scripts/install.sh (auto поставит tg-ws-proxy при необходимости).
   Или WITH_TG_WS_PROXY=0/1 sudo -E ./scripts/install.sh.
5) Запиши /opt/botproxybridge/.env (chmod 600) из параметров выше.
6) systemctl restart botproxybridge; дождись getMe по каждому токену (username в ответе).
7) Подключи указанных ботов к TELEGRAM_API_BASE моста; перезапусти контейнеры/сервисы.
8) Смоук-тест:
   - curl health :8096
   - getMe по токенам
   - sendMessage себе (chat_id integer/string digits) если дали chat_id
   - getUpdates не должен отдавать 400 на allowed_updates=message
9) В финале отчитайся таблицей:
   сервис | active? | порт | боты (usernames) | как подключены
   и 3-5 строк «как откатить» (systemctl stop, вернуть TELEGRAM_API_BASE/прокси из .bak).

ОГРАНИЧЕНИЯ ПРОДУКТА (учти при отладке):
- Мост эмулирует только часть Bot API (getMe, getUpdates, send/edit/deleteMessage,
  answerCallbackQuery, setMyCommands, sendDocument/Photo, getFile, getChat, webhook stubs).
- Unsupported method → либо добавь в app/methods.py, либо скажи пользователю чего не хватает.
- Входящие апдейты идут из Telethon events, не из официального long-poll.
- Не используй SOCKS5 tg-ws-proxy для Bot API HTTPS — только MTProto :1443 для Telethon.

Начни сейчас. Если какого-то параметра из «СЕКРЕТЫ» нет — спроси ОДНИМ сообщением списком, не начинай установку.
```

---

## Короткий вариант (если сервер и секреты уже в контексте агента)

```text
Установи https://github.com/argentezzy/botproxybridge на этот сервер по INSTALL.md
и AI_INSTALL_PROMPT.md из репозитория. Используй существующий tg-ws-proxy :1443.
Подключи боты <имена/пути> к TELEGRAM_API_BASE=http://host.docker.internal:8096,
прокси Telegram очисти. Секреты не печатай. В конце — статус и smoke-тест getMe.
```
