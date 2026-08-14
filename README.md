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

После изменения исходного кода старый уже запущенный контейнер **не обновляется**. Пересоздайте его из нового образа. Для публикации исправления в Docker Hub выполните:

```bash
docker build --pull -t olegegoism/db-stat:latest .
docker push olegegoism/db-stat:latest
docker rm -f db-stat 2>/dev/null || true
```

- Запуск Docker-контейнера с доступом к PostgreSQL на хосте (Linux и Docker Desktop)

```bash
docker run --rm \
  --name db-stat \
  -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e LOCAL_DATABASE_HOST=host.docker.internal \
  olegegoism/db-stat:latest
```

Или используйте готовую конфигурацию:

```bash
docker compose up --build --force-recreate
```

В новом контейнере поле «Хост» по умолчанию показывает `host.docker.internal`. Можно также ввести `localhost` или `127.0.0.1`: приложение заменит их на значение `LOCAL_DATABASE_HOST`. Если сообщение об ошибке всё ещё содержит `127.0.0.1`, запущен **старый образ**, поскольку исправленная версия пытается подключиться к `host.docker.internal`.

PostgreSQL на хосте также должен принимать TCP-подключения не только через Unix-сокет. Проверьте `listen_addresses` в `postgresql.conf`, разрешите Docker-подсеть в `pg_hba.conf` и откройте порт `5432` в firewall. После изменения конфигурации перезапустите PostgreSQL. Не публикуйте порт 5432 в интернет: разрешайте только локальную Docker-подсеть.

Доступно по адресу: http://localhost:8000

Для диагностики разрешения имени и доступности порта:

```bash
docker run --rm --add-host=host.docker.internal:host-gateway busybox nslookup host.docker.internal
docker run --rm --add-host=host.docker.internal:host-gateway busybox nc -vz host.docker.internal 5432
```


## Скачать образ из hub.docker

https://hub.docker.com/r/olegegoism/db-stat
