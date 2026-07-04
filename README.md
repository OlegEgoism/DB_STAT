# DB STAT

## Описание проекта

DB STAT — веб-приложение для мониторинга и диагностики баз данных PostgreSQL и Greenplum.
Проект помогает администраторам и инженерам быстро оценивать состояние подключённых баз данных через единый интерфейс: смотреть размеры баз, схем и таблиц, анализировать распределение данных по сегментам Greenplum, отслеживать активные запросы, блокировки, простоявшие транзакции, временные таблицы,
пользователей, группы и статистику обслуживания.
Приложение хранит список подключений к внешним базам данных, позволяет проверять доступность подключения и открывать разные разделы мониторинга в зависимости от типа выбранной СУБД.
Для PostgreSQL скрываются Greenplum-специфичные разделы, а для Greenplum доступны дополнительные проверки сегментов и распределения данных.
Пользователи приложения работают через простой механизм авторизации по login и email, а права на управление подключениями ограничиваются ролью администратора.
Основная цель DB STAT — упростить ежедневный контроль состояния БД и ускорить первичную диагностику проблем производительности без необходимости вручную запускать множество SQL-запросов в разных инструментах.

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

5. Если при входе появляется ошибка CSRF 403, проверьте `CSRF_TRUSTED_ORIGINS`: значения должны быть с протоколом (`http://` или `https://`) и портом, если приложение открывается не на стандартном порту. Например: `http://localhost:8000,http://127.0.0.1:8000`.

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

## Video on YouTube

[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/9NN8SoxMOZA)

## GitHub

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/OlegEgoism/DB_STAT)