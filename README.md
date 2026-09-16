# <img src="static/img/favicon.svg" width="64">  DB STAT

**Русский** | [English](README.en.md)

## Описание проекта

```
Веб-приложение для мониторинга и диагностики баз данных PostgreSQL/Greenplum/Greengage.
Проект помогает оценивать состояние подключённых баз данных через единый интерфейс.
Приложение позволяет проводить мониторинг БД.
Основная цель DB STAT - упростить ежедневный контроль состояния БД.
```

## Образ из hub.docker

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
- Версия Python 3.12+
- Установка библиотек из файла requirements.txt

```bash
pip install -r requirements.txt
```

- Применение миграций

```bash
python manage.py makemigrations
python manage.py migrate
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
| `make migrations`                      | Сгенерировать миграции по изменениям моделей                                                     |
| `make migrate`                         | Применить миграции к базе данных                                                                 |
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


