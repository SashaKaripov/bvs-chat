#!/usr/bin/env bash
# Возвращает остановленный postgres-primary. Запасную стирает и снимает с него новую копию.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f docker-compose.yml ]; then
  echo "Ошибка: в $(pwd) нет файла сборки compose." >&2
  exit 1
fi

docker compose stop postgres-standby postgres-router

cat > infra/haproxy/haproxy.cfg <<'EOF'
defaults
    mode tcp
    timeout connect 5s
    timeout client 30s
    timeout server 30s

frontend pg_front
    bind *:5432
    default_backend primary

backend primary
    server primary postgres-primary:5432 check
EOF

primary_id="$(docker compose ps -aq postgres-primary)"
project="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$primary_id")"
vol="$(docker volume ls -q --filter "label=com.docker.compose.project=${project}" --filter label=com.docker.compose.volume=postgres-standby-data)"

docker compose rm -sf postgres-standby
if [ -n "$vol" ]; then
  docker volume rm "$vol"
fi

docker compose up -d postgres-primary postgres-standby postgres-router

ok=0
for _ in $(seq 1 60); do
  primary="$(docker compose exec -T postgres-primary psql -U chat -d chat -tAc "SELECT pg_is_in_recovery();" 2>/dev/null | tr -d '\r\n' || true)"
  standby="$(docker compose exec -T postgres-standby psql -U chat -d chat -tAc "SELECT pg_is_in_recovery();" 2>/dev/null | tr -d '\r\n' || true)"
  if [ "$primary" = "f" ] && [ "$standby" = "t" ]; then
    if docker compose exec -T postgres-primary pg_isready -h postgres-router -p 5432 -U chat >/dev/null 2>&1; then
      ok=1
      break
    fi
  fi
  sleep 2
done
if [ "$ok" -ne 1 ]; then
  echo "первая база не вернулась или копия не снялась" >&2
  exit 1
fi

echo "postgres-primary снова принимает запись, standby снял с него копию, маршрутизатор смотрит на primary."
