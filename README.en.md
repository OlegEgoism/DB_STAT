# <img src="static/img/favicon.svg" width="64"> DB STAT

[Русский](README.md) | **English**

## Project description

```
A web application for monitoring and diagnosing PostgreSQL/Greenplum/Greengage databases.
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

- Python version 3.12+

- `.env` file

```
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=*
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
TIME_ZONE=Europe/Minsk
LANGUAGE_CODE=ru

DB_CONNECTION_ENCRYPTION_KEY=

INITIAL_ADMIN_LOGIN=admin
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=admin

# Target used for localhost and ::1 in application database connections
LOCALHOST_DB_HOST=127.0.0.1

SQLITE_NAME=db.sqlite3

STATIC_URL=static/
```

The application's internal data (users, saved connections, audit records, and sessions) is stored exclusively in SQLite.
The file path is configured with `SQLITE_NAME`; by default, `db.sqlite3` in the project root is used.
Environment variables for selecting another Django backend are not supported.
PostgreSQL, Greenplum, and Greengage remain the monitored target databases and are configured through the connection form in the interface.

## Running the project in development mode

- Install dependencies from `requirements.txt`

```bash
pip install -r requirements.txt
```

- Apply migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

- Create a user

`DBUser` is the unified user model (`AUTH_USER_MODEL`): the same account is used to log in both to the application itself and to Django Admin (`/admin/`).

```bash
python manage.py ensure_initial_admin
```

Login to the application is password-protected: after 5 consecutive failed attempts, the user is locked out for 5 minutes.
Users created before the password was introduced (the `password` field is empty or unusable) cannot log in until a password is set — run the following reset command:

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
file across container restarts and upgrades. On startup, the container
automatically applies the migrations committed to the project; generating
migrations in the image or running a separate internal database server is not
required.

Enter `localhost` in the connection form: inside the image, the application
automatically routes such a connection to the Docker host. This works both in
Docker Desktop and regular Docker on Linux without an additional `--add-host`
option.

By default, the image does not set `ALLOWED_HOSTS` and uses the list from the
application settings (`localhost, 127.0.0.1`), which is sufficient for the
command above. If the container is accessed through another hostname or a
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
