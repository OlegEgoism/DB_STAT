#!/bin/sh
set -eu

# The SQLite file may come from a new or an existing persistent volume. Apply
# versioned migrations on every start so both cases use the current schema.
sqlite_dir="$(dirname "${SQLITE_NAME:-/app/data/db.sqlite3}")"
mkdir -p "$sqlite_dir"

# This script starts as root (needed further down for the /etc/hosts write),
# but the app itself must not run — or write files — as root. An existing
# volume from an older, root-only image version may still be owned by root,
# so reconcile it before anything touches the SQLite file.
chown -R appuser:appuser "$sqlite_dir"

runuser -u appuser -- python manage.py migrate --noinput --run-syncdb
runuser -u appuser -- python manage.py recover_maintenance_jobs

# Creates the first account (INITIAL_ADMIN_PASSWORD defaults to "admin" if
# left unset — see ensure_initial_admin.py and the same note in .env.example).
# Existing databases are never modified.
runuser -u appuser -- python manage.py ensure_initial_admin

# Docker Desktop provides host.docker.internal automatically. On native Linux
# Docker it is not always present, so derive Docker's default gateway at runtime
# and add the same portable alias without requiring --add-host on docker run.
# Writing /etc/hosts is the one thing here that genuinely needs root.
if [ "${LOCALHOST_DB_HOST:-}" = "host.docker.internal" ] \
    && ! getent hosts host.docker.internal >/dev/null 2>&1; then
    host_gateway="$(
        python - <<'PY'
import ipaddress

try:
    with open("/proc/net/route", encoding="ascii") as routes:
        next(routes)
        for route in routes:
            fields = route.split()
            if len(fields) >= 4 and fields[1] == "00000000" and int(fields[3], 16) & 2:
                raw_gateway = bytes.fromhex(fields[2])
                print(ipaddress.ip_address(raw_gateway[::-1]))
                break
except (OSError, ValueError):
    pass
PY
    )"
    if [ -n "$host_gateway" ]; then
        printf '%s\t%s\n' "$host_gateway" host.docker.internal >> /etc/hosts
    else
        echo "Warning: Docker host gateway was not found; localhost database connections may be unavailable." >&2
    fi
fi

# Concurrency is tunable per-deployment without rebuilding the image or
# overriding the whole CMD — exec-form CMD can't expand env vars itself. Only
# append these gunicorn-specific flags when gunicorn is actually the command
# being run: an unconditional append here would corrupt any other CMD
# override (`docker run ... manage.py shell`, `manage.py check`, etc.) with
# flags it doesn't recognize instead of just running it as given.
if [ "${1:-}" = "gunicorn" ]; then
    set -- "$@" --workers "${GUNICORN_WORKERS:-3}" --threads "${GUNICORN_THREADS:-2}" --timeout "${GUNICORN_TIMEOUT:-60}"
fi
exec runuser -u appuser -- "$@"
