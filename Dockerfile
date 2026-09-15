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
    && apt-get install --no-install-recommends -y fonts-dejavu-core libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /wheels/requirements-runtime.txt \
    && rm -rf /wheels

COPY . .

# A build context prepared on Windows may contain CRLF despite the repository
# attributes. Normalize the script in the image as a second line of defence.
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh

# Bakes hashed, compressed static files (whitenoise) into the image so the
# app server never has to serve raw STATICFILES_DIRS itself. DEBUG defaults to
# False (see db/settings.py), which is what selects the manifest storage.
# No SECRET_KEY is set here on purpose: the running container still has none
# baked in and must get a real one at `docker run` time (see checks.py's W002
# warning), and collectstatic itself doesn't need one either way.
RUN python manage.py collectstatic --noinput

RUN mkdir -p /app/data

# The app itself never needs root — only docker-entrypoint.sh does, briefly, to
# write /etc/hosts (see below) and reconcile ownership of a volume that may
# have been created by an older, root-only image version. It drops to this
# user via `runuser` right before starting gunicorn.
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app

VOLUME ["/app/data"]

EXPOSE 8000

# /healthz/ is a dependency-free liveness check (see db_statistics/views/additional.py)
# so a container gets marked unhealthy/restarted only for a genuinely dead process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3)" || exit 1

ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
# gunicorn: a real multi-worker WSGI server instead of Django's single-process
# dev server; whitenoise (added to MIDDLEWARE) serves the collected static
# files, so no separate nginx/static container is needed. Concurrency itself
# (GUNICORN_WORKERS/THREADS/TIMEOUT) is appended by docker-entrypoint.sh —
# exec-form CMD can't expand env vars, so it can't live here as `--workers 3`.
CMD ["gunicorn", "db.wsgi:application", "--bind", "0.0.0.0:8000"]
