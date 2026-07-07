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
    ALLOWED_HOSTS=* \
    DB_LOCALHOST_HOST=host.docker.internal

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /wheels/requirements-runtime.txt \
    && rm -rf /wheels

COPY . .

RUN rm -f /app/db.sqlite3 \
    && python manage.py makemigrations \
    && python manage.py migrate \
    && python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin')" \
    && python manage.py shell -c "from db_statistics.models import DBUser; DBUser.objects.filter(login='admin').exists() or DBUser.objects.create(login='admin', email='admin@example.com', role='Администратор', is_active=True)"

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
