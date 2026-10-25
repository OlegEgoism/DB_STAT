# Installation, running and development of DB STAT

The short description is in the [README](../README.en.md).

## Running in Docker

Image on Docker Hub: [olegegoism/db-stat](https://hub.docker.com/r/olegegoism/db-stat).

```bash
docker run -d --name db-stat --restart unless-stopped -p 8000:8000 \
  -v db-stat-data:/app/data \
  -e SECRET_KEY='<random string>' \
  -e DB_CONNECTION_ENCRYPTION_KEY='<another random string>' \
  -e INITIAL_ADMIN_PASSWORD='<administrator password>' \
  -e TIME_ZONE=Europe/Minsk \
  olegegoism/db-stat:latest
```

- Replace `Europe/Minsk` with your own time zone.
- Random strings: `openssl rand -hex 32`. Keep them: saved connection passwords cannot be decrypted without the same `DB_CONNECTION_ENCRYPTION_KEY`.
- Without `INITIAL_ADMIN_PASSWORD` the administrator password is `admin`. Do not leave it.
- Data is kept in the `db-stat-data` volume. Without `-v` it goes to an anonymous volume, which is deleted together with the container when you use `--rm`.
- Open http://localhost:8000 and sign in as `admin` (or the value of `INITIAL_ADMIN_LOGIN`).
- The container applies migrations and missing indexes itself on every start.
- To build the image from sources: `docker build -t db-stat .`. Run it with the same `docker run` command, but replace `olegegoism/db-stat:latest` with `db-stat`.

## Update

```bash
docker pull olegegoism/db-stat:latest
docker stop db-stat && docker rm db-stat
```

Start the container with the same `docker run` command, with the same `-v` and `-e` options. Data stays in the `db-stat-data` volume.

## Backup

All data (users, connections, favorites, audit log) is in the `db-stat-data` volume. Copy it while the container is stopped: a copy of a running SQLite database may turn out inconsistent.

```bash
docker stop db-stat
docker run --rm -v db-stat-data:/data -v "$(pwd)":/backup alpine \
  tar czf /backup/db-stat-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
docker start db-stat
```

Restore from `<archive>.tar.gz`:

```bash
docker stop db-stat
docker run --rm -v db-stat-data:/data -v "$(pwd)":/backup alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/<archive>.tar.gz -C /data"
docker start db-stat
```

## Common problems

- **The page does not open.** Check `docker logs db-stat`. If port 8000 is busy, use `-p 8080:8000`.
- **Opening by the server IP.** Add to the `docker run` command (the container must be recreated): `-e ALLOWED_HOSTS=<ip>,localhost -e CSRF_TRUSTED_ORIGINS=http://<ip>:8000`.
- **Database on this computer.** In the connection use `localhost`: the application replaces it with the host address (`LOCALHOST_DB_HOST`, `host.docker.internal` in the image). Address `127.0.0.1` inside the container means the container itself.
- **HTTP 503 «Превышен лимит соединений с целевой БД»** (the message is shown in Russian: connection limit exceeded). See "Connection budget" below.

## Settings

The full list is in [.env.example](../.env.example). Main ones:

| Variable | Default | When to change |
|---|---|---|
| `SECRET_KEY` | an insecure string | Always set your own key |
| `DB_CONNECTION_ENCRYPTION_KEY` | equal to `SECRET_KEY` | Set it separately before saving the first connection |
| `INITIAL_ADMIN_PASSWORD` | `admin` | Set it on the first start |
| `INITIAL_ADMIN_LOGIN`, `INITIAL_ADMIN_EMAIL` | `admin`, `admin@example.com` | If you need other values |
| `TIME_ZONE` | `Europe/Minsk` | Set your own time zone: without it dates are shown in Europe/Minsk |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | If you open the application by a server IP or another name |
| `CSRF_TRUSTED_ORIGINS` | derived from `ALLOWED_HOSTS` | Together with `ALLOWED_HOSTS`: full addresses with `http://` or `https://` |
| `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` | `False` | Behind a reverse proxy with HTTPS set them to `True` |
| `LANGUAGE_CODE` | `ru` | Default interface language: `ru` or `en` |
| `GUNICORN_WORKERS` | `3` | Number of worker processes in the container |
| `LOCALHOST_DB_HOST` | `127.0.0.1` (`host.docker.internal` in the image) | Address that replaces `localhost` in connections |

### Connection budget

Each gunicorn worker keeps its own pool: up to `DB_CONNECTION_POOL_MAX_CONN` connections (default 10) per saved connection. Total on a target database ≈ `GUNICORN_WORKERS` × `DB_CONNECTION_POOL_MAX_CONN` × number of connections. This must fit into the target database's `max_connections`. When the pool is exhausted, the application responds with 503.

## Development

Requires Python 3.12+ (the Docker image is built on 3.13). Run all commands in this section from the project root — the folder that contains the `Makefile`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
make install
```

Create a `.env` file in the project root. Minimum (all variables are in `.env.example`):

```
DEBUG=True
SECRET_KEY=<random string>
INITIAL_ADMIN_PASSWORD=admin
TIME_ZONE=Europe/Minsk
```

Then:

```bash
make migrate   # migrations and missing indexes: works for both a new and an existing database
make admin     # first administrator: login and password from INITIAL_ADMIN_*
make run       # development server: http://127.0.0.1:8000
```

If you changed models, create a migration and apply it. On the first run this is not needed — `make migrate` is enough. Commit the migration file together with the model:

```bash
make migrations
make migrate
```

Checks:

```bash
make test      # tests without PostgreSQL (integration tests are skipped)
make test-pg   # all tests against PostgreSQL: requires PG_TEST_PASSWORD; other PG_TEST_* variables as needed
make lint      # ruff check
make format    # ruff format
```

Playwright browser tests (`tests/e2e`) check sign-in, a saved connection and the tabs. They need a running application (`make run`) and PostgreSQL. The application address is set by `E2E_BASE_URL` (default `http://127.0.0.1:8000`).

```bash
pip install -r requirements.txt -r requirements-e2e.txt
python -m playwright install chromium
E2E_PG_PASSWORD=... python -m pytest tests/e2e -q
```

Service commands:

- `python manage.py encrypt_connection_passwords` — run once to encrypt connection passwords stored in plain text after an upgrade from an old version. Safe to repeat.
- `python manage.py recover_maintenance_jobs` — requeue interrupted background jobs (VACUUM/ANALYZE, PDF reports) after an abrupt stop. Happens automatically in Docker and with `runserver`.

## Make commands

Full list with descriptions: `make help`.

| Command | What it does |
|---|---|
| `make install` | Install development dependencies |
| `make hooks` | Enable the project's git hooks for this clone (once, after cloning) |
| `make migrations` | Create migrations after model changes |
| `make migrate` | Apply migrations and add missing indexes |
| `make run` | Start the development server |
| `make admin` | Create the first administrator |
| `make test` / `make test-pg` | Tests without PostgreSQL / all tests against PostgreSQL |
| `make lint` / `make format` | Check code / format code (ruff) |
| `make docker-build` | Build the Docker image |
| `make docker-run` / `make docker-stop` | Start / stop the container |
| `make reset-db` | DANGEROUS: delete only the SQLite database (migrations are kept), with confirmation |
