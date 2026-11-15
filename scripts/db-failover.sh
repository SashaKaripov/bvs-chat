#!/usr/bin/env bash
# Обратное включение старого primary без пересборки разойдёт кластер. Вернуть первую базу: ./scripts/db-recover.sh
set -euo pipefail
cd "$(dirname "$0")/.."

psql_router() {
  docker compose run --rm --no-deps -T \
    -e PGPASSWORD=chatpass \
    --entrypoint psql \
    postgres-primary \
    -h postgres-router -U chat -d chat -v ON_ERROR_STOP=1 \
    "$@"
}

docker compose stop postgres-primary
docker compose exec -T postgres-standby gosu postgres pg_ctl -D /var/lib/postgresql/data promote

ok=0
for _ in $(seq 1 30); do
  if docker compose exec -T postgres-standby pg_isready -U chat -d chat >/dev/null 2>&1; then
    state="$(docker compose exec -T postgres-standby psql -U chat -d chat -tAc "SELECT CASE WHEN pg_is_in_recovery() THEN 'transaction read-only' ELSE 'transaction read-write' END;" | tr -d '\r\n' || true)"
    if [ "$state" = "transaction read-write" ]; then
      ok=1
      break
    fi
  fi
  sleep 2
done
if [ "$ok" -ne 1 ]; then
  echo "standby не перешёл в read-write" >&2
  exit 1
fi

cp -f infra/haproxy/standby.cfg infra/haproxy/haproxy.cfg
docker compose restart postgres-router

ok=0
for _ in $(seq 1 30); do
  if docker compose exec -T postgres-standby pg_isready -h postgres-router -p 5432 -U chat >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done
[ "$ok" -eq 1 ]

got="$(psql_router -tAc "INSERT INTO messages (role, content) VALUES ('user', 'failover-ok') RETURNING content;" | head -n 1 | tr -d '[:space:]')"
[ "$got" = "failover-ok" ]
psql_router -c "DELETE FROM messages WHERE role = 'user' AND content = 'failover-ok';" >/dev/null

echo "primary остановлен, standby принимает запись, маршрутизатор смотрит на standby."
