#!/usr/bin/env bash
set -euo pipefail

PGDATA="${PGDATA:-/var/lib/postgresql/data}"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  for _ in $(seq 1 60); do
    pg_isready -h postgres-primary -p 5432 -U chat && break
    sleep 2
  done
  pg_isready -h postgres-primary -p 5432 -U chat

  PGPASSWORD=replpass pg_basebackup -h postgres-primary -p 5432 -U replicator -D "$PGDATA" -Fp -Xs -P -R

  if ! grep -q 'replpass' "$PGDATA/postgresql.auto.conf"; then
    printf "\nprimary_conninfo = 'host=postgres-primary port=5432 user=replicator password=replpass'\n" >> "$PGDATA/postgresql.auto.conf"
  fi
  touch "$PGDATA/standby.signal"
fi

exec docker-entrypoint.sh postgres
