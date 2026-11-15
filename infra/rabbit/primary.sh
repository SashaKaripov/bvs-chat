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

prepare_cookie
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
  if gosu rabbitmq rabbitmqctl await_startup -t 5; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  fail "узел не поднялся за 2 минуты"
fi

/declare.sh || fail "не удалось объявить очередь chat.jobs"

set +e
wait "$pid"
status=$?
set -e
exit "$status"
