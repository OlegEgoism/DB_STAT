# Установка, запуск и разработка DB STAT

Этот документ для тех, кто запускает DB STAT в Docker, настраивает его или разрабатывает. Краткое описание — в [README](../README.md).

## Запуск в Docker

Образ опубликован на Docker Hub: [olegegoism/db-stat](https://hub.docker.com/r/olegegoism/db-stat). Для первого запуска выполните одну команду, заменив значения в `<...>`:

```bash
docker run -d --name db-stat --restart unless-stopped -p 8000:8000 \
  -v db-stat-data:/app/data \
  -e SECRET_KEY='<случайная строка>' \
  -e DB_CONNECTION_ENCRYPTION_KEY='<другая случайная строка>' \
  -e INITIAL_ADMIN_PASSWORD='<пароль первого администратора>' \
  olegegoism/db-stat:latest
```

- Случайные строки можно получить командой `openssl rand -hex 32`.
- `-v db-stat-data:/app/data` хранит все данные приложения в именованном томе. Без этой опции данные удаляются вместе с контейнером, поэтому не добавляйте `--rm`.
- Без `INITIAL_ADMIN_PASSWORD` первый администратор получит пароль `admin`. Не оставляйте его.

Откройте http://localhost:8000 и войдите под логином `admin` (или значением `INITIAL_ADMIN_LOGIN`).

Собрать образ из исходников можно командой `docker build -t db-stat .`. Запуск — той же командой `docker run`, с `db-stat` вместо `olegegoism/db-stat:latest`.

При каждом старте контейнер сам применяет миграции и добавляет недостающие индексы, поэтому существующий том с данными обновляется без ручных действий.

## Обновление

```bash
docker pull olegegoism/db-stat:latest
docker stop db-stat && docker rm db-stat
```

Затем запустите контейнер той же командой, что в разделе «Запуск в Docker», с теми же `-v` и `-e`. Данные остаются в томе `db-stat-data`.

## Резервное копирование

Именованный том `db-stat-data` — единственное место, где хранятся все данные приложения (пользователи, сохранённые подключения, избранное, аудит).
Ничего этого не автоматизировано образом — резервное копирование и восстановление тома нужно делать вручную.

- Сделать резервную копию (контейнер может быть при этом запущен):

```bash
docker run --rm -v db-stat-data:/data -v "$(pwd)":/backup alpine \
  tar czf /backup/db-stat-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
```

- Восстановить из резервной копии (сначала остановите контейнер, чтобы не писать поверх открытого файла БД):

```bash
docker stop db-stat
docker run --rm -v db-stat-data:/data -v "$(pwd)":/backup alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/db-stat-backup-ФАЙЛ.tar.gz -C /data"
docker start db-stat
```

## Частые проблемы в Docker

- **Страница не открывается.** Проверьте `docker ps` и `docker logs db-stat`. Если порт 8000 занят, используйте `-p 8080:8000`.
- **Вход не работает, когда приложение открыто по IP сервера.** Добавьте в команду `-e ALLOWED_HOSTS=<ip>,localhost -e CSRF_TRUSTED_ORIGINS=http://<ip>:8000`.
- **База на этом же компьютере.** В хосте подключения укажите `localhost`: в контейнере приложение заменит его на адрес компьютера, где запущен Docker (переменная `LOCALHOST_DB_HOST`, в образе это `host.docker.internal`). Адрес `127.0.0.1` в контейнере означает сам контейнер.

## Настройки (переменные окружения)

Полный список — в файле `.env.example`. Основные:

| Переменная | По умолчанию | Когда менять |
|---|---|---|
| `SECRET_KEY` | публичная строка из образа | Задайте в любой установке |
| `DB_CONNECTION_ENCRYPTION_KEY` | равен `SECRET_KEY` | Задайте отдельно до сохранения первых подключений |
| `INITIAL_ADMIN_PASSWORD` | `admin` | Обязательно задайте при первом запуске |
| `INITIAL_ADMIN_LOGIN`, `INITIAL_ADMIN_EMAIL` | `admin`, `admin@example.com` | Если нужны другие логин или почта |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Если открываете по IP сервера или другому имени |
| `CSRF_TRUSTED_ORIGINS` | по `ALLOWED_HOSTS` | Вместе с `ALLOWED_HOSTS`: полный адрес с `http://` или `https://` |
| `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` | `False` | За обратным прокси с HTTPS задайте `True` |
| `TIME_ZONE` | `Europe/Minsk` | Задайте свой часовой пояс: без него даты показываются в поясе Europe/Minsk |
| `LANGUAGE_CODE` | `ru` | Язык интерфейса по умолчанию: `ru` или `en` |
| `GUNICORN_WORKERS` | `3` | Число рабочих процессов в контейнере |
| `LOCALHOST_DB_HOST` | `host.docker.internal` в образе | Адрес, на который заменяется `localhost` в подключениях |

## Бюджет соединений с целевыми базами

- Бюджет соединений с целевыми БД. Каждый воркер gunicorn (`GUNICORN_WORKERS`, по умолчанию 3) держит свой пул: на каждое сохранённое подключение — до `DB_CONNECTION_POOL_MAX_CONN` соединений (по умолчанию 10). Фоновые задачи (VACUUM/ANALYZE и PDF-отчёты) берут соединения из тех же пулов.

```
Итого на целевой БД ≈ GUNICORN_WORKERS × DB_CONNECTION_POOL_MAX_CONN × число сохранённых подключений в работе
```

Например, 3 воркера × 10 соединений × 2 подключения дают до 60 соединений на целевой БД. Проверьте, что это укладывается в `max_connections` целевой БД с запасом для других клиентов. Если пул исчерпан, приложение отвечает 503 «Превышен лимит соединений с целевой БД». При `DB_CONNECTION_POOL_MAX_CONN` больше 20 `manage.py check` выводит предупреждение `db_statistics.W003`. Подробности — в `.env.example`.

## Разработка из исходников

### Язык интерфейса

- Сообщения на стороне Python (вход, блокировка, срок сессии, ошибка выбора языка, PDF-отчёт) переведены через gettext: исходный текст русский, английский перевод лежит в `db_statistics/locale/en/LC_MESSAGES/django.po`. После правки `.po` пересоберите `django.mo` (например, `pybabel compile -d db_statistics/locale -D django`; пакета Babel в `requirements.txt` нет).
- Интерфейс в браузере (`static/js/i18n.js`) по-прежнему использует собственный словарь. Перевод JS-части на gettext — известный оставшийся пункт.

### Запуск проекта в режиме разработки

- Файл .env
```
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=*
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False
TIME_ZONE=Europe/Minsk
LANGUAGE_CODE=ru
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
SECURE_PROXY_SSL_HEADER=False
DB_CONNECTION_ENCRYPTION_KEY=
INITIAL_ADMIN_LOGIN=admin
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=admin
SQLITE_NAME=db.sqlite3
STATIC_URL=static/
LOCALHOST_DB_HOST=127.0.0.1
```
- Версия Python 3.12+ (Docker-образ собирается на 3.13, см. `Dockerfile`)
- Установка библиотек: `requirements.txt` (рабочие зависимости) и `requirements-dev.txt` (поверх них, добавляет ruff для проверки кода)

Через обычный `venv` + `pip`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Либо через [uv](https://docs.astral.sh/uv/) — тот же результат, но заметно быстрее:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

`uv venv` создаёт `.venv` в той же папке, что и обычный `venv`, поэтому переконфигурировать интерпретатор в IDE не нужно. Флаг `--python 3.12` важен, если `python3` в системе по умолчанию указывает на более старую версию (Django 6 требует Python 3.12+) — `uv` сам найдёт установленный `python3.12`, если он есть, либо скачает нужную версию.

- Создание таблиц базы данных и применение миграций. Модели `db_statistics` ведутся миграциями из `db_statistics/migrations`. Команда одинаково работает для новой базы и для существующей установки: таблицы существующей базы не пересоздаются

```bash
python manage.py migrate --fake-initial
python manage.py ensure_indexes
```

`--fake-initial` отмечает начальную миграцию применённой, если её таблицы уже есть. Так обновляются установки, созданные до появления миграций: команда `migrate` сама переводит их на историю миграций (см. `db_statistics/management/commands/migrate.py`). `ensure_indexes` добавляет индексы, которых нет в уже существующей базе (миграции создают индексы только вместе с таблицами). Команда безопасна для повторного запуска.

- Изменение схемы (поле, таблица, индекс): поменяйте модель, создайте миграцию и примените её. Файл миграции коммитится вместе с изменением модели:

```bash
make migrations   # то же, что python manage.py makemigrations
make migrate
```


- Создание пользователя для входа в приложение, и входа в Django Admin (`/admin/`).
- логин: admin
- почта: admin@example.com
- пароль: admin
```bash
python manage.py ensure_initial_admin
```

- Шифрование паролей подключений, оставшихся в открытом виде после обновления с версии без шифрования (одноразовая команда, безопасно выполнять повторно)

```bash
python manage.py encrypt_connection_passwords
```

- Возврат прерванных фоновых задач (VACUUM/ANALYZE и PDF-отчёты) в очередь после аварийной остановки сервера. В Docker выполняется автоматически при старте; `runserver` восстанавливает задачи автоматически

```bash
python manage.py recover_maintenance_jobs
```

- Запуск сервера

```bash
python manage.py runserver
```

- Тесты. Модульные тесты запускаются без внешних сервисов. Интеграционные (`test_integration_*`) выполняются против настоящего PostgreSQL и пропускаются, пока не заданы переменные `PG_TEST_*`:

```bash
PG_TEST_HOST=127.0.0.1 PG_TEST_PORT=5432 PG_TEST_USER=postgres PG_TEST_PASSWORD=... PG_TEST_DATABASE=postgres python manage.py test
```

- Проверка и автоисправление кода

```bash
python -m ruff check .
python -m ruff check . --fix
python -m ruff format .
```

### Браузерные smoke-тесты (Playwright)

Каталог `tests/e2e` проверяет в Chromium вход, сохранённое подключение, вкладки «Таблицы», «Временные таблицы» и «TOAST-таблицы», поиск и выход. Тестам нужны запущенное приложение и PostgreSQL: тест сохраняет в приложении подключение к этой базе и на время поиска создаёт в ней две таблицы с TOAST-данными (после теста они удаляются).

```bash
pip install -r requirements.txt -r requirements-e2e.txt
python -m playwright install chromium
E2E_PG_PASSWORD=... python -m pytest tests/e2e -q
```

Адрес приложения задаётся переменной `E2E_BASE_URL` (по умолчанию `http://127.0.0.1:8000`). Первый администратор — `admin` с паролем из `E2E_ADMIN_PASSWORD` (по умолчанию `admin12345`). Если приложение не отвечает, тесты пропускаются. В CI они идут отдельной задачей `e2e`, которая пока не блокирует сборку (`continue-on-error`).

### Команды Make

Основные шаги для `Makefile` — полный список с описанием: `make help` или `make` (по умолчанию).

| Команда                                | Что делает                                                                                       |
|----------------------------------------|--------------------------------------------------------------------------------------------------|
| `make install`                         | Установить зависимости для разработки из requirements-dev.txt                                                       |
| `make hooks`                           | Включить git-хуки проекта для этого клона (один раз после клонирования)                          |
| `make migrations`                      | Сгенерировать миграции после изменения моделей (все приложения, включая `db_statistics`)         |
| `make migrate`                         | Применить миграции и добавить недостающие индексы (`migrate --fake-initial` и `ensure_indexes`)  |
| `make run`                             | Запустить сервер разработки                                                                      |
| `make shell`                           | Открыть интерактивную Django-оболочку                                                            |
| `make admin`                           | Создать первого администратора (см. `INITIAL_ADMIN_*` в `.env`)                                  |
| `make lint` / `make lint-fix`          | Проверить код (без исправлений / с автоисправлением)                                             |
| `make format`                          | Отформатировать код                                                                              |
| `make collectstatic`                   | Собрать статику (как при сборке Docker-образа)                                                   |
| `make docker-build`                    | Собрать Docker-образ                                                                             |
| `make docker-run` / `make docker-stop` | Запустить / остановить Docker-контейнер                                                          |
| `make clean`                           | Удалить кэши и локально собранную статику                                                        |
| `make reset-db`                        | ОПАСНО: удалить только SQLite БД (файлы миграций не трогаются), с подтверждением                 |
