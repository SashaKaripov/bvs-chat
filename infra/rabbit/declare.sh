#!/bin/bash
set -euo pipefail

HOST=rabbitmq-1
MQ_USER=chat
MQ_PASS=rabbitpass
QUEUE=chat.jobs

admin() {
  rabbitmqadmin -H "$HOST" -u "$MQ_USER" -p "$MQ_PASS" -V / -t 15 "$@"
}

nodes_ready() {
  local json
  json=$(admin -f raw_json list nodes name running) || return 1
  printf '%s\n' "$json" | python3 -c '
import json
import sys
need = set([
    "rabbit@rabbitmq-1",
    "rabbit@rabbitmq-2",
    "rabbit@rabbitmq-3",
])
try:
    nodes = json.loads(sys.stdin.read())
except Exception:
    sys.exit(1)
if not isinstance(nodes, list):
    sys.exit(1)
running = set()
for node in nodes:
    if not isinstance(node, dict):
        continue
    flag = node.get("running")
    if flag is True:
        running.add(node.get("name"))
sys.exit(0 if need.issubset(running) else 1)
'
}

queue_exists() {
  local json
  json=$(admin -f raw_json list queues name) || return 1
  printf '%s\n' "$json" | python3 -c '
import json
import sys
try:
    rows = json.loads(sys.stdin.read())
except Exception:
    sys.exit(1)
if not isinstance(rows, list):
    sys.exit(1)
for row in rows:
    if isinstance(row, dict) and row.get("name") == "chat.jobs":
        sys.exit(0)
sys.exit(1)
'
}

deadline=$((SECONDS + 120))
while [ "$SECONDS" -lt "$deadline" ]; do
  if nodes_ready; then
    if admin declare queue name="$QUEUE" durable=true arguments='{"x-queue-type":"quorum"}'; then
      exit 0
    fi
    if queue_exists; then
      exit 0
    fi
  fi
  sleep 2
done

if queue_exists; then
  exit 0
fi

echo "Ошибка: не удалось объявить очередь chat.jobs" >&2
exit 1
