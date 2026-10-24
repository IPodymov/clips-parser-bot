# Как внести вклад

Спасибо, что хотите помочь проекту! Ниже — всё, что нужно, чтобы ваш PR приняли быстро.

## Перед началом

- Нашли баг или хотите новую фичу — сначала откройте issue. Для небольших правок (опечатки, мелкие фиксы) можно сразу PR.
- Уязвимости **не** публикуйте в issue — напишите автору напрямую через GitHub.

## Окружение

Нужны Python 3.12, Docker, ffmpeg и deno (yt-dlp использует его для YouTube).

```bash
git clone https://github.com/IPodymov/clips-parser-bot.git
cd clips-parser-bot
git checkout dev
make venv && make install
cp .env.example .env               # вписать BOT_TOKEN своего тестового бота
docker compose up -d postgres redis
make migrate
```

Запуск бота и воркера с хоста:

```bash
.venv/bin/python -m src.bot.main
.venv/bin/taskiq worker src.worker.broker:broker src.worker.tasks --workers 1 --max-async-tasks 3
```

Без `BOT_API_URL` бот работает через `api.telegram.org` — этого достаточно для разработки (лимит файла 50 МБ).

## Ветки

- Ответвляйтесь от `dev` и открывайте PR **в `dev`**. `main` — стабильная ветка, туда попадает только `dev`.
- Имена веток: `feat/...`, `fix/...`, `docs/...`, `refactor/...`.

## Правила кода

- Бизнес-логика — в `src/services/`, хендлеры тонкие. `src/downloader/` не зависит от Telegram и БД.
- Типизация обязательна: `mypy --strict` должен проходить.
- Тексты для пользователей бота — на русском.
- Конфиг — только через `Settings` (`src/core/config.py`); новую переменную добавьте и в `.env.example` с комментарием.
- Зависимости пинятся точной версией в `requirements.txt` / `requirements-dev.txt`.
- Миграции — только через `make revision m="..."` (autogenerate), руками не писать; сгенерированный файл проверьте глазами. CI падает, если модели и миграции расходятся.
- На новую логику — тесты в `tests/`.

Перед пушем:

```bash
make check   # ruff + mypy + pytest
```

## Коммиты и PR

Сообщения коммитов — в стиле [Conventional Commits](https://www.conventionalcommits.org/): `feat: ...`, `fix: ...`, `docs: ...`, `ci: ...`, `refactor: ...`, `test: ...`.

В описании PR: что и зачем изменено, как проверить, ссылка на issue (`Closes #123`). PR мержится после зелёного CI.

## Лицензия

Отправляя PR, вы соглашаетесь, что ваш вклад распространяется под [лицензией MIT](LICENSE).
