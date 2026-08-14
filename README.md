# <img src="static/img/favicon.svg" width="64">  DB STAT

**Русский** | [English](README.en.md)

## Описание проекта

```
Веб-приложение для мониторинга и диагностики баз данных PostgreSQL/Greenplum.
Проект помогает оценивать состояние подключённых баз данных через единый интерфейс.
Приложение позволяет проводить мониторинг БД.
Основная цель DB STAT - упростить ежедневный контроль состояния БД.
```

## Демо проекта

[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/9NN8SoxMOZA)

## Скриншоты проекта

<table>
  <tr>
    <td><img src="screenshots/db.png" width="700" alt="Database dashboard"></td>
    <td><img src="screenshots/memory.png" width="700" alt="Memory dashboard"></td>
  </tr>
  <tr>
    <td><img src="screenshots/service.png" width="700" alt="Service dashboard"></td>
    <td><img src="screenshots/session.png" width="700" alt="Session dashboard"></td>
  </tr>
</table>

## Настройка окружения

- Версия Python 3.12

- Файл .env

```
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=*
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
TIME_ZONE=Europe/Minsk
LANGUAGE_CODE=ru

DB_CONNECTION_ENCRYPTION_KEY=

# Хост, на который перенаправляются localhost и ::1 в подключениях приложения
LOCALHOST_DB_HOST=127.0.0.1

DB_ENGINE=sqlite
SQLITE_NAME=db.sqlite3

DB_NAME=db_statistics
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

STATIC_URL=static/
```

## Запуск проекта в режиме разаработки

- Установка библиотек из файла requirements.txt

```bash
pip install -r requirements.txt
```

- Применение миграций (команду необходимо выполнять и после обновления проекта)

```bash
python manage.py makemigrations
python manage.py migrate
```

В частности, эта команда создаёт таблицу `db_favorite`, необходимую для работы избранного. Миграция совместима как с новой базой, так и с существующей базой, таблицы которой ранее были созданы через `run-syncdb`.

- Создание суперпользователя для входа в Django Admin

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin')"
```

- Создание пользователя DBUser для авторизации в приложении

```bash
python manage.py shell -c "from db_statistics.models import DBUser; DBUser.objects.filter(login='admin').exists() or DBUser.objects.create(login='admin', email='admin@example.com', role='Администратор', is_active=True)"
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

## Запуск проекта в Docker

- Сборка Docker-образа

```bash
docker build -t db-stat .
```

- Запуск Docker-контейнера

Обычный запуск контейнера с доступом к локальной БД хоста:

```bash
docker run --name db-stat --rm -p 8000:8000 db-stat
```

В форме подключения укажите `localhost`: внутри образа приложение автоматически
направит такое подключение на хост Docker. Это работает в Docker Desktop и в
обычном Docker под Linux без дополнительного параметра `--add-host`.

PostgreSQL на хосте должен принимать подключения не только через Unix-сокет и
разрешать подключения из сети Docker в `listen_addresses` и `pg_hba.conf`.
При необходимости адрес назначения можно переопределить параметром
`-e LOCALHOST_DB_HOST=<адрес>`.

```
Доступно по адресу: http://localhost:8000
Суперпользователь Django Admin:
- логин: admin
- пароль: admin
Пользователь приложения:
- логин: admin
- почта: admin@example.com

Если после сборки есть ошибка подключения к `172.17.0.1` или `192.168.0.1`, значит запущен старый Docker-образ. 
Пересоберите образ и запустите контейнер заново.

Ошибка `exec /app/docker-entrypoint.sh: no such file or directory` означает, что
entrypoint попал в образ с Windows-переносами строк либо используется образ,
собранный до исправления. В актуальной сборке скрипт принудительно переводится
в LF. Пересоберите и опубликуйте образ, затем снова выполните `docker pull`.
```


## Скачать образ из hub.docker

https://hub.docker.com/r/olegegoism/db-stat
