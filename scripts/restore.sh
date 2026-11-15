#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f backups/chat.sql ]; then
  echo "Ошибка: нет файла backups/chat.sql" >&2
  exit 1
fi
docker compose run --rm --no-deps -T \
  -e PGPASSWORD=chatpass \
  -v "$PWD/backups/chat.sql:/dump/chat.sql:ro" \
  --entrypoint psql \
  postgres-primary \
  -h postgres-router -U chat -d chat -v ON_ERROR_STOP=1 \
  -f /dump/chat.sql
docker compose run --rm --no-deps -T \
  -e PGPASSWORD=chatpass \
  --entrypoint psql \
  postgres-primary \
  -h postgres-router -U chat -d chat -tAc "SELECT count(*) FROM messages;"
