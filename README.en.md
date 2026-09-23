# <img src="static/img/favicon.svg" width="64">  DB STAT

[Русский](README.md) | **English**

## Project Description

```
Web application for monitoring and diagnostics of PostgreSQL/Greenplum/Greengage databases.
The project helps assess the state of connected databases through a single interface.
The application allows monitoring of databases.
The main goal of DB STAT is to simplify daily monitoring of database health.
```

## Download image from hub.docker

https://hub.docker.com/r/olegegoism/db-stat

## Project Demo

[![YouTube](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://youtu.be/9NN8SoxMOZA) 
 
## Project Screenshots 
 
<table> 
  <tr> 
    <td align="center"> 
      <img src="screenshots/db.png" width="700" alt="Database dashboard"><br> 
      <sub>Database — size, activity, connection slots</sub> 
    </td> 
    <td align="center"> 
      <img src="screenshots/memory.png" width="700" alt="Memory dashboard"><br> 
      <sub>Memory — parameters and usage</sub> 
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
 
## Running the project in development mode 
 
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
- Python version 3.12+ 
- Install libraries from requirements.txt 
 
```bash 
pip install -r requirements.txt 
``` 
 
- Apply migrations 
 
```bash 
python manage.py makemigrations 
python manage.py migrate 
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
 
- Start the server 
 
```bash 
python manage.py runserver 
``` 
 
- Code check and auto-fix 
 
```bash 
python -m ruff check . 
python -m ruff check . --fix 
python -m ruff format . 
``` 

### Automatic checks before a commit

After installing the dependencies, install the Git hook once:

```bash
python -m pre_commit install
# or: make hooks
```

Before every `git commit`, Ruff will now automatically fix supported issues and
format the **entire project**, then perform a final lint check. If files were
changed or unfixable issues remain, the commit is stopped. Review the changes,
stage them with `git add`, and retry the commit.

Run the same checks manually for the entire project with:

```bash
python -m pre_commit run --all-files
# or: make hooks-run
```

The hook can be bypassed temporarily with `git commit --no-verify`, but this is
not recommended during normal development. CI also runs Ruff for pull requests.

## Make Commands 
 
Main `Makefile` targets — full list with descriptions: `make help` or `make` (default). 
 
| Command                                | What it does                                                                                     | 
|----------------------------------------|--------------------------------------------------------------------------------------------------| 
| `make install`                         | Install dependencies from requirements.txt                                                       | 
| `make migrations`                      | Generate migrations based on model changes                                                       | 
| `make migrate`                         | Apply migrations to the database                                                                 | 
| `make run`                             | Start the development server                                                                     | 
| `make shell`                           | Open an interactive Django shell                                                                 | 
| `make admin`                           | Create the first administrator (see `INITIAL_ADMIN_*` in `.env`)                                 | 
| `make lint` / `make lint-fix`          | Check code (without fixes / with auto-fix)                                                       | 
| `make format`                          | Format code                                                                                       | 
| `make hooks` / `make hooks-run`        | Install the pre-commit hook / manually check the entire project                                  |
| `make collectstatic`                   | Collect static files (as during Docker image build)                                              | 
| `make docker-build`                    | Build Docker image                                                                                 | 
| `make docker-run` / `make docker-stop` | Start / stop Docker container                                                                     | 
| `make clean`                           | Remove caches and locally collected static files                                                 | 
| `make reset-db`                        | DANGEROUS: delete the SQLite DB and all `db_statistics` migrations (except `__init__.py`), with confirmation | 
 
## Running the project in Docker 
 
- Build the Docker image 
 
```bash 
docker build -t db-stat . 
``` 
 
- Run the Docker container 
 
```bash 
docker run --name db-stat --rm -p 8000:8000 olegegoism/db-stat:latest 
``` 
 
## Backup 
 
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
