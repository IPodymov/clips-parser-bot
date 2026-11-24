# CLAUDE.md

## Проект

Telegram-бот для скачивания видео по ссылке (YouTube, TikTok, Instagram, VK, X и всё, что умеет yt-dlp). Пользователь шлёт ссылку → бот ставит задачу в очередь → воркер скачивает через yt-dlp и отправляет видео в чат. Один разработчик; проект в стадии базового функционала, впереди монетизация.

## Архитектура

```
Telegram ⇄ telegram-bot-api (local) ⇄ bot (aiogram, polling)
                                       │  kiq(download_video)
                                       ▼
                                  Redis (taskiq queue "downloads", кэш file_id, антифлуд)
                                       │
                                       ▼
                                  worker (taskiq) → yt-dlp → /downloads (shared volume)
                                       │  send_video(file:///downloads/...)
                                       ▼
                                  telegram-bot-api → Telegram;  PostgreSQL (users, downloads)
```

- `src/core/` — инфраструктура: `config.py` (pydantic-settings, `get_settings()`), `db.py`, `models.py`, `redis.py`, `telegram.py` (фабрика `Bot` для бота и воркера), `logging.py`.
- `src/bot/` — aiogram: `main.py` (сборка Dispatcher, DI через workflow data), `handlers/` (тонкие), `middlewares/` (`DbSessionMiddleware` — сессия на апдейт + commit; `UserMiddleware` — регистрация, `last_active_at`, кладёт `user`/`is_new_user` в data).
- `src/worker/` — `broker.py` (ListQueueBroker, ресурсы воркера в `state.resources: WorkerResources`), `tasks.py` (`download_video`).
- `src/downloader/` — без зависимостей от Telegram/БД: `urls.py` (извлечение, детект платформы, нормализация = ключ кэша), `service.py` (`VideoDownloader`, yt-dlp в `asyncio.to_thread`, таймаут, лимит размера), `errors.py` (исключения с `user_message`).
- `src/services/` — бизнес-логика: `users.py`, `cache.py` (`VideoCache`, `RateLimiter`), `downloads.py`.

Ключевые решения:
- Кэш: `video:<sha1(normalized_url)>` → Telegram `file_id`, TTL `CACHE_TTL_DAYS`. Протухший `file_id` удаляется и видео качается заново.
- Большие файлы: worker и telegram-bot-api монтируют volume в один путь `/downloads`; видео отправляется как `file://` URI (лимит 2 ГБ, без HTTP-аплоада). Без `BOT_API_URL` — `FSInputFile` через api.telegram.org (лимит 50 МБ).
- Брокер Redis создаётся с `socket_timeout=None`: иначе дефолтный 5-секундный таймаут redis-py 8 рвёт блокирующий `BRPOP`.
- yt-dlp для YouTube требует JS-рантайм: в образ копируется `deno`, в зависимостях `yt-dlp[default]` (тянет `yt-dlp-ejs`).
- Статус загрузки пишется в `downloads` одной записью по факту (success/failed), включая попадания в кэш (`from_cache`).

## Конвенции

- Бизнес-логика — в `src/services/`, хендлеры тонкие: разобрать апдейт → вызвать сервис → ответить.
- `src/downloader/` не знает про Telegram и БД.
- Типизация обязательна: `mypy --strict` должен проходить (`make typecheck`). На границе с yt-dlp — `cast`, внутри plain `dict[str, Any]`.
- Тексты для пользователя — на русском; ошибки скачивания — через `DownloaderError.user_message`.
- Все исключения логируются; задача воркера не должна падать из-за вспомогательных вызовов (редактирование статуса, запись в БД).
- Миграции — **только** `alembic revision --autogenerate` (`make revision m="..."`), руками не писать; после генерации проверить файл глазами.
- Зависимости — `requirements.txt` (runtime) и `requirements-dev.txt`, версии пиним точно.
- Перед коммитом: `make check` (ruff + mypy + pytest).
- Конфиг — только через `Settings`; новые переменные добавлять и в `.env.example` с комментарием.

## Команды

```bash
make install / make up / make logs / make migrate / make revision m="..." / make check
.venv/bin/pytest tests/test_urls.py -q
```

## Планы (следующие этапы)

Архитектура уже готова под них: пользователь доступен в каждом хендлере через `UserMiddleware`, `downloads` хранит историю, есть `users.source`.

1. **Лимиты** — N бесплатных загрузок в сутки; считать по `downloads` или счётчиком в Redis; проверка в сервисе перед `kiq`. Поля подписки/тарифа в `users`.
2. **ЮKassa** — платежи/подписка: таблицы `payments`, `subscriptions`; webhook (понадобится aiohttp/FastAPI-сервис) или polling статуса; идемпотентность по `payment_id`.
3. **Админка** — команды для админов (фильтр по `ADMIN_IDS`): статистика из `users`/`downloads`, рассылка (через Taskiq с троттлингом), бан пользователей (`users.is_banned` + проверка в middleware).
4. **Рефералы** — расширить `/start` payload (`ref_<tg_id>` наряду с `src_xxx`), `users.referrer_id`, бонусы к лимитам.
