# <img src="static/img/favicon.svg" width="64"> 
# DB STAT

## Описание проекта

```
Веб-приложение для мониторинга и диагностики баз данных PostgreSQL/Greenplum.
Проект помогает оценивать состояние подключённых баз данных через единый интерфейс.
Приложение позволяет проводить мониторинг в зависимости от типа выбранной СУБД.
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

## Команды

- Установка библиотек из файла requirements.txt

```bash
pip install -r requirements.txt
```

- Создание и применение миграций

```bash
python manage.py makemigrations
python manage.py migrate
```

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

## Docker образ

- Сборка Docker-образа

```bash
docker build -t db-stat .
```

- Запуск Docker-контейнера

```bash
docker run --rm -p 8000:8000 db-stat
```

Если приложение запущено в Docker, то при создании подключения к базе данных на хост-машине в поле **Хост** можно указывать `localhost`. Контейнер автоматически перенаправит такое подключение на адрес хост-машины: сначала используется `DB_LOCALHOST_HOST` (по умолчанию `host.docker.internal`), затем шлюз Docker bridge.

Для Linux можно явно пробросить имя хоста Docker:

```bash
docker run --rm --add-host=host.docker.internal:host-gateway -p 8000:8000 db-stat
```

Важно: PostgreSQL на хост-машине должен принимать TCP-подключения не только с собственного `127.0.0.1`, но и с Docker-сети. При необходимости проверьте `listen_addresses` в `postgresql.conf` и правила `pg_hba.conf`.

```
Доступно по адресу: http://localhost:8000
Суперпользователь Django Admin:
- логин: admin
- пароль: admin
Пользователь приложения:
- логин: admin
- почта: admin@example.com
```

