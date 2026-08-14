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
    <td><img src="screenshots/db.png" width="700" alt="Database dashboard"></td>
    <td><img src="screenshots/memory.png" width="700" alt="Memory dashboard"></td>
  </tr>
  <tr>
    <td><img src="screenshots/service.png" width="700" alt="Service dashboard"></td>
    <td><img src="screenshots/session.png" width="700" alt="Session dashboard"></td>
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

DB_ENGINE=sqlite
SQLITE_NAME=db.sqlite3

DB_NAME=db_statistics
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

STATIC_URL=static/
```

## Running the project in development mode

- Install dependencies from `requirements.txt`

```bash
pip install -r requirements.txt
```

- Apply migrations (also run this command after updating the project)

```bash
python manage.py makemigrations
python manage.py migrate
```

In particular, this creates the `db_favorite` table required by favorites. The migration supports both new databases and existing databases whose tables were previously created with `run-syncdb`.

- Create a superuser for Django Admin access

```bash
python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin')"
```

- Create a DBUser for application authentication

```bash
python manage.py shell -c "from db_statistics.models import DBUser; DBUser.objects.filter(login='admin').exists() or DBUser.objects.create(login='admin', email='admin@example.com', role='Администратор', is_active=True)"
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

Changing the source does **not** update an already running container. Recreate it from the new image. To publish the fix to Docker Hub, run:

```bash
docker build --pull -t olegegoism/db-stat:latest .
docker push olegegoism/db-stat:latest
docker rm -f db-stat 2>/dev/null || true
```

- Run the Docker container with access to PostgreSQL on the host (Linux and Docker Desktop)

```bash
docker run --rm \
  --name db-stat \
  -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e LOCAL_DATABASE_HOST=host.docker.internal \
  olegegoism/db-stat:latest
```

Or use the provided configuration:

```bash
docker compose up --build --force-recreate
```

Enter the familiar `localhost` in the Host field (`127.0.0.1` and `::1` are also supported). The application preserves the user-friendly value but, immediately before connecting from Docker, automatically replaces a loopback address with `LOCAL_DATABASE_HOST` (`host.docker.internal`). For a remote database, enter its real DNS name or IP; non-loopback addresses are not changed.

If an error still mentions `127.0.0.1`, an **old image** is running: the fixed version actually connects to `host.docker.internal` from the container even though the form displays `localhost`.

PostgreSQL on the host must also accept TCP connections rather than Unix-socket connections only. Check `listen_addresses` in `postgresql.conf`, allow the Docker subnet in `pg_hba.conf`, and permit port `5432` through the firewall. Restart PostgreSQL after changing its configuration. Do not expose port 5432 to the internet; allow only the local Docker subnet.

Available at: http://localhost:8000

To diagnose name resolution and port availability:

```bash
docker run --rm --add-host=host.docker.internal:host-gateway busybox nslookup host.docker.internal
docker run --rm --add-host=host.docker.internal:host-gateway busybox nc -vz host.docker.internal 5432
```


## Download image from hub.docker

https://hub.docker.com/r/olegegoism/db-stat
