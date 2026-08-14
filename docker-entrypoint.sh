#!/bin/sh
set -eu

# Docker Desktop provides host.docker.internal automatically. On native Linux
# Docker it is not always present, so derive Docker's default gateway at runtime
# and add the same portable alias without requiring --add-host on docker run.
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

exec "$@"
