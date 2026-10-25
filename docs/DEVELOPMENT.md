# Установка, запуск и разработка DB STAT

Краткое описание — в [README](../README.md).

## Запуск в Docker

Образ на Docker Hub: [olegegoism/db-stat](https://hub.docker.com/r/olegegoism/db-stat).

```bash
docker run -d --name db-stat --restart unless-stopped -p 8000:8000 \
  -v db-stat-data:/app/data \
  -e SECRET_KEY='<случайная строка>' \
  -e DB_CONNECTION_ENCRYPTION_KEY='<другая случайная строка>' \
  -e INITIAL_ADMIN_PASSWORD='<пароль администратора>' \
  -e TIME_ZONE=Europe/Minsk \
  olegegoism/db-stat:latest
```

- Замените `Europe/Minsk` на свой часовой пояс.
- Случайные строки: `openssl rand -hex 32`. Сохраните их: без того же `DB_CONNECTION_ENCRYPTION_KEY` сохранённые пароли подключений не расшифруются.
- Без `INITIAL_ADMIN_PASSWORD` пароль администратора будет `admin`. Не оставляйте его.
- Данные хранятся в томе `db-stat-data`. Без `-v` они лежат в анонимном томе, который при `--rm` удаляется вместе с контейнером.
- Откройте http://localhost:8000 и войдите под логином `admin` (или значением `INITIAL_ADMIN_LOGIN`).
- Миграции и недостающие индексы контейнер применяет сам при каждом старте.
- Собрать образ из исходников: `docker build -t db-stat .`. Запуск — той же командой `docker run`, но вместо `olegegoism/db-stat:latest` укажите `db-stat`.

## Обновление

```bash
docker pull olegegoism/db-stat:latest
docker stop db-stat && docker rm db-stat
```

Запустите контейнер той же командой `docker run` с теми же `-v` и `-e`. Данные остаются в томе `db-stat-data`.

## Резервное копирование

Все данные (пользователи, подключения, избранное, журнал аудита) лежат в томе `db-stat-data`. Копируйте их при остановленном контейнере: копия работающей базы SQLite может получиться неконсистентной.

```bash
docker stop db-stat
docker run --rm -v db-stat-data:/data -v "$(pwd)":/backup alpine \
  tar czf /backup/db-stat-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
docker start db-stat
```

Восстановление из архива `<архив>.tar.gz`:

```bash
docker stop db-stat
docker run --rm -v db-stat-data:/data -v "$(pwd)":/backup alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/<архив>.tar.gz -C /data"
docker start db-stat
```

## Частые проблемы

- **Страница не открывается.** Проверьте `docker logs db-stat`. Если порт 8000 занят, используйте `-p 8080:8000`.
- **Вход по IP сервера.** Добавьте в команду `docker run` (контейнер придётся пересоздать): `-e ALLOWED_HOSTS=<ip>,localhost -e CSRF_TRUSTED_ORIGINS=http://<ip>:8000`.
- **База на этом же компьютере.** В подключении укажите `localhost`: приложение заменит его на адрес хоста (`LOCALHOST_DB_HOST`, в образе это `host.docker.internal`). Адрес `127.0.0.1` внутри контейнера означает сам контейнер.
- **Ошибка 503 «Превышен лимит соединений с целевой БД».** См. «Бюджет соединений» ниже.

## Настройки

Полный список — в [.env.example](../.env.example). Основные:

| Переменная | По умолчанию | Когда менять |
|---|---|---|
| `SECRET_KEY` | небезопасная строка | Всегда задавайте свой ключ |
| `DB_CONNECTION_ENCRYPTION_KEY` | равен `SECRET_KEY` | Задайте отдельно до сохранения первого подключения |
| `INITIAL_ADMIN_PASSWORD` | `admin` | Задайте при первом запуске |
| `INITIAL_ADMIN_LOGIN`, `INITIAL_ADMIN_EMAIL` | `admin`, `admin@example.com` | Если нужны другие значения |
| `TIME_ZONE` | `Europe/Minsk` | Задайте свой часовой пояс: без него даты показываются в поясе Europe/Minsk |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Если открываете приложение по IP сервера или другому имени |
| `CSRF_TRUSTED_ORIGINS` | по `ALLOWED_HOSTS` | Вместе с `ALLOWED_HOSTS`: полные адреса с `http://` или `https://` |
| `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` | `False` | За обратным прокси с HTTPS задайте `True` |
| `LANGUAGE_CODE` | `ru` | Язык интерфейса по умолчанию: `ru` или `en` |
| `GUNICORN_WORKERS` | `3` | Число рабочих процессов в контейнере |
| `LOCALHOST_DB_HOST` | `127.0.0.1` (в образе `host.docker.internal`) | Адрес, на который заменяется `localhost` в подключениях |

### Бюджет соединений

Каждый процесс gunicorn держит свой пул: на каждое сохранённое подключение — до `DB_CONNECTION_POOL_MAX_CONN` соединений (по умолчанию 10). Итого на целевой БД ≈ `GUNICORN_WORKERS` × `DB_CONNECTION_POOL_MAX_CONN` × число подключений. Это число должно укладываться в `max_connections` целевой БД. Если пул исчерпан, приложение отвечает 503.

## Разработка

Нужен Python 3.12+ (Docker-образ собирается на 3.13). Все команды раздела выполняйте из корня проекта — папки, где лежит `Makefile`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
make install
```

Создайте файл `.env` в корне проекта. Минимум (все переменные — в `.env.example`):

```
DEBUG=True
SECRET_KEY=<случайная строка>
INITIAL_ADMIN_PASSWORD=admin
TIME_ZONE=Europe/Minsk
```

Затем:

```bash
make migrate   # миграции и недостающие индексы: подходит и для новой, и для существующей базы
make admin     # первый администратор: логин и пароль из INITIAL_ADMIN_*
make run       # сервер разработки: http://127.0.0.1:8000
```

Если вы меняли модели, создайте миграцию и примените её. При первом запуске это не нужно — достаточно `make migrate`. Файл миграции коммитьте вместе с моделью:

```bash
make migrations
make migrate
```

Проверки:

```bash
make test      # тесты без PostgreSQL (интеграционные пропускаются)
make test-pg   # все тесты против PostgreSQL: нужен PG_TEST_PASSWORD; остальные PG_TEST_* — по необходимости
make lint      # проверка кода ruff
make format    # форматирование ruff
```

Браузерные тесты Playwright (`tests/e2e`) проверяют вход, сохранённое подключение и вкладки. Нужны запущенное приложение (`make run`) и PostgreSQL. Адрес приложения задаёт `E2E_BASE_URL` (по умолчанию `http://127.0.0.1:8000`).

```bash
pip install -r requirements.txt -r requirements-e2e.txt
python -m playwright install chromium
E2E_PG_PASSWORD=... python -m pytest tests/e2e -q
```

Служебные команды:

- `python manage.py encrypt_connection_passwords` — один раз зашифровать пароли подключений, сохранённые открытым текстом после обновления со старой версии. Безопасно повторять.
- `python manage.py recover_maintenance_jobs` — вернуть прерванные фоновые задачи (VACUUM/ANALYZE, PDF-отчёты) в очередь после аварийной остановки. В Docker и при `runserver` это происходит автоматически.

## Команды Make

Полный список с описанием: `make help`.

| Команда | Что делает |
|---|---|
| `make install` | Установить зависимости для разработки |
| `make hooks` | Включить git-хуки проекта для этого клона (один раз после клонирования) |
| `make migrations` | Создать миграции после изменения моделей |
| `make migrate` | Применить миграции и добавить недостающие индексы |
| `make run` | Запустить сервер разработки |
| `make admin` | Создать первого администратора |
| `make test` / `make test-pg` | Тесты без PostgreSQL / все тесты против PostgreSQL |
| `make lint` / `make format` | Проверить код / отформатировать код (ruff) |
| `make docker-build` | Собрать Docker-образ |
| `make docker-run` / `make docker-stop` | Запустить / остановить контейнер |
| `make reset-db` | ОПАСНО: удалить только SQLite-базу (миграции не трогаются), с подтверждением |
