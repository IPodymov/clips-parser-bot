# clips-parser

Telegram-бот для скачивания видео: пользователь присылает ссылку (YouTube, TikTok, Instagram, VK, X и сотни других сайтов, которые поддерживает yt-dlp), бот скачивает видео и присылает его файлом в чат.

**Стек:** Python 3.12, aiogram 3, yt-dlp + ffmpeg + deno, Taskiq + Redis, PostgreSQL + SQLAlchemy 2 (async) + Alembic, Local Bot API Server, Docker Compose.

## Требования

- Docker + Docker Compose v2
- Для локальной разработки: Python 3.12, ffmpeg, deno (нужен yt-dlp для YouTube)
- Токен бота от [@BotFather](https://t.me/BotFather)
- `api_id` и `api_hash` с [my.telegram.org](https://my.telegram.org) → *API development tools* (нужны Local Bot API серверу)

## Настройка

```bash
cp .env.example .env
```

Обязательно заполнить `BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`. Остальные переменные описаны в `.env.example`.

> ⚠️ Если бот раньше работал через `api.telegram.org`, перед переходом на Local Bot API его нужно один раз разлогинить:
> `curl https://api.telegram.org/bot<BOT_TOKEN>/logOut`

`DATABASE_URL`, `REDIS_URL`, `BOT_API_URL` и `DOWNLOAD_DIR` в `.env` — это значения для запуска с хоста. Внутри Docker Compose они переопределяются на адреса сервисов.

## Запуск в Docker

```bash
make up        # docker compose up -d --build
make logs      # логи bot и worker
make ps        # статус контейнеров
make down
```

Сервисы:

| Сервис             | Назначение                                                         |
|--------------------|--------------------------------------------------------------------|
| `bot`              | aiogram polling; при старте применяет миграции (`alembic upgrade head`) |
| `worker`           | Taskiq worker: yt-dlp → отправка видео → кэш → запись в БД         |
| `telegram-bot-api` | Local Bot API Server (`--local`), файлы до 2 ГБ                    |
| `postgres`         | БД; проброшен на `127.0.0.1:5433` для alembic с хоста              |
| `redis`            | очередь задач, кэш `file_id`, антифлуд                             |

Worker и `telegram-bot-api` делят volume `downloads`, смонтированный в `/downloads` в обоих контейнерах: worker передаёт серверу путь `file:///downloads/...`, и тот читает файл с диска без HTTP-загрузки.

## Локальная разработка

```bash
make venv                          # python3.12 -m venv .venv
make install                       # pip install -r requirements-dev.txt
docker compose up -d postgres redis
make migrate                       # alembic upgrade head
```

Зависимости: `requirements.txt` (runtime, ставится в Docker-образ) и `requirements-dev.txt` (+ линтеры и тесты). Версии зафиксированы; при обновлении пакета обновите пин вручную.

## Ветки и CI/CD

- `dev` — основная ветка разработки, PR открываются в неё.
- `main` — стабильная ветка, обновляется только через PR из `dev`.
- Релиз — тег `vX.Y.Z` на `main`.

GitHub Actions:

| Workflow                | Когда                         | Что делает                                                        |
|-------------------------|-------------------------------|-------------------------------------------------------------------|
| `CI`                    | push и PR в `main`/`dev`      | ruff, mypy, pytest; `alembic check` на Postgres; сборка образа    |
| `Publish image`         | push в `main`/`dev`, теги `v*` | образ в `ghcr.io/ipodymov/clips-parser-bot` (`:dev`, `:latest`, `:X.Y.Z`) |

Dependabot раз в неделю открывает PR с обновлениями зависимостей в `dev`.

## Команды Makefile

| Команда                  | Что делает                                        |
|--------------------------|---------------------------------------------------|
| `make up` / `make down`  | поднять / остановить стек                         |
| `make logs`              | логи `bot` и `worker`                             |
| `make migrate`           | применить миграции (с хоста, postgres на :5433)   |
| `make revision m="..."`  | `alembic revision --autogenerate -m "..."`        |
| `make lint`              | `ruff check --fix` + `ruff format`                |
| `make typecheck`         | `mypy src` (strict)                               |
| `make test`              | `pytest`                                          |
| `make check`             | lint + typecheck + test                           |

## Как проверить вручную

1. `/start` — приветствие; `/start src_test` — новому пользователю запишется `users.source = 'test'`.
2. `/help` — инструкция.
3. Ссылка на короткое видео: TikTok, Instagram Reels, X, VK, YouTube Shorts → «⏳ Загружаю…», затем видео и «✅ Готово!».
4. Та же ссылка в другом виде (`youtu.be/…` вместо `youtube.com/shorts/…`, с `?si=…`) → видео приходит сразу из кэша, без «Загружаю».
5. `https://example.com` → «сайт не поддерживается»; приватное/удалённое видео → «видео недоступно».
6. 6+ ссылок за минуту → сообщение антифлуда.

Проверка в БД: `docker compose exec postgres psql -U bot -d bot -c "select * from downloads order by id desc limit 5"`.

## Известные ограничения

- YouTube может отвечать «This video is unavailable» для запросов с IP дата-центров и некоторых сетей. Помогают `PROXY_URL` (резидентный прокси) и/или `YTDLP_COOKIES_FILE`.
- Instagram и часть роликов VK/Vimeo требуют cookies (`YTDLP_COOKIES_FILE`, формат Netscape). Файл нужно смонтировать в контейнер `worker` и указать путь внутри контейнера.
