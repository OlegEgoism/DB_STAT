# DB STAT

## Описание проекта

```
DB STAT - веб-приложение для мониторинга и диагностики баз данных PostgreSQL/Greenplum.
Проект помогает оценивать состояние подключённых баз данных через единый интерфейс.
Приложение позволяет открывать разные разделы мониторинга в зависимости от типа выбранной СУБД.
Основная цель DB STAT - упростить ежедневный контроль состояния БД.
```

## Настройка окружения

1. Создайте файл .env

```.env
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

2. Обязательно замените значения секретов в `.env`:

- `SECRET_KEY` — секрет Django;
- `DB_CONNECTION_ENCRYPTION_KEY` — отдельный стабильный ключ для шифрования паролей сохранённых подключений к внешним БД. Не меняйте его после создания подключений, иначе ранее зашифрованные пароли нельзя будет расшифровать.

3. Для локального запуска можно оставить `DB_ENGINE=sqlite`.
4. Для PostgreSQL задайте `DB_ENGINE=postgresql` и заполните `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

## Команды

- Установка библиотек из файла requirements.txt

```bash
pip install -r requirements.txt
```

- Добавление библиотек в файл requirements.txt

```bash
pip freeze > requirements.txt
```

- Создание и применение миграций

```bash
python manage.py makemigrations
python manage.py migrate
```

- Создание пользователя

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


## Запуск в Docker

Соберите образ приложения:

```bash
docker build -t db-stat .
```

Запустите контейнер с переменными окружения из `.env`:

```bash
docker run --env-file .env -p 8000:8000 db-stat
```

Во время сборки образа применяются миграции и создаётся администратор `admin` с паролем `admin`. При старте контейнер повторно применяет миграции и запускает Django на `0.0.0.0:8000`. Для сохранения SQLite-базы между перезапусками подключите volume, например:

```bash
docker run --env-file .env -e SQLITE_NAME=/data/db.sqlite3 -p 8000:8000 -v db-stat-data:/data db-stat
```

## Video on YouTube

[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/9NN8SoxMOZA)
