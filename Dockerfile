FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0 \
    DJANGO_SUPERUSER_USERNAME=admin \
    DJANGO_SUPERUSER_EMAIL=admin@example.com \
    DJANGO_SUPERUSER_PASSWORD=admin

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN python manage.py migrate --noinput \
    && python manage.py createsuperuser --noinput

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
