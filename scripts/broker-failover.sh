#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "$0")" && pwd)/.."

if [ ! -f docker-compose.yml ]; then
  echo "Ошибка: в $(pwd) нет файла сборки compose." >&2
  exit 1
fi

echo "Останавливаю узел rabbitmq-1..."
docker compose stop rabbitmq-1

deadline=$((SECONDS + 120))
node2=0
while [ "$SECONDS" -lt "$deadline" ]; do
  if docker compose exec -T rabbitmq-2 rabbitmq-diagnostics -q ping >/dev/null; then
    node2=1
    break
  fi
  sleep 2
done
if [ "$node2" -ne 1 ]; then
  echo "Ошибка: узел rabbitmq-2 не отвечает на rabbitmq-diagnostics -q ping." >&2
  exit 1
fi

published=0
deadline=$((SECONDS + 120))
while [ "$SECONDS" -lt "$deadline" ]; do
  if [ "$published" -eq 0 ]; then
    if pub=$(docker compose exec -T rabbitmq-2 \
      rabbitmqadmin -H localhost -u chat -p rabbitpass -t 15 \
      publish routing_key=chat.jobs payload=failover-ok 2>&1); then
      case "$pub" in
        *"NOT routed"*)
          ;;
        *)
          published=1
          ;;
      esac
    fi
  fi
  if [ "$published" -eq 1 ]; then
    if got=$(docker compose exec -T rabbitmq-2 \
      rabbitmqadmin -H localhost -u chat -p rabbitpass -t 15 -f raw_json \
      get queue=chat.jobs count=1 ackmode=ack_requeue_false 2>&1); then
      case "$got" in
        *failover-ok*)
          echo "узел 1 остановлен, очередь жива на оставшихся двух, публикация и чтение прошли."
          exit 0
          ;;
        *'"payload"'*)
          echo "Ошибка: из очереди прочитано не проверочное сообщение." >&2
          exit 1
          ;;
      esac
    fi
  fi
  sleep 3
done

echo "Ошибка: публикация или чтение chat.jobs через rabbitmq-2 не прошли." >&2
exit 1
