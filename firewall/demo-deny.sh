#!/bin/sh
set -eu
CDPATH= cd "$(dirname "$0")/.."

check() {
  if docker compose exec -T web nc -z -w 5 "$1" "$2" >/dev/null 2>&1; then
    echo "$3: разрешено"
  else
    echo "$3: запрещено"
  fi
}

check chat-api 8000 'tcp chat-api:8000'
check chat-api 5432 'tcp chat-api:5432'
