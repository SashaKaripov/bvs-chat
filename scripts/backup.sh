#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
docker compose run --rm --no-deps -T \
  -e PGPASSWORD=chatpass \
  --entrypoint pg_dump \
  postgres-primary \
  -h postgres-router -U chat -d chat --clean --if-exists \
  > backups/chat.sql
test -s backups/chat.sql
grep -q "CREATE TABLE public.messages" backups/chat.sql
