#!/bin/sh
set -e

add_host_docker_internal() {
    if [ "${ADD_HOST_DOCKER_INTERNAL:-1}" = "0" ]; then
        return 0
    fi

    if getent hosts host.docker.internal >/dev/null 2>&1; then
        return 0
    fi

    gateway_ip="${HOST_DOCKER_INTERNAL_IP:-}"
    if [ -z "$gateway_ip" ] && [ -r /proc/net/route ]; then
        gateway_ip="$(python - <<'PY'
from pathlib import Path

for line in Path('/proc/net/route').read_text().splitlines()[1:]:
    fields = line.split()
    if len(fields) >= 3 and fields[1] == '00000000':
        gateway_hex = fields[2]
        octets = [str(int(gateway_hex[i:i + 2], 16)) for i in range(6, -1, -2)]
        print('.'.join(octets))
        break
PY
)"
    fi

    if [ -n "$gateway_ip" ] && [ -w /etc/hosts ]; then
        printf '%s\t%s\n' "$gateway_ip" "host.docker.internal" >> /etc/hosts
    fi
}

add_host_docker_internal

exec "$@"
