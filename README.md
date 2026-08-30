# <img src="static/img/favicon.svg" width="64">  DB STAT

**Русский** | [English](README.en.md)

## Описание проекта

```
Веб-приложение для мониторинга и диагностики баз данных PostgreSQL/Greenplum/Greengage.
Проект помогает оценивать состояние подключённых баз данных через единый интерфейс.
Приложение позволяет проводить мониторинг БД.
Основная цель DB STAT - упростить ежедневный контроль состояния БД.
```

Подробный перечень доступных метрик, порядок подключения, интерпретация показателей и ограничения собраны в [руководстве по мониторингу Greengage](docs/GREENGAGE.md).

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

SQLITE_NAME=db.sqlite3

STATIC_URL=static/
```

Служебные данные самого приложения (пользователи, сохранённые подключения,
аудит и сессии) хранятся только в SQLite. Путь к файлу задаётся переменной
`SQLITE_NAME`; по умолчанию используется `db.sqlite3` в корне проекта.
Переменные выбора другого Django-бэкенда не поддерживаются. PostgreSQL,
Greenplum и Greengage остаются целевыми базами мониторинга и настраиваются
через форму подключения в интерфейсе.

## Запуск проекта в режиме разаработки

- Установка библиотек из файла requirements.txt

Пакет `psycopg2` собирается из исходников и линкуется с системной `libpq`, поэтому
перед установкой (вне Docker) нужны заголовки PostgreSQL, например
`sudo apt install libpq-dev` (Debian/Ubuntu) или `brew install postgresql` (macOS).
Внутри Docker-образа сборочные зависимости уже учтены.

```bash
pip install -r requirements.txt
```

- Применение миграций (команду необходимо выполнять и после обновления проекта)

```bash
python manage.py makemigrations
python manage.py migrate
```

В частности, эта команда создаёт таблицу `db_favorite`, необходимую для работы избранного. Миграция совместима как с новой базой, так и с существующей базой, таблицы которой ранее были созданы через `run-syncdb`.

- Создание пользователя

`DBUser` — единая модель пользователя (`AUTH_USER_MODEL`): один и тот же
аккаунт используется и для входа в само приложение, и для входа в Django
Admin (`/admin/`). Отдельного суперпользователя Django создавать не нужно.

```bash
python manage.py shell -c "from db_statistics.models import DBUser; DBUser.objects.filter(login='admin').exists() or DBUser.objects.create_superuser('admin', 'admin@example.com', 'admin', role='Администратор')"
```

`create_superuser` задаёт `is_staff=True` и `is_superuser=True` (доступ к
`/admin/` с полными правами). Для пользователя без доступа к Django Admin
используйте `DBUser.objects.create_user(login=..., email=..., password=..., role=...)`
— по умолчанию `is_staff=False`.

Вход в приложение защищён паролем: после 5 подряд неверных попыток вход для
пользователя блокируется на 5 минут. Пользователи, созданные до появления
пароля (поле `password` пустое или непригодное), не смогут войти, пока им не
задать пароль — для этого выполните команду сброса:

```bash
python manage.py shell -c "from django.contrib.auth.hashers import make_password; from db_statistics.models import DBUser; u = DBUser.objects.get(login='admin'); u.password = make_password('НОВЫЙ_ПАРОЛЬ'); u.failed_login_attempts = 0; u.lockout_until = None; u.save()"
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

## Запуск проекта в Docker

- Сборка Docker-образа

```bash
docker build -t db-stat .
```

- Запуск Docker-контейнера

Обычный запуск контейнера с доступом к локальной БД хоста:

```bash
docker run --name db-stat --rm -p 8000:8000 \
  -v db-stat-data:/app/data db-stat
```

Именованный том `db-stat-data` хранит единственный файл внутренней SQLite-БД
между перезапусками и обновлениями контейнера. При старте контейнер сам
применяет зафиксированные в проекте миграции; генерировать миграции в образе
или подключать отдельный сервер служебной БД не требуется.

В форме подключения укажите `localhost`: внутри образа приложение автоматически
направит такое подключение на хост Docker. Это работает в Docker Desktop и в
обычном Docker под Linux без дополнительного параметра `--add-host`.

По умолчанию `ALLOWED_HOSTS` не задан образом и используется список из настроек
приложения (`localhost, 127.0.0.1`), которого достаточно для запуска командой
выше. Если контейнер открывается по другому имени хоста или через обратный
прокси, передайте его явно: `-e ALLOWED_HOSTS=example.com`.

PostgreSQL на хосте должен принимать подключения не только через Unix-сокет и
разрешать подключения из сети Docker в `listen_addresses` и `pg_hba.conf`.
При необходимости адрес назначения можно переопределить параметром
`-e LOCALHOST_DB_HOST=<адрес>`.

```
Доступно по адресу: http://localhost:8000
Единый пользователь (вход в приложение и в Django Admin — /admin/):
- логин: admin
- почта: admin@example.com
- пароль: admin

Если после сборки есть ошибка подключения к `172.17.0.1` или `192.168.0.1`, значит запущен старый Docker-образ. 
Пересоберите образ и запустите контейнер заново.

Ошибка `exec /app/docker-entrypoint.sh: no such file or directory` означает, что
entrypoint попал в образ с Windows-переносами строк либо используется образ,
собранный до исправления. В актуальной сборке скрипт принудительно переводится
в LF. Пересоберите и опубликуйте образ, затем снова выполните `docker pull`.
```


## Скачать образ из hub.docker

https://hub.docker.com/r/olegegoism/db-stat