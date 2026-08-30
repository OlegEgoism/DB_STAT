# <img src="static/img/favicon.svg" width="64"> DB STAT

[Русский](README.md) | **English**

## Project description

```
A web application for monitoring and diagnosing PostgreSQL/Greenplum databases.
The project helps evaluate the status of connected databases through a single interface.
The application allows you to monitor databases.
The main goal of DB STAT is to simplify daily database health checks.
```

## Project demo

[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/9NN8SoxMOZA)

## Project screenshots

<table>
  <tr>
    <td align="center">
      <img src="screenshots/db.png" width="700" alt="Database dashboard"><br>
      <sub>Database — size, activity, connection slots</sub>
    </td>
    <td align="center">
      <img src="screenshots/memory.png" width="700" alt="Memory dashboard"><br>
      <sub>Memory — settings and usage</sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="screenshots/service.png" width="700" alt="Service dashboard"><br>
      <sub>Maintenance — VACUUM/ANALYZE, live/dead rows</sub>
    </td>
    <td align="center">
      <img src="screenshots/session.png" width="700" alt="Session dashboard"><br>
      <sub>Sessions — active user connections</sub>
    </td>
  </tr>
</table>

## Environment setup

- Python version 3.12

- `.env` file

```
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=*
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
TIME_ZONE=Europe/Minsk
LANGUAGE_CODE=ru

DB_CONNECTION_ENCRYPTION_KEY=

# Target used for localhost and ::1 in application database connections
LOCALHOST_DB_HOST=127.0.0.1

SQLITE_NAME=db.sqlite3

STATIC_URL=static/
```

The application's own state (users, saved connections, audit records, and
sessions) is stored exclusively in SQLite. Set the database file path with
`SQLITE_NAME`; it defaults to `db.sqlite3` in the project root. Selecting a
different Django database backend through environment variables is not
supported. PostgreSQL, Greenplum, and Greengage remain monitoring targets and
are configured through the connection form in the UI.

## Running the project in development mode

- Install dependencies from `requirements.txt`

`psycopg2` is built from source and links against the system `libpq`, so
outside Docker you need the PostgreSQL headers installed first, e.g.
`sudo apt install libpq-dev` (Debian/Ubuntu) or `brew install postgresql`
(macOS). The Docker image already has the build dependencies covered.

```bash
pip install -r requirements.txt
```

- Apply migrations (also run this command after updating the project)

```bash
python manage.py makemigrations
python manage.py migrate
```

In particular, this creates the `db_favorite` table required by favorites. The migration supports both new databases and existing databases whose tables were previously created with `run-syncdb`.

- Create a user

`DBUser` is the single, unified user model (`AUTH_USER_MODEL`): the same
account logs into the application itself and into Django Admin (`/admin/`).
There is no separate Django superuser to create.

```bash
python manage.py shell -c "from db_statistics.models import DBUser; DBUser.objects.filter(login='admin').exists() or DBUser.objects.create_superuser('admin', 'admin@example.com', 'admin', role='Администратор')"
```

`create_superuser` sets `is_staff=True` and `is_superuser=True` (full access
to `/admin/`). For a user without Django Admin access, use
`DBUser.objects.create_user(login=..., email=..., password=..., role=...)` —
`is_staff` defaults to `False`.

Login is password-protected: after 5 consecutive failed attempts, login is
locked for that user for 5 minutes. Users created before the password field
existed (an empty or unusable `password`) cannot log in until a password is
set — use the same reset command:

```bash
python manage.py shell -c "from django.contrib.auth.hashers import make_password; from db_statistics.models import DBUser; u = DBUser.objects.get(login='admin'); u.password = make_password('NEW_PASSWORD'); u.failed_login_attempts = 0; u.lockout_until = None; u.save()"
```

- Encrypt any connection passwords left in plain text after upgrading from a version without encryption (one-time command, safe to re-run)

```bash
python manage.py encrypt_connection_passwords
```

- Start the server

```bash
python manage.py runserver
```

- Check and automatically fix code style

```bash
python -m ruff check .
python -m ruff check . --fix
python -m ruff format .
```

## Running the project in Docker

- Build the Docker image

```bash
docker build -t db-stat .
```

- Run the Docker container

Run the container with access to a database on the Docker host:

```bash
docker run --name db-stat --rm -p 8000:8000 \
  -v db-stat-data:/app/data db-stat
```

The `db-stat-data` named volume preserves the single internal SQLite database
file across container restarts and upgrades. On startup, the container applies
the versioned migrations committed to the project; generating migrations in
the image or running a separate application database server is unnecessary.

Enter `localhost` in the connection form. Inside the image, the application
automatically routes that connection to the Docker host. This works both in
Docker Desktop and native Docker on Linux without an extra `--add-host` option.

The image no longer defaults `ALLOWED_HOSTS` to `*`; it falls back to the
application's own default (`localhost, 127.0.0.1`), which is enough for the
command above. If the container is reached through another hostname or a
reverse proxy, pass it explicitly: `-e ALLOWED_HOSTS=example.com`.

PostgreSQL on the host must listen on more than its Unix socket and allow the
Docker network in `listen_addresses` and `pg_hba.conf`. If necessary, override
the target with `-e LOCALHOST_DB_HOST=<address>`.

```
Available at: http://localhost:8000
Single account (logs into the app and into Django Admin — /admin/):
- login: admin
- email: admin@example.com
- password: admin

If there is a connection error to `172.17.0.1` or `192.168.0.1` after building, an old Docker image is running.
Rebuild the image and run the container again.

`exec /app/docker-entrypoint.sh: no such file or directory` means that the
entrypoint was copied with Windows line endings or that the image predates the
fix. Current builds force the script to LF. Rebuild and publish the image, then
run `docker pull` again.
```


## Download image from hub.docker

https://hub.docker.com/r/olegegoism/db-stat
