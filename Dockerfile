FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_ENGINE=sqlite \
    SQLITE_NAME=/app/db.sqlite3 \
    ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py migrate --noinput \
    && python manage.py seed_docker_data

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
