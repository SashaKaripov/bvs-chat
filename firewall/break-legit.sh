#!/bin/sh
set -eu
CDPATH= cd "$(dirname "$0")/.."

docker compose exec -T chat-api iptables -I OUTPUT 1 -p tcp --dport 5432 -j REJECT

echo 'запрещено легитимное правило chat-api -> postgres 5432. Запись сообщения должна закончиться ошибкой.'
echo 'Вернуть: ./firewall/restore-legit.sh'
