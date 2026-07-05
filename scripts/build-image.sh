#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-db-stat}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
BASE_IMAGE="${BASE_IMAGE:-python:3.13-slim}"
IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

printf 'Building %s...\n' "$IMAGE"
docker build --tag "$IMAGE" .

printf 'Removing standalone base image tag %s, if it exists...\n' "$BASE_IMAGE"
docker image rm "$BASE_IMAGE" >/dev/null 2>&1 || true

printf 'Removing dangling intermediate images, if any...\n'
docker image prune --force >/dev/null

printf '\nBuild finished. Expected application image:\n'
docker image ls "$IMAGE"
