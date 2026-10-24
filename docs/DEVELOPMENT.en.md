# Installation, running and development of DB STAT

This document is for those who run DB STAT in Docker, configure it or develop it. The short description is in the [README](../README.en.md).

## Running in Docker

The image is published on Docker Hub: [olegegoism/db-stat](https://hub.docker.com/r/olegegoism/db-stat). For the first start, run one command, replacing the values in `<...>`:

```bash
docker run -d --name db-stat --restart unless-stopped -p 8000:8000 \
  -v db-stat-data:/app/data \
  -e SECRET_KEY='<random string>' \
  -e DB_CONNECTION_ENCRYPTION_KEY='<another random string>' \
  -e INITIAL_ADMIN_PASSWORD='<first administrator password>' \
  olegegoism/db-stat:latest
```

- Random strings: `openssl rand -hex 32`.
- `-v db-stat-data:/app/data` keeps all application data in a named volume. Without this option the data is deleted together with the container, so do not add `--rm`.
- Without `INITIAL_ADMIN_PASSWORD` the first administrator gets the password `admin`. Do not leave it.

Open http://localhost:8000 and sign in as `admin` (or the value of `INITIAL_ADMIN_LOGIN`).

To build the image from sources, run `docker build -t db-stat .`. To run it, use the same `docker run` command with `db-stat` instead of `olegegoism/db-stat:latest`.

On every start the container applies migrations and adds missing indexes itself, so an existing data volume is upgraded without manual steps.

## Update

```bash
docker pull olegegoism/db-stat:latest
docker stop db-stat && docker rm db-stat
```

Then start the container with the same command as in "Running in Docker", with the same `-v` and `-e` options. The data stays in the `db-stat-data` volume.

### Backup

The named volume `db-stat-data` is the only place where all application data is stored (users, saved connections, favorites, audit log).
None of this is automated by the image — backing up and restoring the volume must be done manually.

- Create a backup (the container can be running at this time):

```bash
docker run --rm -v db-stat-data:/data -v "$(pwd)":/backup alpine \
  tar czf /backup/db-stat-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
```

- Restore from a backup (stop the container first so you don't write over an open DB file):

```bash
docker stop db-stat
docker run --rm -v db-stat-data:/data -v "$(pwd)":/backup alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/db-stat-backup-FILE.tar.gz -C /data"
docker start db-stat
```

## Common problems in Docker

- **The page does not open.** Check `docker ps` and `docker logs db-stat`. If port 8000 is busy, use `-p 8080:8000`.
- **Sign-in fails when the application is opened by the server IP.** Add `-e ALLOWED_HOSTS=<ip>,localhost -e CSRF_TRUSTED_ORIGINS=http://<ip>:8000` to the command.
- **Database on the same computer.** In the connection host use `localhost`: inside the container the application replaces it with the address of the computer that runs Docker (`LOCALHOST_DB_HOST`, `host.docker.internal` in the image). The address `127.0.0.1` means the container itself.

## Settings (environment variables)

The full list is in `.env.example`. The main ones:

| Variable | Default | When to change |
|---|---|---|
| `SECRET_KEY` | a public string from the image | Set it in every installation |
| `DB_CONNECTION_ENCRYPTION_KEY` | equal to `SECRET_KEY` | Set it separately before saving the first connection |
| `INITIAL_ADMIN_PASSWORD` | `admin` | Must be set on the first start |
| `INITIAL_ADMIN_LOGIN`, `INITIAL_ADMIN_EMAIL` | `admin`, `admin@example.com` | If you need another login or e-mail |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | If you open the application by a server IP or another name |
| `CSRF_TRUSTED_ORIGINS` | derived from `ALLOWED_HOSTS` | Together with `ALLOWED_HOSTS`: the full address with `http://` or `https://` |
| `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` | `False` | Behind a reverse proxy with HTTPS set to `True` |
| `TIME_ZONE` | `Europe/Minsk` | Set your own time zone: without it dates are shown in Europe/Minsk |
| `LANGUAGE_CODE` | `ru` | Default interface language: `ru` or `en` |
| `GUNICORN_WORKERS` | `3` | Number of worker processes in the container |
| `LOCALHOST_DB_HOST` | `host.docker.internal` in the image | Address that replaces `localhost` in connections |

## Connection budget for target databases

- Connection budget for target databases. Each gunicorn worker (`GUNICORN_WORKERS`, default 3) keeps its own pool: up to `DB_CONNECTION_POOL_MAX_CONN` connections (default 10) per saved connection. Background jobs (VACUUM/ANALYZE and PDF reports) take connections from the same pools.

```
Total on the target DB ≈ GUNICORN_WORKERS × DB_CONNECTION_POOL_MAX_CONN × number of saved connections in use
```

For example, 3 workers × 10 connections × 2 saved connections give up to 60 connections on the target DB. Make sure this fits within the target's `max_connections` with room left for other clients. When a pool is exhausted, the app responds with HTTP 503 and a "connection limit exceeded" message (the message text is in Russian, like the rest of the UI). With `DB_CONNECTION_POOL_MAX_CONN` above 20, `manage.py check` prints the warning `db_statistics.W003`. Details are in `.env.example`.

## Development from sources

### Interface language

- Python-side messages (login, lockout, session duration, language selection error, PDF report) use gettext: the source text is Russian, and the English translation is in `db_statistics/locale/en/LC_MESSAGES/django.po`. After editing the `.po`, rebuild `django.mo` (for example, `pybabel compile -d db_statistics/locale -D django`; Babel is not listed in `requirements.txt`).
- The browser interface (`static/js/i18n.js`) still uses its own dictionary. Moving the JS part to gettext is a known remaining item.

### Running the project in development mode

- .env file
```
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=*
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
CSRF_COOKIE_SECURE=False
SESSION_COOKIE_SECURE=False
TIME_ZONE=Europe/Minsk
LANGUAGE_CODE=ru
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
SECURE_PROXY_SSL_HEADER=False
DB_CONNECTION_ENCRYPTION_KEY=
INITIAL_ADMIN_LOGIN=admin
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=admin
SQLITE_NAME=db.sqlite3
STATIC_URL=static/
LOCALHOST_DB_HOST=127.0.0.1
```
- Python version 3.12+ (the Docker image is built on 3.13, see `Dockerfile`)
- Install libraries: `requirements.txt` (runtime dependencies) and `requirements-dev.txt` (on top of them, adds ruff for code checks)

With plain `venv` + `pip`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Or with [uv](https://docs.astral.sh/uv/) — same result, noticeably faster:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements-dev.txt
```

`uv venv` creates `.venv` in the same place as plain `venv`, so no need to
reconfigure your IDE's interpreter. The `--python 3.12` flag matters if
`python3` points to an older version on your system by default (Django 6
requires Python 3.12+) — `uv` will find an installed `python3.12` itself, or
download the right version if none is present.

- Create database tables and apply migrations (`db_statistics` models are managed by migrations in `db_statistics/migrations`). The same command works for a new database and for an existing installation: existing tables are not recreated

```bash
python manage.py migrate --fake-initial
python manage.py ensure_indexes
```

`--fake-initial` marks the initial migration as applied when its tables already exist. This is how installations created before migrations are upgraded: `migrate` moves them onto the migration history itself (see `db_statistics/management/commands/migrate.py`). `ensure_indexes` adds indexes missing from an existing database (migrations create indexes only together with their tables). Safe to run again.

- Schema changes (a field, table or index): change the model, create a migration and apply it. Commit the migration file together with the model change:

```bash
make migrations   # same as: python manage.py makemigrations
make migrate
```


- Create a user for logging into the application and Django Admin (`/admin/`).
- login: admin
- email: admin@example.com
- password: admin
```bash
python manage.py ensure_initial_admin
```

- Encrypt connection passwords that remained in plain text after upgrading from a version without encryption (a one-time command, safe to run repeatedly)

```bash
python manage.py encrypt_connection_passwords
```

- Requeue interrupted background jobs (VACUUM/ANALYZE and PDF reports) after the server was stopped abruptly. Runs automatically at startup in Docker; `runserver` recovers jobs automatically

```bash
python manage.py recover_maintenance_jobs
```

- Start the server

```bash
python manage.py runserver
```

- Tests. Unit tests need no external services. Integration tests (`test_integration_*`) run against a real PostgreSQL and are skipped until the `PG_TEST_*` variables are set:

```bash
PG_TEST_HOST=127.0.0.1 PG_TEST_PORT=5432 PG_TEST_USER=postgres PG_TEST_PASSWORD=... PG_TEST_DATABASE=postgres python manage.py test
```

- Code check and auto-fix

```bash
python -m ruff check .
python -m ruff check . --fix
python -m ruff format .
```

### Browser smoke tests (Playwright)

The `tests/e2e` directory checks sign-in, a saved connection, the "Tables", "Temporary tables" and "TOAST tables" tabs, search and sign-out in Chromium. The tests need a running application and a PostgreSQL database: they save a connection to this database in the application and, for the search test, create two tables with TOAST data there (they are dropped afterwards):

```bash
pip install -r requirements.txt -r requirements-e2e.txt
python -m playwright install chromium
E2E_PG_PASSWORD=... python -m pytest tests/e2e -q
```

The application address is set by `E2E_BASE_URL` (default `http://127.0.0.1:8000`). The first administrator is `admin` with the password from `E2E_ADMIN_PASSWORD` (default `admin12345`). If the application does not respond, the tests are skipped. In CI they run as a separate `e2e` job that does not block the build yet (`continue-on-error`).

### Make Commands

Main `Makefile` targets — full list with descriptions: `make help` or `make` (default).

| Command                                | What it does                                                                                     |
|----------------------------------------|--------------------------------------------------------------------------------------------------|
| `make install`                         | Install development dependencies from requirements-dev.txt                                                       |
| `make hooks`                           | Enable the project's git hooks for this clone (one-time, after cloning)                          |
| `make migrations`                      | Generate migrations after model changes (all apps, including `db_statistics`)                    |
| `make migrate`                         | Apply migrations and add missing indexes (`migrate --fake-initial` and `ensure_indexes`)         |
| `make run`                             | Start the development server                                                                     |
| `make shell`                           | Open an interactive Django shell                                                                 |
| `make admin`                           | Create the first administrator (see `INITIAL_ADMIN_*` in `.env`)                                 |
| `make lint` / `make lint-fix`          | Check code (without fixes / with auto-fix)                                                       |
| `make format`                          | Format code                                                                                       |
| `make collectstatic`                   | Collect static files (as during Docker image build)                                              |
| `make docker-build`                    | Build Docker image                                                                                 |
| `make docker-run` / `make docker-stop` | Start / stop Docker container                                                                     |
| `make clean`                           | Remove caches and locally collected static files                                                 |
| `make reset-db`                        | DANGEROUS: delete only the SQLite DB (migration files are kept), with confirmation               |
