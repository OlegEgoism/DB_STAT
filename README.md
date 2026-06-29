# DB STAT

## Настройка окружения

1. Скопируйте пример переменных окружения:

```bash
cp .env.example .env
```

2. Обязательно замените значения секретов в `.env`:

- `SECRET_KEY` — секрет Django;
- `DB_CONNECTION_ENCRYPTION_KEY` — отдельный стабильный ключ для шифрования паролей сохранённых подключений к внешним БД. Не меняйте его после создания подключений, иначе ранее зашифрованные пароли нельзя будет расшифровать.

3. Для локального запуска можно оставить `DB_ENGINE=sqlite`. Для PostgreSQL задайте `DB_ENGINE=postgresql` и заполните `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

4. Если при входе появляется ошибка CSRF 403, проверьте `CSRF_TRUSTED_ORIGINS`: значения должны быть с протоколом (`http://` или `https://`) и портом, если приложение открывается не на стандартном порту. Например: `http://localhost:8000,http://127.0.0.1:8000`.

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