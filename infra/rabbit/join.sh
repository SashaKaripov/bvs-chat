#!/bin/bash
set -euo pipefail

prepare_cookie() {
  local cookie_file=/var/lib/rabbitmq/.erlang.cookie
  if [ -z "${RABBITMQ_ERLANG_COOKIE:-}" ]; then
    return 0
  fi
  printf '%s' "$RABBITMQ_ERLANG_COOKIE" > "$cookie_file"
  chown rabbitmq:rabbitmq "$cookie_file"
  chmod 400 "$cookie_file"
}

ctl() {
  gosu rabbitmq rabbitmqctl "$@"
}

prepare_cookie

pid=""

on_stop() {
  trap - TERM INT
  if [ -n "${pid}" ]; then
    kill -TERM "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
  fi
  exit 0
}

fail() {
  echo "$1" >&2
  if [ -n "${pid}" ]; then
    kill -TERM "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
  fi
  exit 1
}

disk_has_seed() {
  local status_text="$1"
  local line section norm
  section=0
  while IFS= read -r line; do
    norm=$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]' | tr -d "[:space:]'\"")
    case "$norm" in
      disknodes)
        section=1
        ;;
      runningnodes)
        section=0
        ;;
      *)
        if [ "$section" -eq 1 ]; then
          case ",${norm}," in
            *,rabbit@rabbitmq-1,*)
              return 0
              ;;
          esac
        fi
        ;;
    esac
  done <<EOF
$status_text
EOF
  return 1
}

in_cluster_with_seed() {
  local status_text
  status_text=$(ctl cluster_status 2>/dev/null) || return 1
  disk_has_seed "$status_text"
}

trap on_stop TERM INT

docker-entrypoint.sh rabbitmq-server &
pid=$!

deadline=$((SECONDS + 120))
ready=0
while [ "$SECONDS" -lt "$deadline" ]; do
  if ! kill -0 "$pid" 2>/dev/null; then
    wait "$pid" || true
    fail "процесс rabbitmq-server завершился до готовности"
  fi
  if ctl await_startup -t 5; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  fail "узел не поднялся за 2 минуты"
fi

if in_cluster_with_seed; then
  echo "узел $(hostname) уже в кластере с rabbit@rabbitmq-1"
else
  echo "узел $(hostname) входит в rabbit@rabbitmq-1"
  ctl stop_app
  joined=0
  deadline=$((SECONDS + 120))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if ctl join_cluster rabbit@rabbitmq-1; then
      joined=1
      break
    fi
    ctl stop_app || true
    ctl reset || true
    if ctl join_cluster rabbit@rabbitmq-1; then
      joined=1
      break
    fi
    sleep 3
  done
  if [ "$joined" -ne 1 ]; then
    fail "не удалось войти в кластер rabbit@rabbitmq-1"
  fi
  ctl start_app || fail "не удалось запустить приложение после входа в кластер"
fi

set +e
wait "$pid"
status=$?
set -e
exit "$status"
