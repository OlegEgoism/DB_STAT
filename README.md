# DB STAT

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
## Email-уведомления DBNotification

Модель `DBNotification` задаёт, какие проверки нужно выполнять для подключения и кому отправлять письмо:

- `user` — получатели уведомления;
- `interval_update` — минимальный интервал между проверками в минутах;
- `segment_monitor` — проверка сегментов Greenplum не в `up` или не в preferred role;
- `temp_tables_monitor` — наличие временных таблиц;
- `query_monitor` + `query_threshold` — активные запросы дольше порога в секундах;
- `lock_monitor` + `lock_threshold` — блокировки дольше порога в секундах;
- `transaction_monitor` + `transactions_threshold` — `idle in transaction` дольше порога в секундах.

Для отправки почты заполните SMTP-параметры в `.env`:

```.env
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=monitor@example.com
EMAIL_HOST_PASSWORD=secret
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_TIMEOUT=10
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=monitor@example.com
```

Если `EMAIL_HOST` пустой, проект автоматически использует консольный backend вместо SMTP, чтобы локальная тестовая отправка не падала из-за пустого SMTP-хоста.

Локально можно проверять письма через консольный backend явно:

```.env
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=db-stat@localhost
```

Запуск проверки уведомлений:

```bash
python manage.py send_db_notifications
```

Отправка тестового письма без проверки `DBNotification`:

```bash
python manage.py send_db_notifications --test-email user@example.com
```

Тестовое письмо можно отправить с собственными темой и текстом:

```bash
python manage.py send_db_notifications --test-email user@example.com --test-subject "DB-STAT test" --test-message "Проверка SMTP"
```

Принудительная проверка без ожидания `interval_update`:

```bash
python manage.py send_db_notifications --force
```

Для регулярной отправки добавьте команду в cron/systemd timer/Celery Beat. Например, cron каждую минуту:

```cron
* * * * * cd /path/to/DB-STAT && /path/to/venv/bin/python manage.py send_db_notifications >> /var/log/db-stat-notifications.log 2>&1
```

Команда сама пропускает настройки, у которых ещё не прошёл `interval_update`, и сохраняет в админке `last_checked`, `last_sent`, `last_error`.
