#!/bin/sh
set -eu
CDPATH= cd "$(dirname "$0")/.."

docker compose exec -T chat-api /firewall/apply.sh chat-api

echo 'правило на базу возвращено.'
