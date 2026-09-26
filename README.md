# <img src="static/img/favicon.svg" width="64">  DB STAT

**Русский** | [English](README.en.md)

## Описание проекта

```
Веб-приложение для мониторинга и диагностики баз данных PostgreSQL/Greenplum/Greengage.
Проект помогает оценивать состояние подключённых баз данных через единый интерфейс.
Приложение позволяет проводить мониторинг баз данных.
Основная цель DB STAT - упростить ежедневный контроль состояния БД.

По каждому подключению можно сформировать общий диагностический PDF-отчёт (размеры схем и
крупнейших таблиц, активные запросы/сессии/блокировки, эффективность доступа к таблицам,
статистика VACUUM/ANALYZE и заключение о производительности) — отчёт формируется в фоне,
на русском или английском, история и скачивание готовых файлов — во вкладке
«Настройки → PDF-отчёты».
```

## Скачать образ из hub.docker

https://hub.docker.com/r/olegegoism/db-stat

## Демо проекта

[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/9NN8SoxMOZA)

## Скриншоты проекта

<table>
  <tr>
    <td align="center">
      <img src="screenshots/db.png" width="700" alt="Database dashboard"><br>
      <sub>База данных — размер, активность, слоты подключений</sub>
    </td>
    <td align="center">
      <img src="screenshots/memory.png" width="700" alt="Memory dashboard"><br>
      <sub>Память — параметры и использование</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="screenshots/service.png" width="700" alt="Service dashboard"><br>
      <sub>Обслуживание — VACUUM/ANALYZE, живые/мёртвые строки</sub>
    </td>
    <td align="center">
      <img src="screenshots/session.png" width="700" alt="Session dashboard"><br>
      <sub>Сессии — активные подключения пользователей</sub>
    </td>
  </tr>
</table>

## Запуск проекта в режиме разаработки

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
- Установка библиотек из файла requirements.txt

Через обычный `venv` + `pip`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Либо через [uv](https://docs.astral.sh/uv/) — тот же результат, но заметно быстрее:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

`uv venv` создаёт `.venv` в той же папке, что и обычный `venv`, поэтому переконфигурировать интерпретатор в IDE не нужно. Флаг `--python 3.12` важен, если `python3` в системе по умолчанию указывает на более старую версию (Django 6 требует Python 3.12+) — `uv` сам найдёт установленный `python3.12`, если он есть, либо скачает нужную версию.

- Создание таблиц базы данных (модели `db_statistics` не используют миграции — см. `MIGRATION_MODULES` в `db/settings.py` — их таблицы синхронизируются напрямую из моделей)

```bash
python manage.py migrate --run-syncdb
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

- Запуск сервера

```bash
python manage.py runserver
```

- Проверка и автоисправление кода

```bash
python -m ruff check .
python -m ruff check . --fix
python -m ruff format .
```

## Команды Make

Основные шаги для `Makefile` — полный список с описанием: `make help` или `make` (по умолчанию).

| Команда                                | Что делает                                                                                       |
|----------------------------------------|--------------------------------------------------------------------------------------------------|
| `make install`                         | Установить зависимости из requirements.txt                                                       |
| `make hooks`                           | Включить git-хуки проекта для этого клона (один раз после клонирования)                          |
| `make migrations`                      | Сгенерировать миграции для встроенных приложений Django (`db_statistics` их не использует)       |
| `make migrate`                         | Применить миграции Django и синхронизировать таблицы `db_statistics`                             |
| `make run`                             | Запустить сервер разработки                                                                      |
| `make shell`                           | Открыть интерактивную Django-оболочку                                                            |
| `make admin`                           | Создать первого администратора (см. `INITIAL_ADMIN_*` в `.env`)                                  |
| `make lint` / `make lint-fix`          | Проверить код (без исправлений / с автоисправлением)                                             |
| `make format`                          | Отформатировать код                                                                              |
| `make collectstatic`                   | Собрать статику (как при сборке Docker-образа)                                                   |
| `make docker-build`                    | Собрать Docker-образ                                                                             |
| `make docker-run` / `make docker-stop` | Запустить / остановить Docker-контейнер                                                          |
| `make clean`                           | Удалить кэши и локально собранную статику                                                        |
| `make reset-db`                        | ОПАСНО: удалить SQLite БД и все миграции `db_statistics` (кроме `__init__.py`), с подтверждением |

## Запуск проекта в Docker

- Сборка Docker-образа

```bash
docker build -t db-stat .
```

- Запуск Docker-контейнера

```bash
docker run --name db-stat --rm -p 8000:8000 olegegoism/db-stat:latest
```

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