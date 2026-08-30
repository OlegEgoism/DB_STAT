FROM python:3.13-slim AS builder

WORKDIR /wheels

RUN apt-get update \
    && apt-get install --no-install-recommends -y gcc libc6-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN sed '/^ruff==/d' requirements.txt > requirements-runtime.txt \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-runtime.txt

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SQLITE_NAME=/app/data/db.sqlite3 \
    LOCALHOST_DB_HOST=host.docker.internal

WORKDIR /app

# psycopg2 (non-binary) links against the system libpq at runtime instead of
# bundling its own copy; the builder stage already has libpq-dev to compile it.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /wheels/requirements-runtime.txt \
    && rm -rf /wheels

COPY . .

# A build context prepared on Windows may contain CRLF despite the repository
# attributes. Normalize the script in the image as a second line of defence.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh

RUN mkdir -p /app/data

VOLUME ["/app/data"]

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
# --insecure: DEBUG defaults to False (see db/settings.py), and without it the
# dev server stops serving STATIC_URL entirely, breaking every page's CSS/JS.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--insecure"]
