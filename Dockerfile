FROM python:3.13-slim AS builder

WORKDIR /wheels

RUN apt-get update \
    && apt-get install --no-install-recommends -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN sed '/^ruff==/d' requirements.txt > requirements-runtime.txt \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-runtime.txt

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_ENGINE=sqlite \
    SQLITE_NAME=/app/db.sqlite3 \
    DJANGO_SUPERUSER_USERNAME=admin \
    DJANGO_SUPERUSER_EMAIL=admin@example.com \
    DJANGO_SUPERUSER_PASSWORD=admin \
    ALLOWED_HOSTS=*

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /wheels/requirements-runtime.txt \
    && rm -rf /wheels

COPY . .

RUN rm -f /app/db.sqlite3 \
    && python manage.py makemigrations \
    && python manage.py migrate \
    && python manage.py createsuperuser --noinput \
    && python manage.py shell -c "from db_statistics.models import DBUser; DBUser.objects.update_or_create(login='test', defaults={'email': 'test@gmail.com', 'role': 'Администратор', 'is_active': True})"

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
