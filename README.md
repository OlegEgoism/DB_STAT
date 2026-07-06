# <img src="static/img/favicon.svg" width="22"> DB STAT

## Описание проекта

```
DB STAT - веб-приложение для мониторинга и диагностики баз данных PostgreSQL/Greenplum.
Проект помогает оценивать состояние подключённых баз данных через единый интерфейс.
Приложение позволяет открывать разные разделы мониторинга в зависимости от типа выбранной СУБД.
Основная цель DB STAT - упростить ежедневный контроль состояния БД.
```

## Демо проекта

[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/9NN8SoxMOZA)

## Настройка окружения

- Версия Python 3.12

- Создайте файл .env

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

- Создание суперпользователя Django Admin

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin')"
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

```
Доступно по адресу: http://localhost:8000
Суперпользователь, логин: admin; пароль admin 
Пользователь приложения  логин: test; почта: test@gmail.com
```

